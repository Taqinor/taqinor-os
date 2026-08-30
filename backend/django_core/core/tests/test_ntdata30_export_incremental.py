"""Tests NTDATA30 — extraction incrémentale (high-watermark) des extraits.

Couvre :
  * le mode ``complet`` (défaut) est INCHANGÉ : toute la population à chaque
    passage, aucun curseur posé ;
  * premier passage incrémental = complet, puis le curseur est mémorisé ;
  * un 2e passage n'extrait QUE les lignes créées/modifiées entre les deux ;
  * le curseur avance même si le champ curseur n'est pas projeté (agrégat max) ;
  * un chargement en ERREUR ne fait pas avancer le curseur (rejouable) ;
  * ``dernier_curseur`` est en lecture seule côté API.
"""
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import data_explorer, scheduled_export
from core.models import ChangelogEntry, ScheduledExport
from core.views import ScheduledExportViewSet

User = get_user_model()


def _changelog_dataset(company, user):
    """Dataset de FONDATION (aucune app métier) porteur d'un champ date."""
    return ChangelogEntry.objects.all()


class ExportIncrementalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.t0 = timezone.now() - timedelta(days=3)

    def setUp(self):
        data_explorer.register_dataset(
            'changelog', 'Nouveautés', ['id', 'titre', 'publie_le'],
            _changelog_dataset)

    def _entree(self, titre, quand):
        obj = ChangelogEntry.objects.create(titre=titre, publie_le=quand)
        return obj

    def _export(self, **kw):
        params = dict(company=self.company, titre='Chg', dataset='changelog',
                      spec={'select': ['titre', 'publie_le']}, format='csv',
                      destination='sftp')
        params.update(kw)
        return ScheduledExport.objects.create(**params)

    def test_mode_complet_inchange_et_sans_curseur(self):
        self._entree('A', self.t0)
        exp = self._export()
        self.assertEqual(exp.mode, ScheduledExport.MODE_COMPLET)
        _f, data, _ct, rows = scheduled_export.rendre_extrait_detaille(exp)
        self.assertEqual(len(rows), 1)
        self.assertIn(b'A', data)
        scheduled_export.executer(exp)
        exp.refresh_from_db()
        self.assertEqual(exp.dernier_curseur, '')

    def test_premier_passage_complet_puis_curseur_memorise(self):
        self._entree('A', self.t0)
        self._entree('B', self.t0 + timedelta(days=1))
        exp = self._export(mode=ScheduledExport.MODE_INCREMENTAL,
                           champ_curseur='publie_le')
        _f, _d, _ct, rows = scheduled_export.rendre_extrait_detaille(exp)
        self.assertEqual(len(rows), 2)
        scheduled_export.executer(exp)
        exp.refresh_from_db()
        self.assertEqual(exp.dernier_curseur,
                         (self.t0 + timedelta(days=1)).isoformat()[:64])

    def test_second_passage_extrait_seulement_le_delta(self):
        self._entree('A', self.t0)
        exp = self._export(mode=ScheduledExport.MODE_INCREMENTAL,
                           champ_curseur='publie_le')
        scheduled_export.executer(exp)
        exp.refresh_from_db()
        premier_curseur = exp.dernier_curseur
        self.assertTrue(premier_curseur)

        self._entree('B', self.t0 + timedelta(days=2))
        _f, data, _ct, rows = scheduled_export.rendre_extrait_detaille(exp)
        titres = {r['titre'] for r in rows}
        self.assertEqual(titres, {'B'})
        self.assertNotIn(b'A,', data)

        scheduled_export.executer(exp)
        exp.refresh_from_db()
        self.assertNotEqual(exp.dernier_curseur, premier_curseur)

        # 3e passage sans nouvelle donnée : plus rien à extraire.
        _f, _d, _ct, rows3 = scheduled_export.rendre_extrait_detaille(exp)
        self.assertEqual(rows3, [])

    def test_curseur_avance_meme_si_le_champ_nest_pas_projete(self):
        self._entree('A', self.t0)
        exp = self._export(mode=ScheduledExport.MODE_INCREMENTAL,
                           champ_curseur='publie_le',
                           spec={'select': ['titre']})
        scheduled_export.executer(exp)
        exp.refresh_from_db()
        self.assertEqual(exp.dernier_curseur, self.t0.isoformat()[:64])

    def test_champ_curseur_hors_liste_blanche_ne_casse_pas_lexport(self):
        self._entree('A', self.t0)
        exp = self._export(mode=ScheduledExport.MODE_INCREMENTAL,
                           champ_curseur='secret', spec={'select': ['titre']})
        scheduled_export.executer(exp)
        exp.refresh_from_db()
        self.assertEqual(exp.dernier_curseur, '')
        self.assertIsNotNone(exp.derniere_execution_le)

    def test_chargement_en_erreur_ne_fait_pas_avancer_le_curseur(self):
        self._entree('A', self.t0)
        exp = self._export(mode=ScheduledExport.MODE_INCREMENTAL,
                           champ_curseur='publie_le', destination='minio')
        with mock.patch.object(scheduled_export, '_minio_client',
                               side_effect=RuntimeError('HS')):
            with self.settings(MINIO_ENDPOINT='minio:9000'):
                scheduled_export.executer(exp)
        exp.refresh_from_db()
        self.assertEqual(exp.dernier_statut, 'erreur')
        self.assertEqual(exp.dernier_curseur, '')


class ExportIncrementalApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME')
        cls.admin = User.objects.create_user(
            username='inc_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.factory = APIRequestFactory()

    def test_dernier_curseur_est_en_lecture_seule(self):
        body = {'titre': 'E', 'dataset': 'changelog', 'destination': 'sftp',
                'mode': 'incremental', 'champ_curseur': 'publie_le',
                'dernier_curseur': '2999-01-01T00:00:00+00:00'}
        req = self.factory.post('/scheduled-exports/', body, format='json')
        force_authenticate(req, user=self.admin)
        resp = ScheduledExportViewSet.as_view({'post': 'create'})(req)
        self.assertEqual(resp.status_code, 201)
        exp = ScheduledExport.objects.get(pk=resp.data['id'])
        self.assertEqual(exp.mode, 'incremental')
        self.assertEqual(exp.champ_curseur, 'publie_le')
        self.assertEqual(exp.dernier_curseur, '')

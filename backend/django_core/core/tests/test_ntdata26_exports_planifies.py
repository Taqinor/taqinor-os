"""Tests NTDATA26 — planification des extraits (`ScheduledExport.cron` LU).

`cron` portait déjà la cadence, mais rien ne la lisait : un extrait
« quotidien » ne partait que si quelqu'un cliquait « exécuter ». Ces tests
couvrent le job qui ferme le trou.

Couvre :
  * le critère d'acceptation : un extrait QUOTIDIEN en CSV vers une
    destination NON CONFIGURÉE reste un no-op propre ET horodate son statut ;
  * le grain de planification = l'HEURE (le champ minute est ignoré) ;
  * un extrait inactif, sans cron, ou au cron illisible n'est JAMAIS dû ;
  * l'idempotence : un extrait déjà passé dans l'heure courante ne repart pas ;
  * les sociétés SUSPENDUES ne sont jamais balayées (SCA19) ;
  * un extrait en erreur n'interrompt pas les suivants ;
  * le CRUD `core/scheduled-exports/` impose la société côté serveur.

Le marqueur de no-op tracé du dépôt est ``non_configure`` (même vocabulaire
que `core.backup`, déjà asserté par les tests NTDATA27/29 et remonté par
`core.health.recent_incidents`) — c'est lui qui est vérifié ici plutôt qu'un
second libellé qui dirait la même chose.
"""
from datetime import datetime, timezone as dt_timezone
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import data_explorer, scheduled_export
from core.models import ScheduledExport
from core.views import ScheduledExportViewSet

User = get_user_model()

#: Horloge FIGÉE : mardi 14 avril 2026, 02 h 00 UTC.
MARDI_02H = datetime(2026, 4, 14, 2, 0, tzinfo=dt_timezone.utc)


def _companies_dataset(company, user):
    return Company.objects.filter(pk=company.pk)


class CronDuTests(TestCase):
    """Le matcheur de cadence : grain = heure, et aucun doute n'est « dû »."""

    def test_quotidien_du_a_la_bonne_heure(self):
        self.assertTrue(scheduled_export.cron_du('0 2 * * *', MARDI_02H))

    def test_quotidien_pas_du_a_une_autre_heure(self):
        self.assertFalse(scheduled_export.cron_du('0 5 * * *', MARDI_02H))

    def test_le_champ_minute_est_ignore(self):
        """Le beat passe à l'heure : « 0 2 » et « 45 2 » sont dus pareil."""
        self.assertTrue(scheduled_export.cron_du('45 2 * * *', MARDI_02H))

    def test_jour_de_semaine_respecte(self):
        # 0 = dimanche ; le 14/04/2026 est un mardi (2).
        self.assertTrue(scheduled_export.cron_du('0 2 * * 2', MARDI_02H))
        self.assertFalse(scheduled_export.cron_du('0 2 * * 0', MARDI_02H))

    def test_jour_du_mois_et_mois_respectes(self):
        self.assertTrue(scheduled_export.cron_du('0 2 14 4 *', MARDI_02H))
        self.assertFalse(scheduled_export.cron_du('0 2 15 4 *', MARDI_02H))
        self.assertFalse(scheduled_export.cron_du('0 2 14 5 *', MARDI_02H))

    def test_intervalles_et_pas(self):
        self.assertTrue(scheduled_export.cron_du('0 0-6 * * *', MARDI_02H))
        self.assertTrue(scheduled_export.cron_du('0 */2 * * *', MARDI_02H))
        self.assertFalse(scheduled_export.cron_du('0 1-6/2 * * *', MARDI_02H))

    def test_expression_vide_ou_illisible_jamais_due(self):
        """Un extrait part vers une destination EXTERNE : le doute = non."""
        for expression in ('', '   ', '0 2 * *', 'tous les jours',
                           '0 99 * * *', '0 2 * * abc'):
            self.assertFalse(
                scheduled_export.cron_du(expression, MARDI_02H), expression)


class ExportsDusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA26 SA',
                                             slug='ntdata26-sa')

    def setUp(self):
        data_explorer.register_dataset(
            'societes_ntdata26', 'Sociétés', ['id', 'nom'],
            _companies_dataset)

    def _export(self, **kw):
        params = dict(company=self.company, titre='Extrait quotidien',
                      dataset='societes_ntdata26', spec={'select': ['nom']},
                      format=ScheduledExport.FORMAT_CSV,
                      destination=ScheduledExport.DEST_SFTP,
                      cron='0 2 * * *')
        params.update(kw)
        return ScheduledExport.objects.create(**params)

    def test_destination_non_configuree_reste_un_no_op_horodate(self):
        """Critère d'acceptation NTDATA26."""
        export = self._export()
        recap = scheduled_export.executer_exports_dus(now=MARDI_02H)

        self.assertEqual(len(recap), 1)
        export.refresh_from_db()
        # No-op TRACÉ : le statut dit pourquoi rien n'est parti, et la date
        # d'exécution prouve que le job est bien passé.
        self.assertEqual(export.dernier_statut, 'non_configure')
        self.assertEqual(export.derniere_execution_le, MARDI_02H)
        # Le no-op DIT pourquoi rien n'est parti.
        self.assertIn('detail', export.dernier_detail)
        self.assertIn('non configurée', export.dernier_detail['detail'])

    def test_extrait_inactif_jamais_du(self):
        self._export(actif=False)
        self.assertEqual(
            scheduled_export.exports_dus(MARDI_02H), [])

    def test_extrait_sans_cron_jamais_du(self):
        self._export(cron='')
        self.assertEqual(scheduled_export.exports_dus(MARDI_02H), [])

    def test_idempotent_dans_l_heure(self):
        export = self._export()
        scheduled_export.executer_exports_dus(now=MARDI_02H)
        export.refresh_from_db()
        self.assertFalse(scheduled_export.est_du(export, MARDI_02H))
        recap = scheduled_export.executer_exports_dus(now=MARDI_02H)
        self.assertEqual(recap, [])

    def test_balayage_borne_aux_societes_passees(self):
        """SCA19 — la tâche passe les sociétés ACTIVES ; hors liste, rien ne part.

        L'extrait d'une société absente de la liste n'est pas exécuté : c'est
        le mécanisme par lequel un tenant suspendu cesse d'émettre vers une
        destination externe.
        """
        hors_perimetre = Company.objects.create(nom='NTDATA26 Suspendue',
                                                slug='ntdata26-susp')
        etranger = self._export(company=hors_perimetre)
        dus = scheduled_export.exports_dus(MARDI_02H,
                                           companies=[self.company])
        self.assertNotIn(etranger, dus)
        self.assertEqual(dus, [])

    def test_la_tache_beat_passe_les_societes_actives(self):
        from core.tasks import executer_exports_planifies_task

        with mock.patch.object(
                scheduled_export, 'executer_exports_dus',
                return_value=[]) as espion:
            executer_exports_planifies_task()
        _args, kwargs = espion.call_args
        self.assertIn(self.company, kwargs['companies'])

    def test_un_extrait_en_erreur_n_interrompt_pas_les_suivants(self):
        premier = self._export(titre='Premier')
        second = self._export(titre='Second')
        reel = scheduled_export.executer

        def _executer(export, now=None):
            if export.pk == premier.pk:
                raise RuntimeError('destination injoignable')
            return reel(export, now=now)

        with mock.patch.object(scheduled_export, 'executer', _executer):
            recap = scheduled_export.executer_exports_dus(now=MARDI_02H)

        self.assertEqual([ligne['export'] for ligne in recap], [second.pk])
        second.refresh_from_db()
        self.assertEqual(second.dernier_statut, 'non_configure')


class ScheduledExportCrudTests(TestCase):
    """Le CRUD `core/scheduled-exports/` impose la société côté serveur."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA26 API',
                                             slug='ntdata26-api')
        cls.autre = Company.objects.create(nom='NTDATA26 Autre',
                                           slug='ntdata26-autre')
        cls.admin = User.objects.create_user(
            username='ntdata26_admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.etranger = ScheduledExport.objects.create(
            company=cls.autre, titre='Ailleurs', dataset='societes_ntdata26')

    def test_creation_force_la_societe_du_demandeur(self):
        fabrique = APIRequestFactory()
        requete = fabrique.post(
            '/api/django/core/scheduled-exports/',
            {'titre': 'Mien', 'dataset': 'societes_ntdata26',
             'cron': '0 2 * * *'}, format='json')
        force_authenticate(requete, user=self.admin)
        reponse = ScheduledExportViewSet.as_view({'post': 'create'})(requete)
        self.assertEqual(reponse.status_code, status.HTTP_201_CREATED)
        cree = ScheduledExport.objects.get(pk=reponse.data['id'])
        self.assertEqual(cree.company_id, self.company.pk)

    def test_liste_bornee_a_la_societe(self):
        fabrique = APIRequestFactory()
        requete = fabrique.get('/api/django/core/scheduled-exports/')
        force_authenticate(requete, user=self.admin)
        reponse = ScheduledExportViewSet.as_view({'get': 'list'})(requete)
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        identifiants = [ligne['id'] for ligne in reponse.data]
        self.assertNotIn(self.etranger.pk, identifiants)

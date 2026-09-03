# -*- coding: utf-8 -*-
"""QJR432 (S3-N1) — l'aperçu d'étude du commercial passe lui aussi
``jour_reference``, pour montrer la même journée que le devis.

MÊME CLASSE que QJR406 (``public_views.py``) et QJR232
(``profils_comparatifs.py``) — une classe déjà rencontrée deux fois dans ce
groupe : un appelant de ``jours_types_annee`` (ici via
``calculer_etude_horaire``) omettait ``jour_reference``, donc recalculait
contre l'horloge du SERVEUR au moment de l'appel plutôt que contre la date de
référence PERSISTÉE du devis (``domain.entrees.jour_reference_du_devis`` —
surcharge D12 déclarée, sinon la date de création du devis). L'écart est
visible pendant et autour du Ramadan (fenêtre imsak/iftar dépendante de la
date). Surface INTERNE, propre à cette lane (``etude_horaire_view.py`` ; ne
pas fusionner avec ``public_views.py``, propriété de la lane
``qjr4/public-securite`` — règle permanente 3 du groupe QJR4).

Technique de test IDENTIQUE au précédent QJR232
(``test_qjr232_jour_reference_epingle.ProfilsComparatifsPartagentLHorloge``) :
espionner les kwargs REÇUS par ``calculer_etude_horaire`` plutôt que rejouer
un vrai calendrier Ramadan — ``jour_reference`` est soit transmis, soit non,
peu importe la date du jour où ce test s'exécute.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_qjr432_apercu_jour_reference"
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.domain import entrees as _entrees
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ventes/etude-horaire/preview/'


class _Base(TestCase):

    def setUp(self):
        self.company, _created = Company.objects.get_or_create(
            slug='qjr432-co', defaults={'nom': 'QJR432 Co'})
        self.user = User.objects.create_user(
            username='qjr432_user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR432')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR432-0001',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user, taux_tva=Decimal('20'),
            mode_installation='residentiel',
            etude_params={'conso_kwh_mensuelles': [800.0] * 12})

    def _espionner_calculer_etude_horaire(self, corps):
        """POST l'aperçu en espionnant les kwargs REÇUS par
        ``calculer_etude_horaire`` — renvoie ``(response, kwargs_vus)``.
        Le calcul réel n'a pas besoin d'aboutir : seul l'APPEL nous
        intéresse."""
        vues = {}

        def _espion(**kwargs):
            vues.update(kwargs)
            return None

        with mock.patch('apps.ventes.etude_horaire.calculer_etude_horaire',
                        side_effect=_espion):
            resp = self.api.post(URL, corps, format='json')
        return resp, vues


class ApercuAvecDevisResoluRecoitSaDateTest(_Base):
    """(1) — un devis RÉSOLU transmet SA date à ``calculer_etude_horaire``."""

    def test_rouge_l_apercu_d_un_devis_recoit_jour_reference(self):
        """ROUGE avant le correctif : ``jour_reference`` n'apparaissait
        jamais dans les kwargs — l'aperçu recalculait contre l'horloge du
        serveur, pas la date du devis résolu."""
        resp, vues = self._espionner_calculer_etude_horaire({
            'devis': self.devis.id, 'kwc': 6.0, 'dimensionner': False,
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn(
            'jour_reference', vues,
            'etude_horaire_view.py OMETTAIT jour_reference — QJR432 non '
            'corrigé')
        self.assertEqual(vues['jour_reference'],
                         _entrees.jour_reference_du_devis(self.devis))

    def test_la_surcharge_d12_declaree_atteint_aussi_l_apercu(self):
        """Même discipline que QJR232 : une date DÉCLARÉE sur le devis
        (registre D12) doit atteindre l'aperçu, pas seulement le devis
        enregistré."""
        from apps.ventes.domain import overrides as _overrides
        _overrides.ecrire_colonne(self.devis, _overrides.poser(
            self.devis, 'etude.jour_reference', '2026-03-15'))
        self.devis.refresh_from_db()

        _resp, vues = self._espionner_calculer_etude_horaire({
            'devis': self.devis.id, 'kwc': 6.0, 'dimensionner': False,
        })
        self.assertEqual(vues.get('jour_reference'),
                         _entrees.jour_reference_du_devis(self.devis))
        self.assertEqual(vues.get('jour_reference').isoformat(), '2026-03-15')


class ApercuSansDevisResoluInchangeTest(_Base):
    """(2) — non-régression : sans devis résolu, comportement ACTUEL, à
    l'octet (repli sur l'horloge serveur, posé dans ``jours_types_annee``,
    jamais ici)."""

    def test_sans_devis_ni_lead_jour_reference_reste_none(self):
        _resp, vues = self._espionner_calculer_etude_horaire({
            'kwc': 6.0, 'conso_kwh_mensuelles': [800.0] * 12,
            'dimensionner': False,
        })
        self.assertIn('jour_reference', vues)
        self.assertIsNone(
            vues['jour_reference'],
            'sans devis résolu, jour_reference doit rester None — le repli '
            'reste celui de jours_types_annee, inchangé par cette tâche')

    def test_devis_introuvable_dans_la_societe_retombe_aussi_sur_none(self):
        """Un ``devis`` fourni mais NON résolu (mauvaise société, ou
        inexistant) doit se comporter EXACTEMENT comme l'absence de devis —
        jamais une date empruntée à un devis qu'on n'a pas le droit de lire."""
        _resp, vues = self._espionner_calculer_etude_horaire({
            'devis': self.devis.id + 999999, 'kwc': 6.0,
            'conso_kwh_mensuelles': [800.0] * 12, 'dimensionner': False,
        })
        self.assertIn('jour_reference', vues)
        self.assertIsNone(vues['jour_reference'])

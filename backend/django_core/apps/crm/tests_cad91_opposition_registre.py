"""CAD91 — l'opposition (« ne plus contacter ») est tracée au registre.

Avant : cocher la case arrêtait les cadences et bloquait tout redémarrage,
mais RIEN n'écrivait de ``ConsentRecord(granted=False)`` — le registre ne
pouvait pas prouver qu'une opposition avait été honorée, ce qu'un contrôle
vérifie en premier après une plainte (loi 09-08 art. 59). L'art. 9 al. 2
n'exige aucun motif du client : l'écriture n'en demande aucun.

Done de la tâche : cocher « ne plus contacter » (fiche) et répondre « Ne plus
me contacter » (touche, CAD5) écrivent CHACUN une entrée ``granted=False``
DATÉE.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import ConsentRecord
from testkit.time import frozen

from apps.crm import horaires, stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import (
    BASE_LEGALE_OPPOSITION, CONSENT_SOURCE_OPPOSITION_FICHE,
    CONSENT_SOURCE_OPPOSITION_TOUCHE)
from apps.parametres.models import CompanyProfile

User = get_user_model()

MERCREDI = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)
TELEPHONE = '+212661000911'


class _Base(TestCase):
    slug = 'cad91'

    def setUp(self):
        gel = frozen(MERCREDI)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(
            nom='CAD91 Solaire', slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Salma', stage=stages.CONTACTED,
            owner=self.acteur, telephone=TELEPHONE)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _oppositions(self):
        return list(ConsentRecord.objects.filter(
            company=self.company, subject_identifier=TELEPHONE,
            granted=False, source__contains=BASE_LEGALE_OPPOSITION))


class OppositionFicheTests(_Base):
    slug = 'cad91-fiche'

    def test_cocher_la_case_ecrit_une_opposition_datee(self):
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'ne_plus_contacter': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        oppositions = self._oppositions()
        self.assertEqual(len(oppositions), 1)
        entree = oppositions[0]
        self.assertFalse(entree.granted)
        self.assertIn(CONSENT_SOURCE_OPPOSITION_FICHE, entree.source)
        self.assertEqual(entree.occurred_at, MERCREDI)

    def test_aucun_motif_n_est_exige(self):
        # Ni `motif_perte`, ni note : l'opposition passe telle quelle.
        resp = self.api.patch(
            f'/api/django/crm/leads/{self.lead.pk}/',
            {'ne_plus_contacter': True}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(self._oppositions()), 1)

    def test_un_patch_sans_bascule_n_ecrit_rien(self):
        self.api.patch(f'/api/django/crm/leads/{self.lead.pk}/',
                       {'ville': 'Casablanca'}, format='json')
        self.assertEqual(self._oppositions(), [])


class OppositionToucheTests(_Base):
    slug = 'cad91-touche'

    def test_la_reponse_de_touche_ecrit_une_opposition_datee(self):
        quand = MERCREDI + datetime.timedelta(hours=1)
        etape = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=4,
            canal=RelanceEtape.Canal.APPEL, libelle='Appel 3', due_at=quand,
            due_date=quand.astimezone(horaires.CASABLANCA).date())
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{etape.pk}/fait/',
            {'reponse': 'ne_plus_contacter'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        oppositions = self._oppositions()
        self.assertEqual(len(oppositions), 1)
        self.assertIn(CONSENT_SOURCE_OPPOSITION_TOUCHE, oppositions[0].source)
        self.assertEqual(oppositions[0].occurred_at, MERCREDI)

"""AGR530 — D-AGR-4 côté cadence : après un appel abouti, un pompage au point
d'eau inconnu (groupe HYDRAULIQUE de la règle « devis auto prêt » manquant,
AGR403) reçoit « Planifier la visite — relevé du point d'eau », jamais
« Préparer et envoyer le devis ». Le résidentiel est inchangé, et
l'avertissement de planification est celui d'AGR408 (jamais « APRÈS le
devis »).

Run :
    python manage.py test apps.crm.tests_agr_visite_point_eau -v 2
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, services
from apps.crm.cadence_config import (
    CLE_APPEL_APRES_REPONSE, CLE_DEVIS, CLE_PLANIFIER, cle_de)
from apps.crm.devis_auto import releve_eau_manquant
from apps.crm.models import Lead, RelanceEtape
from apps.parametres.models import CompanyProfile

User = get_user_model()

MAINTENANT = datetime.datetime(2026, 9, 23, 10, 0, tzinfo=horaires.CASABLANCA)


class _Base(TestCase):
    slug = 'agr530'

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company = Company.objects.create(nom=self.slug, slug=self.slug)
        CompanyProfile.objects.get_or_create(company=self.company)
        self.user = User.objects.create_user(
            username=f'{self.slug}-u', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.n = 0

    def _lead(self, **champs):
        self.n += 1
        resp = self.api.post('/api/django/crm/leads/', {
            'nom': f'Fellah {self.slug} {self.n}',
            'telephone': f'+2126610053{self.n:02d}', **champs}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        return Lead.objects.get(pk=resp.data['id'])

    def _joint_au_premier_appel(self, lead):
        appel = (lead.relance_etapes
                 .filter(statut=RelanceEtape.Statut.A_FAIRE,
                         canal=RelanceEtape.Canal.APPEL)
                 .order_by('due_at', 'pk').first())
        if appel is None:
            appel = (lead.relance_etapes
                     .filter(statut=RelanceEtape.Statut.A_FAIRE)
                     .order_by('due_at', 'pk').first())
        resp = self.api.post(f'/api/django/crm/relance-etapes/{appel.pk}/fait/',
                             {'outcome': 'joint'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        # Cadence RÉACTIVE : à la création seule la touche 1 (le MESSAGE
        # d'identité) existe. Un message répondu pose d'abord « Appeler le
        # client — il a répondu » (RELANCE-SUITE) ; c'est CET appel, abouti,
        # qui décide de la suite que ce module verrouille.
        rappel = lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE,
            cle=CLE_APPEL_APRES_REPONSE).first()
        if rappel is not None:
            resp = self.api.post(
                f'/api/django/crm/relance-etapes/{rappel.pk}/fait/',
                {'outcome': 'joint'}, format='json')
            self.assertEqual(resp.status_code, 200, resp.data)

    def _cles_ouvertes(self, lead):
        return {cle_de(e) for e in lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE)}


class SuiteApresAppel(_Base):
    slug = 'agr530-suite'

    def test_a_agricole_sans_releve_planifier_la_visite(self):
        lead = self._lead(type_installation='agricole')
        self.assertTrue(releve_eau_manquant(lead))
        self._joint_au_premier_appel(lead)
        cles = self._cles_ouvertes(lead)
        self.assertIn(CLE_PLANIFIER, cles)
        self.assertNotIn(CLE_DEVIS, cles)
        etape = lead.relance_etapes.get(
            statut=RelanceEtape.Statut.A_FAIRE, cle=CLE_PLANIFIER)
        self.assertIn('Relevé du point d’eau', etape.note)
        self.assertIn('ABH', etape.note)

    def test_b_agricole_avec_niveau_et_debit_etape_devis(self):
        lead = self._lead(type_installation='agricole',
                          niveau_statique_m='32', pompe_debit_m3h='12')
        self.assertFalse(releve_eau_manquant(lead))
        self._joint_au_premier_appel(lead)
        cles = self._cles_ouvertes(lead)
        self.assertIn(CLE_DEVIS, cles)
        self.assertNotIn(CLE_PLANIFIER, cles)

    def test_c_residentiel_inchange(self):
        lead = self._lead(type_installation='residentiel')
        self.assertFalse(releve_eau_manquant(lead))
        self._joint_au_premier_appel(lead)
        cles = self._cles_ouvertes(lead)
        self.assertIn(CLE_DEVIS, cles)
        self.assertNotIn(CLE_PLANIFIER, cles)

    def test_d_avertissement_celui_d_agr408(self):
        lead = self._lead(type_installation='agricole')
        self._joint_au_premier_appel(lead)
        texte = services.avertissement_visite(lead)['avertissement_sans_devis']
        self.assertEqual(texte, services.AVERTISSEMENT_VISITE_POINT_EAU)
        self.assertNotIn('APRÈS le devis', texte)

    def test_visite_refusee_la_reprise_pose_le_devis(self):
        lead = self._lead(type_installation='agricole')
        self._joint_au_premier_appel(lead)
        planifier = lead.relance_etapes.get(
            statut=RelanceEtape.Statut.A_FAIRE, cle=CLE_PLANIFIER)
        resp = self.api.post(
            f'/api/django/crm/relance-etapes/{planifier.pk}/fait/',
            {'reponse': 'visite_abandonnee'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        cles = self._cles_ouvertes(lead)
        self.assertIn(CLE_DEVIS, cles)
        self.assertNotIn(CLE_PLANIFIER, cles)

"""YCASH4 — Feedback recouvrement -> front du funnel.

Couvre :
  * un client SANS facture en retard → `a_jour=True`, aucun avertissement
    recouvrement enrichi ;
  * un client avec une facture en retard au-delà d'un seuil FollowupLevel →
    l'avertissement chiffré (jours de retard + niveau + encours échu) ;
  * le flag se lève dès que la facture est réglée (`montant_du` = 0) ;
  * scoping société (cross-tenant 404) ;
  * l'endpoint `/credit-warning/` expose `recouvrement` sans dupliquer le
    blocage dur (XFAC28) — reste un avertissement.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Facture, FollowupLevel, Paiement
from apps.ventes.selectors import etat_recouvrement_client

User = get_user_model()


def make_company(slug='ycash4-co', nom='YCASH4 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


class Ycash4TestBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ycash4_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='YCASH4',
            telephone='+212600000004')
        FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Rappel', delai_jours=7)
        FollowupLevel.objects.create(
            company=self.company, ordre=2, nom='Relance ferme',
            delai_jours=15)

    def _facture_en_retard(self, jours_retard, montant=Decimal('1000')):
        echeance = timezone.now().date() - timedelta(days=jours_retard)
        return Facture.objects.create(
            company=self.company, reference=f'FAC-YCASH4-{jours_retard}',
            client=self.client_obj, statut=Facture.Statut.EN_RETARD,
            taux_tva=Decimal('20.00'), montant_ttc=montant,
            date_echeance=echeance)


class TestClientAJour(Ycash4TestBase):
    def test_client_sans_retard_a_jour(self):
        result = etat_recouvrement_client(self.company, self.client_obj.id)
        self.assertTrue(result['a_jour'])
        self.assertEqual(result['retard_max_jours'], 0)
        self.assertIsNone(result['niveau_relance'])
        self.assertEqual(result['encours_echu'], Decimal('0'))

    def test_endpoint_sans_retard_pas_de_warning_recouvrement(self):
        r = self.api.get(
            f'/api/django/ventes/clients/{self.client_obj.id}/credit-warning/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['recouvrement']['a_jour'])


class TestClientEnRetard(Ycash4TestBase):
    def test_retard_au_dela_du_seuil_affiche_avertissement_chiffre(self):
        self._facture_en_retard(20, montant=Decimal('1500'))
        result = etat_recouvrement_client(self.company, self.client_obj.id)
        self.assertFalse(result['a_jour'])
        self.assertEqual(result['retard_max_jours'], 20)
        self.assertIsNotNone(result['niveau_relance'])
        self.assertEqual(result['niveau_relance']['nom'], 'Relance ferme')
        self.assertEqual(result['encours_echu'], Decimal('1500'))

    def test_endpoint_expose_message_recouvrement_chiffre(self):
        self._facture_en_retard(20, montant=Decimal('1500'))
        r = self.api.get(
            f'/api/django/ventes/clients/{self.client_obj.id}/credit-warning/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['recouvrement']['a_jour'])
        self.assertIn('20', r.data['message'])
        self.assertIn('1500', r.data['message'])

    def test_retard_max_parmi_plusieurs_factures(self):
        self._facture_en_retard(5, montant=Decimal('100'))
        self._facture_en_retard(25, montant=Decimal('200'))
        result = etat_recouvrement_client(self.company, self.client_obj.id)
        self.assertEqual(result['retard_max_jours'], 25)
        self.assertEqual(result['encours_echu'], Decimal('300'))


class TestFlagSeLeveAuReglement(Ycash4TestBase):
    def test_facture_reglee_leve_le_flag(self):
        facture = self._facture_en_retard(20, montant=Decimal('1000'))
        result = etat_recouvrement_client(self.company, self.client_obj.id)
        self.assertFalse(result['a_jour'])

        Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('1000'),
            date_paiement=timezone.localdate(), mode=Paiement.Mode.VIREMENT)
        facture.statut = Facture.Statut.PAYEE
        facture.save(update_fields=['statut'])

        result_apres = etat_recouvrement_client(self.company, self.client_obj.id)
        self.assertTrue(result_apres['a_jour'])
        self.assertEqual(result_apres['encours_echu'], Decimal('0'))


class TestScopingRecouvrement(Ycash4TestBase):
    def test_cross_tenant_404(self):
        other = make_company('ycash4-other', 'Other YCASH4 Co')
        other_user = User.objects.create_user(
            username='ycash4_other', password='x', role_legacy='responsable',
            company=other)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(other_user)}')
        r = api.get(
            f'/api/django/ventes/clients/{self.client_obj.id}/credit-warning/')
        self.assertEqual(r.status_code, 404)

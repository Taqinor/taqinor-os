"""
NTP2P10 — OCR facture fournisseur → auto-lien BCF + auto-évaluation 3-voies.

CRITÈRE D'ACCEPTATION : uploader une facture OCR d'un fournisseur ayant un
BCF ouvert du même montant (± tolérance) propose ce BCF en premier choix
(``stock/factures-fournisseur/suggestions-bcf/?fournisseur=&montant=``).
Ne lie JAMAIS rien silencieusement (lecture seule) ; la confirmation
(PATCH classique posant ``bon_commande``) déclenche IMMÉDIATEMENT
``services.evaluate_facture_exception`` au lieu d'attendre le prochain
paiement.

Run :
    python manage.py test apps.stock.test_ntp2p10_ocr_suggestions_bcf -v2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock import selectors as stock_selectors
from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, Fournisseur, Produit,
)

User = get_user_model()
BASE = '/api/django/stock'


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username):
    role = Role.objects.create(
        company=company, nom=f'r-{username}',
        permissions=['stock_modifier', 'stock_voir'])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class SuggererBcfPourFactureTests(TestCase):
    def setUp(self):
        self.company = _company('ntp2p10-co')
        self.user = _user(self.company, 'ntp2p10-user')
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTP2P10')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur NTP2P10', sku='OND-NTP2P10',
            prix_vente=Decimal('5000'), prix_achat=Decimal('3000'))

    def _bcf(self, ref, montant_ligne, *, statut=BonCommandeFournisseur.Statut.ENVOYE,
             jours_avant=5):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=ref, fournisseur=self.fournisseur,
            statut=statut,
            date_commande=timezone.localdate() - timedelta(days=jours_avant))
        bc.lignes.create(
            produit=self.produit, quantite=1, prix_achat_unitaire=montant_ligne)
        return bc

    def test_meilleur_candidat_en_premier(self):
        self._bcf('BCF-LOIN', Decimal('1000'), jours_avant=3)
        proche = self._bcf('BCF-PROCHE', Decimal('3050'), jours_avant=10)

        suggestions = stock_selectors.suggerer_bcf_pour_facture(
            self.company, fournisseur_id=self.fournisseur.id, montant='3000')

        self.assertEqual(suggestions[0]['id'], proche.id)

    def test_bcf_brouillon_exclu(self):
        self._bcf(
            'BCF-BROUILLON', Decimal('3000'),
            statut=BonCommandeFournisseur.Statut.BROUILLON)

        suggestions = stock_selectors.suggerer_bcf_pour_facture(
            self.company, fournisseur_id=self.fournisseur.id, montant='3000')
        self.assertEqual(suggestions, [])

    def test_bcf_trop_ancien_exclu(self):
        self._bcf('BCF-VIEUX', Decimal('3000'), jours_avant=90)

        suggestions = stock_selectors.suggerer_bcf_pour_facture(
            self.company, fournisseur_id=self.fournisseur.id, montant='3000',
            jours_fenetre=60)
        self.assertEqual(suggestions, [])

    def test_sans_fournisseur_liste_vide(self):
        self.assertEqual(
            stock_selectors.suggerer_bcf_pour_facture(
                self.company, fournisseur_id=None, montant='3000'), [])

    def test_endpoint_api_expose_les_suggestions(self):
        bc = self._bcf('BCF-API', Decimal('3000'))
        resp = self.api.get(
            f'{BASE}/factures-fournisseur/suggestions-bcf/',
            {'fournisseur': self.fournisseur.id, 'montant': '3000'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]['id'], bc.id)

    def test_endpoint_sans_fournisseur_refuse(self):
        resp = self.api.get(f'{BASE}/factures-fournisseur/suggestions-bcf/')
        self.assertEqual(resp.status_code, 400)


class ConfirmationDeclencheRapprochementTests(TestCase):
    def setUp(self):
        self.company = _company('ntp2p10-confirm-co')
        self.user = _user(self.company, 'ntp2p10-confirm-user')
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTP2P10 Confirm')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau NTP2P10', sku='PAN-NTP2P10-CF',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'))
        self.bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-CONFIRM',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_commande=timezone.localdate())
        self.bc.lignes.create(
            produit=self.produit, quantite=1, prix_achat_unitaire=Decimal('1000'))
        self.facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-NTP2P10-CONFIRM',
            fournisseur=self.fournisseur, date_facture=date.today(),
            montant_ht=Decimal('1000'), montant_ttc=Decimal('1000'))

    def test_patch_bon_commande_declenche_evaluation_immediate(self):
        resp = self.api.patch(
            f'{BASE}/factures-fournisseur/{self.facture.id}/',
            {'bon_commande': self.bc.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.bon_commande_id, self.bc.id)
        # Le rapprochement 3 voies a été créé/rafraîchi (AUD233) : la
        # facture n'a pas attendu le prochain paiement pour être évaluée.
        from apps.compta.selectors import rapprochement_ecart_pct
        self.assertIsNotNone(
            rapprochement_ecart_pct(self.company, self.bc.id))

    def test_patch_sans_changer_bon_commande_ne_relance_rien(self):
        # Un PATCH qui ne touche pas bon_commande (ex. note) ne déclenche
        # rien — comportement historique inchangé, aucune évaluation.
        resp = self.api.patch(
            f'{BASE}/factures-fournisseur/{self.facture.id}/',
            {'note': 'test'}, format='json')
        self.assertEqual(resp.status_code, 200)
        from apps.compta.selectors import rapprochement_ecart_pct
        self.assertIsNone(rapprochement_ecart_pct(self.company, self.bc.id))

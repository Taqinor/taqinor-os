"""
NTP2P21 — Suggestions de consolidation de commandes.

CRITÈRE D'ACCEPTATION : deux BCF brouillon vers le même fournisseur dans la
même semaine déclenchent une suggestion visible sur la liste BCF
(``bons-commande-fournisseur/suggestions-consolidation/``). Ne fusionne
JAMAIS rien elle-même (lecture seule) ; l'économie estimée n'apparaît que si
``Fournisseur.frais_livraison_estimes`` est configuré (jamais un montant
inventé).

Run :
    python manage.py test apps.stock.test_ntp2p21_suggestions_consolidation -v2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock import selectors as stock_selectors
from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit

User = get_user_model()


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


def _bcf_brouillon(company, fournisseur, ref, *, date_creation=None):
    bc = BonCommandeFournisseur.objects.create(
        company=company, reference=ref, fournisseur=fournisseur,
        statut=BonCommandeFournisseur.Statut.BROUILLON)
    if date_creation is not None:
        BonCommandeFournisseur.objects.filter(pk=bc.pk).update(
            date_creation=date_creation)
        bc.refresh_from_db()
    return bc


class SuggestionsConsolidationBcfTests(TestCase):
    def setUp(self):
        self.company = _company('ntp2p21-co')
        self.user = _user(self.company, 'ntp2p21-user')
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTP2P21')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau NTP2P21', sku='PAN-NTP2P21',
            prix_vente=Decimal('100'), prix_achat=Decimal('60'))

    def test_deux_bcf_meme_fournisseur_meme_semaine_declenchent_suggestion(self):
        now = timezone.now()
        b1 = _bcf_brouillon(self.company, self.fournisseur, 'BCF-C1',
                            date_creation=now)
        b2 = _bcf_brouillon(self.company, self.fournisseur, 'BCF-C2',
                            date_creation=now + timedelta(hours=2))
        for b in (b1, b2):
            b.lignes.create(produit=self.produit, quantite=2,
                            prix_achat_unitaire=Decimal('60'))

        suggestions = stock_selectors.suggestions_consolidation_bcf(
            self.company)
        self.assertEqual(len(suggestions), 1)
        s = suggestions[0]
        self.assertEqual(s['fournisseur_id'], self.fournisseur.id)
        self.assertEqual(s['nb_bons'], 2)
        self.assertIsNone(s['economie_estimee'])  # pas de champ configuré

        resp = self.api.get(
            '/api/django/stock/bons-commande-fournisseur/'
            'suggestions-consolidation/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 1)
        self.assertEqual(resp.json()[0]['nb_bons'], 2)

    def test_un_seul_bcf_ne_declenche_rien(self):
        _bcf_brouillon(self.company, self.fournisseur, 'BCF-SOLO')
        suggestions = stock_selectors.suggestions_consolidation_bcf(
            self.company)
        self.assertEqual(suggestions, [])

    def test_semaines_differentes_ne_fusionnent_pas(self):
        now = timezone.now()
        _bcf_brouillon(self.company, self.fournisseur, 'BCF-S1',
                       date_creation=now)
        _bcf_brouillon(self.company, self.fournisseur, 'BCF-S2',
                       date_creation=now + timedelta(days=30))
        suggestions = stock_selectors.suggestions_consolidation_bcf(
            self.company)
        self.assertEqual(suggestions, [])

    def test_economie_estimee_quand_fournisseur_configure(self):
        self.fournisseur.frais_livraison_estimes = Decimal('150')
        self.fournisseur.save(update_fields=['frais_livraison_estimes'])
        now = timezone.now()
        _bcf_brouillon(self.company, self.fournisseur, 'BCF-E1',
                       date_creation=now)
        _bcf_brouillon(self.company, self.fournisseur, 'BCF-E2',
                       date_creation=now + timedelta(hours=1))
        _bcf_brouillon(self.company, self.fournisseur, 'BCF-E3',
                       date_creation=now + timedelta(hours=2))
        suggestions = stock_selectors.suggestions_consolidation_bcf(
            self.company)
        self.assertEqual(len(suggestions), 1)
        # 3 bons -> (3 - 1) x 150 = 300 MAD d'économie estimée.
        self.assertEqual(suggestions[0]['economie_estimee'], Decimal('300'))

    def test_bcf_non_brouillon_exclu(self):
        now = timezone.now()
        b1 = _bcf_brouillon(self.company, self.fournisseur, 'BCF-ENV1',
                            date_creation=now)
        b1.statut = BonCommandeFournisseur.Statut.ENVOYE
        b1.save(update_fields=['statut'])
        _bcf_brouillon(self.company, self.fournisseur, 'BCF-ENV2',
                       date_creation=now + timedelta(hours=1))
        suggestions = stock_selectors.suggestions_consolidation_bcf(
            self.company)
        self.assertEqual(suggestions, [])

    def test_ne_fusionne_jamais_rien_elle_meme(self):
        now = timezone.now()
        _bcf_brouillon(self.company, self.fournisseur, 'BCF-RO1',
                       date_creation=now)
        _bcf_brouillon(self.company, self.fournisseur, 'BCF-RO2',
                       date_creation=now + timedelta(hours=1))
        stock_selectors.suggestions_consolidation_bcf(self.company)
        self.assertEqual(
            BonCommandeFournisseur.objects.filter(
                company=self.company,
                statut=BonCommandeFournisseur.Statut.BROUILLON).count(), 2)

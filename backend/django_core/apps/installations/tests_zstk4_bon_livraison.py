"""ZSTK4 — Bon de livraison imprimable depuis une Livraison planifiée.

Le BL PDF actuel (N22) part d'un devis/chantier ; la `Livraison` planifiée
(FG329) n'avait AUCUN document imprimable. Couvre :

  * une livraison rend un BL PDF téléchargeable (200, `application/pdf`) ;
  * AUCUN champ de coût interne (`cout_transport`, prix d'achat) n'apparaît
    dans le contexte de rendu (test dédié « cout_transport absent ») ;
  * une livraison cross-company → 404.

Run :
    python manage.py test apps.installations.tests_zstk4_bon_livraison -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit, EmplacementStock
from apps.installations.models import Installation, Livraison, LivraisonLigne
from apps.installations import livraison_pdf

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'zstk4-co-{n}', defaults={'nom': f'ZSTK4 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'zstk4-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='ZSTK4',
        email=f'zstk4-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-ZSTK4-{n}', client=client,
        statut=Installation.Statut.PLANIFIE)


def make_livraison(company, installation, cout_transport=Decimal('250')):
    depot = EmplacementStock.objects.create(
        company=company, nom='Dépôt principal', is_principal=True)
    produit = Produit.objects.create(
        company=company, nom='Panneau ZSTK4',
        prix_vente=Decimal('100'), prix_achat=Decimal('60'),
        quantite_stock=Decimal('20'))
    liv = Livraison.objects.create(
        company=company, reference='LIV-ZSTK4-0001', installation=installation,
        depot=depot, cout_transport=cout_transport,
        transporteur_nom='Transporteur X')
    LivraisonLigne.objects.create(
        livraison=liv, produit=produit, designation=produit.nom, quantite=6)
    return liv


class TestBonLivraisonPdf(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other_company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.liv = make_livraison(self.company, self.inst)

    def test_endpoint_renvoie_un_pdf(self):
        r = self.api.get(f'{BASE}/livraisons/{self.liv.id}/bon-livraison/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_contexte_sans_cout_interne(self):
        """Le contexte de rendu ne porte JAMAIS `cout_transport` ni un prix
        d'achat — seulement désignation/quantité pour les lignes."""
        context_keys_forbidden = ('cout_transport', 'prix_achat', 'marge')
        # On inspecte directement le payload de lignes (source du rendu HTML).
        lignes = livraison_pdf._lignes_payload(self.liv)
        for ligne in lignes:
            for forbidden in context_keys_forbidden:
                self.assertNotIn(forbidden, ligne)
        # Le module ne construit jamais de clé de contexte portant le coût.
        import inspect
        source = inspect.getsource(livraison_pdf.bon_livraison_pdf)
        self.assertNotIn('cout_transport', source)
        self.assertNotIn('prix_achat', source)

    def test_cross_company_404(self):
        other_inst = make_installation(self.other_company)
        other_liv = make_livraison(self.other_company, other_inst)
        r = self.api.get(f'{BASE}/livraisons/{other_liv.id}/bon-livraison/')
        self.assertEqual(r.status_code, 404)

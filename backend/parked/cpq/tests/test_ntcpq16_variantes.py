"""NTCPQ16 — Moteur de génération de variantes de devis par substitution."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.cpq.models import ProduitEquivalent
from apps.cpq.services import generer_variantes_devis
from apps.ventes.models import Devis, LigneDevis
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)

EQUIV = '/api/django/cpq/produits-equivalents/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestVariantesDevis(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.base = ProduitFactory(
            company=self.company, prix_vente=Decimal('1000.00'))
        self.eco = ProduitFactory(
            company=self.company, prix_vente=Decimal('700.00'))
        self.premium = ProduitFactory(
            company=self.company, prix_vente=Decimal('1500.00'))
        ProduitEquivalent.objects.create(
            company=self.company, produit_source=self.base,
            produit_substitut=self.eco,
            tier=ProduitEquivalent.Tier.ECONOMIQUE)
        ProduitEquivalent.objects.create(
            company=self.company, produit_source=self.base,
            produit_substitut=self.premium,
            tier=ProduitEquivalent.Tier.PREMIUM)
        self.devis = DevisFactory(company=self.company)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.base, designation=self.base.nom,
            quantite=Decimal('1'), prix_unitaire=Decimal('1000.00'))

    def test_genere_trois_variantes_liees_avec_totaux_differents(self):
        variantes = generer_variantes_devis(self.devis, user=self.user)
        self.assertEqual(len(variantes), 3)
        par_tier = {v.variante_tier: v for v in variantes}
        self.assertEqual(set(par_tier), {'economique', 'standard', 'premium'})
        for v in variantes:
            self.assertEqual(v.variante_de_id, self.devis.id)
            self.assertEqual(v.statut, Devis.Statut.BROUILLON)
            self.assertEqual(v.company_id, self.company.id)
        self.assertEqual(par_tier['economique'].total_ht, Decimal('700.00'))
        self.assertEqual(par_tier['standard'].total_ht, Decimal('1000.00'))
        self.assertEqual(par_tier['premium'].total_ht, Decimal('1500.00'))

    def test_substitution_remplace_bien_le_produit(self):
        variantes = generer_variantes_devis(self.devis, user=self.user)
        eco = next(v for v in variantes if v.variante_tier == 'economique')
        ligne = eco.lignes.get()
        self.assertEqual(ligne.produit_id, self.eco.id)
        self.assertEqual(ligne.designation, self.eco.nom)

    def test_le_devis_de_base_reste_intact(self):
        generer_variantes_devis(self.devis, user=self.user)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(self.devis.lignes.get().produit_id, self.base.id)
        self.assertEqual(self.devis.total_ht, Decimal('1000.00'))

    def test_regeneration_ne_double_pas_les_variantes(self):
        generer_variantes_devis(self.devis, user=self.user)
        generer_variantes_devis(self.devis, user=self.user)
        self.assertEqual(
            Devis.objects.filter(variante_de=self.devis).count(), 3)

    def test_refus_de_generer_depuis_une_variante(self):
        variantes = generer_variantes_devis(self.devis, user=self.user)
        with self.assertRaises(ValidationError):
            generer_variantes_devis(variantes[0], user=self.user)

    def test_tier_inconnu_refuse(self):
        with self.assertRaises(ValidationError):
            generer_variantes_devis(
                self.devis, user=self.user, tiers=['luxe'])

    def test_substitution_dune_autre_societe_ignoree(self):
        autre = CompanyFactory()
        etranger = ProduitFactory(company=autre, prix_vente=Decimal('1.00'))
        ProduitEquivalent.objects.create(
            company=autre, produit_source=self.base,
            produit_substitut=etranger,
            tier=ProduitEquivalent.Tier.STANDARD)
        variantes = generer_variantes_devis(self.devis, user=self.user)
        standard = next(v for v in variantes
                        if v.variante_tier == 'standard')
        self.assertEqual(standard.total_ht, Decimal('1000.00'))

    def test_endpoint_post_puis_get(self):
        url = f'/api/django/cpq/devis/{self.devis.id}/variantes/'
        api = auth(self.user)
        resp = api.post(url, {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 3)
        resp = api.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            sorted(v['tier'] for v in resp.data),
            ['economique', 'premium', 'standard'])

    def test_endpoint_isole_les_societes(self):
        autre = DevisFactory(company=CompanyFactory())
        resp = auth(self.user).post(
            f'/api/django/cpq/devis/{autre.id}/variantes/', {}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_crud_equivalents_company_posee_serveur(self):
        resp = auth(self.user).post(EQUIV, {
            'produit_source': self.base.id,
            'produit_substitut': self.eco.id,
            'tier': 'standard',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        eq = ProduitEquivalent.objects.get(id=resp.data['id'])
        self.assertEqual(eq.company_id, self.company.id)

    def test_crud_refuse_un_produit_dune_autre_societe(self):
        etranger = ProduitFactory(company=CompanyFactory())
        resp = auth(self.user).post(EQUIV, {
            'produit_source': etranger.id,
            'produit_substitut': self.eco.id,
            'tier': 'standard',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

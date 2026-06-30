"""Tests des tâches DC (référentiels uniques / câblage masters) du lot Stock.

Couvre :
  - DC15 : identité légale fournisseur (ICE/IF/RC/RIB).
  - DC28 : résolveur unique `cout_achat_courant` (accord/dernier payé/fallback).
  - DC30/DC31 : sélecteur d'identité tiers fournisseur consommé par
    Compta (comptes auxiliaires) et Contrats (parties) — jamais re-saisir
    nom/ICE/RIB sur le compte ou la partie.

INTERNE : les prix d'achat ne sont jamais client-facing.

Run :
    python manage.py test apps.stock.test_dc -v 2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import Produit, Fournisseur, PrixFournisseur

User = get_user_model()


def make_company(slug='dc-co', nom='DC Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class DCBase(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company(slug='dc-co-2', nom='Autre Co')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Grossiste Solaire',
            ice='001234567000089', identifiant_fiscal='IF12345',
            rc='RC987', rib='011780000012345678901234')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND5',
            prix_achat=Decimal('600'), prix_vente=Decimal('900'),
            quantite_stock=5)


class TestDC15FournisseurIdentite(DCBase):
    """DC15 — Fournisseur porte ICE/IF/RC/RIB, optionnels et persistés."""

    def test_fields_persisted(self):
        f = Fournisseur.objects.get(pk=self.fournisseur.pk)
        self.assertEqual(f.ice, '001234567000089')
        self.assertEqual(f.identifiant_fiscal, 'IF12345')
        self.assertEqual(f.rc, 'RC987')
        self.assertEqual(f.rib, '011780000012345678901234')

    def test_fields_optional(self):
        f = Fournisseur.objects.create(company=self.company, nom='Sans identité')
        self.assertIsNone(f.ice)
        self.assertIsNone(f.identifiant_fiscal)
        self.assertIsNone(f.rc)
        self.assertIsNone(f.rib)


class TestDC28CoutAchatCourant(DCBase):
    """DC28 — un seul résolveur de coût d'achat courant, précédence documentée :
    PrixFournisseur (dernier payé) → Produit.prix_achat (fallback)."""

    def test_fallback_to_catalogue(self):
        from apps.stock.services import cout_achat_courant_with_source
        cout, source = cout_achat_courant_with_source(self.produit)
        self.assertEqual(cout, Decimal('600'))
        self.assertEqual(source, 'catalogue')

    def test_prix_fournisseur_takes_precedence(self):
        from apps.stock.services import cout_achat_courant_with_source
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('550'),
            date_dernier_achat=date(2026, 1, 1))
        cout, source = cout_achat_courant_with_source(self.produit)
        self.assertEqual(cout, Decimal('550'))
        self.assertEqual(source, 'prix_fournisseur')

    def test_latest_paid_wins_over_older(self):
        from apps.stock.services import cout_achat_courant_with_source
        f2 = Fournisseur.objects.create(company=self.company, nom='Autre four')
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('580'),
            date_dernier_achat=date(2026, 1, 1))
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=f2, prix_achat=Decimal('520'),
            date_dernier_achat=date(2026, 5, 1))
        cout, source = cout_achat_courant_with_source(self.produit)
        # Dernier payé = mai (520), pas le moins cher.
        self.assertEqual(cout, Decimal('520'))
        self.assertEqual(source, 'prix_fournisseur')

    def test_zero_price_fournisseur_ignored(self):
        from apps.stock.services import cout_achat_courant_with_source
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('0'),
            date_dernier_achat=date(2026, 1, 1))
        cout, source = cout_achat_courant_with_source(self.produit)
        self.assertEqual(cout, Decimal('600'))
        self.assertEqual(source, 'catalogue')

    def test_scalar_accessor_matches_source_value(self):
        from apps.stock.services import (
            cout_achat_courant, cout_achat_courant_with_source)
        self.assertEqual(
            cout_achat_courant(self.produit),
            cout_achat_courant_with_source(self.produit)[0])


class TestDC30DC31TiersIdentite(DCBase):
    """DC30/DC31 — l'identité d'un compte auxiliaire (compta) / d'une partie au
    contrat se DÉRIVE du Fournisseur via le sélecteur, jamais re-stockée."""

    def test_selector_returns_identity(self):
        from apps.stock.selectors import get_fournisseur_tiers_identity
        ident = get_fournisseur_tiers_identity(self.company, self.fournisseur.id)
        self.assertEqual(ident['nom'], 'Grossiste Solaire')
        self.assertEqual(ident['ice'], '001234567000089')
        self.assertEqual(ident['identifiant_fiscal'], 'IF12345')
        self.assertEqual(ident['rc'], 'RC987')
        self.assertEqual(ident['rib'], '011780000012345678901234')
        self.assertEqual(ident['type_tiers'], 'fournisseur')

    def test_selector_scoped_to_company(self):
        from apps.stock.selectors import get_fournisseur_tiers_identity
        ident = get_fournisseur_tiers_identity(self.other, self.fournisseur.id)
        self.assertIsNone(ident)

    def test_selector_missing_returns_none(self):
        from apps.stock.selectors import get_fournisseur_tiers_identity
        self.assertIsNone(
            get_fournisseur_tiers_identity(self.company, 999999))


class TestDC35FicheTechnique(DCBase):
    """DC35 / FG254 — la fiche technique référence `Produit` par FK et ne
    re-stocke pas marque/garantie/specs/courbe ; seuls des params électriques
    normalisés (Pmax/Voc/Isc…) + le PDF y vivent. OneToOne par produit."""

    def _make_fiche(self, produit=None, **kwargs):
        from apps.stock.models import FicheTechnique
        return FicheTechnique.objects.create(
            company=self.company, produit=produit or self.produit, **kwargs)

    def test_params_persisted(self):
        fiche = self._make_fiche(
            pmax_wc=Decimal('550'), voc_v=Decimal('49.5'),
            isc_a=Decimal('14.2'), rendement_pct=Decimal('21.30'))
        from apps.stock.models import FicheTechnique
        f = FicheTechnique.objects.get(pk=fiche.pk)
        self.assertEqual(f.pmax_wc, Decimal('550'))
        self.assertEqual(f.voc_v, Decimal('49.5'))
        self.assertEqual(f.isc_a, Decimal('14.2'))
        self.assertEqual(f.rendement_pct, Decimal('21.30'))

    def test_all_params_optional_pdf_only(self):
        # Une fiche peut ne porter qu'un PDF (ou rien), tous les params nullables.
        fiche = self._make_fiche()
        self.assertIsNone(fiche.pmax_wc)
        self.assertIsNone(fiche.voc_v)
        self.assertIsNone(fiche.isc_a)
        self.assertFalse(fiche.pdf)

    def test_one_fiche_per_produit(self):
        from django.db import IntegrityError, transaction
        self._make_fiche()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make_fiche()

    def test_does_not_restore_identity(self):
        # L'identité (marque/garantie) reste sur Produit — pas de champ qui la
        # recopie sur la fiche.
        from apps.stock.models import FicheTechnique
        field_names = {f.name for f in FicheTechnique._meta.get_fields()}
        for forbidden in ('marque', 'garantie', 'courbe_pompe', 'description',
                          'prix_vente', 'tva'):
            self.assertNotIn(forbidden, field_names)

    def test_serializer_reads_identity_from_produit(self):
        from apps.stock.serializers import FicheTechniqueSerializer
        self.produit.marque = 'JA Solar'
        self.produit.garantie = '12 ans produit / 30 ans production'
        self.produit.save(update_fields=['marque', 'garantie'])
        fiche = self._make_fiche(pmax_wc=Decimal('550'))
        data = FicheTechniqueSerializer(fiche).data
        self.assertEqual(data['produit_nom'], 'Onduleur 5kW')
        self.assertEqual(data['produit_marque'], 'JA Solar')
        self.assertEqual(
            data['produit_garantie'], '12 ans produit / 30 ans production')


class TestDC35FicheTechniqueAPI(DCBase):
    """DC35 — multi-tenant : `company` forcé serveur, queryset scopé société,
    produit cross-tenant rejeté."""

    def setUp(self):
        super().setUp()
        from rest_framework.test import APIClient
        self.user = User.objects.create_user(
            username='ft-user', password='x', company=self.company)
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_forces_company_from_request(self):
        resp = self.client.post(
            '/api/django/stock/fiches-techniques/',
            {'produit': self.produit.id, 'company': self.other.id,
             'pmax_wc': '550'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        from apps.stock.models import FicheTechnique
        fiche = FicheTechnique.objects.get(pk=resp.data['id'])
        # company forcé sur la société du demandeur, jamais celle du body.
        self.assertEqual(fiche.company_id, self.company.id)

    def test_queryset_scoped_to_company(self):
        from apps.stock.models import FicheTechnique
        other_prod = Produit.objects.create(
            company=self.other, nom='Autre', sku='AUT',
            prix_vente=Decimal('1'), quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.other, produit=other_prod, pmax_wc=Decimal('400'))
        FicheTechnique.objects.create(
            company=self.company, produit=self.produit, pmax_wc=Decimal('550'))
        resp = self.client.get('/api/django/stock/fiches-techniques/')
        self.assertEqual(resp.status_code, 200)
        results = resp.data.get('results', resp.data)
        produit_ids = {r['produit'] for r in results}
        self.assertIn(self.produit.id, produit_ids)
        self.assertNotIn(other_prod.id, produit_ids)

    def test_cross_tenant_produit_rejected(self):
        other_prod = Produit.objects.create(
            company=self.other, nom='Autre', sku='AUT2',
            prix_vente=Decimal('1'), quantite_stock=1)
        resp = self.client.post(
            '/api/django/stock/fiches-techniques/',
            {'produit': other_prod.id, 'pmax_wc': '550'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

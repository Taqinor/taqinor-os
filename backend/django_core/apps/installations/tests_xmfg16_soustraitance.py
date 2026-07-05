"""
XMFG16 — Assemblage sous-traité (façon) avec suivi des composants confiés.

Couvre :
  * cycle confié→reçu : la confirmation (`demarrer`) transfère les composants
    vers un emplacement dédié « chez {sous-traitant} » (idempotent) ;
  * la clôture (`terminer`) consomme DEPUIS cet emplacement (backflush XMFG1
    avec `emplacement_source` forcé) ;
  * le coût du composite intègre la façon (composants + montant OST),
    JAMAIS client-facing ;
  * le rapport des composants restant chez chaque sous-traitant ;
  * permissions responsable/admin sur les endpoints de coût/rapport.

Run :
    python manage.py test apps.installations.tests_xmfg16_soustraitance -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, OrdreSousTraitance,
)
from apps.stock.models import Fournisseur

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xmfg16-co-{n}', defaults={'nom': nom or f'XMFG16 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg16-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100, prix_achat=0):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=prix_achat,
        quantite_stock=stock)


def make_soustraitant(company, nom='Atelier Façon'):
    return Fournisseur.objects.create(
        company=company, nom=nom, type=Fournisseur.Type.SERVICE)


class TestConfierComposants(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(
            self.company, nom='Onduleur', stock=50, prix_achat=100)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=2)
        self.sous_traitant = make_soustraitant(self.company)

    def test_demarrer_confie_composants_emplacement_dedie(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ST1', kit=self.kit,
            quantite=1, sous_traitant=self.sous_traitant, created_by=self.user)
        resp = self.api.post(f'{BASE}/ordres-assemblage/{ordre.id}/demarrer/')
        self.assertEqual(resp.status_code, 200, resp.content)
        ordre.refresh_from_db()
        self.assertIsNotNone(ordre.emplacement_source_id)
        self.assertIn(
            self.sous_traitant.nom, ordre.emplacement_source.nom)

    def test_demarrer_idempotent_ne_retransfere_pas(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ST2', kit=self.kit,
            quantite=1, sous_traitant=self.sous_traitant, created_by=self.user)
        self.api.post(f'{BASE}/ordres-assemblage/{ordre.id}/demarrer/')
        ordre.refresh_from_db()
        emplacement_id_1 = ordre.emplacement_source_id
        # ré-appel manuel du service (le statut est déjà en_cours — simule
        # une ré-exécution défensive) : ne doit pas planter ni retransférer.
        from apps.installations.services import confier_composants_soustraitance
        confier_composants_soustraitance(ordre)
        ordre.refresh_from_db()
        self.assertEqual(ordre.emplacement_source_id, emplacement_id_1)

    def test_ordre_sans_soustraitant_comportement_inchange(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ST3', kit=self.kit,
            quantite=1, created_by=self.user)
        resp = self.api.post(f'{BASE}/ordres-assemblage/{ordre.id}/demarrer/')
        self.assertEqual(resp.status_code, 200, resp.content)
        ordre.refresh_from_db()
        self.assertIsNone(ordre.emplacement_source_id)


class TestReceptionEtCoutFacon(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(
            self.company, nom='Onduleur', stock=50, prix_achat=100)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=2)
        self.sous_traitant = make_soustraitant(self.company)
        self.ost = OrdreSousTraitance.objects.create(
            company=self.company, reference='OST-XMFG16-1',
            sous_traitant=self.sous_traitant, prestation='Assemblage façon',
            montant=Decimal('500'), montant_realise=Decimal('450'),
            created_by=self.user)

    def test_cycle_confie_recu_consomme_depuis_emplacement_dedie(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ST4', kit=self.kit,
            quantite=1, sous_traitant=self.sous_traitant,
            ordre_sous_traitance=self.ost, created_by=self.user)
        resp = self.api.post(f'{BASE}/ordres-assemblage/{ordre.id}/demarrer/')
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/',
            {'quantite_produite': 1}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ordre.refresh_from_db()
        self.assertTrue(ordre.stock_mouvemente)
        self.comp1.refresh_from_db()
        self.assertEqual(self.comp1.quantite_stock, 48)  # 50 - 2

    def test_cout_composite_integre_facon(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ST5', kit=self.kit,
            quantite=1, sous_traitant=self.sous_traitant,
            ordre_sous_traitance=self.ost, created_by=self.user)
        resp = self.api.get(
            f'{BASE}/ordres-assemblage/{ordre.id}/cout-soustraitance/')
        self.assertEqual(resp.status_code, 200, resp.content)
        # coût composants = 2 × 100 = 200 ; façon (montant_realise) = 450.
        self.assertAlmostEqual(resp.data['cout_composite'], 650.0)

    def test_cout_none_sans_ost(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ST6', kit=self.kit,
            quantite=1, created_by=self.user)
        resp = self.api.get(
            f'{BASE}/ordres-assemblage/{ordre.id}/cout-soustraitance/')
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_permission_refusee_role_limite(self):
        limited = make_user(self.company, role='normal')
        api = auth(limited)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ST7', kit=self.kit,
            quantite=1, ordre_sous_traitance=self.ost, created_by=self.user)
        resp = api.get(
            f'{BASE}/ordres-assemblage/{ordre.id}/cout-soustraitance/')
        self.assertEqual(resp.status_code, 403)


class TestRapportSousTraitants(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(
            self.company, nom='Onduleur', stock=50, prix_achat=100)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=2)
        self.sous_traitant = make_soustraitant(self.company)

    def test_reliquat_liste_apres_confie_avant_reception(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ST8', kit=self.kit,
            quantite=1, sous_traitant=self.sous_traitant, created_by=self.user)
        self.api.post(f'{BASE}/ordres-assemblage/{ordre.id}/demarrer/')
        resp = self.api.get(f'{BASE}/ordres-assemblage/rapport-soustraitants/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(
            resp.data[0]['sous_traitant_id'], self.sous_traitant.id)

    def test_reliquat_vide_apres_reception(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ST9', kit=self.kit,
            quantite=1, sous_traitant=self.sous_traitant, created_by=self.user)
        self.api.post(f'{BASE}/ordres-assemblage/{ordre.id}/demarrer/')
        self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/terminer/',
            {'quantite_produite': 1}, format='json')
        resp = self.api.get(f'{BASE}/ordres-assemblage/rapport-soustraitants/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data, [])

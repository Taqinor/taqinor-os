"""NTMFG11 — Coût de revient standard vs réel, au niveau entreprise
(nomenclature + gamme).

Critère : un standard versionné se calcule et se fige, le rapport décompose
les écarts matière/MO/rendement sur un cas testé, permission admin
vérifiée."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import CoutStandard, Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.selectors import analyse_couts, cout_standard_courant
from apps.mrp.services import (
    cloturer_of, confirmer_of, demarrer_operation, figer_cout_standard, terminer_operation,
)
from apps.stock.models import KitComposant, KitProduit, Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom, quantite_stock=0, prix_achat=0):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=0, tva=20,
        quantite_stock=quantite_stock, prix_achat=prix_achat)


class FigerCoutStandardTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-cstd-1', 'MRP CSTD 1')
        self.composant = make_produit(
            self.company, 'Composant', quantite_stock=1000, prix_achat=Decimal('5'))
        self.composite = make_produit(self.company, 'Composite')
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-CSTD', nom='Poste CSTD',
            cout_horaire=Decimal('120'))
        self.kit = KitProduit.objects.create(company=self.company, nom='Kit CSTD')
        KitComposant.objects.create(
            kit=self.kit, produit=self.composant, quantite=Decimal('2'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme CSTD', produit=self.composite,
            kit_source=self.kit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste, libelle='Op CSTD',
            temps_unitaire_min=Decimal('30'))  # 30 min/unité.

    def test_calcul_et_gel_du_standard(self):
        standard = figer_cout_standard(self.company, self.composite, self.gamme)
        # Matière : 2 composants x 5 = 10.
        self.assertEqual(standard.cout_matiere, Decimal('10'))
        # MO : 30 min = 0.5h x 120 = 60.
        self.assertEqual(standard.cout_main_oeuvre, Decimal('60'))
        self.assertEqual(standard.version, 1)
        self.assertEqual(standard.cout_unitaire_total, Decimal('70'))

    def test_figer_deux_fois_incremente_la_version_sans_ecraser(self):
        v1 = figer_cout_standard(self.company, self.composite, self.gamme)
        self.composant.prix_achat = Decimal('8')
        self.composant.save(update_fields=['prix_achat'])
        v2 = figer_cout_standard(self.company, self.composite, self.gamme)
        self.assertEqual(v1.version, 1)
        self.assertEqual(v2.version, 2)
        v1.refresh_from_db()
        self.assertEqual(v1.cout_matiere, Decimal('10'))  # v1 jamais modifiée.
        self.assertEqual(v2.cout_matiere, Decimal('16'))  # 2 x 8.

    def test_cout_standard_courant_renvoie_la_derniere_version(self):
        figer_cout_standard(self.company, self.composite, self.gamme)
        v2 = figer_cout_standard(self.company, self.composite, self.gamme)
        courant = cout_standard_courant(self.company, self.composite.id)
        self.assertEqual(courant.id, v2.id)

    def test_cross_tenant_isolation(self):
        autre = make_company('mrp-cstd-2', 'MRP CSTD 2')
        self.assertIsNone(cout_standard_courant(autre, self.composite.id))


class AnalyseCoutsTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-cstd-3', 'MRP CSTD 3')
        self.composant = make_produit(
            self.company, 'Composant AC', quantite_stock=1000, prix_achat=Decimal('5'))
        self.composite = make_produit(self.company, 'Composite AC')
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-AC', nom='Poste AC',
            cout_horaire=Decimal('60'))
        self.kit = KitProduit.objects.create(company=self.company, nom='Kit AC')
        KitComposant.objects.create(
            kit=self.kit, produit=self.composant, quantite=Decimal('1'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme AC', produit=self.composite,
            kit_source=self.kit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste, libelle='Op AC',
            temps_unitaire_min=Decimal('60'))  # 60 min/unité -> 1h.
        # Standard : matière = 1x5 = 5 ; MO = 1h x 60 = 60 -> total 65/unité.
        self.standard = figer_cout_standard(self.company, self.composite, self.gamme)

    def test_rapport_decompose_matiere_mo_rendement(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.composite, quantite=2,
            gamme=self.gamme)
        confirmer_of(of)
        of.refresh_from_db()
        op = of.operations.first()
        demarrer_operation(op)
        terminer_operation(op, quantite_bonne=2)
        op.refresh_from_db()
        # Force le temps réel à 3h (au lieu de 2h standard pour 2 unités) —
        # déterministe, indépendant du temps d'exécution du test.
        op.temps_reel_min = Decimal('180')
        op.save(update_fields=['temps_reel_min'])
        cloturer_of(of)

        rapport = analyse_couts(self.company, produit_id=self.composite.id)
        self.assertEqual(len(rapport), 1)
        ligne = rapport[0]
        self.assertEqual(ligne['nb_of'], 1)
        # Matière réelle = 2 x 5 = 10 ; standard = 2 x 5 = 10 -> écart = 0.
        self.assertEqual(Decimal(ligne['cout_matiere_reel']), Decimal('10'))
        self.assertEqual(Decimal(ligne['ecart_matiere']), Decimal('0'))
        # MO réelle = 3h x 60 = 180 ; standard = 2 x 60 = 120 -> écart = +60.
        self.assertEqual(Decimal(ligne['cout_main_oeuvre_reel']), Decimal('180'))
        self.assertEqual(Decimal(ligne['ecart_main_oeuvre']), Decimal('60'))
        # Rendement : 2 bonnes produites == 2 planifiées -> écart = 0.
        self.assertEqual(Decimal(ligne['ecart_rendement']), Decimal('0'))

    def test_of_sans_standard_est_ignore(self):
        autre_composite = make_produit(self.company, 'Sans standard')
        gamme2 = Gamme.objects.create(
            company=self.company, nom='Gamme sans standard',
            produit=autre_composite)
        OrdreFabrication.objects.create(
            company=self.company, produit=autre_composite, quantite=1,
            gamme=gamme2, statut=OrdreFabrication.Statut.TERMINE)
        rapport = analyse_couts(self.company, produit_id=autre_composite.id)
        self.assertEqual(rapport, [])


class CoutStandardApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-cstd-api-1', 'MRP CSTD API 1')
        self.admin = make_user(self.company, 'mrp-cstd-admin', role='admin')
        self.normal = make_user(self.company, 'mrp-cstd-normal', role='normal')
        self.composant = make_produit(self.company, 'C-API', prix_achat=Decimal('1'))
        self.composite = make_produit(self.company, 'Composite API')
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-API-CSTD', nom='Poste API CSTD')
        self.kit = KitProduit.objects.create(company=self.company, nom='Kit API CSTD')
        KitComposant.objects.create(kit=self.kit, produit=self.composant, quantite=Decimal('1'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme API CSTD', produit=self.composite,
            kit_source=self.kit)

    def test_figer_reserve_admin_responsable(self):
        api = auth(self.normal)
        resp = api.post('/api/django/mrp/couts-standard/figer/', {
            'produit': self.composite.id, 'gamme': self.gamme.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_figer_admin_ok(self):
        api = auth(self.admin)
        resp = api.post('/api/django/mrp/couts-standard/figer/', {
            'produit': self.composite.id, 'gamme': self.gamme.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(CoutStandard.objects.filter(company=self.company).count(), 1)

    def test_analyse_couts_reserve_admin_responsable(self):
        api = auth(self.normal)
        resp = api.get('/api/django/mrp/analyse-couts/')
        self.assertEqual(resp.status_code, 403)

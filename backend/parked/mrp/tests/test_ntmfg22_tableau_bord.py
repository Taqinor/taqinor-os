"""NTMFG22 — Tableau de bord Production consolidé (portefeuille d'OF,
retards, charge globale).

Critère : les 4 indicateurs sont exacts sur fixtures datées, carte visible
uniquement responsable/admin, dégrade proprement sans données."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import (
    EcheanceEntretienPoste, Gamme, OperationGamme, OrdreFabrication,
    PlanEntretienPoste, PosteDeCharge,
)
from apps.mrp.selectors import tableau_bord_production
from apps.mrp.services import confirmer_of, demarrer_operation, terminer_operation

from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class TableauBordTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-tb-1', 'MRP TableauBord 1')

    def test_degrade_sans_donnees(self):
        resultat = tableau_bord_production(self.company)
        self.assertEqual(resultat['of_en_retard'], 0)
        self.assertEqual(resultat['charge_moyenne_pct'], '0.0')
        self.assertEqual(resultat['trs_moyen_pct'], '0.0')
        self.assertEqual(resultat['postes_en_alerte_maintenance'], 0)

    def test_of_en_retard_compte_correctement(self):
        produit = make_produit(self.company)
        hier = timezone.now() - timedelta(days=1)
        OrdreFabrication.objects.create(
            company=self.company, produit=produit, quantite=1,
            statut=OrdreFabrication.Statut.PLANIFIE, date_fin_planifiee=hier)
        # OF prototype (NTMFG16) EXCLU du décompte.
        OrdreFabrication.objects.create(
            company=self.company, produit=produit, quantite=1,
            statut=OrdreFabrication.Statut.PLANIFIE, date_fin_planifiee=hier,
            est_prototype=True)
        # OF terminé (pas « en retard » — déjà clôturé).
        OrdreFabrication.objects.create(
            company=self.company, produit=produit, quantite=1,
            statut=OrdreFabrication.Statut.TERMINE, date_fin_planifiee=hier)
        resultat = tableau_bord_production(self.company)
        self.assertEqual(resultat['of_en_retard'], 1)

    def test_postes_en_alerte_maintenance_comptes(self):
        poste = PosteDeCharge.objects.create(
            company=self.company, code='P-TB', nom='Poste TB')
        plan = PlanEntretienPoste.objects.create(
            company=self.company, poste_charge=poste,
            description='Contrôle', intervalle_jours=30)
        EcheanceEntretienPoste.objects.create(
            plan=plan, date_prevue=timezone.localdate() - timedelta(days=2))
        resultat = tableau_bord_production(self.company)
        self.assertEqual(resultat['postes_en_alerte_maintenance'], 1)

    def test_charge_et_trs_moyens_sur_fixture(self):
        produit = make_produit(self.company)
        poste = PosteDeCharge.objects.create(
            company=self.company, code='P-TB2', nom='Poste TB2',
            capacite_heures_jour=Decimal('1'))  # 60 min/jour.
        gamme = Gamme.objects.create(
            company=self.company, nom='Gamme TB', produit=produit)
        OperationGamme.objects.create(
            gamme=gamme, ordre=1, poste_charge=poste, libelle='Op',
            temps_unitaire_min=Decimal('30'))
        of = OrdreFabrication.objects.create(
            company=self.company, produit=produit, quantite=1, gamme=gamme)
        confirmer_of(of)
        of.refresh_from_db()
        op = of.operations.first()
        demarrer_operation(op)
        op.demarree_le = timezone.now() - timedelta(minutes=30)
        op.save(update_fields=['demarree_le'])
        terminer_operation(op, quantite_bonne=1)

        resultat = tableau_bord_production(self.company)
        # Charge planifiée (7 prochains jours) : 30 min sur 60 min -> 50%.
        self.assertEqual(resultat['charge_moyenne_pct'], '50.0')
        # TRS moyen (7 derniers jours) : au moins un poste a des données.
        self.assertNotEqual(resultat['trs_moyen_pct'], '0.0')

    def test_isolation_tenant(self):
        autre_company = make_company('mrp-tb-2', 'MRP TableauBord 2')
        produit = make_produit(self.company)
        hier = timezone.now() - timedelta(days=1)
        OrdreFabrication.objects.create(
            company=self.company, produit=produit, quantite=1,
            statut=OrdreFabrication.Statut.PLANIFIE, date_fin_planifiee=hier)
        resultat = tableau_bord_production(autre_company)
        self.assertEqual(resultat['of_en_retard'], 0)


class TableauBordApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-tb-api-1', 'MRP TableauBord API 1')

    def test_responsable_accede(self):
        user = make_user(self.company, 'mrp-tb-resp', role='responsable')
        resp = auth(user).get('/api/django/mrp/tableau-bord/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('of_en_retard', resp.data)

    def test_role_limite_refuse(self):
        user = make_user(self.company, 'mrp-tb-normal', role='normal')
        resp = auth(user).get('/api/django/mrp/tableau-bord/')
        self.assertEqual(resp.status_code, 403)

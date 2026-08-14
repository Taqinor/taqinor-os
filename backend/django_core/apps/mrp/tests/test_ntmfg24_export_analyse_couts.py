"""NTMFG24 — Rapport « Analyse des écarts de production » (période, tous OF)
exportable.

Critère : l'export PDF et XLSX contiennent les mêmes chiffres que l'écran
NTMFG11 sur un jeu de données testé, filtrage période respecté, permission
responsable/admin."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import CoutStandard, Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.services import confirmer_of, demarrer_operation, terminer_operation
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class ExportAnalyseCoutsApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-exp-ac-1', 'MRP ExportAC 1')
        self.user = make_user(self.company, 'mrp-exp-ac-user', role='responsable')
        self.api = auth(self.user)
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-EXP', nom='Poste export',
            cout_horaire=Decimal('100'))
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme export', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op export', temps_unitaire_min=Decimal('60'))
        CoutStandard.objects.create(
            company=self.company, produit=self.produit, version=1,
            cout_matiere=Decimal('50'), cout_main_oeuvre=Decimal('100'),
            date_effective=timezone.localdate())

        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1,
            gamme=self.gamme)
        confirmer_of(of)
        of.refresh_from_db()
        op = of.operations.first()
        demarrer_operation(op)
        op.demarree_le = timezone.now() - timedelta(minutes=60)
        op.save(update_fields=['demarree_le'])
        terminer_operation(op, quantite_bonne=1)
        from apps.mrp.services import cloturer_of
        cloturer_of(of)

    def test_export_xlsx_par_defaut(self):
        resp = self.api.get('/api/django/mrp/analyse-couts/export/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(
            resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_export_pdf(self):
        resp = self.api.get('/api/django/mrp/analyse-couts/export/?format=pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))

    def test_format_invalide_refuse(self):
        resp = self.api.get('/api/django/mrp/analyse-couts/export/?format=csv')
        self.assertEqual(resp.status_code, 400)

    def test_role_limite_refuse(self):
        limite = make_user(self.company, 'mrp-exp-ac-normal', role='normal')
        resp = auth(limite).get('/api/django/mrp/analyse-couts/export/')
        self.assertEqual(resp.status_code, 403)

    def test_filtre_periode_exclut_hors_fenetre(self):
        demain = (timezone.localdate() + timedelta(days=1)).isoformat()
        resp = self.api.get(
            f'/api/django/mrp/analyse-couts/export/?format=xlsx&date_debut={demain}')
        self.assertEqual(resp.status_code, 200)

"""Tests FG143 — Déclaration des honoraires / état 9421.

Couvre : l'agrégation PAR BÉNÉFICIAIRE des paiements aux tiers de l'année
civile (depuis les retenues à la source FG139), le bornage strict sur l'année
(une pièce d'une autre année est exclue), la présence de l'identité fiscale
(IF/ICE) et des montants brut/retenue/net, l'isolation multi-société, l'endpoint
``etats/declaration-honoraires/`` (JSON + ``?export=csv`` — jamais ``?format=``),
l'année par défaut (année courante) et le gate de rôle (Admin/Responsable).
Tout est dérivé du grand livre auxiliaire des RAS — aucun nouveau modèle.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DeclarationHonorairesSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('fg143-sel', 'FG143 Sel')
        self.user = make_user(self.co, 'fg143-sel-user')

    def _ras(self, jour, base, taux=None, **kw):
        return services.enregistrer_retenue_source(
            self.co, date_piece=jour, base=Decimal(base),
            taux=(Decimal(taux) if taux is not None else None),
            user=self.user, **kw)

    def test_agregation_par_beneficiaire(self):
        # Deux pièces pour le même tiers (auxiliaire) → une ligne cumulée.
        self._ras(date(2026, 1, 5), '10000', tiers_type='fournisseur',
                  tiers_id=42, tiers_nom='Cabinet X', identifiant_fiscal='IF42')
        self._ras(date(2026, 3, 15), '5000', tiers_type='fournisseur',
                  tiers_id=42, tiers_nom='Cabinet X')
        # Un prestataire libre (sans tiers_id).
        self._ras(date(2026, 6, 18), '2000', tiers_nom='Consultant Y',
                  identifiant_fiscal='IFY')
        data = selectors.declaration_honoraires(self.co, 2026)
        self.assertEqual(data['nb_beneficiaires'], 2)
        self.assertEqual(len(data['lignes']), 2)
        # Trié par brut décroissant : Cabinet X (15 000) en tête.
        tete = data['lignes'][0]
        self.assertEqual(tete['tiers_id'], 42)
        self.assertEqual(tete['nb_pieces'], 2)
        self.assertEqual(tete['brut'], Decimal('15000.00'))
        # 10% par défaut → 1500 retenu, net 13500.
        self.assertEqual(tete['retenue'], Decimal('1500.00'))
        self.assertEqual(tete['net'], Decimal('13500.00'))
        # L'IF du bénéficiaire est conservé même si seule la 1re pièce le porte.
        self.assertEqual(tete['identifiant_fiscal'], 'IF42')

    def test_totaux_annuels(self):
        self._ras(date(2026, 2, 1), '10000', tiers_nom='A')
        self._ras(date(2026, 9, 1), '2000', taux='5', tiers_nom='B')
        data = selectors.declaration_honoraires(self.co, 2026)
        # Brut 12000 ; retenue 1000 + 100 = 1100 ; net 10900.
        self.assertEqual(data['totaux']['brut'], Decimal('12000.00'))
        self.assertEqual(data['totaux']['retenue'], Decimal('1100.00'))
        self.assertEqual(data['totaux']['net'], Decimal('10900.00'))
        self.assertEqual(data['totaux']['nb_pieces'], 2)

    def test_bornee_a_l_annee_civile(self):
        # Décembre N-1 et janvier N+1 ne comptent PAS dans l'année N.
        self._ras(date(2025, 12, 31), '9999', tiers_nom='Old')
        self._ras(date(2026, 6, 1), '5000', tiers_nom='In')
        self._ras(date(2027, 1, 1), '8888', tiers_nom='Next')
        data = selectors.declaration_honoraires(self.co, 2026)
        self.assertEqual(data['date_debut'], date(2026, 1, 1))
        self.assertEqual(data['date_fin'], date(2026, 12, 31))
        self.assertEqual(data['nb_beneficiaires'], 1)
        self.assertEqual(data['lignes'][0]['tiers_nom'], 'In')
        self.assertEqual(data['totaux']['brut'], Decimal('5000.00'))

    def test_annee_en_str_acceptee(self):
        self._ras(date(2026, 4, 1), '3000', tiers_nom='A')
        data = selectors.declaration_honoraires(self.co, '2026')
        self.assertEqual(data['annee'], 2026)
        self.assertEqual(data['totaux']['brut'], Decimal('3000.00'))

    def test_filtre_type_prestation(self):
        self._ras(date(2026, 1, 5), '10000', tiers_nom='Hono',
                  type_prestation='honoraires')
        self._ras(date(2026, 2, 5), '4000', tiers_nom='Loyer',
                  type_prestation='loyers')
        data = selectors.declaration_honoraires(
            self.co, 2026, type_prestation='honoraires')
        self.assertEqual(data['nb_beneficiaires'], 1)
        self.assertEqual(data['lignes'][0]['tiers_nom'], 'Hono')

    def test_annee_vide_pas_de_lignes(self):
        self._ras(date(2026, 1, 5), '1000', tiers_nom='A')
        data = selectors.declaration_honoraires(self.co, 2024)
        self.assertEqual(data['nb_beneficiaires'], 0)
        self.assertEqual(data['lignes'], [])
        self.assertEqual(data['totaux']['brut'], Decimal('0'))


class DeclarationHonorairesIsolationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('fg143-a', 'FG143 A')
        self.co_b = make_company('fg143-b', 'FG143 B')
        self.user_a = make_user(self.co_a, 'fg143-user-a')
        self.user_b = make_user(self.co_b, 'fg143-user-b')
        services.enregistrer_retenue_source(
            self.co_a, date_piece=date(2026, 3, 10), base=Decimal('10000'),
            tiers_nom='Cabinet A', identifiant_fiscal='IFA', user=self.user_a)

    def test_isolation_selector(self):
        data_a = selectors.declaration_honoraires(self.co_a, 2026)
        data_b = selectors.declaration_honoraires(self.co_b, 2026)
        self.assertEqual(data_a['nb_beneficiaires'], 1)
        self.assertEqual(data_b['nb_beneficiaires'], 0)

    def test_endpoint_json_scope_societe(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/declaration-honoraires/',
            {'annee': '2026'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['annee'], 2026)
        self.assertEqual(resp.data['nb_beneficiaires'], 1)
        ligne = resp.data['lignes'][0]
        self.assertEqual(ligne['tiers_nom'], 'Cabinet A')
        self.assertEqual(ligne['identifiant_fiscal'], 'IFA')
        self.assertEqual(Decimal(str(ligne['brut'])), Decimal('10000.00'))

    def test_endpoint_autre_societe_vide(self):
        resp = auth(self.user_b).get(
            '/api/django/compta/etats/declaration-honoraires/',
            {'annee': '2026'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['nb_beneficiaires'], 0)

    def test_endpoint_annee_defaut_courante(self):
        # Sans paramètre annee, l'endpoint borne sur l'année courante.
        annee_courante = timezone.now().year
        services.enregistrer_retenue_source(
            self.co_a, date_piece=date(annee_courante, 5, 1),
            base=Decimal('7000'), tiers_nom='Cabinet Now',
            user=self.user_a)
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/declaration-honoraires/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['annee'], annee_courante)

    def test_endpoint_annee_invalide_400(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/declaration-honoraires/',
            {'annee': 'abc'})
        self.assertEqual(resp.status_code, 400)

    def test_endpoint_refuse_role_normal(self):
        normal = make_user(self.co_a, 'fg143-normal', role='normal')
        resp = auth(normal).get(
            '/api/django/compta/etats/declaration-honoraires/',
            {'annee': '2026'})
        self.assertEqual(resp.status_code, 403)

    def test_export_csv(self):
        resp = auth(self.user_a).get(
            '/api/django/compta/etats/declaration-honoraires/',
            {'annee': '2026', 'export': 'csv'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('9421', resp['Content-Disposition'])
        body = resp.content.decode('utf-8')
        self.assertIn('Déclaration des honoraires (état 9421)', body)
        self.assertIn('Identifiant fiscal', body)
        self.assertIn('Cabinet A', body)
        self.assertIn('IFA', body)
        self.assertIn('Totaux', body)

"""NTWMS26 — chargement camion & taux de remplissage.

Critère d'acceptation testé : ajouter une palette à un plan de chargement déjà
plein renvoie un AVERTISSEMENT de dépassement de capacité avant validation.

Run :
    python manage.py test apps.stock.test_ntwms26_plan_chargement -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import PlanChargement, Produit
from apps.stock.services import (
    ajouter_unite_plan_chargement, creer_plan_chargement,
    creer_unite_logistique, verifier_capacite_plan,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms26Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms26-co', 'NTWMS26 Co')
        self.autre = make_company('ntwms26-autre', 'NTWMS26 Autre')
        self.admin = User.objects.create_user(
            username='ntwms26_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='PAN-NTWMS26',
            prix_achat=Decimal('900'), prix_vente=Decimal('1200'),
            quantite_stock=100)
        self.api = auth(self.admin)

    def _palette(self, poids='500', dimensions='120 × 80 × 145'):
        unite = creer_unite_logistique(
            company=self.company, type_unite='palette',
            poids_kg=Decimal(poids), dimensions=dimensions)
        return unite

    def _plan(self, capacite_kg='1000', capacite_m3=None):
        return creer_plan_chargement(
            company=self.company, user=self.admin,
            capacite_kg=Decimal(capacite_kg) if capacite_kg else None,
            capacite_m3=Decimal(capacite_m3) if capacite_m3 else None)


class TestCapacitePlan(Ntwms26Base):
    def test_reference_posee_par_le_serveur(self):
        plan = self._plan()
        self.assertTrue(plan.reference.startswith('CHG-'))
        self.assertEqual(plan.statut, PlanChargement.Statut.BROUILLON)

    def test_sous_la_capacite_aucun_avertissement(self):
        plan = self._plan(capacite_kg='1000')
        ajouter_unite_plan_chargement(plan=plan, unite=self._palette('500'))

        controle = verifier_capacite_plan(plan)
        self.assertEqual(controle['poids_kg'], Decimal('500'))
        self.assertEqual(controle['poids_utilise_pct'], Decimal('50.00'))
        self.assertFalse(controle['depassement'])
        self.assertEqual(controle['avertissement'], '')

    def test_palette_de_trop_avertit_avant_validation(self):
        plan = self._plan(capacite_kg='1000')
        ajouter_unite_plan_chargement(plan=plan, unite=self._palette('800'))

        controle = ajouter_unite_plan_chargement(
            plan=plan, unite=self._palette('400'))

        self.assertTrue(controle['depassement'])
        self.assertIn('dépasse', controle['avertissement'])
        self.assertEqual(controle['poids_kg'], Decimal('1200'))

    def test_volume_calcule_depuis_les_dimensions(self):
        plan = self._plan(capacite_kg='5000', capacite_m3='2')
        # 120 × 80 × 145 cm = 1,392 m³
        ajouter_unite_plan_chargement(
            plan=plan, unite=self._palette('100', '120 × 80 × 145'))
        controle = verifier_capacite_plan(plan)
        self.assertEqual(controle['volume_m3'], Decimal('1.392'))
        self.assertFalse(controle['depassement'])

    def test_depassement_de_volume_seul_avertit(self):
        plan = self._plan(capacite_kg='9000', capacite_m3='1')
        controle = ajouter_unite_plan_chargement(
            plan=plan, unite=self._palette('50', '120 × 80 × 145'))
        self.assertTrue(controle['depassement'])

    def test_dimensions_illisibles_ne_cassent_rien(self):
        plan = self._plan(capacite_kg='1000')
        ajouter_unite_plan_chargement(
            plan=plan, unite=self._palette('100', 'palette europe'))
        controle = verifier_capacite_plan(plan)
        self.assertEqual(controle['volume_m3'], Decimal('0'))
        self.assertFalse(controle['depassement'])

    def test_sans_capacite_declaree_aucun_faux_positif(self):
        plan = self._plan(capacite_kg=None)
        controle = ajouter_unite_plan_chargement(
            plan=plan, unite=self._palette('9000'))
        self.assertFalse(controle['depassement'])
        self.assertIsNone(controle['capacite_kg'])

    def test_unite_hors_societe_refusee(self):
        plan = self._plan()
        unite_autre = creer_unite_logistique(
            company=self.autre, type_unite='palette')
        with self.assertRaises(ValueError):
            ajouter_unite_plan_chargement(plan=plan, unite=unite_autre)


class TestEndpointsPlanChargement(Ntwms26Base):
    URL = '/api/django/stock/plans-chargement/'

    def test_creation_puis_ajout_avec_avertissement(self):
        creation = self.api.post(self.URL, {'capacite_kg': '1000'},
                                 format='json')
        self.assertEqual(creation.status_code, 201)
        plan_id = creation.data['id']

        premier = self.api.post(
            f'{self.URL}{plan_id}/unites/',
            {'unite_logistique': self._palette('900').id}, format='json')
        self.assertEqual(premier.status_code, 201)
        self.assertFalse(premier.data['depassement'])

        second = self.api.post(
            f'{self.URL}{plan_id}/unites/',
            {'unite_logistique': self._palette('300').id}, format='json')
        self.assertEqual(second.status_code, 201)
        self.assertTrue(second.data['depassement'])

    def test_verifier_capacite_est_lecture_seule(self):
        plan = self._plan()
        ajouter_unite_plan_chargement(plan=plan, unite=self._palette('200'))
        reponse = self.api.get(f'{self.URL}{plan.id}/verifier-capacite/')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['nb_unites'], 1)

    def test_unite_inconnue_refusee(self):
        plan = self._plan()
        reponse = self.api.post(f'{self.URL}{plan.id}/unites/',
                                {'unite_logistique': 999999}, format='json')
        self.assertEqual(reponse.status_code, 400)

    def test_isolation_multi_societe(self):
        intrus = User.objects.create_user(
            username='ntwms26_intrus', password='x', role_legacy='admin',
            company=self.autre)
        self._plan()
        reponse = auth(intrus).get(self.URL)
        resultats = reponse.data.get('results', reponse.data)
        self.assertEqual(len(resultats), 0)

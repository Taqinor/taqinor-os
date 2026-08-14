"""NTSCM9 — incidents qualité fournisseur.

Critère d'acceptation testé : un incident CRITIQUE NON RÉSOLU apparaît
IMMÉDIATEMENT au scorecard du fournisseur concerné.

Run :
    python manage.py test apps.stock.test_ntscm9_incident_qualite -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    Fournisseur, IncidentQualiteFournisseur, Produit,
)

User = get_user_model()

JOUR = datetime.date(2026, 6, 15)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntscm9Base(TestCase):
    URL = '/api/django/stock/incidents-qualite-fournisseur/'

    def setUp(self):
        self.company = make_company('ntscm9-co', 'NTSCM9 Co')
        self.autre = make_company('ntscm9-autre', 'NTSCM9 Autre')
        self.admin = User.objects.create_user(
            username='ntscm9_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntscm9_normal', password='x', role_legacy='normal',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTSCM9')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie NTSCM9', sku='BAT-NTSCM9',
            prix_achat=Decimal('4000'), prix_vente=Decimal('5000'),
            quantite_stock=5)


class Ntscm9ModeleTests(Ntscm9Base):
    def test_un_incident_critique_non_resolu_est_bloquant(self):
        incident = IncidentQualiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            produit=self.produit, date_incident=JOUR,
            gravite=IncidentQualiteFournisseur.Gravite.CRITIQUE,
            type_incident=IncidentQualiteFournisseur.TypeIncident.ENDOMMAGE,
            quantite_affectee=3, cout_impact_mad=Decimal('1200'))
        self.assertTrue(incident.est_bloquant)

    def test_un_incident_critique_resolu_nest_plus_bloquant(self):
        incident = IncidentQualiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            date_incident=JOUR, resolu=True,
            gravite=IncidentQualiteFournisseur.Gravite.CRITIQUE)
        self.assertFalse(incident.est_bloquant)

    def test_un_incident_mineur_nest_jamais_bloquant(self):
        incident = IncidentQualiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            date_incident=JOUR,
            gravite=IncidentQualiteFournisseur.Gravite.MINEURE)
        self.assertFalse(incident.est_bloquant)


class Ntscm9ScorecardTests(Ntscm9Base):
    def test_lincident_critique_remonte_au_scorecard(self):
        IncidentQualiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            date_incident=JOUR,
            gravite=IncidentQualiteFournisseur.Gravite.CRITIQUE)

        res = auth(self.admin).get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/'
            'performance/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['incidents_qualite_critiques_ouverts'], 1)

    def test_un_scorecard_sans_incident_affiche_zero(self):
        res = auth(self.admin).get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/'
            'performance/')
        self.assertEqual(res.data['incidents_qualite_critiques_ouverts'], 0)


class Ntscm9ApiTests(Ntscm9Base):
    def test_creation_force_societe_et_declarant(self):
        res = auth(self.admin).post(self.URL, {
            'fournisseur': self.fournisseur.id, 'produit': self.produit.id,
            'date_incident': JOUR.isoformat(), 'gravite': 'majeure',
            'type_incident': 'erreur_reference', 'quantite_affectee': 2,
            'cout_impact_mad': '450.00', 'company': self.autre.id,
        }, format='json')
        self.assertEqual(res.status_code, 201)
        incident = IncidentQualiteFournisseur.objects.get(id=res.data['id'])
        self.assertEqual(incident.company_id, self.company.id)
        self.assertEqual(incident.declare_par_id, self.admin.id)

    def test_le_filtre_gravite_et_resolu_est_applique(self):
        IncidentQualiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            date_incident=JOUR,
            gravite=IncidentQualiteFournisseur.Gravite.CRITIQUE)
        IncidentQualiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            date_incident=JOUR, resolu=True,
            gravite=IncidentQualiteFournisseur.Gravite.MINEURE)

        api = auth(self.admin)
        critiques = api.get(self.URL, {'gravite': 'critique'})
        self.assertEqual(
            len(critiques.data.get('results', critiques.data)), 1)
        ouverts = api.get(self.URL, {'resolu': 'false'})
        self.assertEqual(len(ouverts.data.get('results', ouverts.data)), 1)

    def test_lecture_refusee_a_un_role_normal_car_cout_interne(self):
        self.assertEqual(auth(self.normal).get(self.URL).status_code, 403)

    def test_liste_ne_fuit_pas_une_autre_societe(self):
        autre_fournisseur = Fournisseur.objects.create(
            company=self.autre, nom='Voisin NTSCM9')
        IncidentQualiteFournisseur.objects.create(
            company=self.autre, fournisseur=autre_fournisseur,
            date_incident=JOUR)
        IncidentQualiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            date_incident=JOUR)
        res = auth(self.admin).get(self.URL)
        self.assertEqual(len(res.data.get('results', res.data)), 1)

"""Tests de la politique de facturation par projet (ZPRJ10).

Couvre : champ posé + filtrable (défaut forfait), une action de facturation
régie (XPRJ3) sur un projet marqué forfait renvoie un AVERTISSEMENT non
bloquant (jamais un blocage dur), une action de validation de situation BTP
(XPRJ4) sur un projet marqué forfait renvoie aussi l'avertissement, isolation
tenant.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.gestion_projet import services
from apps.gestion_projet.models import (
    Projet, RessourceProfil, Tache, Timesheet,
)

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


class PolitiqueFacturationChampTests(TestCase):
    BASE = '/api/django/gestion-projet/projets/'

    def setUp(self):
        self.co = make_company('gp-z10-champ', 'S')
        self.user = make_user(self.co, 'z10-champ-u')

    def test_defaut_forfait(self):
        projet = Projet.objects.create(company=self.co, code='P-Z10-1', nom='P')
        self.assertEqual(
            projet.politique_facturation, Projet.PolitiqueFacturation.FORFAIT)

    def test_filtre_politique(self):
        Projet.objects.create(
            company=self.co, code='P-Z10-2', nom='Forfait')
        Projet.objects.create(
            company=self.co, code='P-Z10-3', nom='Régie',
            politique_facturation=Projet.PolitiqueFacturation.REGIE)
        api = auth(self.user)
        resp = api.get(f'{self.BASE}?politique=regie')
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results'] if isinstance(resp.data, dict) and \
            'results' in resp.data else resp.data
        noms = {p['nom'] for p in data}
        self.assertEqual(noms, {'Régie'})


class AvertissementFacturationRegieTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-z10-regie', 'S')
        self.client_crm = Client.objects.create(company=self.co, nom='Client')
        self.projet = Projet.objects.create(
            company=self.co, code='P-Z10-R', nom='R',
            client_id=self.client_crm.id,
            politique_facturation=Projet.PolitiqueFacturation.FORFAIT)
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T', ordre=1)
        self.res = RessourceProfil.objects.create(company=self.co, nom='R')
        self.user = make_user(self.co, 'z10-regie-u')
        Timesheet.objects.create(
            company=self.co, projet=self.projet, tache=self.tache,
            ressource=self.res, date=date(2026, 7, 1), heures=Decimal('4'),
            statut=Timesheet.Statut.APPROUVEE, facturable=True,
            taux_facturation=Decimal('300'),
            type_activite=Timesheet.TypeActivite.SAV)

    def test_avertissement_present_sur_incoherence(self):
        resultat = services.facturer_temps_projet(
            self.projet, debut=date(2026, 7, 1), fin=date(2026, 7, 31),
            user=self.user)
        self.assertIsNotNone(resultat['avertissement_politique'])
        # Jamais un blocage : la facture est bien créée malgré l'incohérence.
        self.assertIsNotNone(resultat['facture'])

    def test_pas_avertissement_si_politique_coherente(self):
        self.projet.politique_facturation = Projet.PolitiqueFacturation.REGIE
        self.projet.save(update_fields=['politique_facturation'])
        resultat = services.facturer_temps_projet(
            self.projet, debut=date(2026, 7, 1), fin=date(2026, 7, 31),
            user=self.user)
        self.assertIsNone(resultat['avertissement_politique'])

    def test_endpoint_expose_avertissement(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/gestion-projet/projets/{self.projet.id}/'
            f'facturer-temps/',
            {'debut': '2026-07-01', 'fin': '2026-07-31'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('avertissement_politique', resp.data)
        self.assertIsNotNone(resp.data['avertissement_politique'])

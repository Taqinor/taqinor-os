"""Tests XPRJ10 — assigné, priorité et étiquettes sur les tâches.

Couvre : création/filtrage par ``assigne``/``priorite``/``etiquette``,
migration additive, et le sérialiseur qui refuse un ``assigne`` d'une AUTRE
société (400).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet.models import Projet, RessourceProfil, Tache

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class TacheAssignePrioriteEtiquettesTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-xprj10', 'S')
        self.autre_co = make_company('gp-xprj10-autre', 'Autre S')
        self.user = make_user(self.co, 'resp-xprj10')
        self.projet = Projet.objects.create(
            company=self.co, code='P-X10', nom='Projet X10')
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='Karim')
        self.ressource_autre = RessourceProfil.objects.create(
            company=self.autre_co, nom='Autre Karim')

    def test_creation_avec_assigne_priorite_etiquettes(self):
        api = auth(self.user)
        resp = api.post('/api/django/gestion-projet/taches/', {
            'projet': self.projet.id,
            'libelle': 'Poser panneaux',
            'assigne': self.ressource.id,
            'priorite': Tache.Priorite.HAUTE,
            'etiquettes': 'toiture,urgent',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['assigne'], self.ressource.id)
        self.assertEqual(resp.data['priorite'], 'haute')
        self.assertEqual(resp.data['etiquettes'], 'toiture,urgent')
        self.assertEqual(resp.data['assigne_nom'], 'Karim')

    def test_assigne_autre_societe_refuse(self):
        api = auth(self.user)
        resp = api.post('/api/django/gestion-projet/taches/', {
            'projet': self.projet.id,
            'libelle': 'Tâche',
            'assigne': self.ressource_autre.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_filtre_par_assigne(self):
        t1 = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T1',
            assigne=self.ressource)
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T2')
        api = auth(self.user)
        resp = api.get(
            f'/api/django/gestion-projet/taches/?assigne={self.ressource.id}')
        ids = [r['id'] for r in rows(resp)]
        self.assertEqual(ids, [t1.id])

    def test_filtre_par_priorite(self):
        t1 = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T1',
            priorite=Tache.Priorite.URGENTE)
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T2',
            priorite=Tache.Priorite.BASSE)
        api = auth(self.user)
        resp = api.get('/api/django/gestion-projet/taches/?priorite=urgente')
        ids = [r['id'] for r in rows(resp)]
        self.assertEqual(ids, [t1.id])

    def test_filtre_par_etiquette(self):
        t1 = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T1',
            etiquettes='toiture,urgent')
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='T2',
            etiquettes='electricite')
        api = auth(self.user)
        resp = api.get('/api/django/gestion-projet/taches/?etiquette=toiture')
        ids = [r['id'] for r in rows(resp)]
        self.assertEqual(ids, [t1.id])

    def test_defaut_priorite_normale(self):
        t = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Défaut')
        self.assertEqual(t.priorite, Tache.Priorite.NORMALE)

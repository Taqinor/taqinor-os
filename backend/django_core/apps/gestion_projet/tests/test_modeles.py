"""Tests des templates de projet par type d'installation (PROJ35).

Un ``ModeleProjet`` porte des ``ModeleTache`` (tâches-types par phase) ;
l'instanciation crée les phases nécessaires + les tâches sur un projet (additif,
n'écrase rien). Couvre : service ``instancier_modele`` (phases + tâches créées,
charge copiée) ; refus cross-société ; endpoint ``instancier`` ; refus projet
hors société (400) ; scoping ; accès Administrateur/Responsable (403).
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.gestion_projet import services
from apps.gestion_projet.models import (
    ModeleProjet,
    ModeleTache,
    PhaseProjet,
    Projet,
    Tache,
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


class ModeleServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-mod-svc', 'S')
        self.modele = ModeleProjet.objects.create(
            company=self.co, nom='Résidentiel standard',
            type_installation=ModeleProjet.TypeInstallation.RESIDENTIEL)
        ModeleTache.objects.create(
            company=self.co, modele=self.modele,
            type_phase=PhaseProjet.TypePhase.ETUDE, libelle='Visite technique',
            ordre=1, charge_estimee=Decimal('1'))
        ModeleTache.objects.create(
            company=self.co, modele=self.modele,
            type_phase=PhaseProjet.TypePhase.POSE, libelle='Pose panneaux',
            ordre=2, charge_estimee=Decimal('3'))

    def test_instancier_cree_phases_et_taches(self):
        projet = Projet.objects.create(
            company=self.co, code='P-MOD', nom='P')
        creees = services.instancier_modele(self.modele, projet)
        self.assertEqual(len(creees), 2)
        # Deux phases créées (étude, pose).
        types = set(projet.phases.values_list('type_phase', flat=True))
        self.assertEqual(types, {'etude', 'pose'})
        # Tâches rattachées à leur phase, charge copiée.
        pose = Tache.objects.get(projet=projet, libelle='Pose panneaux')
        self.assertEqual(pose.charge_estimee, Decimal('3'))
        self.assertEqual(pose.phase.type_phase, 'pose')

    def test_instancier_additif_phase_existante(self):
        projet = Projet.objects.create(
            company=self.co, code='P-MOD2', nom='P')
        # Une phase étude préexiste : ne doit pas être dupliquée.
        PhaseProjet.objects.create(
            company=self.co, projet=projet,
            type_phase=PhaseProjet.TypePhase.ETUDE, libelle='Étude maison')
        services.instancier_modele(self.modele, projet)
        etudes = projet.phases.filter(type_phase='etude')
        self.assertEqual(etudes.count(), 1)
        # Le libellé existant est préservé (additif).
        self.assertEqual(etudes.first().libelle, 'Étude maison')

    def test_instancier_cross_societe_refuse(self):
        autre_co = make_company('gp-mod-other', 'O')
        projet = Projet.objects.create(
            company=autre_co, code='P-X', nom='X')
        with self.assertRaises(services.ModeleProjetError):
            services.instancier_modele(self.modele, projet)


class ModeleApiTests(TestCase):
    BASE = '/api/django/gestion-projet/modeles/'

    def setUp(self):
        self.co_a = make_company('gp-mod-a', 'A')
        self.co_b = make_company('gp-mod-b', 'B')
        self.user_a = make_user(self.co_a, 'mod-a')
        self.modele = ModeleProjet.objects.create(
            company=self.co_a, nom='M',
            type_installation=ModeleProjet.TypeInstallation.AGRICOLE)
        ModeleTache.objects.create(
            company=self.co_a, modele=self.modele,
            type_phase=PhaseProjet.TypePhase.ETUDE, libelle='T', ordre=1)
        self.projet = Projet.objects.create(
            company=self.co_a, code='P-A', nom='A')

    def test_instancier_endpoint(self):
        api = auth(self.user_a)
        resp = api.post(
            f'{self.BASE}{self.modele.id}/instancier/',
            {'projet': self.projet.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(self.projet.taches.count(), 1)

    def test_instancier_projet_hors_societe_400(self):
        autre = Projet.objects.create(company=self.co_b, code='P-B', nom='B')
        api = auth(self.user_a)
        resp = api.post(
            f'{self.BASE}{self.modele.id}/instancier/',
            {'projet': autre.id}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_creation_company_serveur(self):
        api = auth(self.user_a)
        resp = api.post(self.BASE, {
            'nom': 'Nouveau modèle', 'type_installation': 'industriel',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        modele = ModeleProjet.objects.get(id=resp.data['id'])
        self.assertEqual(modele.company_id, self.co_a.id)

    def test_role_normal_interdit(self):
        normal = make_user(self.co_a, 'mod-normal', role='normal')
        api = auth(normal)
        resp = api.get(self.BASE)
        self.assertEqual(resp.status_code, 403)

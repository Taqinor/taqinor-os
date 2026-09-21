"""XQHS24 — Gestion du changement (MOC léger).

Couvre :
  * un changement suit son cycle avec approbation AVANT déploiement ;
  * un changement temporaire expire et relance ;
  * les actions liées (CAPA) se suivent ;
  * le scoping société.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import DemandeChangement
from apps.qhse.services import (
    creer_capa_mise_en_oeuvre_moc, demandes_changement_a_reverser,
    relancer_demandes_changement, transitionner_demande_changement,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_demande(company, **kwargs):
    defaults = dict(company=company, description='Nouveau fournisseur onduleurs')
    defaults.update(kwargs)
    return DemandeChangement.objects.create(**defaults)


class CycleDeVieTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs24-cycle', 'Xqhs24 Cycle')
        self.user = make_user(self.company, 'xqhs24-approbateur')

    def test_transitions_valides_brouillon_vers_deploye(self):
        demande = make_demande(self.company)
        demande = transitionner_demande_changement(
            demande, DemandeChangement.Statut.EN_REVUE)
        self.assertEqual(demande.statut, DemandeChangement.Statut.EN_REVUE)

        demande = transitionner_demande_changement(
            demande, DemandeChangement.Statut.APPROUVE,
            approbateur=self.user)
        self.assertEqual(demande.statut, DemandeChangement.Statut.APPROUVE)
        self.assertEqual(demande.approbateur_id, self.user.pk)
        self.assertIsNotNone(demande.date_approbation)

        demande = transitionner_demande_changement(
            demande, DemandeChangement.Statut.DEPLOYE)
        self.assertEqual(demande.statut, DemandeChangement.Statut.DEPLOYE)

    def test_deploiement_sans_approbation_bloque(self):
        demande = make_demande(
            self.company, statut=DemandeChangement.Statut.EN_REVUE)
        with self.assertRaises(ValueError):
            transitionner_demande_changement(
                demande, DemandeChangement.Statut.DEPLOYE)

    def test_brouillon_direct_vers_deploye_bloque(self):
        demande = make_demande(self.company)
        with self.assertRaises(ValueError):
            transitionner_demande_changement(
                demande, DemandeChangement.Statut.DEPLOYE)

    def test_clos_ne_peut_plus_transitionner(self):
        demande = make_demande(
            self.company, statut=DemandeChangement.Statut.CLOS)
        with self.assertRaises(ValueError):
            transitionner_demande_changement(
                demande, DemandeChangement.Statut.EN_REVUE)


class ChangementTemporaireTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs24-temp', 'Xqhs24 Temp')

    def test_temporaire_expire_est_du(self):
        demande = make_demande(
            self.company, est_temporaire=True,
            date_expiration=timezone.localdate() - timedelta(days=1),
            statut=DemandeChangement.Statut.DEPLOYE)
        dus = demandes_changement_a_reverser(self.company)
        self.assertIn(demande, dus)

    def test_temporaire_non_expire_pas_du(self):
        demande = make_demande(
            self.company, est_temporaire=True,
            date_expiration=timezone.localdate() + timedelta(days=10),
            statut=DemandeChangement.Statut.DEPLOYE)
        dus = demandes_changement_a_reverser(self.company)
        self.assertNotIn(demande, dus)

    def test_permanent_jamais_du(self):
        make_demande(
            self.company, est_temporaire=False,
            statut=DemandeChangement.Statut.DEPLOYE)
        dus = demandes_changement_a_reverser(self.company)
        self.assertEqual(len(dus), 0)

    def test_clos_nest_plus_du(self):
        make_demande(
            self.company, est_temporaire=True,
            date_expiration=timezone.localdate() - timedelta(days=1),
            statut=DemandeChangement.Statut.CLOS)
        dus = demandes_changement_a_reverser(self.company)
        self.assertEqual(len(dus), 0)

    def test_relance_ne_leve_pas(self):
        make_demande(
            self.company, est_temporaire=True,
            date_expiration=timezone.localdate() - timedelta(days=1),
            statut=DemandeChangement.Statut.DEPLOYE)
        relances = relancer_demandes_changement(self.company)
        self.assertEqual(len(relances), 1)


class CapaMiseEnOeuvreTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs24-capa', 'Xqhs24 Capa')

    def test_creer_capa_lie_demande(self):
        demande = make_demande(self.company)
        capa = creer_capa_mise_en_oeuvre_moc(
            demande, description='Former les équipes au nouveau matériel')
        self.assertEqual(demande.capa_liees.count(), 1)
        self.assertEqual(demande.capa_liees.first().capa_id, capa.pk)

    def test_plusieurs_capa_possibles(self):
        demande = make_demande(self.company)
        creer_capa_mise_en_oeuvre_moc(demande, description='Action 1')
        creer_capa_mise_en_oeuvre_moc(demande, description='Action 2')
        self.assertEqual(demande.capa_liees.count(), 2)


class DemandeChangementApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs24-api', 'Xqhs24 Api')
        self.user = make_user(self.company, 'xqhs24-user')

    def test_create_pose_company_serveur(self):
        resp = auth(self.user).post(
            '/api/django/qhse/demandes-changement/',
            {'type_changement': 'equipement',
             'description': 'Nouveau type de structure'}, format='json')
        self.assertEqual(resp.status_code, 201)
        demande = DemandeChangement.objects.get(id=resp.data['id'])
        self.assertEqual(demande.company_id, self.company.pk)

    def test_transitionner_action(self):
        demande = make_demande(self.company)
        resp = auth(self.user).post(
            f'/api/django/qhse/demandes-changement/{demande.pk}/transitionner/',
            {'statut': 'en_revue'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['statut'], 'en_revue')

    def test_deploiement_sans_approbation_400(self):
        demande = make_demande(
            self.company, statut=DemandeChangement.Statut.EN_REVUE)
        resp = auth(self.user).post(
            f'/api/django/qhse/demandes-changement/{demande.pk}/transitionner/',
            {'statut': 'deploye'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_a_reverser_endpoint(self):
        make_demande(
            self.company, est_temporaire=True,
            date_expiration=timezone.localdate() - timedelta(days=1),
            statut=DemandeChangement.Statut.DEPLOYE)
        resp = auth(self.user).get(
            '/api/django/qhse/demandes-changement/a-reverser/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_isolation_societe(self):
        other_co = make_company('xqhs24-api-other', 'Xqhs24 Api Other')
        other_user = make_user(other_co, 'xqhs24-other-user')
        make_demande(self.company)
        resp = auth(other_user).get('/api/django/qhse/demandes-changement/')
        ids = [item['id'] for item in resp.data.get('results', resp.data)]
        self.assertEqual(len(ids), 0)

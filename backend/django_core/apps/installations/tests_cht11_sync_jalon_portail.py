"""CHT11 — Synchro automatique jalons internes → portail client.

Avant CHT11, ``JalonChantierPortail`` (portail) et ``JalonProjet`` (interne)
vivaient en DOUBLE SAISIE : rien ne propageait l'atteinte d'un jalon interne
vers la timeline visible du client. Ce module couvre le nouveau
``services.synchroniser_jalon_portail`` sur ses DEUX chemins : le PATCH
manuel (``JalonProjetViewSet.perform_update``, via l'API) et l'auto-atteinte
via ``changer_statut_chantier`` (``notifier_reception_solde_a_facturer`` à
RECEPTIONNE).

Run :
    python manage.py test apps.installations.tests_cht11_sync_jalon_portail -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, JalonProjet
from apps.installations.services import (
    notifier_reception_solde_a_facturer, synchroniser_jalon_portail,
)
from apps.portail.models import JalonChantierPortail
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'cht11-co-{n}', defaults={'nom': nom or f'CHT11 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'cht11-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='CHT11',
        email=f'cht11-{company.id}-{n}@example.invalid')


def make_installation(company, client, devis=None, annule=False):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CHT-CHT11-{n}', client=client,
        devis=devis, annule=annule)


class TestSynchroniserJalonPortailDirect(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.inst = make_installation(self.company, self.client_obj)

    def test_jalon_atteint_publie_une_ligne_portail(self):
        jalon = JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=JalonProjet.Phase.ETUDE, libelle='Étude', atteint=True)
        synchroniser_jalon_portail(jalon)
        ligne = JalonChantierPortail.objects.get(
            company=self.company, chantier=self.inst, cle_phase='etude')
        self.assertEqual(ligne.libelle, 'Étude')
        self.assertTrue(ligne.atteint)

    def test_republication_met_a_jour_sans_dupliquer(self):
        jalon = JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=JalonProjet.Phase.POSE, libelle='Pose', atteint=True)
        synchroniser_jalon_portail(jalon)
        jalon.libelle = 'Pose terminée'
        jalon.save(update_fields=['libelle'])
        synchroniser_jalon_portail(jalon)
        self.assertEqual(
            JalonChantierPortail.objects.filter(
                chantier=self.inst, cle_phase='pose').count(), 1)
        self.assertEqual(
            JalonChantierPortail.objects.get(
                chantier=self.inst, cle_phase='pose').libelle,
            'Pose terminée')

    def test_jalon_non_atteint_ne_publie_rien(self):
        jalon = JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=JalonProjet.Phase.APPRO, libelle='Appro', atteint=False)
        synchroniser_jalon_portail(jalon)
        self.assertFalse(
            JalonChantierPortail.objects.filter(chantier=self.inst).exists())

    def test_jalon_ad_hoc_sans_phase_ne_publie_rien(self):
        jalon = JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=None, libelle='Point ad hoc', atteint=True)
        synchroniser_jalon_portail(jalon)
        self.assertFalse(
            JalonChantierPortail.objects.filter(chantier=self.inst).exists())

    def test_chantier_annule_aucun_nouveau_jalon_publie(self):
        annule = make_installation(
            self.company, self.client_obj, annule=True)
        jalon = JalonProjet.objects.create(
            company=self.company, installation=annule,
            phase=JalonProjet.Phase.POSE, libelle='Pose', atteint=True)
        synchroniser_jalon_portail(jalon)
        self.assertFalse(
            JalonChantierPortail.objects.filter(chantier=annule).exists())

    def test_societe_sans_compte_portail_ne_leve_aucune_erreur(self):
        """Aucun ComptePortailClient pour ce client : l'email best-effort est
        simplement sauté, la publication portail elle-même reste posée."""
        jalon = JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=JalonProjet.Phase.MES, libelle='Mise en service',
            atteint=True)
        synchroniser_jalon_portail(jalon)  # ne lève rien
        self.assertTrue(
            JalonChantierPortail.objects.filter(
                chantier=self.inst, cle_phase='mes').exists())


class TestPatchManuelSynchronisePortail(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = make_user(self.company, role='admin')
        self.api = auth(self.admin)
        self.client_obj = make_client(self.company)
        self.inst = make_installation(self.company, self.client_obj)
        self.jalon = JalonProjet.objects.create(
            company=self.company, installation=self.inst,
            phase=JalonProjet.Phase.ETUDE, libelle='Étude', atteint=False)

    def test_patch_atteint_publie_le_jalon_au_portail(self):
        r = self.api.patch(
            f'{BASE}/jalons-projet/{self.jalon.id}/', {'atteint': True},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(
            JalonChantierPortail.objects.filter(
                chantier=self.inst, cle_phase='etude', atteint=True).exists())


class TestReceptionAutoSynchronisePortail(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-CHT11-{next(_seq)}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        self.inst = make_installation(
            self.company, self.client_obj, devis=self.devis)

    def test_reception_marque_le_jalon_atteint_et_publie_au_portail(self):
        notifier_reception_solde_a_facturer(self.inst, self.user)
        self.assertTrue(
            JalonChantierPortail.objects.filter(
                chantier=self.inst, cle_phase='reception',
                atteint=True).exists())

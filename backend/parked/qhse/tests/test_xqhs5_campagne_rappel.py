"""Tests XQHS5 — Campagne de rappel / containment par produit-lot-série.

Couvre :

* le peuplement des ``ElementRappel`` depuis le parc réel, lu UNIQUEMENT via
  ``sav.selectors`` (jamais un import de ``apps.sav.models``) ;
* l'idempotence du peuplement ;
* la notification des responsables ;
* la planification du remplacement via ``sav.services`` ;
* la clôture conditionnée à la vérification d'efficacité ;
* le scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.qhse.models import CampagneRappel, ElementRappel
from apps.qhse.services import (
    cloturer_campagne_rappel, notifier_elements_rappel,
    peupler_campagne_rappel, planifier_remplacement_element_rappel,
)
from apps.sav.models import Equipement
from apps.stock.models import Produit

User = get_user_model()

CAMPAGNES = '/api/django/qhse/campagnes-rappel/'
ELEMENTS = '/api/django/qhse/elements-rappel/'


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_produit(company, nom='Onduleur X'):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1000)


def make_installation(company, ref='CHT'):
    client = Client.objects.create(company=company, nom='Client Test')
    return Installation.objects.create(
        company=company, reference=f'{ref}-{company.id}', client=client)


def make_equipement(company, produit, installation, serie):
    return Equipement.objects.create(
        company=company, produit=produit, installation=installation,
        numero_serie=serie)


class PeuplerCampagneRappelTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs5-peuple', 'CoXqhs5Peuple')
        self.produit = make_produit(self.company)
        self.installation = make_installation(self.company)

    def test_peuple_depuis_le_parc(self):
        make_equipement(self.company, self.produit, self.installation, 'SN001')
        make_equipement(self.company, self.produit, self.installation, 'SN002')
        campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel onduleurs', produit=self.produit)
        crees = peupler_campagne_rappel(campagne)
        self.assertEqual(len(crees), 2)
        self.assertEqual(campagne.elements.count(), 2)

    def test_peuplement_idempotent(self):
        make_equipement(self.company, self.produit, self.installation, 'SN010')
        campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel', produit=self.produit)
        peupler_campagne_rappel(campagne)
        second = peupler_campagne_rappel(campagne)
        self.assertEqual(len(second), 0)
        self.assertEqual(campagne.elements.count(), 1)

    def test_filtre_plage_series(self):
        make_equipement(self.company, self.produit, self.installation, 'A001')
        make_equipement(self.company, self.produit, self.installation, 'B999')
        campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel bornée', produit=self.produit,
            serie_debut='A000', serie_fin='A999')
        crees = peupler_campagne_rappel(campagne)
        self.assertEqual(len(crees), 1)
        self.assertEqual(crees[0].numero_serie, 'A001')

    def test_isolation_societe(self):
        autre = make_company('co-xqhs5-peuple-autre', 'CoXqhs5PeupleAutre')
        make_equipement(self.company, self.produit, self.installation, 'SN020')
        campagne = CampagneRappel.objects.create(
            company=autre, titre='Rappel autre', produit=self.produit)
        crees = peupler_campagne_rappel(campagne)
        self.assertEqual(len(crees), 0)


class NotifierElementsRappelTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs5-notif', 'CoXqhs5Notif')
        self.produit = make_produit(self.company)
        self.installation = make_installation(self.company)
        self.responsable = make_user(self.company, 'resp-xqhs5-notif')

    def test_notifie_et_avance_statut(self):
        make_equipement(self.company, self.produit, self.installation, 'SN030')
        campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel', produit=self.produit,
            responsable=self.responsable)
        peupler_campagne_rappel(campagne)
        notifies = notifier_elements_rappel(campagne)
        self.assertEqual(len(notifies), 1)
        element = campagne.elements.first()
        self.assertEqual(element.statut, ElementRappel.Statut.NOTIFIE)
        self.assertIsNotNone(element.notifie_le)

    def test_sans_responsable_ne_notifie_rien(self):
        make_equipement(self.company, self.produit, self.installation, 'SN031')
        campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel sans resp', produit=self.produit)
        peupler_campagne_rappel(campagne)
        notifies = notifier_elements_rappel(campagne)
        self.assertEqual(len(notifies), 0)


class PlanifierRemplacementTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs5-plan', 'CoXqhs5Plan')
        self.produit = make_produit(self.company)
        self.installation = make_installation(self.company)
        self.user = make_user(self.company, 'resp-xqhs5-plan')

    def test_planifie_via_sav_services(self):
        eq = make_equipement(self.company, self.produit, self.installation, 'SN040')
        campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel', produit=self.produit)
        peupler_campagne_rappel(campagne)
        element = campagne.elements.get(equipement_id=eq.id)
        planifier_remplacement_element_rappel(
            element, client=self.installation.client, created_by=self.user)
        element.refresh_from_db()
        self.assertEqual(element.statut, ElementRappel.Statut.PLANIFIE)
        self.assertIsNotNone(element.ticket_sav_id)


class CloturerCampagneRappelTests(TestCase):
    def setUp(self):
        self.company = make_company('co-xqhs5-clot', 'CoXqhs5Clot')
        self.produit = make_produit(self.company)
        self.installation = make_installation(self.company)

    def test_cloture_refusee_si_elements_non_traites(self):
        make_equipement(self.company, self.produit, self.installation, 'SN050')
        campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel', produit=self.produit)
        peupler_campagne_rappel(campagne)
        with self.assertRaises(ValueError):
            cloturer_campagne_rappel(campagne, '2026-07-01')

    def test_cloture_ok_si_tous_remplaces(self):
        make_equipement(self.company, self.produit, self.installation, 'SN060')
        campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel', produit=self.produit)
        peupler_campagne_rappel(campagne)
        campagne.elements.update(statut=ElementRappel.Statut.REMPLACE)
        cloturer_campagne_rappel(campagne, '2026-07-01')
        campagne.refresh_from_db()
        self.assertEqual(campagne.statut, CampagneRappel.Statut.CLOTUREE)
        self.assertEqual(
            campagne.elements.filter(
                statut=ElementRappel.Statut.CLOS).count(), 1)


class CampagneRappelApiTests(TestCase):
    """WIR275 — CRUD REST + actions ``peupler``/``notifier``/``cloturer``
    (services testés, jusqu'ici totalement orphelins côté REST)."""

    def setUp(self):
        self.company = make_company('co-xqhs5-api', 'CoXqhs5Api')
        self.user = make_user(self.company, 'resp-xqhs5-api')
        self.api = auth_client(self.user)
        self.produit = make_produit(self.company)
        self.installation = make_installation(self.company)

    def test_create_pose_company(self):
        resp = self.api.post(CAMPAGNES, {
            'titre': 'Rappel onduleurs X', 'produit': self.produit.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        campagne = CampagneRappel.objects.get(id=resp.data['id'])
        self.assertEqual(campagne.company_id, self.company.id)

    def test_peupler_action(self):
        make_equipement(self.company, self.produit, self.installation, 'API01')
        campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel', produit=self.produit)
        resp = self.api.post(f'{CAMPAGNES}{campagne.id}/peupler/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['crees'], 1)
        self.assertEqual(campagne.elements.count(), 1)

    def test_notifier_action(self):
        eq = make_equipement(self.company, self.produit, self.installation, 'API02')
        campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel', produit=self.produit,
            responsable=self.user)
        peupler_campagne_rappel(campagne)
        resp = self.api.post(f'{CAMPAGNES}{campagne.id}/notifier/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['notifies'], 1)
        element = campagne.elements.get(equipement_id=eq.id)
        self.assertEqual(element.statut, ElementRappel.Statut.NOTIFIE)

    def test_cloturer_action_refusee_si_non_traites(self):
        make_equipement(self.company, self.produit, self.installation, 'API03')
        campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel', produit=self.produit)
        peupler_campagne_rappel(campagne)
        resp = self.api.post(f'{CAMPAGNES}{campagne.id}/cloturer/', {
            'date_verification_efficacite': '2026-08-01',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_isolation_inter_societes(self):
        autre = make_company('co-xqhs5-api-x', 'Autre')
        CampagneRappel.objects.create(
            company=autre, titre='Hors société', produit=self.produit)
        data = self.api.get(CAMPAGNES).data
        rows = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(rows), 0)


class ElementRappelApiTests(TestCase):
    """WIR275 — CRUD REST + action ``planifier-remplacement``
    (``planifier_remplacement_element_rappel`` — client résolu via
    ``apps.crm.selectors``, jamais un import de modèle)."""

    def setUp(self):
        self.company = make_company('co-xqhs5-elem-api', 'CoXqhs5ElemApi')
        self.user = make_user(self.company, 'resp-xqhs5-elem-api')
        self.api = auth_client(self.user)
        self.produit = make_produit(self.company)
        self.installation = make_installation(self.company)
        self.campagne = CampagneRappel.objects.create(
            company=self.company, titre='Rappel', produit=self.produit)

    def test_planifier_remplacement_action(self):
        eq = make_equipement(
            self.company, self.produit, self.installation, 'API10')
        peupler_campagne_rappel(self.campagne)
        element = self.campagne.elements.get(equipement_id=eq.id)
        resp = self.api.post(
            f'{ELEMENTS}{element.id}/planifier-remplacement/',
            {'client_id': self.installation.client_id}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], ElementRappel.Statut.PLANIFIE)

    def test_planifier_remplacement_client_hors_societe_400(self):
        autre = make_company('co-xqhs5-elem-api-x', 'Autre')
        client_autre = Client.objects.create(company=autre, nom='Externe')
        eq = make_equipement(
            self.company, self.produit, self.installation, 'API11')
        peupler_campagne_rappel(self.campagne)
        element = self.campagne.elements.get(equipement_id=eq.id)
        resp = self.api.post(
            f'{ELEMENTS}{element.id}/planifier-remplacement/',
            {'client_id': client_autre.id}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_isolation_inter_societes(self):
        autre = make_company('co-xqhs5-elem-api-y', 'Autre2')
        ElementRappel.objects.create(
            company=autre, campagne=self.campagne, numero_serie='HORS')
        data = self.api.get(ELEMENTS).data
        rows = data['results'] if isinstance(data, dict) else data
        self.assertEqual(len(rows), 0)

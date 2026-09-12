"""Tests NTPRT9 — Tableau de bord du portail CLIENT authentifié.

Couvre les 4 cartes résumé (devis en attente, factures impayées + échéance la
plus proche, tickets SAV ouverts, prochain jalon chantier), toutes lues via
les selectors PROPRIÉTAIRES de leur domaine (``ventes``/``sav``/
``installations``) — jamais un import direct de leurs modèles depuis
``portail`` (frontière cross-app CLAUDE.md).

Le cœur de ces tests est, comme NTPRT10/11 : les compteurs sont bornés au
SEUL client rattaché au compte connecté (jamais un chiffre d'un autre client
de la même société, ni d'une autre société), et la portée doit être
EXACTEMENT ``portail_client``.

PACT10 — la forme du payload est celle du contrat COMMITTÉ
(``apps/portail/contract_samples/client_tableau_de_bord.json``, le même
fichier que lit le test frontend) — jamais un dictionnaire réécrit à la main
dans un second endroit.

Run :
    python manage.py test apps.portail.tests.test_ntprt9_tableau_de_bord_client -v2
"""
import itertools
import json
import pathlib
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.facturation.models import Facture
from apps.installations.models import Installation
from apps.portail.services import upsert_jalon_chantier
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    Role,
)
from apps.sav.models import Ticket
from apps.ventes.models import Devis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

URL = '/api/django/portail/client/tableau-de-bord/'

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1]
     / 'contract_samples' / 'client_tableau_de_bord.json')
    .read_text(encoding='utf-8'))


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'NTPRT9-{n}',
        email=f'ntprt9-{company.id}-{n}@example.invalid')


def make_devis(company, client, statut=Devis.Statut.ENVOYE):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-NTPRT9-{n}', client=client,
        statut=statut, taux_tva=Decimal('20'))


def make_facture(company, client, statut=Facture.Statut.EMISE, date_echeance=None):
    n = next(_seq)
    return Facture.objects.create(
        company=company, reference=f'FAC-NTPRT9-{n}', client=client,
        statut=statut, montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
        montant_ttc=Decimal('1200'), taux_tva=Decimal('20'),
        date_echeance=date_echeance)


def make_ticket(company, client, statut=Ticket.Statut.NOUVEAU):
    n = next(_seq)
    return Ticket.objects.create(
        company=company, reference=f'SAV-NTPRT9-{n}', client=client,
        statut=statut)


def make_installation(company, client):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CH-NTPRT9-{n}', client=client)


_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_CLIENT: (
        ROLE_PORTAIL_CLIENT, 'portail_client_id', PORTAIL_CLIENT_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
}


def make_portal_user(company, username, portee, scope_id):
    role_nom, champ, perms = _PORTAIL[portee]
    role, _ = Role.objects.get_or_create(
        company=company, nom=role_nom,
        defaults={'permissions': list(perms), 'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = portee
    setattr(user, champ, scope_id)
    user.save()
    return user


def make_interne(company, username, permissions):
    role, _ = Role.objects.get_or_create(
        company=company, nom=f'role-{username}',
        defaults={'permissions': list(permissions)})
    return CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)


class TableauDeBordClientTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt9-co-a', 'NTPRT9 Société A')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')

        # Devis : 1 en attente (ENVOYE) + 1 accepté (ne compte pas) + 1
        # brouillon (jamais montré au client).
        make_devis(self.company, self.client_a, statut=Devis.Statut.ENVOYE)
        make_devis(self.company, self.client_a, statut=Devis.Statut.ACCEPTE)
        make_devis(self.company, self.client_a, statut=Devis.Statut.BROUILLON)

        # Factures : 1 émise (impayée, échéance proche) + 1 en retard
        # (impayée, échéance lointaine) + 1 payée (ne compte pas).
        today = date.today()
        make_facture(self.company, self.client_a, statut=Facture.Statut.EMISE,
                     date_echeance=today + timedelta(days=5))
        make_facture(self.company, self.client_a,
                     statut=Facture.Statut.EN_RETARD,
                     date_echeance=today + timedelta(days=30))
        make_facture(self.company, self.client_a, statut=Facture.Statut.PAYEE,
                     date_echeance=today + timedelta(days=1))

        # Tickets SAV : 2 ouverts + 1 clôturé (ne compte pas).
        make_ticket(self.company, self.client_a, statut=Ticket.Statut.NOUVEAU)
        make_ticket(self.company, self.client_a, statut=Ticket.Statut.EN_COURS)
        make_ticket(self.company, self.client_a, statut=Ticket.Statut.CLOTURE)

        # Chantier avec un jalon non atteint (prochain jalon) + un jalon
        # atteint (déjà passé).
        self.chantier = make_installation(self.company, self.client_a)
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'etude', 'Étude technique',
            atteint=True, date_jalon=date.today())
        upsert_jalon_chantier(
            self.company, self.chantier.id, 'installation',
            'Installation', atteint=False)

        self.user_a = make_portal_user(
            self.company, 'ntprt9-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id)
        self.api = APIClient()

    def test_devis_en_attente(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['devis_en_attente'], 1)

    def test_factures_impayees_et_prochaine_echeance(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get(URL)
        self.assertEqual(res.data['factures_impayees'], 2)
        self.assertEqual(
            res.data['prochaine_echeance'],
            str(date.today() + timedelta(days=5)))

    def test_tickets_ouverts(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get(URL)
        self.assertEqual(res.data['tickets_ouverts'], 2)

    def test_prochain_jalon(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get(URL)
        jalon = res.data['prochain_jalon']
        self.assertIsNotNone(jalon)
        self.assertEqual(jalon['chantier_id'], self.chantier.id)
        self.assertEqual(jalon['libelle'], 'Installation')

    # ── PACT10 : la forme servie EST celle du contrat committé ──────────────
    def test_la_reponse_a_exactement_les_cles_du_contrat(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get(URL)
        self.assertEqual(set(res.data.keys()),
                         set(CONTRAT['exemple'].keys()))
        self.assertEqual(
            set(res.data['prochain_jalon'].keys()),
            set(CONTRAT['exemple']['prochain_jalon'].keys()))

    def test_aucun_champ_de_cout_dans_le_payload(self):
        self.api.force_authenticate(user=self.user_a)
        res = self.api.get(URL)
        corps = str(res.data)
        for interdit in ('prix_achat', 'marge', 'montant_ttc', 'montant_ht'):
            self.assertNotIn(interdit, corps)

    def test_client_b_ne_voit_aucun_chiffre_du_client_a(self):
        user_b = make_portal_user(
            self.company, 'ntprt9-portail-b',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_b.id)
        self.api.force_authenticate(user=user_b)
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['devis_en_attente'], 0)
        self.assertEqual(res.data['factures_impayees'], 0)
        self.assertEqual(res.data['tickets_ouverts'], 0)
        self.assertIsNone(res.data['prochain_jalon'])

    def test_client_dune_autre_societe_ne_voit_rien(self):
        autre = make_company('ntprt9-co-b', 'NTPRT9 Société B')
        client_autre = make_client(autre, 'Gamma')
        etranger = make_portal_user(
            autre, 'ntprt9-portail-etranger',
            CustomUser.PORTEE_PORTAIL_CLIENT, client_autre.id)
        self.api.force_authenticate(user=etranger)
        res = self.api.get(URL)
        self.assertEqual(res.data['devis_en_attente'], 0)
        self.assertEqual(res.data['factures_impayees'], 0)
        self.assertEqual(res.data['tickets_ouverts'], 0)
        self.assertIsNone(res.data['prochain_jalon'])

    def test_compte_portail_fournisseur_refuse(self):
        fournisseur = make_portal_user(
            self.company, 'ntprt9-portail-f',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 1)
        self.api.force_authenticate(user=fournisseur)
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 403)

    def test_compte_portail_sans_rattachement_refuse(self):
        orphelin = make_portal_user(
            self.company, 'ntprt9-orphelin',
            CustomUser.PORTEE_PORTAIL_CLIENT, None)
        self.api.force_authenticate(user=orphelin)
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 403)

    def test_utilisateur_interne_refuse(self):
        interne = make_interne(self.company, 'ntprt9-interne',
                               ['ventes_voir', 'roles_gerer'])
        self.api.force_authenticate(user=interne)
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 403)

    def test_anonyme_refuse(self):
        res = APIClient().get(URL)
        self.assertIn(res.status_code, (401, 403))


class TableauDeBordClientSansDonneesTests(TestCase):
    """Un client tout neuf (aucun devis/facture/ticket/chantier) obtient des
    compteurs à ZÉRO, jamais une erreur 500 ni un chiffre fabriqué."""

    def setUp(self):
        self.company = make_company('ntprt9-vide-co', 'NTPRT9 Vide')
        self.client_a = make_client(self.company, 'Neuf')
        self.user_a = make_portal_user(
            self.company, 'ntprt9-vide-a', CustomUser.PORTEE_PORTAIL_CLIENT,
            self.client_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    def test_compteurs_a_zero_sans_erreur(self):
        res = self.api.get(URL)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['devis_en_attente'], 0)
        self.assertEqual(res.data['factures_impayees'], 0)
        self.assertEqual(res.data['tickets_ouverts'], 0)
        self.assertIsNone(res.data['prochaine_echeance'])
        self.assertIsNone(res.data['prochain_jalon'])
        self.assertEqual(set(res.data.keys()),
                         set(CONTRAT['exemple_vide'].keys()))

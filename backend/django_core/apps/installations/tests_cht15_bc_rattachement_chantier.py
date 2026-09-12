"""CHT15 — BC <-> chantier : rattachement automatique.

``Installation.bon_commande`` existe déjà (models_installation.py) mais
n'était jamais posé automatiquement : la jointure devis<->BC<->chantier
restait IMPLICITE (par ``devis_id``), jamais matérialisée sur la ligne
chantier. Ce module couvre le nouveau récepteur
``installations.receivers._rattacher_chantier_on_bon_commande_cree``, abonné
à ``core.events.bon_commande_cree`` (émis par
``ventes.views.devis.DevisViewSet.convertir_en_bc``).

Run :
    python manage.py test apps.installations.tests_cht15_bc_rattachement_chantier -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.ventes.models import BonCommande, Devis
from authentication.models import Company
from core.events import bon_commande_cree

_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'cht15-co-{n}', defaults={'nom': nom or f'CHT15 Co {n}'})
    return company


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='CHT15',
        email=f'cht15-{company.id}-{n}@example.invalid')


def make_devis(company, client):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-CHT15-{n}', client=client,
        statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))


def make_bc(company, devis=None, client=None):
    n = next(_seq)
    return BonCommande.objects.create(
        company=company, reference=f'BC-CHT15-{n}', devis=devis, client=client)


def make_installation(company, client, devis=None):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CHT-CHT15-{n}', client=client, devis=devis)


class TestRattachementAutomatique(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)
        self.inst = make_installation(
            self.company, self.client_obj, devis=self.devis)

    def test_conversion_devis_vers_bc_rattache_le_chantier(self):
        bc = make_bc(self.company, devis=self.devis, client=self.client_obj)
        bon_commande_cree.send(
            sender=BonCommande, instance=bc, company=self.company)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.bon_commande_id, bc.id)

    def test_second_envoi_n_ecrase_pas_le_rattachement(self):
        bc1 = make_bc(self.company, devis=self.devis, client=self.client_obj)
        bon_commande_cree.send(
            sender=BonCommande, instance=bc1, company=self.company)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.bon_commande_id, bc1.id)

        autre_devis = make_devis(self.company, self.client_obj)
        bc2 = make_bc(
            self.company, devis=autre_devis, client=self.client_obj)
        # Re-émettre pour le MÊME devis (BC de remplacement) : le chantier
        # déjà rattaché n'est jamais ré-écrit par un second envoi.
        bon_commande_cree.send(
            sender=BonCommande, instance=bc2, company=self.company)
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.bon_commande_id, bc1.id)

    def test_bc_sans_devis_ne_touche_aucun_chantier(self):
        bc = make_bc(self.company, devis=None, client=self.client_obj)
        bon_commande_cree.send(
            sender=BonCommande, instance=bc, company=self.company)
        self.inst.refresh_from_db()
        self.assertIsNone(self.inst.bon_commande_id)

    def test_scoping_societe(self):
        autre = make_company()
        autre_client = make_client(autre)
        autre_devis = make_devis(autre, autre_client)
        autre_inst = make_installation(autre, autre_client, devis=autre_devis)
        bc = make_bc(self.company, devis=self.devis, client=self.client_obj)
        bon_commande_cree.send(
            sender=BonCommande, instance=bc, company=self.company)
        autre_inst.refresh_from_db()
        self.assertIsNone(autre_inst.bon_commande_id)

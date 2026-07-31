"""Tests WIR95 — FK string-référencées du module portail.

Couvre : ``devis``/``facture``/``client``/``lead``/``chantier``/``ticket``
sont désormais de vraies ``ForeignKey`` (jamais un import direct des modèles
cibles) : un objet référencé supprimé via l'ORM met la référence portail à
NULL (SET_NULL, plus jamais un id orphelin silencieux) ; un id déjà orphelin
(donnée historique/test) reste accepté (db_constraint=False) — pas de
régression sur le contrat existant (cf.
``apps.compta.tests.test_portail_partenaires``).

Run :
    python manage.py test apps.portail.tests.test_wir95_fk_references -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.facturation.models import Facture
from apps.installations.models import Installation
from apps.portail.models import (
    AcceptationDevisPortail, DemandeTicketPortail, DocumentClientPortail,
    JalonChantierPortail, PaiementFacturePortail,
)
from apps.sav.models import Ticket
from apps.ventes.models import Devis

_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'wir95-co-{n}', defaults={'nom': nom or f'WIR95 Co {n}'})
    return company


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='WIR95',
        email=f'wir95-{company.id}-{n}@example.invalid')


def make_lead(company):
    return Lead.objects.create(company=company, nom='Lead WIR95')


def make_devis(company, client):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-WIR95-{n}', client=client,
        taux_tva=Decimal('20'))


def make_facture(company, client):
    n = next(_seq)
    return Facture.objects.create(
        company=company, reference=f'FAC-WIR95-{n}', client=client,
        statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'),
        montant_ttc=Decimal('1000'))


def make_installation(company, client):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CHT-WIR95-{n}', client=client)


def make_ticket(company, client, installation):
    n = next(_seq)
    return Ticket.objects.create(
        company=company, reference=f'SAV-WIR95-{n}', client=client,
        installation=installation)


class AcceptationDevisPortailFkTests(TestCase):
    def test_devis_supprime_met_la_reference_a_null(self):
        co = make_company()
        client = make_client(co)
        devis = make_devis(co, client)
        acc = AcceptationDevisPortail.objects.create(
            company=co, devis=devis, nom_signataire='M. Test')
        self.assertEqual(acc.devis_id, devis.id)
        devis.delete()
        acc.refresh_from_db()
        self.assertIsNone(acc.devis_id)

    def test_id_orphelin_deja_existant_reste_accepte(self):
        # db_constraint=False — pas de contrainte FK au niveau base (les
        # apps domaine restent mutuellement décorrélées) : un id qui ne
        # correspond à rien ne bloque jamais l'écriture (compat des données
        # existantes/tests, cf. compta.tests.test_portail_partenaires).
        co = make_company()
        acc = AcceptationDevisPortail.objects.create(
            company=co, devis_id=999999, nom_signataire='M. Orphelin')
        self.assertEqual(acc.devis_id, 999999)


class PaiementFacturePortailFkTests(TestCase):
    def test_facture_supprimee_met_la_reference_a_null(self):
        co = make_company()
        client = make_client(co)
        facture = make_facture(co, client)
        paiement = PaiementFacturePortail.objects.create(
            company=co, facture=facture, montant=Decimal('500'))
        facture.delete()
        paiement.refresh_from_db()
        self.assertIsNone(paiement.facture_id)


class DocumentClientPortailFkTests(TestCase):
    def test_client_et_lead_supprimes_mettent_la_reference_a_null(self):
        co = make_company()
        client = make_client(co)
        lead = make_lead(co)
        doc = DocumentClientPortail.objects.create(
            company=co, client=client, lead=lead)
        client.delete()
        lead.delete()
        doc.refresh_from_db()
        self.assertIsNone(doc.client_id)
        self.assertIsNone(doc.lead_id)


class JalonChantierPortailFkTests(TestCase):
    def test_chantier_supprime_met_la_reference_a_null(self):
        co = make_company()
        client = make_client(co)
        installation = make_installation(co, client)
        jalon = JalonChantierPortail.objects.create(
            company=co, chantier=installation, libelle='Étude')
        installation.delete()
        jalon.refresh_from_db()
        self.assertIsNone(jalon.chantier_id)


class DemandeTicketPortailFkTests(TestCase):
    def test_client_chantier_ticket_supprimes_mettent_la_reference_a_null(self):
        co = make_company()
        client = make_client(co)
        installation = make_installation(co, client)
        ticket = make_ticket(co, client, installation)
        demande = DemandeTicketPortail.objects.create(
            company=co, client=client, chantier=installation, ticket=ticket,
            sujet='Onduleur en panne')
        ticket.delete()
        installation.delete()
        client.delete()
        demande.refresh_from_db()
        self.assertIsNone(demande.ticket_id)
        self.assertIsNone(demande.chantier_id)
        self.assertIsNone(demande.client_id)

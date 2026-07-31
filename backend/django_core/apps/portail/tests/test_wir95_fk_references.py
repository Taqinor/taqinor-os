"""Tests WIR95 — FK string-référencées du module portail.

Couvre : ``devis``/``facture``/``client``/``lead``/``chantier``/``ticket``
sont de vraies ``ForeignKey`` (jamais un import direct des modèles cibles),
avec DEUX politiques de suppression distinctes :

* ``SET_NULL`` pour les références informatives (client, lead, chantier,
  ticket) — l'objet référencé supprimé met la référence portail à NULL, plus
  jamais un id orphelin silencieux ;
* ``PROTECT`` (YDATA2) pour ``PaiementFacturePortail.facture`` (argent : un
  ``montant`` MAD réel, parfois ``statut='paye'``) et
  ``AcceptationDevisPortail.devis`` (preuve d'acceptation électronique —
  signataire/IP/horodatage, loi 53-05) : la suppression du parent est REFUSÉE
  (``ProtectedError``) et les deux lignes survivent intactes. Ces deux champs
  gardent ``db_constraint=False`` : la protection vient du collector Django
  (``deletion.PROTECT``), jamais d'une contrainte base — d'où le test
  d'orphelin ci-dessous, qui prouve qu'aucune contrainte FK physique n'existe.

Un id déjà orphelin (donnée historique/test) reste accepté
(db_constraint=False) — pas de régression sur le contrat existant (cf.
``apps.compta.tests.test_portail_partenaires``).

Run :
    python manage.py test apps.portail.tests.test_wir95_fk_references -v2
"""
import itertools
from decimal import Decimal

from django.db.models import ProtectedError
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
    def test_devis_signe_ne_peut_pas_etre_supprime(self):
        """YDATA2 — PROTECT : la preuve d'acceptation (loi 53-05) refuse la
        suppression du devis, et RIEN n'est perdu des deux côtés.

        ``PROTECT`` est levé par le collector Django pendant ``collect()``,
        AVANT le moindre SQL : ``db_constraint=False`` (aucune contrainte FK
        physique) n'y change rien, et la transaction de test n'est pas cassée
        — les requêtes d'assertion qui suivent fonctionnent normalement.
        """
        co = make_company()
        client = make_client(co)
        devis = make_devis(co, client)
        acc = AcceptationDevisPortail.objects.create(
            company=co, devis=devis, nom_signataire='M. Test',
            signature_ip='10.0.0.1', accepte=True)
        self.assertEqual(acc.devis_id, devis.id)

        with self.assertRaises(ProtectedError):
            devis.delete()

        # Les DEUX lignes survivent : le devis n'est pas supprimé et la preuve
        # d'acceptation pointe toujours sur LUI (jamais détachée).
        self.assertTrue(Devis.objects.filter(pk=devis.pk).exists())
        self.assertTrue(
            AcceptationDevisPortail.objects.filter(pk=acc.pk).exists())
        acc.refresh_from_db()
        self.assertEqual(acc.devis_id, devis.pk)
        self.assertEqual(acc.nom_signataire, 'M. Test')

    def test_devis_sans_acceptation_reste_supprimable(self):
        """PROTECT ne bloque QUE tant qu'une preuve existe (pas de blocage
        généralisé de la suppression de devis)."""
        co = make_company()
        client = make_client(co)
        devis = make_devis(co, client)
        devis.delete()
        self.assertFalse(Devis.objects.filter(pk=devis.pk).exists())

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
    def test_facture_avec_paiement_ne_peut_pas_etre_supprimee(self):
        """YDATA2 — PROTECT : de l'argent réel ne devient jamais orphelin.

        Avant, ``SET_NULL`` laissait une ligne de paiement portant un montant
        MAD (et un ``statut='paye'``) pointant sur RIEN.
        """
        co = make_company()
        client = make_client(co)
        facture = make_facture(co, client)
        paiement = PaiementFacturePortail.objects.create(
            company=co, facture=facture, montant=Decimal('500'),
            statut=PaiementFacturePortail.Statut.PAYE)

        with self.assertRaises(ProtectedError):
            facture.delete()

        # Les DEUX lignes survivent : la facture n'est pas supprimée et le
        # paiement reste rattaché à ELLE (montant jamais orphelin).
        self.assertTrue(Facture.objects.filter(pk=facture.pk).exists())
        self.assertTrue(
            PaiementFacturePortail.objects.filter(pk=paiement.pk).exists())
        paiement.refresh_from_db()
        self.assertEqual(paiement.facture_id, facture.pk)
        self.assertEqual(paiement.montant, Decimal('500'))

    def test_facture_sans_paiement_portail_reste_supprimable(self):
        co = make_company()
        client = make_client(co)
        facture = make_facture(co, client)
        facture.delete()
        self.assertFalse(Facture.objects.filter(pk=facture.pk).exists())

    def test_id_orphelin_deja_existant_reste_accepte(self):
        # db_constraint=False — aucune contrainte FK physique : PROTECT vient
        # du collector Django, pas de la base. Un id qui ne correspond à rien
        # reste donc écrivable (compat des données existantes/tests).
        co = make_company()
        paiement = PaiementFacturePortail.objects.create(
            company=co, facture_id=999999, montant=Decimal('42'))
        self.assertEqual(paiement.facture_id, 999999)


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

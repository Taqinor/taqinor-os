"""Tests YDOCF5 — Contrat signé/actif : émission d'un événement métier sur le
bus core (``core/events.py``).

Couvre : signer le dernier signataire requis émet ``contrat_signe`` puis
``contrat_actif`` (si ``date_debut`` ≤ aujourd'hui) EXACTEMENT une fois ; un
abonné de test les reçoit ; CONTRAT16/17 restent inchangés (mêmes bascules de
statut qu'avant, mêmes gardes).
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import Contrat, PartieContrat
from core.events import contrat_actif, contrat_signe


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_contrat(company, *, date_debut=None):
    contrat = Contrat.objects.create(
        company=company, objet='Contrat YDOCF5', montant=Decimal('50000'),
        type_contrat='vente', statut='en_approbation', date_debut=date_debut)
    PartieContrat.objects.create(
        company=company, contrat=contrat,
        type_partie='client', nom='Client SARL', ordre=0)
    PartieContrat.objects.create(
        company=company, contrat=contrat,
        type_partie='prestataire', nom='Taqinor', ordre=1)
    return contrat


class _Receiver:
    """Abonné de test : accumule les envois reçus pour assertion."""

    def __init__(self):
        self.calls = []

    def __call__(self, sender, **kwargs):
        self.calls.append(kwargs)


class ContratSigneActifEventsTests(TestCase):
    def setUp(self):
        self.company = make_company('ydocf5', 'YDOCF5')
        self.receiver_signe = _Receiver()
        self.receiver_actif = _Receiver()
        contrat_signe.connect(self.receiver_signe)
        contrat_actif.connect(self.receiver_actif)
        self.addCleanup(contrat_signe.disconnect, self.receiver_signe)
        self.addCleanup(contrat_actif.disconnect, self.receiver_actif)

    def test_signature_complete_prise_effet_immediate_emet_les_deux(self):
        contrat = make_contrat(self.company, date_debut=None)

        services.signer_contrat(
            contrat, signataire_nom='Client SARL',
            role_signataire='client')
        # Signature partielle : aucun événement encore.
        self.assertEqual(len(self.receiver_signe.calls), 0)
        self.assertEqual(len(self.receiver_actif.calls), 0)

        services.signer_contrat(
            contrat, signataire_nom='Taqinor',
            role_signataire='prestataire')

        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

        self.assertEqual(len(self.receiver_signe.calls), 1)
        self.assertEqual(len(self.receiver_actif.calls), 1)

        appel_signe = self.receiver_signe.calls[0]
        self.assertEqual(appel_signe['contrat'].id, contrat.id)
        self.assertEqual(appel_signe['company'], self.company)

        appel_actif = self.receiver_actif.calls[0]
        self.assertEqual(appel_actif['contrat'].id, contrat.id)
        self.assertEqual(appel_actif['company'], self.company)

    def test_prise_effet_future_emet_signe_seul(self):
        contrat = make_contrat(
            self.company,
            date_debut=timezone.localdate() + timedelta(days=30))

        services.signer_contrat(
            contrat, signataire_nom='Client SARL', role_signataire='client')
        services.signer_contrat(
            contrat, signataire_nom='Taqinor', role_signataire='prestataire')

        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.SIGNE)

        self.assertEqual(len(self.receiver_signe.calls), 1)
        self.assertEqual(len(self.receiver_actif.calls), 0)

    def test_signature_partielle_aucun_evenement(self):
        contrat = make_contrat(self.company)
        services.signer_contrat(
            contrat, signataire_nom='Client SARL', role_signataire='client')

        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.EN_APPROBATION)
        self.assertEqual(len(self.receiver_signe.calls), 0)
        self.assertEqual(len(self.receiver_actif.calls), 0)

    def test_evenement_emis_exactement_une_fois(self):
        """Un second appel à ``signer_contrat`` sur un contrat DÉJÀ signé (ex.
        un rôle supplémentaire comme témoin) ne réémet PAS ``contrat_signe``
        (la garde ``contrat.statut != SIGNE`` empêche une seconde bascule)."""
        contrat = make_contrat(self.company, date_debut=None)
        services.signer_contrat(
            contrat, signataire_nom='Client SARL', role_signataire='client')
        services.signer_contrat(
            contrat, signataire_nom='Taqinor', role_signataire='prestataire')
        self.assertEqual(len(self.receiver_signe.calls), 1)
        self.assertEqual(len(self.receiver_actif.calls), 1)

        # Une signature additionnelle (témoin) ne change pas le statut (déjà
        # actif) — aucun événement supplémentaire.
        services.signer_contrat(
            contrat, signataire_nom='Notaire', role_signataire='temoin')
        self.assertEqual(len(self.receiver_signe.calls), 1)
        self.assertEqual(len(self.receiver_actif.calls), 1)

    def test_activer_si_eligible_direct_emet_contrat_actif(self):
        """``activer_si_eligible`` appelé directement (pas seulement via
        ``signer_contrat``) émet aussi ``contrat_actif`` — YDOCF5 exige les
        deux points d'émission."""
        contrat = Contrat.objects.create(
            company=self.company, objet='Direct', montant=Decimal('1000'),
            type_contrat='vente', statut=Contrat.Statut.SIGNE,
            date_debut=None)
        activee = services.activer_si_eligible(contrat)
        self.assertTrue(activee)
        self.assertEqual(len(self.receiver_actif.calls), 1)

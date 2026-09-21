"""WIR148 — planifie `generer_echeances_loyer` en tâche Celery récurrente.

Avant cette tâche, le cycle de vie du bail (signature/révision/dépôt/
échéancier/quittancement/impayés) était backend-only et TESTÉ, mais rien ne
matérialisait automatiquement les `EcheanceLoyer` dues chaque mois — seule la
commande manage fonctionnait, jamais exécutée. Ces tests couvrent
`immobilier.generer_echeances_loyer` (multi-société, idempotente, isolation
d'erreur par société, ignore les baux non actifs) ; la joignabilité au beat
est vérifiée génériquement par
`apps.ventes.tests.test_qx11_beat_reachability`.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.immobilier.models import (
    Bail, Batiment, EcheanceLoyer, Local, Locataire, Niveau, Site,
)
from apps.immobilier.services import creer_bail
from apps.immobilier.tasks import generer_echeances_loyer_task

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def _make_bail(company, *, statut=Bail.Statut.ACTIF):
    site = Site.objects.create(company=company, nom='Résidence')
    batiment = Batiment.objects.create(company=company, site=site, nom='Bât')
    niveau = Niveau.objects.create(company=company, batiment=batiment, numero='RDC')
    local = Local.objects.create(company=company, niveau=niveau, reference='RDC-01')
    locataire = Locataire.objects.create(company=company, nom='Bennani')
    return creer_bail(
        company=company, local=local, locataire=locataire,
        type_bail=Bail.TypeBail.HABITATION, date_debut=date(2026, 1, 1),
        duree_mois=3, loyer_mensuel_ht=Decimal('3000.00'),
        charges_mensuelles_provisions=Decimal('200.00'), statut=statut)


class Wir148GenererEcheancesLoyerTaskTests(TestCase):
    def setUp(self):
        self.co_a = make_company('wir148-a', 'WIR148 A')
        self.co_b = make_company('wir148-b', 'WIR148 B')
        self.bail_a = _make_bail(self.co_a)
        self.bail_b = _make_bail(self.co_b)

    def test_generates_echeances_for_every_active_company(self):
        result = generer_echeances_loyer_task()
        self.assertEqual(result['baux'], 2)
        self.assertEqual(result['echeances_creees'], 6)  # 3 mois x 2 baux
        self.assertEqual(
            EcheanceLoyer.objects.filter(bail=self.bail_a).count(), 3)
        self.assertEqual(
            EcheanceLoyer.objects.filter(bail=self.bail_b).count(), 3)

    def test_idempotent_rerun_creates_no_duplicate(self):
        generer_echeances_loyer_task()
        generer_echeances_loyer_task()
        self.assertEqual(
            EcheanceLoyer.objects.filter(bail=self.bail_a).count(), 3)

    def test_draft_bail_generates_nothing(self):
        co_c = make_company('wir148-c', 'WIR148 C')
        bail_c = _make_bail(co_c, statut=Bail.Statut.BROUILLON)
        result = generer_echeances_loyer_task()
        self.assertEqual(
            EcheanceLoyer.objects.filter(bail=bail_c).count(), 0)
        # Les baux actifs des autres sociétés sont quand même traités.
        self.assertGreaterEqual(result['baux'], 2)

    def test_suspended_company_excluded(self):
        self.co_b.actif = False
        self.co_b.save(update_fields=['actif'])
        result = generer_echeances_loyer_task()
        self.assertEqual(result['baux'], 1)
        self.assertEqual(
            EcheanceLoyer.objects.filter(bail=self.bail_b).count(), 0)

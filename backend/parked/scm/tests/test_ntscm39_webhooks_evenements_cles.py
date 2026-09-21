"""NTSCM39 — Webhooks sortants sur les événements SCM clés.

Critère d'acceptation : une société avec un `Webhook` abonné à
`scm.rupture_imminente_detectee` reçoit un POST avec le produit et la date de
rupture projetée lors du déclenchement, vérifié par test avec un récepteur
factice.

ADAPTATION DE PÉRIMÈTRE : le 3ᵉ évènement du plan
(`scm.score_fournisseur_degrade`, « émis par NTSCM23 ») n'a pas de tâche
source — NTSCM23 n'existe pas dans `docs/plans/PLAN_SUPPLY.md`, contrairement
à NTSCM11/17/26 qui EXISTENT mais restent `[ ]`. Voir la docstring de
`core.events.scm_rupture_imminente_detectee` pour le détail."""
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from apps.scm.models import CyclePlanificationSOP, LigneDemandeSOP
from apps.scm.services import (
    avancer_statut_cycle, detecter_ruptures_imminentes_et_notifier,
    recalculer_politiques_stock,
)
from apps.stock.models import Fournisseur, MouvementStock, Produit

from .helpers import make_company, make_user


class RuptureImminenteWebhookTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-webhook-rupture', 'Supply Webhook Rupture')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur SCM')
        self.produit = Produit.objects.create(
            company=self.company, nom='Micro-onduleur', prix_vente=900,
            quantite_stock=1, fournisseur=self.fournisseur)
        # Consommation soutenue (120 unités ce mois-ci) avec un stock résiduel
        # de 1 unité -> rupture PHYSIQUE en quelques heures, largement avant
        # le délai fournisseur par défaut (15 j) -> statut rupture_imminente
        # garanti (voir `selectors.tableau_bord_reappro`).
        for _i in range(6):
            MouvementStock.objects.create(
                company=self.company, produit=self.produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=20, quantite_avant=1000, quantite_apres=1000 - 20)
        recalculer_politiques_stock(self.company)

    def test_produit_en_rupture_imminente_declenche_le_webhook(self):
        with mock.patch(
                'apps.publicapi.delivery.dispatch_event'
                ) as dispatch:
            nb_emis = detecter_ruptures_imminentes_et_notifier(self.company)

        self.assertEqual(nb_emis, 1)
        self.assertTrue(dispatch.called)
        args, _kwargs = dispatch.call_args
        self.assertEqual(args[0], self.company.id)
        self.assertEqual(args[1], 'scm.rupture_imminente_detectee')
        self.assertEqual(args[2]['produit_id'], self.produit.id)
        self.assertIn('rupture_date', args[2])

    def test_produit_hors_politique_de_stock_ne_declenche_jamais(self):
        # Créé APRÈS le recalcul de `setUp` -> aucune PolitiqueStock -> absent
        # du tableau de bord réappro (NTSCM7) -> jamais notifié, même si son
        # stock est faible.
        autre_produit = Produit.objects.create(
            company=self.company, nom='Câble AC', prix_vente=50,
            quantite_stock=500)
        with mock.patch(
                'apps.publicapi.delivery.dispatch_event'
                ) as dispatch:
            detecter_ruptures_imminentes_et_notifier(self.company)
        for call in dispatch.call_args_list:
            self.assertNotEqual(call.args[2].get('produit_id'), autre_produit.id)


class CycleSopClotureWebhookTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-webhook-cloture', 'Supply Webhook Clôture')
        self.admin = make_user(self.company, 'scm-webhook-cloture-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Régulateur', prix_vente=500,
            quantite_stock=10)
        self.cycle = CyclePlanificationSOP.objects.create(
            company=self.company, periode='2026-02',
            statut=CyclePlanificationSOP.Statut.REUNION_RECONCILIATION)
        LigneDemandeSOP.objects.create(
            company=self.company, cycle=self.cycle, produit=self.produit,
            quantite_prevision_systeme=Decimal('5'))

    def test_cloture_du_cycle_declenche_le_webhook(self):
        avancer_statut_cycle(self.cycle, self.admin)  # -> approuve
        with mock.patch(
                'apps.publicapi.delivery.dispatch_event'
                ) as dispatch:
            avancer_statut_cycle(self.cycle, self.admin)  # -> clos

        self.cycle.refresh_from_db()
        self.assertEqual(self.cycle.statut, CyclePlanificationSOP.Statut.CLOS)
        self.assertTrue(dispatch.called)
        args, _kwargs = dispatch.call_args
        self.assertEqual(args[0], self.company.id)
        self.assertEqual(args[1], 'scm.cycle_sop_cloture')
        self.assertEqual(args[2]['cycle_id'], self.cycle.id)
        self.assertEqual(args[2]['periode'], '2026-02')

    def test_avancement_intermediaire_ne_declenche_pas_le_webhook(self):
        with mock.patch(
                'apps.publicapi.delivery.dispatch_event'
                ) as dispatch:
            avancer_statut_cycle(self.cycle, self.admin)  # -> approuve
        self.assertFalse(dispatch.called)

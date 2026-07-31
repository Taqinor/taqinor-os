"""WIR85 / XACC6 — l'écriture de stock automatique est enfin BRANCHÉE.

``compta.services.poster_mouvement_stock`` était défini et testé
(``test_mouvement_stock_gl.py``) mais n'avait AUCUN appelant de production, et
``core.events`` ne portait aucun événement « mouvement de stock » : l'écriture
d'inventaire permanent ne partait jamais.

WIR85 ajoute ``core.events.mouvement_stock_enregistre``, émis par
``stock.services.record_stock_movement`` (le SEUL point de création d'un
``MouvementStock``), auquel ``compta.receivers`` s'abonne.

Test d'INTÉGRATION de bout en bout : on crée un vrai ``MouvementStock`` par le
service stock et on vérifie l'écriture produite, avec le double garde-fou
(toggle WIR24 ``COMPTA_AUTO_ECRITURES`` + ``PlanComptable.inventaire_permanent``).

Run :
    docker compose exec django_core python manage.py test \
        apps.compta.tests.test_wir85_mouvement_stock_event -v 2
"""
from decimal import Decimal

from django.test import TestCase, override_settings

from authentication.models import Company

from apps.compta import services
from apps.compta.models import EcritureComptable
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import record_stock_movement


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class WIR85MouvementStockEventTests(TestCase):
    def setUp(self):
        self.co = make_company('wir85', 'WIR85 Co')
        self.plan = services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau 450W', prix_vente=Decimal('1500'),
            prix_achat=Decimal('900'), quantite_stock=100)

    def _activer_inventaire_permanent(self):
        self.plan.inventaire_permanent = True
        self.plan.save(update_fields=['inventaire_permanent'])

    def _mouvement(self, type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                   quantite=5, avant=100, apres=95):
        return record_stock_movement(
            company=self.co, produit=self.produit,
            type_mouvement=type_mouvement, quantite=quantite,
            quantite_avant=avant, quantite_apres=apres,
            reference='WIR85-TEST', note='', created_by=None)

    def _ecritures(self):
        return EcritureComptable.objects.filter(
            company=self.co, source_type='mouvement_stock')

    # ── Toggles OFF : comportement strictement inchangé ──────────────────
    def test_sans_toggle_aucune_ecriture(self):
        mvt = self._mouvement()
        self.assertIsNotNone(mvt.pk)
        self.assertEqual(self._ecritures().count(), 0)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_auto_ecritures_seul_ne_suffit_pas(self):
        """Sans inventaire permanent, toujours aucune écriture de stock."""
        self._mouvement()
        self.assertEqual(self._ecritures().count(), 0)

    def test_inventaire_permanent_seul_ne_suffit_pas(self):
        """Sans le toggle WIR24, le miroir comptable reste muet."""
        self._activer_inventaire_permanent()
        self._mouvement()
        self.assertEqual(self._ecritures().count(), 0)

    # ── Les deux toggles ON : exactement UNE écriture équilibrée ─────────
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_mouvement_reel_produit_une_ecriture_equilibree(self):
        self._activer_inventaire_permanent()
        mvt = self._mouvement()

        ecritures = self._ecritures()
        self.assertEqual(ecritures.count(), 1)
        ecr = ecritures.first()
        self.assertTrue(ecr.est_equilibree)
        self.assertEqual(ecr.source_id, mvt.pk)
        # 5 × 900 = 4500 — sortie : 6114 débit / 3111 crédit.
        self.assertEqual(ecr.total_debit, Decimal('4500'))
        self.assertEqual(ecr.total_debit, ecr.total_credit)
        self.assertEqual(
            ecr.lignes.get(compte__numero='6114').debit, Decimal('4500'))
        self.assertEqual(
            ecr.lignes.get(compte__numero='3111').credit, Decimal('4500'))

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_entree_poste_le_sens_inverse(self):
        self._activer_inventaire_permanent()
        self._mouvement(
            type_mouvement=MouvementStock.TypeMouvement.ENTREE,
            quantite=3, avant=100, apres=103)
        ecr = self._ecritures().get()
        self.assertEqual(
            ecr.lignes.get(compte__numero='3111').debit, Decimal('2700'))
        self.assertEqual(
            ecr.lignes.get(compte__numero='6114').credit, Decimal('2700'))

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_deux_mouvements_deux_ecritures_distinctes(self):
        """Chaque mouvement a sa propre référence : aucune collision."""
        self._activer_inventaire_permanent()
        self._mouvement(quantite=5, avant=100, apres=95)
        self._mouvement(quantite=2, avant=95, apres=93)
        self.assertEqual(self._ecritures().count(), 2)

    # ── Types sans impact de valeur ──────────────────────────────────────
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_transfert_ne_poste_rien(self):
        """Un transfert est un déplacement INTERNE : la valeur ne bouge pas."""
        self._activer_inventaire_permanent()
        self._mouvement(
            type_mouvement=MouvementStock.TypeMouvement.TRANSFERT,
            quantite=4, avant=100, apres=100)
        self.assertEqual(self._ecritures().count(), 0)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_rebut_est_une_sortie(self):
        self._activer_inventaire_permanent()
        self._mouvement(
            type_mouvement=MouvementStock.TypeMouvement.REBUT,
            quantite=2, avant=100, apres=98)
        ecr = self._ecritures().get()
        self.assertEqual(
            ecr.lignes.get(compte__numero='6114').debit, Decimal('1800'))

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_ajustement_est_signe_par_la_variation(self):
        self._activer_inventaire_permanent()
        # Ajustement à la HAUSSE → entrée.
        self._mouvement(
            type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT,
            quantite=2, avant=100, apres=102)
        ecr = self._ecritures().get()
        self.assertEqual(
            ecr.lignes.get(compte__numero='3111').debit, Decimal('1800'))

    # ── Idempotence & robustesse ─────────────────────────────────────────
    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_signal_rejoue_ne_duplique_pas_lecriture(self):
        from core.events import mouvement_stock_enregistre

        self._activer_inventaire_permanent()
        mvt = self._mouvement()
        self.assertEqual(self._ecritures().count(), 1)

        mouvement_stock_enregistre.send(
            sender=type(mvt), instance=mvt, company=self.co)
        self.assertEqual(self._ecritures().count(), 1)

    @override_settings(COMPTA_AUTO_ECRITURES=True)
    def test_echec_comptable_ne_casse_jamais_le_mouvement(self):
        """La compta est le MIROIR du stock, jamais son gardien."""
        from unittest.mock import patch

        self._activer_inventaire_permanent()
        with patch('apps.compta.receivers.poster_mouvement_stock',
                   side_effect=RuntimeError('boom')):
            mvt = self._mouvement()
        self.assertIsNotNone(mvt.pk)
        self.assertTrue(MouvementStock.objects.filter(pk=mvt.pk).exists())
        self.assertEqual(self._ecritures().count(), 0)

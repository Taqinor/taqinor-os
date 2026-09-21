"""AUD233 — le rapprochement 3 voies n'est plus opt-in par bon de commande.

[DÉCISION FONDATEUR 03/09/2026 : ON par défaut pour les NOUVEAUX BCF (réglage
société), jamais rétroactif sur l'historique.]

``creer_rapprochement_3voies`` n'avait qu'UN appelant — une action manuelle
explicite. Par défaut, aucun ``Rapprochement`` n'existait donc jamais :
``compta.selectors.rapprochement_ecart_pct`` renvoyait ``None`` et
``stock.services.evaluate_facture_exception`` était un NO-OP STRUCTUREL. Une
facture fournisseur pouvait être payée pour PLUS que ce qui avait été reçu
sans qu'aucune alerte ne se déclenche.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.compta.models import Rapprochement
from apps.compta.selectors import rapprochement_ecart_pct
from apps.stock import services as stock_services
from apps.stock.models import (
    AchatsParametres, BonCommandeFournisseur, FactureFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, LigneReceptionFournisseur, Produit,
    ReceptionFournisseur,
)
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestRapprochementAutomatique(TestCase):
    """Un BCF de 10 × 90 = 900 HT commandé."""

    def setUp(self):
        n = _nxt()
        self.co = Company.objects.create(slug=f'aud233-{n}', nom='AUD233 Co')
        self.user = User.objects.create_user(
            username=f'aud233_{n}', password='x', company=self.co,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.co, nom='Grossiste AUD233')
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau 550W', sku=f'AUD233-{n}',
            prix_achat=Decimal('90'), prix_vente=Decimal('150'),
            quantite_stock=0)
        self.bon = BonCommandeFournisseur.objects.create(
            company=self.co, reference=f'BCF-AUD233-{n}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bon, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('90'))

    def _recevoir(self, qte):
        rec = ReceptionFournisseur.objects.create(
            company=self.co, reference=f'REC-AUD233-{_nxt()}',
            bon_commande=self.bon)
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=self.ligne, produit=self.produit,
            quantite=qte)
        stock_services.confirm_reception_fournisseur(rec, self.user)
        return rec

    def _facturer(self, montant_ht):
        return FactureFournisseur.objects.create(
            company=self.co, reference=f'FF-AUD233-{_nxt()}',
            fournisseur=self.fournisseur, bon_commande=self.bon,
            montant_ht=Decimal(montant_ht), montant_tva=Decimal('0'),
            montant_ttc=Decimal(montant_ht))

    # ── L'auto-création ────────────────────────────────────────────────────

    def test_la_reception_confirmee_cree_le_rapprochement(self):
        """ROUGE avant le correctif : AUCUN Rapprochement n'existait."""
        self.assertFalse(Rapprochement.objects.filter(
            company=self.co, bon_commande_id=self.bon.id).exists())
        self._recevoir(10)
        rapp = Rapprochement.objects.get(
            company=self.co, bon_commande_id=self.bon.id)
        self.assertEqual(rapp.montant_commande, Decimal('900'))
        self.assertEqual(rapp.montant_recu, Decimal('900'))

    def test_l_ecart_reel_est_enfin_detectable(self):
        """Le cœur du constat : sur-facturation payable sans alerte.

        On reçoit 8 unités (720 HT) et le fournisseur facture 900 HT.
        ``evaluate_facture_exception`` ne pouvait STRUCTURELLEMENT pas voir
        cet écart : il n'y avait pas de Rapprochement à lire."""
        self._recevoir(8)
        facture = self._facturer('900')
        # Tolérance société à 0 % → tout écart est une exception.
        en_exception, ecart_pct = stock_services.evaluate_facture_exception(
            self.co, facture)
        self.assertTrue(en_exception)
        self.assertIsNotNone(ecart_pct)
        # (900 − 720) / 720 = 25 %
        self.assertEqual(ecart_pct.quantize(Decimal('0.01')),
                         Decimal('25.00'))
        facture.refresh_from_db()
        self.assertEqual(facture.statut_controle,
                         FactureFournisseur.StatutControle.EXCEPTION)

    def test_pas_d_ecart_quand_recu_et_facture_concordent(self):
        self._recevoir(10)
        facture = self._facturer('900')
        en_exception, ecart_pct = stock_services.evaluate_facture_exception(
            self.co, facture)
        self.assertFalse(en_exception)
        self.assertEqual(ecart_pct, Decimal('0'))

    def test_idempotent_deux_receptions_un_seul_rapprochement(self):
        self._recevoir(5)
        self._recevoir(5)
        self.assertEqual(
            Rapprochement.objects.filter(
                company=self.co, bon_commande_id=self.bon.id).count(), 1)
        self.assertEqual(
            rapprochement_ecart_pct(self.co, self.bon.id), Decimal('0'))

    # ── Le réglage société ─────────────────────────────────────────────────

    def test_reglage_societe_off_retablit_le_comportement_historique(self):
        parametres = AchatsParametres.for_company(self.co)
        self.assertTrue(parametres.rapprochement_3voies_auto,
                        'décision fondateur : ON par défaut')
        parametres.rapprochement_3voies_auto = False
        parametres.save(update_fields=['rapprochement_3voies_auto'])

        self._recevoir(8)
        self.assertFalse(Rapprochement.objects.filter(
            company=self.co, bon_commande_id=self.bon.id).exists())
        facture = self._facturer('900')
        en_exception, ecart_pct = stock_services.evaluate_facture_exception(
            self.co, facture)
        self.assertFalse(en_exception)
        self.assertIsNone(ecart_pct)

    def test_jamais_retroactif_aucun_rattrapage_de_l_historique(self):
        """La non-rétroactivité est portée par le DÉCLENCHEUR : sans nouvel
        événement, un BCF historique ne reçoit aucun rapprochement."""
        historique = BonCommandeFournisseur.objects.create(
            company=self.co, reference=f'BCF-AUD233-{_nxt()}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=historique, produit=self.produit, quantite=4,
            prix_achat_unitaire=Decimal('90'))
        # Un autre BCF vit sa vie (réception + facture) : l'historique reste
        # intouché.
        self._recevoir(10)
        self.assertFalse(Rapprochement.objects.filter(
            company=self.co, bon_commande_id=historique.id).exists())

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(
            slug=f'aud233b-{_nxt()}', nom='AUD233 B')
        rapp = stock_services.rafraichir_rapprochement_3voies_auto(
            autre, self.bon.id)
        # Le BCF n'appartient pas à cette société : rien n'est créé, et la
        # réception/facturation ne casse jamais pour autant.
        self.assertIsNone(rapp)
        self.assertFalse(Rapprochement.objects.filter(
            company=autre, bon_commande_id=self.bon.id).exists())

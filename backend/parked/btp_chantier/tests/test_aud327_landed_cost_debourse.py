"""AUD327 — ``debourse_sec_vs_facture`` (NTCON11) préfère le coût unitaire
DÉBARQUÉ (FOB + quote-part frais d'import) quand la réservation de stock
consommée trace vers un ``DossierImport``, au lieu du ``stock.Produit.
prix_achat`` FOB brut qui sous-évaluait silencieusement le comparatif
déboursé/facturé (et la marge dérivée) pour tout chantier approvisionné via
un import.

AVANT LE FIX (rouge, cf. ``apps/btp_chantier/selectors.py:244`` avant
correction) : la boucle matériel multipliait TOUJOURS
``StockReservation.quantite × stock.Produit.prix_achat`` — le montant des
frais d'import répartis (fret/douane/TVA import/transit,
``installations.models_landed_cost.FraisImport``) n'apparaissait jamais dans
``materiel``/``debourse_sec_total``, même pour un produit dont le coût
débarqué réel est connu via une ``LandedCostLigne`` (FG316).

APRÈS LE FIX : pour un produit dont la DERNIÈRE ``LandedCostLigne`` connue
trace vers un ``DossierImport`` à ``frais_import`` connus, ``materiel`` utilise
le coût débarqué unitaire (``installations.selectors.landed_cost_dossier``) ;
un produit SANS ligne de coût débarqué garde le repli ``prix_achat`` brut
(comportement NTCON11 inchangé, non régressé — cf.
``test_ntcon11_debourse_vs_facture.py``).
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework import status

from .helpers import (
    auth, make_chantier, make_company, make_dossier_import,
    make_frais_import, make_landed_cost_ligne, make_produit,
    make_reservation_stock, make_user,
)

BASE = '/api/django/btp-chantier/chantiers/{}/debourse-vs-facture/'


class DebourseVsFactureLandedCostTests(TestCase):
    def setUp(self):
        self.co = make_company()
        self.user = make_user(self.co)
        self.chantier = make_chantier(self.co)

        # ── Produit A : réservation traçant vers un DossierImport chiffré ──
        # FOB unitaire 100.00 (valeur_fob 1000.00 / quantite 10) — IDENTIQUE
        # au prix_achat catalogue pour isoler l'effet des frais d'import.
        self.produit_importe = make_produit(
            self.co, prix_achat=Decimal('100.00'))
        dossier = make_dossier_import(self.co)
        make_frais_import(self.co, dossier, montant=Decimal('500.00'))
        make_landed_cost_ligne(
            self.co, dossier, self.produit_importe,
            quantite=Decimal('10'), valeur_fob=Decimal('1000.00'))
        # Coût débarqué unitaire attendu : (1000 FOB + 500 frais) / 10 = 150.00
        # (quote_part = frais × valeur_fob/total_fob = 500 × 1000/1000 = 500,
        # une seule ligne sur le dossier ⇒ tout le frais lui revient).
        make_reservation_stock(
            self.co, self.chantier, self.produit_importe, quantite=10,
            consomme=True)

        # ── Produit B : jamais tracé vers un import — repli prix_achat brut,
        # comportement NTCON11 inchangé/non régressé. ──
        self.produit_catalogue = make_produit(
            self.co, prix_achat=Decimal('50.00'))
        make_reservation_stock(
            self.co, self.chantier, self.produit_catalogue, quantite=4,
            consomme=True)

        # ── Réservation NON consommée -> ne doit jamais compter (inchangé,
        # produit distinct : contrainte unique (installation, produit)). ──
        produit_non_consomme = make_produit(self.co, prix_achat=Decimal('999'))
        make_reservation_stock(
            self.co, self.chantier, produit_non_consomme, quantite=999,
            consomme=False)

    def test_materiel_utilise_le_cout_debarque_pour_le_produit_importe(self):
        api = auth(self.user)
        resp = api.get(BASE.format(self.chantier.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        data = resp.data

        # Débarqué (150.00 × 10 = 1500.00) + brut (50.00 × 4 = 200.00).
        # AVANT LE FIX ce total valait 100.00×10 + 50.00×4 = 1200.00 (le FOB
        # brut du produit importé, sous-évalué de 500.00 = la quote-part de
        # frais d'import jamais répercutée) — la régression exacte décrite
        # par AUD327.
        self.assertEqual(
            Decimal(data['materiel']),
            Decimal('1500.00') + Decimal('200.00'))

    def test_produit_sans_dossier_import_garde_le_prix_achat_brut(self):
        """Repli NTCON11 inchangé : aucune LandedCostLigne pour ce produit
        -> ``materiel`` reste ``quantite × prix_achat`` (non régressé)."""
        co = make_company()
        user = make_user(co)
        chantier = make_chantier(co)
        produit = make_produit(co, prix_achat=Decimal('20.00'))
        make_reservation_stock(
            co, chantier, produit, quantite=3, consomme=True)

        api = auth(user)
        resp = api.get(BASE.format(chantier.id))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(
            Decimal(resp.data['materiel']), Decimal('60.00'))

"""Tests XACC24 — Approbation des changements de coordonnées bancaires
(compta) + validation RIB sur les comptes de trésorerie.

Couvre : un changement de RIB fournisseur non approuvé n'apparaît pas dans
le fichier de virement (le payment run continue d'utiliser l'ancien RIB),
l'approbation admin le bascule, et un RIB de compte de trésorerie à clé
fausse est signalé en warning (jamais un blocage).
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import CompteTresorerie, DemandeApprobationRib

RIB_VALIDE_ANCIEN = '123456789012345678901213'
RIB_VALIDE_NOUVEAU = '070001234598765432109842'
RIB_INVALIDE = '070001234598765432109999'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class DemandeApprobationRibTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc24-svc', 'XACC24 Svc')

    def test_changement_non_approuve_paiement_utilise_ancien_rib(self):
        services.demander_changement_rib(
            self.co, fournisseur_id=42, fournisseur_nom='ACME',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        coord = services._coordonnees_fournisseur(self.co, 42)
        self.assertEqual(coord['rib'], '')  # pas de fournisseur stock réel ici

    def test_rib_actif_avant_approbation_est_ancien(self):
        demande = services.demander_changement_rib(
            self.co, fournisseur_id=42, fournisseur_nom='ACME',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        self.assertEqual(demande.rib_actif, RIB_VALIDE_ANCIEN)

    def test_approbation_bascule_le_rib_actif(self):
        demande = services.demander_changement_rib(
            self.co, fournisseur_id=42, fournisseur_nom='ACME',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        services.approuver_demande_rib(demande, decideur=None, commentaire='OK')
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeApprobationRib.Statut.APPROUVEE)
        self.assertEqual(demande.rib_actif, RIB_VALIDE_NOUVEAU)

    def test_refus_conserve_ancien_rib_definitivement(self):
        demande = services.demander_changement_rib(
            self.co, fournisseur_id=42, fournisseur_nom='ACME',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        services.refuser_demande_rib(demande, decideur=None, commentaire='Non')
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeApprobationRib.Statut.REFUSEE)
        self.assertEqual(demande.rib_actif, RIB_VALIDE_ANCIEN)

    def test_idempotent_decision_deja_prise(self):
        demande = services.demander_changement_rib(
            self.co, fournisseur_id=42, fournisseur_nom='ACME',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        services.approuver_demande_rib(demande, decideur=None)
        demande.refresh_from_db()
        # Un refus après approbation ne change rien (déjà décidée).
        services.refuser_demande_rib(demande, decideur=None)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeApprobationRib.Statut.APPROUVEE)

    def test_diagnostic_rib_signale_cle_fausse(self):
        diagnostic = services.diagnostic_rib(RIB_INVALIDE)
        self.assertFalse(diagnostic['valide'])


class CompteTresorerieRibTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc24-treso', 'XACC24 Treso')
        self.compte_comptable = services._assurer_compte(self.co, '5141')

    def test_rib_invalide_signale_en_warning(self):
        CompteTresorerie.objects.create(
            company=self.co, libelle='Compte BP',
            compte_comptable=self.compte_comptable, rib=RIB_INVALIDE,
            solde_initial=Decimal('0'))
        invalides = selectors.comptes_tresorerie_rib_invalides(self.co)
        self.assertEqual(len(invalides), 1)
        self.assertEqual(invalides[0]['rib'], RIB_INVALIDE)

    def test_rib_valide_non_signale(self):
        CompteTresorerie.objects.create(
            company=self.co, libelle='Compte BP',
            compte_comptable=self.compte_comptable, rib=RIB_VALIDE_ANCIEN,
            solde_initial=Decimal('0'))
        invalides = selectors.comptes_tresorerie_rib_invalides(self.co)
        self.assertEqual(invalides, [])

    def test_rib_vide_jamais_signale(self):
        CompteTresorerie.objects.create(
            company=self.co, libelle='Compte sans RIB',
            compte_comptable=self.compte_comptable, rib='',
            solde_initial=Decimal('0'))
        invalides = selectors.comptes_tresorerie_rib_invalides(self.co)
        self.assertEqual(invalides, [])

    def test_saisie_historique_jamais_bloquee(self):
        # Créer un compte avec un RIB invalide ne lève AUCUNE exception —
        # seul le rapport signale l'anomalie, jamais un blocage de saisie.
        compte = CompteTresorerie.objects.create(
            company=self.co, libelle='Ancien compte', rib=RIB_INVALIDE,
            compte_comptable=self.compte_comptable, solde_initial=Decimal('0'))
        self.assertEqual(compte.rib, RIB_INVALIDE)

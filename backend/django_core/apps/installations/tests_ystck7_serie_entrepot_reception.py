"""YSTCK7 — Réception BCF peuple automatiquement le registre entrepôt
(SerieEntrepot) depuis les séries capturées (`numeros_serie`, FG61/DC37).

Avant : `confirm_reception_fournisseur` ne créait AUCUN `SerieEntrepot` — le
registre devait être peuplé à la main. Couvre :

  * confirmer une réception avec 5 séries crée 5 entrées `SerieEntrepot`
    « en stock » ;
  * re-confirmer / ré-émettre l'événement n'en double aucune (idempotence) ;
  * une série déjà enregistrée (autre réception) n'est pas dupliquée ;
  * une ligne sans série ne crée rien (no-op) ;
  * isolation multi-tenant (unique_together company+produit+numero_serie).

Run :
    python manage.py test \
        apps.installations.tests_ystck7_serie_entrepot_reception -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.installations.models import SerieEntrepot
from apps.installations.services import peupler_series_entrepot_reception
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import confirm_reception_fournisseur

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_produit(company, nom, prix_vente=100):
    return Produit.objects.create(company=company, nom=nom, prix_vente=prix_vente)


def make_reception_avec_series(company, produit, user, quantite, series):
    fournisseur = Fournisseur.objects.create(
        company=company, nom=f'Fourn-{produit.id}')
    bc = BonCommandeFournisseur.objects.create(
        company=company, fournisseur=fournisseur, reference=f'BC-{produit.id}')
    ligne_cmd = LigneBonCommandeFournisseur.objects.create(
        bon_commande=bc, produit=produit, quantite=quantite,
        prix_achat_unitaire=10)
    reception = ReceptionFournisseur.objects.create(
        company=company, reference=f'REC-{produit.id}', bon_commande=bc)
    LigneReceptionFournisseur.objects.create(
        reception=reception, ligne_commande=ligne_cmd, produit=produit,
        quantite=quantite, numeros_serie=series)
    return reception, bc


class TestPeuplerSerieEntrepotAReception(TestCase):
    def setUp(self):
        self.company = make_company('co-ystck7', 'CoYstck7')
        self.user = make_user(self.company, 'resp-ystck7')
        self.produit = make_produit(self.company, 'Onduleur Y')

    def test_confirmation_avec_5_series_cree_5_entrees(self):
        series = [f'SN{i:03d}' for i in range(5)]
        reception, _bc = make_reception_avec_series(
            self.company, self.produit, self.user, quantite=5, series=series)
        confirm_reception_fournisseur(reception, self.user)

        entries = SerieEntrepot.objects.filter(
            company=self.company, produit=self.produit)
        self.assertEqual(entries.count(), 5)
        for e in entries:
            self.assertEqual(e.statut, SerieEntrepot.Statut.EN_STOCK)
            self.assertEqual(e.reference_reception, reception.reference)

    def test_reconfirmer_evenement_idempotent(self):
        series = ['SN-A', 'SN-B']
        reception, _bc = make_reception_avec_series(
            self.company, self.produit, self.user, quantite=2, series=series)
        confirm_reception_fournisseur(reception, self.user)
        # Ré-appel direct du service (simule une seconde émission) — idempotent.
        peupler_series_entrepot_reception(
            reception=reception, company=self.company, user=self.user)
        self.assertEqual(
            SerieEntrepot.objects.filter(
                company=self.company, produit=self.produit).count(),
            2)

    def test_serie_deja_enregistree_pas_dupliquee(self):
        SerieEntrepot.objects.create(
            company=self.company, produit=self.produit, numero_serie='SN-X')
        series = ['SN-X', 'SN-Y']
        reception, _bc = make_reception_avec_series(
            self.company, self.produit, self.user, quantite=2, series=series)
        confirm_reception_fournisseur(reception, self.user)
        self.assertEqual(
            SerieEntrepot.objects.filter(
                company=self.company, produit=self.produit,
                numero_serie='SN-X').count(),
            1)
        self.assertTrue(
            SerieEntrepot.objects.filter(
                company=self.company, produit=self.produit,
                numero_serie='SN-Y').exists())

    def test_ligne_sans_serie_ne_cree_rien(self):
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fourn-sans-serie')
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, fournisseur=fournisseur, reference='BC-NS')
        ligne_cmd = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=3,
            prix_achat_unitaire=10)
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-NS', bon_commande=bc)
        LigneReceptionFournisseur.objects.create(
            reception=reception, ligne_commande=ligne_cmd,
            produit=self.produit, quantite=3, numeros_serie=None)
        confirm_reception_fournisseur(reception, self.user)
        self.assertFalse(
            SerieEntrepot.objects.filter(
                company=self.company, produit=self.produit).exists())

    def test_isolation_tenant_meme_numero_serie(self):
        other_company = make_company('co-ystck7-b', 'CoYstck7B')
        other_user = make_user(other_company, 'resp-ystck7-b')
        other_produit = make_produit(other_company, 'Onduleur Z')
        reception, _bc = make_reception_avec_series(
            self.company, self.produit, self.user, quantite=1,
            series=['SN-SHARED'])
        confirm_reception_fournisseur(reception, self.user)
        reception2, _bc2 = make_reception_avec_series(
            other_company, other_produit, other_user, quantite=1,
            series=['SN-SHARED'])
        confirm_reception_fournisseur(reception2, other_user)
        self.assertEqual(
            SerieEntrepot.objects.filter(numero_serie='SN-SHARED').count(), 2)

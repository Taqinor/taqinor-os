"""XSTK17 — Profils saisonniers de seuils min/max (saison pompage).

Couvre :
  * en saison (mois courant dans la fenêtre), le seuil saisonnier prime sur
    `seuil_alerte` (un produit peut apparaître dans les besoins de réappro
    même avec un `seuil_alerte` à 0, tant qu'un profil actif le couvre) ;
  * hors saison, `produits_a_reapprovisionner` reste BYTE-IDENTIQUE au
    comportement historique (repli sur `seuil_alerte` /
    `quantite_reappro_cible`) ;
  * un profil peut cibler une CATÉGORIE (tous ses produits) ;
  * chevauchement de deux profils de la MÊME cible → refusé ;
  * deux profils sur des cibles DIFFÉRENTES ne se gênent jamais ;
  * `ProfilSaisonnier` exige produit XOR catégorie (jamais les deux, jamais
    aucun) ;
  * une fenêtre qui boucle l'année (ex. nov→fév) est bien couverte.

Run:
    python manage.py test apps.stock.test_xstk17_profil_saisonnier -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import Categorie, Produit, ProfilSaisonnier
from apps.stock.services import (
    creer_profil_saisonnier, produits_a_reapprovisionner,
    seuil_effectif_produit,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username):
    role = Role.objects.create(company=company, nom=f'r-{username}')
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


class Xstk17Base(TestCase):
    def setUp(self):
        self.company = _company('xstk17-co')
        self.user = _user(self.company, 'xstk17-user')
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Pompage X17')


class TestModelXorConstraint(Xstk17Base):
    def test_produit_xor_categorie_via_service(self):
        with self.assertRaises(ValueError):
            creer_profil_saisonnier(
                self.company, mois_debut=5, mois_fin=8)  # ni l'un ni l'autre

    def test_produit_et_categorie_ensemble_refuse(self):
        produit = Produit.objects.create(
            company=self.company, nom='Pompe X17', prix_vente=Decimal('5000'))
        with self.assertRaises(ValueError):
            creer_profil_saisonnier(
                self.company, produit=produit, categorie=self.categorie,
                mois_debut=5, mois_fin=8)


class TestCouvreMois(TestCase):
    def test_fenetre_simple(self):
        p = ProfilSaisonnier(mois_debut=5, mois_fin=8)
        self.assertTrue(p.couvre_mois(6))
        self.assertFalse(p.couvre_mois(9))

    def test_fenetre_bouclee_annee(self):
        p = ProfilSaisonnier(mois_debut=11, mois_fin=2)
        self.assertTrue(p.couvre_mois(12))
        self.assertTrue(p.couvre_mois(1))
        self.assertFalse(p.couvre_mois(6))


class TestChevauchement(Xstk17Base):
    def test_chevauchement_meme_produit_refuse(self):
        produit = Produit.objects.create(
            company=self.company, nom='Pompe X17b', prix_vente=Decimal('5000'))
        creer_profil_saisonnier(
            self.company, produit=produit, mois_debut=4, mois_fin=8,
            seuil_min=10)
        with self.assertRaises(ValueError):
            creer_profil_saisonnier(
                self.company, produit=produit, mois_debut=6, mois_fin=10,
                seuil_min=15)

    def test_pas_de_chevauchement_cibles_differentes(self):
        p1 = Produit.objects.create(
            company=self.company, nom='Pompe X17c', prix_vente=Decimal('5000'))
        p2 = Produit.objects.create(
            company=self.company, nom='Pompe X17d', prix_vente=Decimal('5000'))
        creer_profil_saisonnier(
            self.company, produit=p1, mois_debut=4, mois_fin=8, seuil_min=10)
        # Même fenêtre calendaire, produit DIFFÉRENT : autorisé.
        creer_profil_saisonnier(
            self.company, produit=p2, mois_debut=4, mois_fin=8, seuil_min=5)
        self.assertEqual(ProfilSaisonnier.objects.count(), 2)


class TestSeuilEffectif(Xstk17Base):
    def test_hors_saison_repli_seuil_statique(self):
        produit = Produit.objects.create(
            company=self.company, nom='Pompe X17e', prix_vente=Decimal('5000'),
            seuil_alerte=3, quantite_reappro_cible=6)
        creer_profil_saisonnier(
            self.company, produit=produit, mois_debut=5, mois_fin=8,
            seuil_min=20, quantite_cible=40)
        # Mois HORS fenêtre (5-8) : décembre.
        seuil, cible = seuil_effectif_produit(
            self.company, produit, mois=12)
        self.assertEqual(seuil, 3)
        self.assertEqual(cible, 6)

    def test_en_saison_seuil_saisonnier_prime(self):
        produit = Produit.objects.create(
            company=self.company, nom='Pompe X17f', prix_vente=Decimal('5000'),
            seuil_alerte=3, quantite_reappro_cible=6)
        creer_profil_saisonnier(
            self.company, produit=produit, mois_debut=5, mois_fin=8,
            seuil_min=20, quantite_cible=40)
        seuil, cible = seuil_effectif_produit(self.company, produit, mois=6)
        self.assertEqual(seuil, 20)
        self.assertEqual(cible, 40)


class TestReapproHorsSaisonInchange(Xstk17Base):
    def test_hors_saison_byte_identique_sans_profil(self):
        produit = Produit.objects.create(
            company=self.company, nom='Panneau X17g', prix_vente=Decimal('1200'),
            quantite_stock=2, seuil_alerte=5)
        with mock.patch('django.utils.timezone.now') as mock_now:
            import datetime
            mock_now.return_value = datetime.datetime(2026, 1, 15)
            besoins = produits_a_reapprovisionner(self.company)
        item = next(b for b in besoins if b['produit_id'] == produit.id)
        self.assertEqual(item['quantite_suggere'], 10)  # seuil × 2 (inchangé)

    def test_produit_seuil_zero_reste_exclu_hors_saison(self):
        Produit.objects.create(
            company=self.company, nom='Panneau X17h', prix_vente=Decimal('1200'),
            quantite_stock=0, seuil_alerte=0)
        besoins = produits_a_reapprovisionner(self.company)
        self.assertEqual(besoins, [])


class TestReapproEnSaison(Xstk17Base):
    def test_produit_seuil_zero_apparait_en_saison_avec_profil(self):
        produit = Produit.objects.create(
            company=self.company, nom='Pompe X17i', prix_vente=Decimal('5000'),
            quantite_stock=8, seuil_alerte=0)
        creer_profil_saisonnier(
            self.company, produit=produit, mois_debut=1, mois_fin=12,
            seuil_min=10, quantite_cible=25)
        with mock.patch('django.utils.timezone.now') as mock_now:
            import datetime
            mock_now.return_value = datetime.datetime(2026, 6, 1)
            besoins = produits_a_reapprovisionner(self.company)
        item = next(
            (b for b in besoins if b['produit_id'] == produit.id), None)
        self.assertIsNotNone(item)
        self.assertEqual(item['quantite_suggere'], 25)

    def test_profil_categorie_couvre_tous_ses_produits(self):
        p1 = Produit.objects.create(
            company=self.company, nom='Pompe cat X17j',
            prix_vente=Decimal('5000'), quantite_stock=5, seuil_alerte=0,
            categorie=self.categorie)
        creer_profil_saisonnier(
            self.company, categorie=self.categorie, mois_debut=1,
            mois_fin=12, seuil_min=8, quantite_cible=20)
        with mock.patch('django.utils.timezone.now') as mock_now:
            import datetime
            mock_now.return_value = datetime.datetime(2026, 6, 1)
            besoins = produits_a_reapprovisionner(self.company)
        ids = [b['produit_id'] for b in besoins]
        self.assertIn(p1.id, ids)

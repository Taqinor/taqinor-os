"""NTWMS25 — suivi de palette en mouvement (license plate tracking).

Critère d'acceptation testé : déplacer une palette scellée de plusieurs lignes
vers un nouveau casier se fait en UN SEUL appel ; chaque ligne est tracée
casier→casier, et la ventilation par emplacement suit quand l'entrepôt change.

Run :
    python manage.py test apps.stock.test_ntwms25_deplacer_unite -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, MouvementStock, Produit, StockEmplacement,
    UniteLogistique,
)
from apps.stock.services import (
    ajouter_ligne_unite_logistique, creer_unite_logistique,
    deplacer_unite_logistique, sceller_unite_logistique,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms25Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinLocation

        self.company = make_company('ntwms25-co', 'NTWMS25 Co')
        self.autre = make_company('ntwms25-autre', 'NTWMS25 Autre')
        self.admin = User.objects.create_user(
            username='ntwms25_admin', password='x', role_legacy='admin',
            company=self.company)
        self.entrepot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS25', is_principal=True)
        self.annexe = EmplacementStock.objects.create(
            company=self.company, nom='Annexe NTWMS25')
        self.casier_a = BinLocation.objects.create(
            company=self.company, emplacement=self.entrepot, code='A-01-01',
            zone='A', allee='01', casier='01', ordre=10)
        self.casier_b = BinLocation.objects.create(
            company=self.company, emplacement=self.entrepot, code='B-02-04',
            zone='B', allee='02', casier='04', ordre=40)
        self.casier_annexe = BinLocation.objects.create(
            company=self.company, emplacement=self.annexe, code='X-01-01',
            zone='X', allee='01', casier='01', ordre=10)
        self.produits = [
            Produit.objects.create(
                company=self.company, nom=f'Produit {i}',
                sku=f'P{i}-NTWMS25', prix_achat=Decimal('100'),
                prix_vente=Decimal('150'), quantite_stock=100)
            for i in range(1, 5)
        ]
        self.api = auth(self.admin)

    def _palette(self, nb_lignes=4, bin_actuel=None):
        unite = creer_unite_logistique(
            company=self.company, type_unite='palette')
        for produit in self.produits[:nb_lignes]:
            ajouter_ligne_unite_logistique(
                company=self.company, unite=unite, produit=produit,
                quantite=5)
        unite.bin_actuel = bin_actuel or self.casier_a
        unite.save(update_fields=['bin_actuel'])
        return unite


class TestDeplacementUnite(Ntwms25Base):
    def test_un_seul_appel_deplace_toutes_les_lignes(self):
        palette = self._palette(nb_lignes=4)
        sceller_unite_logistique(unite=palette, user=self.admin)

        resultat = deplacer_unite_logistique(
            unite=palette, bin_destination=self.casier_b, user=self.admin)

        self.assertEqual(resultat['lignes_deplacees'], 4)
        palette.refresh_from_db()
        self.assertEqual(palette.bin_actuel_id, self.casier_b.id)
        mouvements = MouvementStock.objects.filter(
            company=self.company, unite_logistique=palette)
        self.assertEqual(mouvements.count(), 4)
        for mouvement in mouvements:
            self.assertEqual(mouvement.type_mouvement,
                             MouvementStock.TypeMouvement.TRANSFERT)
            self.assertEqual(mouvement.bin_source_id, self.casier_a.id)
            self.assertEqual(mouvement.bin_destination_id, self.casier_b.id)

    def test_le_total_du_produit_ne_bouge_pas(self):
        palette = self._palette(nb_lignes=2)
        deplacer_unite_logistique(
            unite=palette, bin_destination=self.casier_b, user=self.admin)
        for produit in self.produits[:2]:
            produit.refresh_from_db()
            self.assertEqual(produit.quantite_stock, 100)

    def test_changement_d_entrepot_met_a_jour_la_ventilation(self):
        palette = self._palette(nb_lignes=1)
        deplacer_unite_logistique(
            unite=palette, bin_destination=self.casier_annexe,
            user=self.admin)
        self.assertEqual(
            StockEmplacement.objects.get(
                produit=self.produits[0], emplacement=self.annexe).quantite,
            5)

    def test_palette_entraine_ses_colis_enfants(self):
        palette = self._palette(nb_lignes=1)
        colis = creer_unite_logistique(
            company=self.company, type_unite='colis', parent=palette)
        ajouter_ligne_unite_logistique(
            company=self.company, unite=colis, produit=self.produits[3],
            quantite=2)
        colis.bin_actuel = self.casier_a
        colis.save(update_fields=['bin_actuel'])

        resultat = deplacer_unite_logistique(
            unite=palette, bin_destination=self.casier_b, user=self.admin)

        self.assertEqual(resultat['lignes_deplacees'], 2)
        colis.refresh_from_db()
        self.assertEqual(colis.bin_actuel_id, self.casier_b.id)

    def test_unite_vide_refusee(self):
        vide = creer_unite_logistique(
            company=self.company, type_unite='colis')
        with self.assertRaises(ValueError):
            deplacer_unite_logistique(
                unite=vide, bin_destination=self.casier_b, user=self.admin)

    def test_unite_expediee_ne_bouge_plus(self):
        palette = self._palette(nb_lignes=1)
        palette.statut = UniteLogistique.Statut.EXPEDIE
        palette.save(update_fields=['statut'])
        with self.assertRaises(ValueError):
            deplacer_unite_logistique(
                unite=palette, bin_destination=self.casier_b, user=self.admin)

    def test_casier_absent_refuse(self):
        palette = self._palette(nb_lignes=1)
        with self.assertRaises(ValueError):
            deplacer_unite_logistique(
                unite=palette, bin_destination=None, user=self.admin)


class TestEndpointDeplacer(Ntwms25Base):
    def test_deplacer_via_api(self):
        palette = self._palette(nb_lignes=3)
        reponse = self.api.post(
            f'/api/django/stock/unites-logistiques/{palette.id}/deplacer/',
            {'bin_destination': self.casier_b.id}, format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['lignes_deplacees'], 3)
        self.assertEqual(reponse.data['bin_code'], 'B-02-04')

    def test_casier_hors_societe_refuse(self):
        from apps.installations.models import BinLocation
        emplacement_autre = EmplacementStock.objects.create(
            company=self.autre, nom='Dépôt autre', is_principal=True)
        casier_autre = BinLocation.objects.create(
            company=self.autre, emplacement=emplacement_autre,
            code='Z-09-09', ordre=10)
        palette = self._palette(nb_lignes=1)
        reponse = self.api.post(
            f'/api/django/stock/unites-logistiques/{palette.id}/deplacer/',
            {'bin_destination': casier_autre.id}, format='json')
        self.assertEqual(reponse.status_code, 400)

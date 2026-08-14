"""NTWMS41 — retour fournisseur guidé par le casier physique.

Critère d'acceptation testé : initier un retour fournisseur DEPUIS LE POSTE
SCANNER localise le produit et le retire du BON casier — sans ressaisie de
référence — et le mouvement de départ porte enfin son casier source ET son
casier de destination.

Run :
    python manage.py test apps.stock.test_ntwms41_retour_scanne -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, Fournisseur, LigneRetourFournisseur, MouvementStock,
    Produit, RetourFournisseur,
)
from apps.stock.services_retour_scanne import (
    casier_retours_fournisseur, deplacer_vers_casier_retours,
    preparer_ligne_retour_scannee, valider_retour_scanne,
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


class Ntwms41Base(TestCase):
    def setUp(self):
        from apps.installations.models import BinAffectation, BinLocation

        self.company = make_company('ntwms41-co', 'NTWMS41 Co')
        self.autre = make_company('ntwms41-autre', 'NTWMS41 Autre')
        self.admin = User.objects.create_user(
            username='ntwms41_admin', password='x', role_legacy='admin',
            company=self.company)
        self.magasinier = User.objects.create_user(
            username='ntwms41_magasinier', password='x', role_legacy='normal',
            company=self.company)
        self.emplacement = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS41', is_principal=True)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTWMS41')

        self.casier_stock = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-05-02', zone='A', allee='05', casier='02', ordre=50)
        self.casier_peu = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='A-06-01', zone='A', allee='06', casier='01', ordre=60)
        self.casier_departs = BinLocation.objects.create(
            company=self.company, emplacement=self.emplacement,
            code='EXP-01', zone='EXP', allee='01', casier='01', ordre=990)

        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur défectueux 5 kW',
            sku='OND5-NTWMS41', code_barres='3401234567890',
            fournisseur=self.fournisseur, prix_achat=Decimal('7000'),
            prix_vente=Decimal('9000'), quantite_stock=20)
        BinAffectation.objects.create(
            company=self.company, bin=self.casier_stock, produit=self.produit,
            quantite=15)
        BinAffectation.objects.create(
            company=self.company, bin=self.casier_peu, produit=self.produit,
            quantite=2)

    def _retour(self, quantite=3):
        retour = RetourFournisseur.objects.create(
            company=self.company, reference='RET-NTWMS41-0001',
            fournisseur=self.fournisseur)
        LigneRetourFournisseur.objects.create(
            retour=retour, produit=self.produit, quantite=quantite,
            motif='Défaut usine')
        return retour


class Ntwms41ScanTests(Ntwms41Base):
    def test_le_scan_du_gtin_prerempli_la_ligne_et_le_casier(self):
        ligne = preparer_ligne_retour_scannee(
            self.company, '3401234567890', quantite=3)

        self.assertEqual(ligne['produit'], self.produit.id)
        self.assertEqual(ligne['sku'], 'OND5-NTWMS41')
        self.assertEqual(ligne['quantite'], 3)
        # Casier le PLUS rempli : celui où le magasinier ira vraiment.
        self.assertEqual(ligne['bin_source'], self.casier_stock.id)
        self.assertEqual(ligne['bin_source_code'], 'A-05-02')
        self.assertEqual(ligne['bin_destination'], self.casier_departs.id)
        self.assertEqual(ligne['fournisseur'], self.fournisseur.id)

    def test_le_scan_du_sku_marche_aussi(self):
        ligne = preparer_ligne_retour_scannee(self.company, 'OND5-NTWMS41')
        self.assertEqual(ligne['produit'], self.produit.id)

    def test_un_code_inconnu_ou_une_quantite_nulle_sont_refuses(self):
        with self.assertRaises(ValueError):
            preparer_ligne_retour_scannee(self.company, 'CODE-BIDON')
        with self.assertRaises(ValueError):
            preparer_ligne_retour_scannee(
                self.company, 'OND5-NTWMS41', quantite=0)

    def test_scanner_un_casier_demande_de_scanner_le_produit(self):
        with self.assertRaises(ValueError) as ctx:
            preparer_ligne_retour_scannee(self.company, 'A-05-02')
        self.assertIn('scannez le produit', str(ctx.exception))

    def test_le_casier_de_departs_est_resolu_par_convention(self):
        casier = casier_retours_fournisseur(self.company)
        self.assertEqual(casier.id, self.casier_departs.id)

    def test_sans_casier_de_departs_rien_nest_bloque(self):
        self.casier_departs.archived = True
        self.casier_departs.save(update_fields=['archived'])
        ligne = preparer_ligne_retour_scannee(self.company, 'OND5-NTWMS41')
        self.assertIsNone(ligne['bin_destination'])
        self.assertIsNone(deplacer_vers_casier_retours(
            self.company, self.admin, produit=self.produit, quantite=1))


class Ntwms41DeplacementTests(Ntwms41Base):
    def test_le_deplacement_trace_source_et_destination_sans_bouger_le_total(
            self):
        avant = self.produit.quantite_stock
        mouvement = deplacer_vers_casier_retours(
            self.company, self.admin, produit=self.produit, quantite=3,
            bin_source=self.casier_stock.id, reference='RET-NTWMS41-0001')

        self.assertEqual(mouvement.type_mouvement,
                         MouvementStock.TypeMouvement.TRANSFERT)
        self.assertEqual(mouvement.bin_source_id, self.casier_stock.id)
        self.assertEqual(mouvement.bin_destination_id,
                         self.casier_departs.id)
        self.assertEqual(mouvement.quantite_avant, avant)
        self.assertEqual(mouvement.quantite_apres, avant)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, avant)

    def test_la_validation_scannee_deplace_puis_sort_le_stock(self):
        retour = self._retour(quantite=3)
        valider_retour_scanne(
            retour, self.admin,
            bins_source={retour.lignes.first().id: self.casier_stock.id})

        retour.refresh_from_db()
        self.assertEqual(retour.statut, RetourFournisseur.Statut.VALIDE)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 17)

        transfert = MouvementStock.objects.get(
            company=self.company,
            type_mouvement=MouvementStock.TypeMouvement.TRANSFERT)
        self.assertEqual(transfert.bin_source_id, self.casier_stock.id)
        sortie = MouvementStock.objects.get(
            company=self.company,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE)
        self.assertEqual(sortie.quantite, 3)

    def test_un_retour_deja_valide_nest_jamais_rejoue(self):
        retour = self._retour(quantite=2)
        valider_retour_scanne(retour, self.admin)
        with self.assertRaises(ValueError):
            valider_retour_scanne(retour, self.admin)


class Ntwms41ApiTests(Ntwms41Base):
    URL = '/api/django/stock/scanner/retour-fournisseur/'

    def test_le_magasinier_prerempli_sa_ligne_par_scan(self):
        res = auth(self.magasinier).get(
            self.URL, {'code': '3401234567890', 'quantite': 2})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['produit'], self.produit.id)
        self.assertEqual(res.data['bin_source_code'], 'A-05-02')

    def test_code_inconnu_renvoie_400_et_jamais_500(self):
        res = auth(self.magasinier).get(self.URL, {'code': 'INEXISTANT'})
        self.assertEqual(res.status_code, 400)

    def test_endpoint_refuse_lanonyme(self):
        self.assertEqual(APIClient().get(self.URL).status_code, 401)

    def test_action_valider_scanne(self):
        retour = self._retour(quantite=1)
        res = auth(self.admin).post(
            f'/api/django/stock/retours-fournisseur/{retour.id}/'
            'valider-scanne/', {'bins_source': {}}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['statut'],
                         RetourFournisseur.Statut.VALIDE)

    def test_action_valider_scanne_refusee_a_un_role_normal(self):
        retour = self._retour(quantite=1)
        res = auth(self.magasinier).post(
            f'/api/django/stock/retours-fournisseur/{retour.id}/'
            'valider-scanne/', {}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_un_produit_dune_autre_societe_reste_invisible(self):
        Produit.objects.create(
            company=self.autre, nom='Voisin', sku='VOISIN-41',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=1)
        res = auth(self.magasinier).get(self.URL, {'code': 'VOISIN-41'})
        self.assertEqual(res.status_code, 400)

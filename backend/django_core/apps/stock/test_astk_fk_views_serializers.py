"""ASTK7 (C-ASTK-001) — les sérialiseurs DÉCLARÉS dans apps/stock/views/*.py
et les ids bruts des services n'acceptent plus l'id d'une autre société.

Sondes d'origine : FOUR-1 (incident qualité sur le fournisseur de B → 201,
``fournisseur_nom`` = FOURNISSEUR-B-SECRET, puis la suppression du
fournisseur de B levait ``ProtectedError``) ; TEN-6(5) (PATCH consignation
vers un client de B → 200) ; TEN-6(8) (accord RFA sur un fournisseur de B →
201).

Désormais : ``CompanyScopedRelationsMixin`` sur chaque sérialiseur de ces
vues, ``creer_depot_consignation`` relit le client borné à la société, et
``valider_retour_scanne`` relit les casiers sources bornés à la société.
Réponse : 400 « objet inexistant », comme l'id 99999999.

Aucun mock : mixin core, vues et services réels.

Run :
    python manage.py test apps.stock.test_astk_fk_views_serializers -v 2
"""
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    Categorie, DepotConsignation, EmplacementStock, Fournisseur,
    IncidentQualiteFournisseur, LigneRetourFournisseur, MouvementStock,
    Produit, RetourFournisseur,
)
from apps.stock.services_consignation import creer_depot_consignation

User = get_user_model()

BASE = '/api/django/stock'
JOUR = '2026-10-01'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class FkViewsSerializersTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.installations.models import BinLocation

        self.a = make_company('astk7-a', 'ASTK7 A')
        self.b = make_company('astk7-b', 'ASTK7 B')
        self.resp_a = User.objects.create_user(
            username='astk7_resp_a', password='x', role_legacy='responsable',
            company=self.a)
        self.api = auth_client(self.resp_a)

        # --- A -----------------------------------------------------------
        self.fa = Fournisseur.objects.create(company=self.a, nom='Fourn. A')
        self.pa = Produit.objects.create(
            company=self.a, nom='ProdA', sku='ASTK7-PA', fournisseur=self.fa,
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=50)
        self.client_a = Client.objects.create(
            company=self.a, nom='Client A ASTK7')
        emp_a = EmplacementStock.objects.create(
            company=self.a, nom='Dépôt A', is_principal=True)
        self.bin_a = BinLocation.objects.create(
            company=self.a, emplacement=emp_a, code='A-07-01')
        self.bin_exp_a = BinLocation.objects.create(
            company=self.a, emplacement=emp_a, code='EXP-07', ordre=990)

        # --- B -----------------------------------------------------------
        self.fb = Fournisseur.objects.create(
            company=self.b, nom='FOURNISSEUR-B-SECRET')
        self.pb = Produit.objects.create(
            company=self.b, nom='ProdB-secret', sku='ASTK7-PB',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=5)
        self.client_b = Client.objects.create(
            company=self.b, nom='CLIENT-B-SECRET')
        self.cat_b = Categorie.objects.create(company=self.b, nom='Cat B')
        emp_b = EmplacementStock.objects.create(
            company=self.b, nom='Dépôt B', is_principal=True)
        self.bin_b = BinLocation.objects.create(
            company=self.b, emplacement=emp_b, code='B-07-SECRET')

    def assertObjetInexistant(self, reponse, champ):
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn(champ, reponse.data, reponse.content)
        self.assertEqual(reponse.data[champ][0].code, 'does_not_exist',
                         reponse.content)

    # --- incident qualité fournisseur (FOUR-1) ------------------------------
    def test_incident_fournisseur_etranger(self):
        corps = {'type_incident': 'autre', 'gravite': 'mineure',
                 'date_incident': JOUR}
        r = self.api.post(f'{BASE}/incidents-qualite-fournisseur/',
                          {**corps, 'fournisseur': self.fb.id}, format='json')
        self.assertObjetInexistant(r, 'fournisseur')
        self.assertNotIn('FOURNISSEUR-B-SECRET', r.content.decode('utf-8'))
        inconnu = self.api.post(f'{BASE}/incidents-qualite-fournisseur/',
                                {**corps, 'fournisseur': 99999999},
                                format='json')
        self.assertObjetInexistant(inconnu, 'fournisseur')
        self.assertFalse(IncidentQualiteFournisseur.objects.exists())
        # Le fournisseur de B reste supprimable (aucun incident de A ne le
        # PROTÈGE).
        self.fb.delete()
        self.assertFalse(Fournisseur.objects.filter(pk=self.fb.pk).exists())

    # --- accord RFA (TEN-6(8)) ----------------------------------------------
    def test_rfa_fournisseur_etranger(self):
        r = self.api.post(f'{BASE}/accords-rfa-fournisseur/', {
            'fournisseur': self.fb.id, 'periode_debut': '2026-01-01',
            'periode_fin': '2026-12-31', 'taux_pct': '2'}, format='json')
        self.assertObjetInexistant(r, 'fournisseur')

    # --- consignation (TEN-6(5)) --------------------------------------------
    def test_consignation_client_etranger(self):
        depot = creer_depot_consignation(
            company=self.a, user=self.resp_a, client_id=self.client_a.id,
            produit_id=self.pa.id, quantite=2, date_depot=JOUR)
        r = self.api.patch(f'{BASE}/consignations/{depot.id}/', {
            'client': self.client_b.id}, format='json')
        self.assertObjetInexistant(r, 'client')
        depot.refresh_from_db()
        self.assertEqual(depot.client_id, self.client_a.id)

        avant = DepotConsignation.objects.count()
        with self.assertRaises(ValueError):
            creer_depot_consignation(
                company=self.a, user=self.resp_a, client_id=self.client_b.id,
                produit_id=self.pa.id, quantite=1, date_depot=JOUR)
        r = self.api.post(f'{BASE}/consignations/', {
            'client': self.client_b.id, 'produit': self.pa.id,
            'quantite_deposee': 1, 'date_depot': JOUR}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(DepotConsignation.objects.count(), avant)
        self.pa.refresh_from_db()
        self.assertEqual(self.pa.quantite_stock, 48)

    def test_export_consignations_jamais_un_client_de_b(self):
        from openpyxl import load_workbook

        depot = creer_depot_consignation(
            company=self.a, user=self.resp_a, client_id=self.client_a.id,
            produit_id=self.pa.id, quantite=2, date_depot=JOUR)
        # État hérité d'avant la borne : client de B injecté en base.
        DepotConsignation.objects.filter(pk=depot.pk).update(
            client=self.client_b)
        r = self.api.get(f'{BASE}/consignations/export-xlsx/')
        self.assertEqual(r.status_code, 200)
        feuille = load_workbook(io.BytesIO(r.content)).active
        valeurs = [str(c.value) for ligne in feuille.iter_rows()
                   for c in ligne if c.value is not None]
        self.assertNotIn('CLIENT-B-SECRET', valeurs)

    # --- autres sérialiseurs déclarés dans les vues -------------------------
    def test_hazmat_casier_etranger(self):
        r = self.api.post(f'{BASE}/casiers-hazmat/', {
            'bin': self.bin_b.id, 'classe_danger': 'BATTERIE_LITHIUM'},
            format='json')
        self.assertObjetInexistant(r, 'bin')

    def test_onboarding_fournisseur_etranger(self):
        r = self.api.post(f'{BASE}/dossiers-onboarding-fournisseur/', {
            'fournisseur': self.fb.id}, format='json')
        self.assertObjetInexistant(r, 'fournisseur')

    def test_profil_saisonnier_produit_etranger(self):
        r = self.api.post(f'{BASE}/profils-saisonniers/', {
            'produit': self.pb.id, 'mois_debut': 1, 'mois_fin': 3,
            'seuil_min': 1, 'nom': 'Hiver'}, format='json')
        self.assertObjetInexistant(r, 'produit')

    def test_plan_echantillonnage_categorie_etrangere(self):
        r = self.api.post(f'{BASE}/plans-echantillonnage/', {
            'categorie': self.cat_b.id, 'taux_echantillon_pct': 10},
            format='json')
        self.assertObjetInexistant(r, 'categorie')

    def test_reappro_casier_etranger(self):
        r = self.api.post(f'{BASE}/seuils-reappro-casier/', {
            'bin': self.bin_b.id, 'produit': self.pa.id, 'seuil': 1,
            'quantite_cible': 5}, format='json')
        self.assertObjetInexistant(r, 'bin')
        r = self.api.post(f'{BASE}/taches-reappro-interne/', {
            'produit': self.pb.id, 'bin_cible': self.bin_a.id,
            'quantite': 1}, format='json')
        self.assertObjetInexistant(r, 'produit')

    # --- retour fournisseur scanné : bins_source bornés ---------------------
    def test_valider_scanne_casier_source_etranger(self):
        retour = RetourFournisseur.objects.create(
            company=self.a, reference='RET-ASTK7-0001', fournisseur=self.fa)
        ligne = LigneRetourFournisseur.objects.create(
            retour=retour, produit=self.pa, quantite=1, motif='Défaut')
        r = self.api.post(
            f'{BASE}/retours-fournisseur/{retour.id}/valider-scanne/',
            {'bins_source': {str(ligne.id): self.bin_b.id}}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        retour.refresh_from_db()
        self.assertEqual(retour.statut, RetourFournisseur.Statut.BROUILLON)
        self.assertFalse(MouvementStock.objects.filter(
            reference='RET-ASTK7-0001').exists())
        self.pa.refresh_from_db()
        self.assertEqual(self.pa.quantite_stock, 50)

    # --- ENF17 : FK en lecture seule des sérialiseurs restants ---------------
    def test_enf17_fk_lecture_seule_jamais_ecrites(self):
        """Un id de B posté sur ces FK en lecture seule n'est jamais écrit ;
        chaque sérialiseur porte le mixin qui les bornerait sinon."""
        from types import SimpleNamespace

        from core.serializers import CompanyScopedRelationsMixin
        from apps.stock.serializers import (
            LotEntrepotSerializer, RevisionKitSerializer,
        )
        from apps.stock.views.budget_departement import (
            EngagementBudgetSerializer,
        )
        from apps.stock.views.catalogue_achat import CatalogueAchatSerializer

        ctx = {'request': SimpleNamespace(user=self.resp_a)}
        cas = (
            (RevisionKitSerializer, {'kit': self.pb.pk, 'user': 1}),
            (LotEntrepotSerializer, {'produit': self.pb.pk,
                                     'emplacement': self.bin_b.emplacement_id}),
            (EngagementBudgetSerializer, {'budget': 1, 'demande_achat': 1,
                                          'bon_commande': 1}),
            (CatalogueAchatSerializer, {'categorie': self.cat_b.pk}),
        )
        for cls, corps in cas:
            with self.subTest(serializer=cls.__name__):
                self.assertTrue(issubclass(cls, CompanyScopedRelationsMixin))
                ser = cls(data=corps, partial=True, context=ctx)
                self.assertTrue(ser.is_valid(), ser.errors)
                for champ in corps:
                    self.assertNotIn(champ, ser.validated_data)


class CorpsFuzzTests(TestCase):
    """ERR fuzz (api-fuzz-pr #986, stock) — corps non objet, ids non entiers et
    champs plus lâches que leur schéma : 400 (ou 409 pour un doublon), jamais
    500 ni acceptation silencieuse."""

    def setUp(self):
        from apps.stock.models import KitProduit, ModeleBonCommandeFournisseur
        self.a = make_company('fuzz-stock-a', 'Fuzz stock A')
        self.admin = User.objects.create_user(
            username='fuzz_stock_admin', password='x', role_legacy='admin',
            company=self.a)
        self.api = auth_client(self.admin)
        self.fa = Fournisseur.objects.create(company=self.a, nom='Fourn. F')
        self.pa = Produit.objects.create(
            company=self.a, nom='ProdF', sku='FUZZ-PA', fournisseur=self.fa,
            prix_achat=Decimal('10'), prix_vente=Decimal('20'))
        self.emp = EmplacementStock.objects.create(
            company=self.a, nom='Dépôt F', is_principal=True)
        self.kit = KitProduit.objects.create(company=self.a, nom='Kit F')
        self.modele = ModeleBonCommandeFournisseur.objects.create(
            company=self.a, nom='Modèle F')

    def test_fuzz_corps_non_objet_400(self):
        cas = [('post', '/api/django/achats/paiements-fournisseur/')] + [
            ('post', f'{BASE}/{fin}') for fin in (
                'paiements-fournisseur/', 'consignations/', 'mouvements-rebut/',
                'retours-client/', 'scanner/mouvement/', 'transferts/',
                'transferts/demander/', f'kits/{self.kit.id}/dupliquer/',
                'kits/remplacer-composant/')] + [
            (m, f'{BASE}/emplacements/{self.emp.id}/') for m in ('put', 'patch')]
        for methode, url in cas:
            with self.subTest(url=url, methode=methode):
                r = getattr(self.api, methode)(url, [None, None], format='json')
                self.assertEqual(r.status_code, 400, r.content)

    def test_fuzz_ids_non_entiers_400(self):
        cas = (
            ('produits/generer-bcf-reappro/', {'fournisseur_id': [None, None]}),
            ('expeditions/', {'unite_logistique': {}, 'destination': ''}),
            ('produits/bulk/', {'action': 'set_price', 'ids': [{}], 'mode': '0',
                                'valeur': '0'}),
            ('produits/bulk/', {'action': {}, 'ids': [0]}),
            ('produits/bulk/', {'action': 'set_category', 'ids': [self.pa.id], 'categorie_id': {}}),
            ('produits/bulk/', {'action': 'set_brand', 'ids': [self.pa.id], 'marque': 5}),
            ('produits/bulk/', {'action': 'set_warranty', 'ids': [self.pa.id],
                                'garantie_mois': '99999999999'}),
            ('produits/decoupes/', {'produit_source': self.pa.id, 'produit_cible': {},
                                    'quantite_consommee': 1, 'quantite_produite': 1}),
        )
        for fin, corps in cas:
            with self.subTest(url=fin):
                r = self.api.post(f'{BASE}/{fin}', corps, format='json')
                self.assertEqual(r.status_code, 400, r.content)

    def test_fuzz_modele_bcf_lignes_et_note(self):
        url = f'{BASE}/modeles-bcf/{self.modele.id}/'
        for lignes in ([{'quantite': 0}], [{'produit': self.pa.id}, {'produit': self.pa.id}]):
            with self.subTest(lignes=lignes):
                r = self.api.patch(url, {'lignes': lignes}, format='json')
                self.assertEqual(r.status_code, 400, r.content)
        r = self.api.put(url, {'nom': 'M', 'note': 0, 'lignes': []}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.api.post(f'{BASE}/modeles-bcf/', {
            'nom': 'Neuf', 'note': 'ok', 'lignes': [{'produit': self.pa.id, 'quantite': 3}]},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['lignes'][0]['quantite'], 3)

    def test_fuzz_kits_booleens_stricts(self):
        url = f'{BASE}/kits/{self.kit.id}/'
        r = self.api.patch(url, {'is_archived': 0}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.api.get(f'{url}?avec_disponibilite=null&avec_disponibilite=null')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(self.api.get(f'{url}?avec_disponibilite=true').status_code, 200)
        r = self.api.get(f'{url}exploser/?quantite=null&quantite=null')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.api.put(url, {'nom': 'K', 'sku': 0, 'composants': []}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        for facteur, attendu in (('0', 400), (0.00001, 400), (2, 201)):
            with self.subTest(facteur=facteur):
                r = self.api.post(f'{url}dupliquer/', {'facteur_echelle': facteur}, format='json')
                self.assertEqual(r.status_code, attendu, r.content)

    def test_fuzz_prix_fournisseur_texte_strict(self):
        r = self.api.post(f'{BASE}/prix-fournisseurs/', {
            'produit': self.pa.id, 'fournisseur': self.fa.id, 'prix_achat': '5',
            'ref_produit_fournisseur': 0}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('ref_produit_fournisseur', r.data)

    def test_fuzz_fournisseur_et_inventaire_stricts(self):
        url = f'{BASE}/fournisseurs/'
        r = self.api.post(url, {'nom': 'F vide', 'frais_livraison_estimes': ''}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(r.data['frais_livraison_estimes'])
        r = self.api.post(url, {'nom': 'F nombre', 'frais_livraison_estimes': 12.5}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.api.post(url, {'nom': 7}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.api.post(url, {'nom': 'F escompte', 'escompte_pct': 0}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.api.post(f'{BASE}/inventaire-sessions/', {'motif': 0, 'lignes': []}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.api.post(f'{BASE}/inventaire-sessions/', {'motif': 'm', 'lignes': []}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        r = self.api.patch(f"{BASE}/inventaire-sessions/{r.data['id']}/",
                           {'lignes': [{'quantite_comptee': 1}]}, format='json')
        self.assertEqual(r.status_code, 400, r.content)

    def test_fuzz_bornes_publiees_et_doublon_409(self):
        from apps.stock.serializers_wms import PlanComptageTournantSerializer
        from apps.stock.views.qualite_reception import PlanEchantillonnageSerializer
        self.assertEqual(
            PlanEchantillonnageSerializer().fields['taux_echantillon_pct'].max_value, 100)
        self.assertEqual(
            PlanComptageTournantSerializer().fields['frequence_jours'].min_value, 1)
        r = self.api.post(f'{BASE}/plans-comptage-tournant/', {
            'classe_abc': 'A', 'frequence_jours': 1, 'actif': 0}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.api.post(f'{BASE}/plans-echantillonnage/', {
            'categorie': None, 'taux_echantillon_pct': 101, 'actif': False, 'note': ''},
            format='json')
        self.assertEqual(r.status_code, 400, r.content)
        # Rien à réapprovisionner = refus d'état (409), le corps était conforme.
        Produit.objects.filter(pk=self.pa.pk).update(quantite_stock=10000)
        r = self.api.post(f'{BASE}/produits/generer-bcf-reappro/', {'fournisseur_id': None},
                          format='json')
        self.assertEqual(r.status_code, 409, r.content)
        Categorie.objects.create(company=self.a, nom='Prise')
        autre = Categorie.objects.create(company=self.a, nom='Libre')
        r = self.api.patch(f'{BASE}/categories/{autre.id}/', {'nom': 'Prise'}, format='json')
        self.assertEqual(r.status_code, 409, r.content)

    def test_fuzz_budget_note_stricte_et_passage_annuel(self):
        url = f'{BASE}/budgets-departement/'
        r = self.api.post(url, {'annee': 2026, 'periodicite': 'annuelle', 'note': 0}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.api.post(url, {'annee': 2026, 'periodicite': 'annuelle', 'montant_alloue': 0}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = self.api.post(url, {'annee': 2026, 'periodicite': 'mensuelle', 'mois': 5,
                                'montant_alloue': '10'}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        # Passer en annuel sans renvoyer le mois remet le mois à 0 (plus de 400).
        r = self.api.patch(f"{url}{r.data['id']}/", {'periodicite': 'annuelle'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['mois'], 0)

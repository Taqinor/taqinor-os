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

    def assertObjetInexistant(self, reponse, champ, statut=400):
        self.assertEqual(reponse.status_code, statut, reponse.content)
        self.assertIn(champ, reponse.data, reponse.content)
        self.assertEqual(reponse.data[champ][0].code, 'does_not_exist',
                         reponse.content)

    # --- incident qualité fournisseur (FOUR-1) ------------------------------
    def test_incident_fournisseur_etranger(self):
        corps = {'type_incident': 'autre', 'gravite': 'mineure',
                 'date_incident': JOUR}
        r = self.api.post(f'{BASE}/incidents-qualite-fournisseur/',
                          {**corps, 'fournisseur': self.fb.id}, format='json')
        self.assertObjetInexistant(r, 'fournisseur', 404)
        self.assertNotIn('FOURNISSEUR-B-SECRET', r.content.decode('utf-8'))
        inconnu = self.api.post(f'{BASE}/incidents-qualite-fournisseur/',
                                {**corps, 'fournisseur': 99999999},
                                format='json')
        self.assertObjetInexistant(inconnu, 'fournisseur', 404)
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
        self.assertObjetInexistant(r, 'bin', 404)

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
        self.assertObjetInexistant(r, 'bin', 404)
        r = self.api.post(f'{BASE}/taches-reappro-interne/', {
            'produit': self.pb.id, 'bin_cible': self.bin_a.id,
            'quantite': 1}, format='json')
        self.assertObjetInexistant(r, 'produit', 404)

    def test_scanner_casier_ou_produit_etranger_404(self):
        # ENF11 (nocturne 15/10) — un id inconnu de la société est une
        # ressource qui manque (404), même corps qu'un id inexistant.
        url = f'{BASE}/scanner/mouvement/'
        corps = {'produit': self.pa.id, 'type_mouvement': 'entree', 'quantite': 1}
        r = self.api.post(url, {**corps, 'bin_destination': self.bin_b.id}, format='json')
        r_absent = self.api.post(url, {**corps, 'bin_destination': 99999999}, format='json')
        self.assertEqual(r.status_code, 404, r.content)
        self.assertEqual(r.json(), r_absent.json())
        r = self.api.post(url, {**corps, 'produit': self.pb.id}, format='json')
        self.assertEqual(r.status_code, 404, r.content)

    # --- retour fournisseur scanné : bins_source bornés ---------------------
    def test_valider_scanne_casier_source_etranger(self):
        retour = RetourFournisseur.objects.create(
            company=self.a, reference='RET-ASTK7-0001', fournisseur=self.fa)
        ligne = LigneRetourFournisseur.objects.create(
            retour=retour, produit=self.pa, quantite=1, motif='Défaut')
        r = self.api.post(
            f'{BASE}/retours-fournisseur/{retour.id}/valider-scanne/',
            {'bins_source': {str(ligne.id): self.bin_b.id}}, format='json')
        self.assertEqual(r.status_code, 404, r.content)  # id inconnu de la société
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
            nom = cls.__name__
            self.assertTrue(issubclass(cls, CompanyScopedRelationsMixin), nom)
            ser = cls(data=corps, partial=True, context=ctx)
            self.assertTrue(ser.is_valid(), (nom, ser.errors))
            for champ in corps:
                self.assertNotIn(champ, ser.validated_data, (nom, champ))


class CorpsFuzzTests(TestCase):
    """ERR fuzz (api-fuzz-pr #986, stock) — corps non objet, ids non entiers et
    champs plus lâches que leur schéma : 400 (ou 409 pour un doublon), jamais
    500 ni acceptation silencieuse."""

    def setUp(self):
        from apps.crm.models import Client
        from apps.installations.models import BinLocation
        from apps.stock.models import KitProduit, ModeleBonCommandeFournisseur
        self.a = make_company('fuzz-stock-a', 'Fuzz stock A')
        self.admin = User.objects.create_user(
            username='fuzz_stock_admin', password='x', role_legacy='admin',
            company=self.a)
        self.api = auth_client(self.admin)
        self.fa = Fournisseur.objects.create(company=self.a, nom='Fourn. F')
        # Stock 50 : les refus d'état (sortie 51, ajustement au niveau actuel)
        # et les « stock inchangé » des tests CI #997 lisent ce niveau.
        self.pa = Produit.objects.create(
            company=self.a, nom='ProdF', sku='FUZZ-PA', fournisseur=self.fa,
            prix_achat=Decimal('10'), prix_vente=Decimal('20'), quantite_stock=50)
        # CI #997 — produit d'une AUTRE société (cible d'un remplacement de composant).
        self.pb = Produit.objects.create(
            company=make_company('fuzz-stock-b', 'Fuzz stock B'), nom='ProdFB',
            sku='FUZZ-PB', prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=5)
        self.emp = EmplacementStock.objects.create(
            company=self.a, nom='Dépôt F', is_principal=True)
        self.client_a = Client.objects.create(company=self.a, nom='Client F')
        self.bin_a = BinLocation.objects.create(
            company=self.a, emplacement=self.emp, code='F-07-01')
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
            r = getattr(self.api, methode)(url, [None, None], format='json')
            self.assertEqual(r.status_code, 400, (methode, url, r.content))

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
            r = self.api.post(f'{BASE}/{fin}', corps, format='json')
            self.assertEqual(r.status_code, 400, (fin, corps, r.content))

    def test_fuzz_modele_bcf_lignes_et_note(self):
        url = f'{BASE}/modeles-bcf/{self.modele.id}/'
        r = self.api.patch(url, {'lignes': [{'quantite': 0}]}, format='json')
        self.assertEqual(r.status_code, 400, r.content)  # sans produit : hors schéma
        r = self.api.patch(url, {'lignes': [{'produit': self.pa.id}, {'produit': self.pa.id}]},
                           format='json')
        self.assertEqual(r.status_code, 409, r.content)  # doublon : règle d'état
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
            r = self.api.post(f'{url}dupliquer/', {'facteur_echelle': facteur}, format='json')
            self.assertEqual(r.status_code, attendu, (facteur, r.content))

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

    def _api_admin(self):
        admin = User.objects.create_user(
            username='astk7_admin_ci997', password='x', role_legacy='admin', company=self.a)
        return auth_client(admin)

    def test_fuzz_ci997_corps_ou_ids_mal_types_400_jamais_500(self):
        api = self._api_admin()
        cas = (
            ('blocages-qualite/lever-quarantaine/', [None, None]),
            ('blocages-qualite/lever-quarantaine/', {'bin': {}}),
            ('blocages-qualite/lever-quarantaine/', {'bin': 0}),
            ('produits/inventaire/', {'lignes': [{'quantite_comptee': 1}]}),
            ('produits/inventaire/', {'lignes': [{'produit': self.pa.id, 'quantite_comptee': 1000001}]}),
            ('produits/inventaire/', {'lignes': [{'produit': self.pa.id, 'quantite_comptee': ' 7 '}]}),
            ('kits/remplacer-composant/', {'produit_ancien': self.pa.id, 'produit_nouveau': self.pb.id,
                                           'dry_run': 0}),
            ('kits/remplacer-composant/', {'produit_ancien': 0, 'produit_nouveau': {},
                                           'ratio_quantite': '0', 'dry_run': False}),
            ('produits/inventaire/', [None, None]),
            ('produits/inventaire/', {'motif': 5, 'lignes': [{'produit': self.pa.id, 'quantite_comptee': 1}]}),
            ('produits/inventaire/', {'lignes': [{'produit': {}, 'quantite_comptee': 1}]}),
            ('scanner/mouvement/', {'produit': {}, 'type_mouvement': 'entree', 'quantite': 1,
                                    'bin_source': None, 'bin_destination': None, 'reference': '0'}),
            ('scanner/mouvement/', {'produit': self.pa.id, 'type_mouvement': 'entree', 'quantite': 1,
                                    'reference': 5}),
            ('factures-fournisseur/', {'fournisseur': self.fa.id, 'ref_fournisseur': '', 'date_facture': {},
                                       'montant_ttc': '0', 'lignes': []}),
        )
        for fin, corps in cas:
            r = api.post(f'{BASE}/{fin}', corps, format='json')
            self.assertEqual(r.status_code, 400, (fin, corps, r.content))
        self.pa.refresh_from_db()
        self.assertEqual(self.pa.quantite_stock, 50)
        # Date extrême conforme : le détecteur de doublon ne déborde plus (± 7 j).
        r = api.post('/api/django/achats/factures-fournisseur/', {
            'fournisseur': self.fa.id, 'ref_fournisseur': '', 'date_facture': '0001-01-01',
            'montant_ttc': '0', 'lignes': []}, format='json')
        self.assertLess(r.status_code, 500, r.content)

    def test_fuzz_ci997_filtres_requete_stricts(self):
        api = self._api_admin()
        refuses = (
            'produits/?entite=null&entite=null', 'profils-saisonniers/?actif=null&actif=null',
            'blocages-qualite/?produit=null&produit=null', 'budgets-departement/?actif=null&actif=null',
            'budgets-departement/?annee=99999999999', 'retours-client/?client=null&client=null',
            'catalogue-achat/?recent=null&recent=null', 'quais/?actif=null&actif=null',
            'quais/planning/?date=2026-01-05&quai=null&quai=null', 'catalogue-b2b/?offset=null&offset=null',
            'rendez-vous-transporteur/?quai=null&quai=null', 'mouvements/?date_min=abc',
            'mouvements/agregation/?date_max=abc', 'mouvements/?produit=null',
        )
        for fin in refuses:
            self.assertEqual(api.get(f'{BASE}/{fin}').status_code, 400, fin)
        acceptes = (
            'produits/?entite=', 'profils-saisonniers/?actif=true', f'blocages-qualite/?produit={self.pa.id}',
            'budgets-departement/?annee=2026&mois=0&actif=false', 'quais/?actif=1',
            'catalogue-b2b/?offset=0&limite=10', 'mouvements/?date_min=', 'mouvements/agregation/?date_min=',
        )
        for fin in acceptes:
            self.assertEqual(api.get(f'{BASE}/{fin}').status_code, 200, fin)
        r = api.post(f'{BASE}/mouvements/export-xlsx/?date_min=')
        self.assertEqual(r.status_code, 200, r.content)

    def test_fuzz_ci997_corps_types_declares(self):
        api = self._api_admin()
        fa, pa = self.fa.id, self.pa.id
        refuses = (
            ('alertes-rappel/', {'produit': pa, 'motif': 0}, 'motif'),
            ('bons-commande-fournisseur/', {'fournisseur': fa, 'conditions_paiement': 0,
                                            'lignes': [{'designation': 'x', 'quantite': 1}]}, 'conditions_paiement'),
            ('conditionnements/', {'produit': pa, 'nom': 'C', 'facteur': '1', 'code_barres': 0}, 'code_barres'),
            ('consignations/', {'client': self.client_a.id, 'produit': pa, 'quantite_deposee': 1,
                                'date_depot': JOUR, 'note': {}}, 'note'),
            ('contacts-fournisseur/', {'fournisseur': fa, 'nom': 'N', 'telephone': 0}, 'telephone'),
            ('documents-conformite-fournisseur/', {'fournisseur': fa, 'type_document': 'arf', 'note': 0}, 'note'),
            ('dossiers-onboarding-fournisseur/', {'fournisseur': fa, 'note': 0}, 'note'),
            ('produits/', {'nom': 'P', 'prix_vente': '1', 'courbe_frequence_hz': False}, 'courbe_frequence_hz'),
            ('quais/', {'nom': 'Q', 'emplacement': self.bin_a.emplacement_id, 'actif': 0}, 'actif'),
            ('retours-fournisseur/', {'fournisseur': fa, 'lignes': [{'produit': pa, 'quantite': 1, 'motif': 0}]},
             'motif'),
            ('revalorisations-stock/', {'produit': pa, 'nouveau_cout': '1', 'motif': [None, None]}, 'motif'),
        )
        # QG4 : la création de produit est réservée à Directeur / Commercial
        # responsable — l'admin de la classe reçoit 403 avant toute validation.
        from apps.roles.models import Role
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        directeur = User.objects.create_user(
            username='fuzz_stock_directeur', password='x', company=self.a,
            role=Role.objects.create(
                company=self.a, nom='Directeur', est_systeme=True,
                permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Directeur'])))
        api_directeur = auth_client(directeur)
        for fin, corps, champ in refuses:
            cli = api_directeur if fin == 'produits/' else api
            r = cli.post(f'{BASE}/{fin}', corps, format='json')
            self.assertEqual(r.status_code, 400, (fin, r.content))
            self.assertIn(champ, r.content.decode('utf-8'), fin)
        # Ce que les écrans envoient reste accepté : prix d'achat en nombre JSON
        # (fiche produit), décimal nullable vide = non renseigné.
        r = api.post(f'{BASE}/prix-fournisseurs/', {'produit': pa, 'fournisseur': fa, 'prix_achat': 12.5},
                     format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['prix_achat'], '12.50')
        r = api.post(f'{BASE}/tolerances-rapprochement-categorie/', {
            'categorie': Categorie.objects.create(company=self.a, nom='Tol').id,
            'tolerance_prix_pct': '2', 'tolerance_prix_absolu_mad': ''}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(r.data['tolerance_prix_absolu_mad'])

    def test_fuzz_ci997_refus_d_etat_409_et_reference_inconnue_404(self):
        api = self._api_admin()
        pa = self.pa.id
        # Stock (50) insuffisant : l'état s'oppose, le corps est conforme.
        r = api.post(f'{BASE}/mouvements/', {'produit': pa, 'type_mouvement': 'sortie', 'quantite': 51},
                     format='json')
        self.assertEqual(r.status_code, 409, r.content)
        r = api.post(f'{BASE}/mouvements/', {'produit': pa, 'type_mouvement': 'ajustement', 'quantite': 50},
                     format='json')
        self.assertEqual(r.status_code, 409, r.content)
        r = api.post(f'{BASE}/mouvements-rebut/', {'produit': pa, 'quantite': 51, 'motif': 'casse'}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        for corps in ({'produit': pa, 'quantite': 1, 'motif': 'casse', 'note': 5},
                      {'produit': pa, 'quantite': '1', 'motif': 'casse'}):
            r = api.post(f'{BASE}/mouvements-rebut/', corps, format='json')
            self.assertEqual(r.status_code, 400, (corps, r.content))
        r = api.post(f'{BASE}/blocages-qualite/', {'produit': pa, 'quantite': 1, 'motif': 5}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = api.post(f'{BASE}/produits/bulk/', {'action': 'set_category', 'ids': [pa], 'categorie_id': 999999},
                     format='json')
        self.assertEqual(r.status_code, 404, r.content)
        r = api.post(f'{BASE}/produits/bulk/', {'action': 'set_price', 'ids': [pa], 'mode': 'fixed',
                                                'valeur': '99999999.50'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        # Corps multipart : JSON seul (les booléens d'un formulaire sont du texte).
        r = api.post(f'{BASE}/categories-fournisseur/', {'nom': 'C', 'archived': 'True'}, format='multipart')
        self.assertEqual(r.status_code, 415, r.content)
        self.pa.refresh_from_db()
        self.assertEqual(self.pa.quantite_stock, 50)

    def test_fuzz_ci997_3_entier_hors_colonne_et_texte_trop_long_400(self):
        """CI #997 fuzz (3) — un entier au-delà de la colonne (``maximum``
        publié 2147483647) répond 400 avant tout calcul (il faisait un 500 au
        save) ; un texte plus long que son ``maxLength`` publié répond 400 (il
        était tronqué en silence, 201). La borne exacte reste acceptée."""
        api = self._api_admin()
        pa = self.pa.id
        url = f'{BASE}/blocages-qualite/'
        r = api.post(url, {'produit': pa, 'quantite': 2147483648, 'motif': ''}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('quantite', r.data)
        r = api.post(url, {'produit': pa, 'quantite': 2147483647, 'motif': ''}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        r = api.post(f'{BASE}/mouvements-rebut/', {'produit': pa, 'quantite': 2147483648, 'motif': 'casse'},
                     format='json')
        self.assertEqual(r.status_code, 400, r.content)
        corps = {'client': self.client_a.id, 'produit': pa, 'quantite_deposee': 1, 'date_depot': JOUR}
        r = api.post(f'{BASE}/consignations/', {**corps, 'adresse_site': 'x' * 256}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('adresse_site', r.data)
        r = api.post(f'{BASE}/consignations/', {**corps, 'quantite_deposee': 2147483648}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('quantite_deposee', r.data)
        r = api.post(f'{BASE}/consignations/', {**corps, 'adresse_site': 'x' * 255}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data['adresse_site'], 'x' * 255)

    def test_fuzz_ci997_3_bcf_fournisseur_mal_forme_400(self):
        """CI #997 fuzz (3) — `fournisseur: [null, null]` (ou `{}`) dans un
        corps de BCF par ailleurs complet faisait un 500 (pré-contrôles du
        fournisseur) : 400 nommant `fournisseur` ; un corps non objet aussi."""
        api = self._api_admin()
        url = f'{BASE}/bons-commande-fournisseur/'
        corps = {'date_commande': JOUR, 'devise': 'MAD', 'taux_change': '1',
                 'lignes': [{'designation': 'x', 'quantite': 1}]}
        for fournisseur in ([None, None], {}, True):
            r = api.post(url, {**corps, 'fournisseur': fournisseur}, format='json')
            self.assertEqual(r.status_code, 400, (fournisseur, r.content))
            self.assertIn('fournisseur', r.data, fournisseur)
        r = api.post(url, [None, None], format='json')
        self.assertEqual(r.status_code, 400, r.content)
        r = api.post(url, {**corps, 'fournisseur': self.fa.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)

    def test_fuzz_ci997_3_quantite_plafonnee_et_compteur_deborde_409(self):
        """CI #997 fuzz (3) — mouvement libre et scan : quantité publiée
        ``maximum`` QUANTITE_MAX, vérifiée avant tout calcul (400) ; un
        compteur (stock produit, casier) qui déborderait sa colonne entière
        répond 409 sans rien écrire (il faisait un 500 au save) ; un transfert
        scanné vers un seul casier destination reste accepté."""
        from apps.installations.models import BinAffectation
        from apps.stock.models import MouvementStock
        from core.champs_stricts import QUANTITE_MAX
        api = self._api_admin()
        pa = self.pa.id
        mouvements = f'{BASE}/mouvements/'
        scanner = f'{BASE}/scanner/mouvement/'
        r = api.post(mouvements, {'produit': pa, 'type_mouvement': 'entree', 'quantite': QUANTITE_MAX + 1},
                     format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('quantite', r.data)
        r = api.post(scanner, {'produit': pa, 'type_mouvement': 'entree', 'quantite': QUANTITE_MAX + 1},
                     format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.pa.refresh_from_db()
        self.assertEqual(self.pa.quantite_stock, 50)
        r = api.post(scanner, {'produit': pa, 'type_mouvement': 'transfert', 'quantite': 1,
                               'bin_destination': self.bin_a.id}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        # Stock produit au bord de la colonne : l'entrée déborderait → 409.
        Produit.objects.filter(pk=pa).update(quantite_stock=2147483647 - 10)
        avant = MouvementStock.objects.count()
        r = api.post(mouvements, {'produit': pa, 'type_mouvement': 'entree', 'quantite': 11}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        r = api.post(scanner, {'produit': pa, 'type_mouvement': 'entree', 'quantite': 11}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(MouvementStock.objects.count(), avant)
        # Casier au bord de la colonne : le transfert scanné déborderait → 409.
        Produit.objects.filter(pk=pa).update(quantite_stock=50)
        BinAffectation.objects.filter(bin=self.bin_a, produit_id=pa).update(quantite=2147483647)
        r = api.post(scanner, {'produit': pa, 'type_mouvement': 'transfert', 'quantite': 1,
                               'bin_destination': self.bin_a.id}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(MouvementStock.objects.count(), avant)
        self.assertEqual(BinAffectation.objects.get(bin=self.bin_a, produit_id=pa).quantite, 2147483647)

    def test_fuzz_ci997_3_kit_composant_sous_kit_champs_produit_null_publies(self):
        """CI #997 fuzz (3) — un composant SOUS-KIT n'a pas de produit : ses
        `produit_nom`/`produit_sku`/`prix_vente` valent null (et
        `composant_kit_nom` pour un composant produit) — publiés null-ables,
        la réponse respecte le schéma."""
        from apps.stock.serializers import KitComposantSerializer
        champs = KitComposantSerializer().fields
        for nom in ('produit_nom', 'produit_sku', 'prix_vente', 'composant_kit_nom'):
            self.assertTrue(champs[nom].allow_null, nom)
        api = self._api_admin()
        r = api.post(f'{BASE}/kits/', {'nom': 'Kit parent', 'composants': [
            {'composant_kit': self.kit.id, 'quantite': '1'},
            {'produit': self.pa.id, 'quantite': '2'}]}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        sous_kit, produit = sorted(r.data['composants'], key=lambda c: c['produit'] is not None)
        self.assertEqual(sous_kit['composant_kit_nom'], 'Kit F')
        for nom in ('produit_nom', 'produit_sku', 'prix_vente'):
            self.assertIsNone(sous_kit[nom], nom)
        self.assertEqual(produit['produit_nom'], 'ProdF')
        self.assertIsNone(produit['composant_kit_nom'])

    def test_fuzz_ci997_4_transfert_direct_ecart_reception_null_publie(self):
        """CI #997 (4) — un transfert direct (jamais réceptionné) n'a ni
        `quantite_recue` ni écart : `ecart_reception` vaut null, publié
        null-able ; liste et création respectent le schéma."""
        from apps.stock.serializers import TransfertStockSerializer
        self.assertTrue(TransfertStockSerializer().fields['ecart_reception'].allow_null)
        api = self._api_admin()
        dest = EmplacementStock.objects.create(company=self.a, nom='Camionnette F')
        r = api.post(f'{BASE}/transferts/', {
            'produit': self.pa.id, 'source': self.emp.id, 'destination': dest.id,
            'quantite': 1, 'note': ''}, format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIsNone(r.data['ecart_reception'])
        r = api.get(f'{BASE}/transferts/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(r.data['results'][0]['ecart_reception'])

    def test_fuzz_ci997_4_numeros_serie_liste_de_chaines_et_tracabilite_serie(self):
        """CI #997 (4) — `numeros_serie` d'une ligne de réception est une liste
        de chaînes : un scalaire JSON (`1`, `true`) était stocké puis itéré par
        la traçabilité (`?serie=0` -> 500). Désormais refusé à l'écriture ; la
        traçabilité d'une série inconnue reste un 404."""
        from rest_framework.exceptions import ValidationError
        from apps.stock.serializers import LigneReceptionFournisseurSerializer
        champ = LigneReceptionFournisseurSerializer().fields['numeros_serie']
        for valeur in (1, True, 1.5, 'SN1', {'a': 1}, [1], [None], [{}]):
            with self.assertRaises(ValidationError, msg=repr(valeur)):
                champ.run_validation(valeur)
        self.assertEqual(champ.run_validation(['SN1', 'SN2']), ['SN1', 'SN2'])
        self.assertEqual(champ.run_validation([]), [])
        self.assertIsNone(champ.run_validation(None))
        r = self._api_admin().get(f'{BASE}/produits/tracabilite/?serie=0')
        self.assertEqual(r.status_code, 404, r.content)


class FuzzFiltresEtCorpsStockATests(TestCase):
    """api-fuzz 24/10 — filtres de liste et corps libres : jamais 500."""

    def setUp(self):
        self.co = make_company('drain-stock-a', 'Drain stock A')
        self.admin = User.objects.create_user(
            username='drain_a_admin', password='x', role_legacy='admin',
            company=self.co)
        self.api = auth_client(self.admin)

    def test_filtres_de_liste_illisibles_en_400(self):
        for chemin in (
                'dossiers-onboarding-fournisseur/?statut=%00',
                'dossiers-onboarding-fournisseur/?statut=inconnu',
                'dossiers-onboarding-fournisseur/?fournisseur=abc',
                'documents-fournisseur/?type_document=%00',
                'documents-fournisseur/?dossier=99999999999',
                'expeditions/?statut=%00',
                'receptions-fournisseur/?statut=%00',
                'receptions-fournisseur/?bon_commande=abc',
                'retours-client/?statut=%00',
                'consignations/?statut=%00',
                'consignations/?client=abc',
                'consignations/export-xlsx/?statut=%00',
                'portails-tiers/?tiers_nom=%00',
                'catalogue-achat/?q=a%00b',
                'scanner/resoudre/?code=a%00b',
                'bons-commande-fournisseur/bcf-similaires/?fournisseur=1&fournisseur=2',
                'bons-commande-fournisseur/bcf-similaires/?fournisseur=%EE%9E%87',
        ):
            r = self.api.get(f'{BASE}/{chemin}')
            self.assertEqual(r.status_code, 400, (chemin, r.content))

    def test_filtres_de_liste_conformes_200(self):
        for chemin in (
                'dossiers-onboarding-fournisseur/?statut=&fournisseur=',
                'documents-fournisseur/?dossier=1&type_document=autre',
                'expeditions/?statut=brouillon',
                'receptions-fournisseur/?statut=brouillon&bon_commande=1',
                'retours-client/?statut=demande',
                'consignations/?statut=actif&client=1',
                'portails-tiers/?tiers_nom=abc',
                'catalogue-achat/?q=abc',
        ):
            r = self.api.get(f'{BASE}/{chemin}')
            self.assertEqual(r.status_code, 200, (chemin, r.content))

    def test_bcf_similaires_produits_non_ascii_ignores(self):
        fournisseur = Fournisseur.objects.create(company=self.co, nom='Fourn. drain A')
        r = self.api.get(
            f'{BASE}/bons-commande-fournisseur/bcf-similaires/'
            f'?fournisseur={fournisseur.id}&produits=%C2%B2,3,99999999999999999999')
        self.assertEqual(r.status_code, 200, r.content)

    def test_valider_scanne_corps_mal_type_400(self):
        fournisseur = Fournisseur.objects.create(company=self.co, nom='Fourn. drain B')
        retour = RetourFournisseur.objects.create(
            company=self.co, reference='RET-DRAIN-A', fournisseur=fournisseur)
        url = f'{BASE}/retours-fournisseur/{retour.id}/valider-scanne/'
        for corps in ({'bins_source': [1]}, {'bins_source': {'1': {}}},
                      {'bins_source': {'1': 1.5}}, [1]):
            r = self.api.post(url, corps, format='json')
            self.assertEqual(r.status_code, 400, (corps, r.content))
        r = self.api.post(url, {'bins_source': {'1': 987654321}}, format='json')
        self.assertEqual(r.status_code, 404, r.content)

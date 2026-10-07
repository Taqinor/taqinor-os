"""ASTK6 (C-ASTK-001) — aucune surface WMS n'accepte plus l'id d'une autre
société.

Sonde TEN-4 d'origine : un responsable de A créait un rappel sur le produit
« ProdB-secret » de B (201, ``produit_nom`` = ProdB-secret) puis lisait
``impact`` (200 avec nom + SKU + casiers de B). Même défaut sur les blocages,
rebuts, retours client, plans de chargement, rendez-vous et unités
logistiques (parent / vague).

Désormais chaque sérialiseur de ``serializers_wms.py`` porte
``CompanyScopedRelationsMixin`` et les ``create`` maison résolvent leurs FK
par ces champs scopés : un id étranger répond 400 « objet inexistant »
(code ``does_not_exist``), exactement comme l'id 99999999.

Aucun mock : mixin core, vues et services réels.

Run :
    python manage.py test apps.stock.test_astk_fk_wms -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import EmplacementStock, LotEntrepot, Produit
from apps.stock.models_wms import (
    AlerteRappel, BlocageQualite, MouvementRebut, PlanChargement, Quai,
    RendezVousTransporteur, RetourClient, UniteLogistique,
)
from apps.stock.services import (
    creer_plan_chargement, creer_retour_client, creer_unite_logistique,
    creer_vague_depuis_besoins, mettre_en_quarantaine,
)

User = get_user_model()

BASE = '/api/django/stock'


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth_client(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class FkWmsTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.installations.models import (
            BinLocation, Installation, Livraison, Transporteur,
        )

        self.a = make_company('astk6-a', 'ASTK6 A')
        self.b = make_company('astk6-b', 'ASTK6 B')
        self.resp_a = User.objects.create_user(
            username='astk6_resp_a', password='x', role_legacy='responsable',
            company=self.a)
        self.admin_a = User.objects.create_user(
            username='astk6_admin_a', password='x', role_legacy='admin',
            company=self.a)
        self.api = auth_client(self.resp_a)

        # --- société A ---------------------------------------------------
        self.pa = Produit.objects.create(
            company=self.a, nom='ProdA', sku='ASTK6-PA',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=10)
        self.emp_a = EmplacementStock.objects.create(
            company=self.a, nom='Dépôt A', is_principal=True)
        self.bin_a = BinLocation.objects.create(
            company=self.a, emplacement=self.emp_a, code='A-01-01')
        self.client_a = Client.objects.create(
            company=self.a, nom='Client', prenom='A',
            email='astk6-a@example.invalid')
        self.quai_a = Quai.objects.create(
            company=self.a, nom='Quai A', emplacement=self.emp_a)
        debut = timezone.now() + timedelta(days=1)
        self.rdv_a = RendezVousTransporteur.objects.create(
            company=self.a, quai=self.quai_a, date_heure_debut=debut,
            date_heure_fin=debut + timedelta(hours=1))
        self.ul_a = creer_unite_logistique(company=self.a)

        # --- société B ---------------------------------------------------
        self.pb = Produit.objects.create(
            company=self.b, nom='ProdB-secret', sku='ASTK6-PB-SECRET',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'),
            quantite_stock=5)
        self.lot_b = LotEntrepot.objects.create(
            company=self.b, produit=self.pb, numero_lot='LOT-B-SECRET',
            quantite_recue=5, quantite_restante=5, reference_reception='R-B')
        self.emp_b = EmplacementStock.objects.create(
            company=self.b, nom='Dépôt B', is_principal=True)
        self.bin_b = BinLocation.objects.create(
            company=self.b, emplacement=self.emp_b, code='B-SECRET-01')
        self.client_b = Client.objects.create(
            company=self.b, nom='Client', prenom='B',
            email='astk6-b@example.invalid')
        self.chantier_b = Installation.objects.create(
            company=self.b, reference='INST-ASTK6-B')
        self.livraison_b = Livraison.objects.create(
            company=self.b, reference='LIV-ASTK6-B',
            installation=self.chantier_b)
        self.transporteur_b = Transporteur.objects.create(
            company=self.b, nom='Transporteur B')
        self.vague_b = creer_vague_depuis_besoins(
            company=self.b, besoins=[{'produit_id': self.pb.id,
                                      'quantite': 1}])
        self.palette_b = creer_unite_logistique(
            company=self.b, type_unite='palette')

    # ------------------------------------------------------------------
    def assertObjetInexistant(self, reponse, champ):
        self.assertEqual(reponse.status_code, 400, reponse.content)
        self.assertIn(champ, reponse.data, reponse.content)
        self.assertEqual(reponse.data[champ][0].code, 'does_not_exist',
                         reponse.content)

    # --- rappel -----------------------------------------------------------
    def test_rappel_produit_etranger(self):
        avant = AlerteRappel.objects.count()
        r = self.api.post(f'{BASE}/alertes-rappel/', {
            'produit': self.pb.id, 'motif': 'Défaut'}, format='json')
        self.assertObjetInexistant(r, 'produit')
        inconnu = self.api.post(f'{BASE}/alertes-rappel/', {
            'produit': 99999999, 'motif': 'Défaut'}, format='json')
        self.assertObjetInexistant(inconnu, 'produit')
        self.assertNotIn('ProdB-secret', r.content.decode('utf-8'))
        self.assertEqual(AlerteRappel.objects.count(), avant)

    def test_rappel_lot_etranger(self):
        r = self.api.post(f'{BASE}/alertes-rappel/', {
            'produit': self.pa.id, 'lot': self.lot_b.id, 'motif': 'Défaut'},
            format='json')
        self.assertObjetInexistant(r, 'lot')
        self.assertFalse(AlerteRappel.objects.filter(company=self.a).exists())

    def test_rappel_impact_ne_divulgue_pas_b(self):
        """Rappel hérité (créé avant la borne) qui pointe un produit de B."""
        alerte = AlerteRappel.objects.create(
            company=self.a, produit=self.pb, motif='Hérité')
        r = self.api.get(f'{BASE}/alertes-rappel/{alerte.id}/impact/')
        self.assertEqual(r.status_code, 200, r.content)
        contenu = r.content.decode('utf-8')
        self.assertNotIn('ProdB-secret', contenu)
        self.assertNotIn('ASTK6-PB-SECRET', contenu)
        self.assertNotIn('B-SECRET-01', contenu)

    # --- blocage qualité --------------------------------------------------
    def test_blocage_lot_etranger(self):
        r = self.api.post(f'{BASE}/blocages-qualite/', {
            'produit': self.pa.id, 'quantite': 1, 'lot': self.lot_b.id},
            format='json')
        self.assertObjetInexistant(r, 'lot')
        self.assertFalse(BlocageQualite.objects.exists())

    def test_blocage_patch_casier_etranger(self):
        blocage = mettre_en_quarantaine(
            company=self.a, produit=self.pa, quantite=1, user=self.resp_a,
            bin_quarantaine=self.bin_a)
        r = self.api.patch(f'{BASE}/blocages-qualite/{blocage.id}/', {
            'bin': self.bin_b.id}, format='json')
        self.assertObjetInexistant(r, 'bin')
        blocage.refresh_from_db()
        self.assertEqual(blocage.bin_id, self.bin_a.id)

    # --- rebut ------------------------------------------------------------
    def test_rebut_casier_etranger(self):
        r = self.api.post(f'{BASE}/mouvements-rebut/', {
            'produit': self.pa.id, 'quantite': 1, 'motif': 'casse',
            'bin': self.bin_b.id}, format='json')
        self.assertObjetInexistant(r, 'bin')
        self.assertFalse(MouvementRebut.objects.exists())
        self.pa.refresh_from_db()
        self.assertEqual(self.pa.quantite_stock, 10)

    # --- retour client ----------------------------------------------------
    def test_retour_client_etranger(self):
        lignes = [{'produit': self.pa.id, 'quantite': 1}]
        r = self.api.post(f'{BASE}/retours-client/', {
            'client': self.client_b.id, 'lignes': lignes}, format='json')
        self.assertObjetInexistant(r, 'client')
        r = self.api.post(f'{BASE}/retours-client/', {
            'client': self.client_a.id, 'chantier': self.chantier_b.id,
            'lignes': lignes}, format='json')
        self.assertObjetInexistant(r, 'chantier')
        r = self.api.post(f'{BASE}/retours-client/', {
            'client': self.client_a.id,
            'lignes': [{'produit': self.pa.id, 'quantite': 1,
                        'bin': self.bin_b.id}]}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertFalse(RetourClient.objects.exists())

    def test_retour_client_patch_chantier_etranger(self):
        retour = creer_retour_client(
            company=self.a, user=self.resp_a, client=self.client_a,
            lignes=[{'produit': self.pa.id, 'quantite': 1}])
        r = self.api.patch(f'{BASE}/retours-client/{retour.id}/', {
            'chantier': self.chantier_b.id}, format='json')
        self.assertObjetInexistant(r, 'chantier')
        retour.refresh_from_db()
        self.assertIsNone(retour.chantier_id)

    # --- plan de chargement -----------------------------------------------
    def test_plan_chargement_livraison_etrangere(self):
        r = self.api.post(f'{BASE}/plans-chargement/', {
            'livraison': self.livraison_b.id}, format='json')
        self.assertObjetInexistant(r, 'livraison')
        self.assertFalse(PlanChargement.objects.exists())
        plan = creer_plan_chargement(company=self.a, user=self.resp_a)
        r = self.api.patch(f'{BASE}/plans-chargement/{plan.id}/', {
            'livraison': self.livraison_b.id}, format='json')
        self.assertObjetInexistant(r, 'livraison')
        plan.refresh_from_db()
        self.assertIsNone(plan.livraison_id)

    # --- rendez-vous transporteur -----------------------------------------
    def test_rendez_vous_transporteur_etranger(self):
        r = self.api.patch(
            f'{BASE}/rendez-vous-transporteur/{self.rdv_a.id}/', {
                'transporteur': self.transporteur_b.id}, format='json')
        self.assertObjetInexistant(r, 'transporteur')
        self.rdv_a.refresh_from_db()
        self.assertIsNone(self.rdv_a.transporteur_id)

    # --- unité logistique -------------------------------------------------
    def test_ul_parent_etranger(self):
        avant = UniteLogistique.objects.filter(company=self.a).count()
        r = self.api.post(f'{BASE}/unites-logistiques/', {
            'type_unite': 'colis', 'parent': self.palette_b.id},
            format='json')
        self.assertObjetInexistant(r, 'parent')
        self.assertEqual(
            UniteLogistique.objects.filter(company=self.a).count(), avant)
        r = self.api.patch(f'{BASE}/unites-logistiques/{self.ul_a.id}/', {
            'parent': self.palette_b.id}, format='json')
        self.assertObjetInexistant(r, 'parent')
        self.ul_a.refresh_from_db()
        self.assertIsNone(self.ul_a.parent_id)

    def test_ul_vague_etrangere(self):
        r = self.api.post(f'{BASE}/unites-logistiques/', {
            'type_unite': 'colis', 'vague': self.vague_b.id}, format='json')
        self.assertObjetInexistant(r, 'vague')
        r = self.api.patch(f'{BASE}/unites-logistiques/{self.ul_a.id}/', {
            'vague': self.vague_b.id}, format='json')
        self.assertObjetInexistant(r, 'vague')
        self.ul_a.refresh_from_db()
        self.assertIsNone(self.ul_a.vague_id)

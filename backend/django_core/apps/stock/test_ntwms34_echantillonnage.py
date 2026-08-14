"""NTWMS34 — contrôle qualité à réception avec échantillonnage.

Critère d'acceptation testé : une catégorie à 100 % d'échantillonnage BLOQUE
la confirmation de réception tant que le contrôle qualité n'est pas saisi —
et une société SANS plan garde exactement le comportement historique.

Run :
    python manage.py test apps.stock.test_ntwms34_echantillonnage -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BlocageQualite, BonCommandeFournisseur, Categorie, ControleReception,
    Fournisseur, LigneBonCommandeFournisseur, LigneReceptionFournisseur,
    PlanEchantillonnage, Produit, ReceptionFournisseur,
)
from apps.stock.services import confirm_reception_fournisseur
from apps.stock.services_qualite_reception import (
    echantillon_attendu_reception, echantillon_requis_pour_reception,
    enregistrer_controle_reception, plan_echantillonnage_pour_produit,
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


class Ntwms34Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms34-co', 'NTWMS34 Co')
        self.autre = make_company('ntwms34-autre', 'NTWMS34 Autre')
        self.admin = User.objects.create_user(
            username='ntwms34_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntwms34_normal', password='x', role_legacy='normal',
            company=self.company)
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Batteries NTWMS34')
        self.categorie_libre = Categorie.objects.create(
            company=self.company, nom='Visserie NTWMS34')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTWMS34')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie LiFePO4', sku='BAT-NTWMS34',
            categorie=self.categorie, prix_achat=Decimal('3000'),
            prix_vente=Decimal('4000'), quantite_stock=0)

    def _reception(self, quantite=10, produit=None):
        produit = produit or self.produit
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-NTWMS34-{produit.id}',
            fournisseur=self.fournisseur)
        ligne_cmd = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=produit, quantite=quantite,
            prix_achat_unitaire=Decimal('3000'))
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-NTWMS34-{produit.id}',
            bon_commande=bc)
        LigneReceptionFournisseur.objects.create(
            reception=reception, ligne_commande=ligne_cmd, produit=produit,
            quantite=quantite)
        return reception


class Ntwms34GardeTests(Ntwms34Base):
    def test_categorie_a_100pct_bloque_la_confirmation_sans_controle(self):
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=self.categorie,
            taux_echantillon_pct=100)
        reception = self._reception(quantite=10)

        self.assertTrue(echantillon_requis_pour_reception(reception))
        self.assertEqual(echantillon_attendu_reception(reception), 10)
        with self.assertRaises(ValueError) as ctx:
            confirm_reception_fournisseur(reception, self.admin)
        self.assertIn('contrôle qualité', str(ctx.exception))
        # Le stock n'a PAS bougé.
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)
        reception.refresh_from_db()
        self.assertEqual(reception.statut,
                         ReceptionFournisseur.Statut.BROUILLON)

    def test_verdict_conforme_laisse_passer_la_confirmation(self):
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=self.categorie,
            taux_echantillon_pct=100)
        reception = self._reception(quantite=10)
        enregistrer_controle_reception(
            reception=reception, user=self.admin,
            resultat=ControleReception.Resultat.CONFORME,
            unites_controlees=10)

        confirm_reception_fournisseur(reception, self.admin)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 10)
        self.assertFalse(BlocageQualite.objects.filter(
            company=self.company, reception=reception).exists())

    def test_verdict_non_conforme_route_vers_la_quarantaine(self):
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=self.categorie,
            taux_echantillon_pct=20)
        reception = self._reception(quantite=10)
        enregistrer_controle_reception(
            reception=reception, user=self.admin,
            resultat=ControleReception.Resultat.NON_CONFORME,
            unites_controlees=2, observation='Cellules gonflées')

        confirm_reception_fournisseur(reception, self.admin)

        blocage = BlocageQualite.objects.get(
            company=self.company, reception=reception)
        self.assertEqual(blocage.quantite, 10)
        self.assertEqual(blocage.statut,
                         BlocageQualite.Statut.EN_QUARANTAINE)

    def test_societe_sans_plan_garde_le_comportement_historique(self):
        reception = self._reception(quantite=7)
        self.assertFalse(echantillon_requis_pour_reception(reception))
        confirm_reception_fournisseur(reception, self.admin)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 7)

    def test_plan_a_zero_pourcent_nexige_aucun_controle(self):
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=self.categorie,
            taux_echantillon_pct=0)
        reception = self._reception(quantite=4)
        self.assertFalse(echantillon_requis_pour_reception(reception))
        confirm_reception_fournisseur(reception, self.admin)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 4)


class Ntwms34PlanTests(Ntwms34Base):
    def test_plan_de_categorie_prime_sur_le_plan_par_defaut(self):
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=None, taux_echantillon_pct=5)
        cible = PlanEchantillonnage.objects.create(
            company=self.company, categorie=self.categorie,
            taux_echantillon_pct=50)
        self.assertEqual(
            plan_echantillonnage_pour_produit(self.company, self.produit).id,
            cible.id)

    def test_plan_par_defaut_couvre_une_categorie_sans_plan_propre(self):
        defaut = PlanEchantillonnage.objects.create(
            company=self.company, categorie=None, taux_echantillon_pct=5)
        autre_produit = Produit.objects.create(
            company=self.company, nom='Vis inox', sku='VIS-NTWMS34',
            categorie=self.categorie_libre, prix_achat=Decimal('1'),
            prix_vente=Decimal('2'), quantite_stock=0)
        self.assertEqual(
            plan_echantillonnage_pour_produit(self.company, autre_produit).id,
            defaut.id)

    def test_plan_inactif_ne_sapplique_jamais(self):
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=self.categorie,
            taux_echantillon_pct=100, actif=False)
        self.assertIsNone(
            plan_echantillonnage_pour_produit(self.company, self.produit))

    def test_echantillon_arrondi_au_superieur(self):
        plan = PlanEchantillonnage(
            company=self.company, taux_echantillon_pct=1)
        self.assertEqual(plan.unites_a_controler(10), 1)
        self.assertEqual(plan.unites_a_controler(0), 0)

    def test_plan_dune_autre_societe_ne_sapplique_jamais(self):
        PlanEchantillonnage.objects.create(
            company=self.autre, categorie=None, taux_echantillon_pct=100)
        reception = self._reception(quantite=3)
        self.assertFalse(echantillon_requis_pour_reception(reception))


class Ntwms34ApiTests(Ntwms34Base):
    URL = '/api/django/stock/plans-echantillonnage/'

    def test_crud_plan_force_la_societe_serveur(self):
        api = auth(self.admin)
        res = api.post(self.URL, {
            'categorie': self.categorie.id, 'taux_echantillon_pct': 100,
            'company': self.autre.id,
        }, format='json')
        self.assertEqual(res.status_code, 201)
        plan = PlanEchantillonnage.objects.get(id=res.data['id'])
        self.assertEqual(plan.company_id, self.company.id)

    def test_taux_superieur_a_100_est_refuse(self):
        res = auth(self.admin).post(self.URL, {
            'categorie': self.categorie.id, 'taux_echantillon_pct': 150,
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_ecriture_refusee_a_un_role_normal(self):
        res = auth(self.normal).post(self.URL, {
            'taux_echantillon_pct': 10}, format='json')
        self.assertEqual(res.status_code, 403)

    def test_liste_ne_fuit_pas_le_plan_dune_autre_societe(self):
        PlanEchantillonnage.objects.create(
            company=self.autre, categorie=None, taux_echantillon_pct=100)
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=self.categorie,
            taux_echantillon_pct=10)
        res = auth(self.admin).get(self.URL)
        self.assertEqual(res.status_code, 200)
        resultats = res.data.get('results', res.data)
        self.assertEqual(len(resultats), 1)

    def test_action_controle_qualite_puis_confirmation(self):
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=self.categorie,
            taux_echantillon_pct=100)
        reception = self._reception(quantite=6)
        api = auth(self.admin)
        base = f'/api/django/stock/receptions-fournisseur/{reception.id}/'

        etat = api.get(base + 'echantillonnage/')
        self.assertEqual(etat.status_code, 200)
        self.assertTrue(etat.data['echantillon_requis'])
        self.assertIsNone(etat.data['controle'])

        bloque = api.post(base + 'confirmer/')
        self.assertEqual(bloque.status_code, 400)

        saisie = api.post(base + 'controle-qualite/',
                          {'resultat': 'conforme', 'unites_controlees': 6},
                          format='json')
        self.assertEqual(saisie.status_code, 200)

        ok = api.post(base + 'confirmer/')
        self.assertEqual(ok.status_code, 200)

    def test_resultat_invalide_renvoie_400(self):
        reception = self._reception(quantite=2)
        res = auth(self.admin).post(
            f'/api/django/stock/receptions-fournisseur/{reception.id}/'
            'controle-qualite/', {'resultat': 'peut_etre'}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_reception_confirmee_ne_se_recontrole_plus(self):
        reception = self._reception(quantite=2)
        confirm_reception_fournisseur(reception, self.admin)
        with self.assertRaises(ValueError):
            enregistrer_controle_reception(
                reception=reception, user=self.admin,
                resultat=ControleReception.Resultat.NON_CONFORME)

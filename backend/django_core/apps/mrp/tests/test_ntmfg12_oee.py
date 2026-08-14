"""NTMFG12 — TRS/OEE par poste de charge (disponibilité × performance ×
qualité).

Critère : calcul exact sur fixtures avec arrêts/rebuts connus, tendance
hebdomadaire correcte, isolation tenant."""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.selectors import oee_poste, oee_tendance_hebdomadaire, oee_tous_postes
from apps.mrp.services import confirmer_of
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


def _prochain_lundi():
    """Un lundi FIXE et déterministe (fenêtre 1 jour ouvré exacte pour un
    calcul OEE reproductible, indépendant du jour d'exécution du test)."""
    aujourd_hui = date.today()
    jours_avant_lundi = (aujourd_hui.weekday()) % 7
    lundi = aujourd_hui - timedelta(days=jours_avant_lundi) + timedelta(days=7)
    return lundi


class OeePosteTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-oee-1', 'MRP OEE 1')
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-OEE', nom='Poste OEE',
            capacite_heures_jour=Decimal('8'))  # 480 min/jour.
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme OEE', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste,
            libelle='Op OEE', temps_unitaire_min=Decimal('10'))
        self.jour = _prochain_lundi()

        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=10,
            gamme=self.gamme)
        confirmer_of(of)
        of.refresh_from_db()
        self.operation = of.operations.first()
        # Fixture connue : temps réel 120min (2h), 8 bonnes, 2 rebut.
        from django.utils import timezone
        self.operation.statut = 'terminee'
        self.operation.terminee_le = timezone.make_aware(
            timezone.datetime.combine(self.jour, timezone.datetime.min.time()))
        self.operation.temps_reel_min = Decimal('120')
        self.operation.quantite_bonne = Decimal('8')
        self.operation.quantite_rebut = Decimal('2')
        self.operation.save(update_fields=[
            'statut', 'terminee_le', 'temps_reel_min', 'quantite_bonne',
            'quantite_rebut'])

    def test_calcul_exact_disponibilite_performance_qualite_trs(self):
        resultat = oee_poste(self.company, self.poste.id, self.jour, self.jour)
        self.assertTrue(resultat['donnees'])
        # Disponibilité = 120 / 480 = 25.0%.
        self.assertEqual(resultat['disponibilite_pct'], '25.0')
        # Performance = temps standard (10min x 8 bonnes = 80) / 120 = 66.7%.
        self.assertEqual(resultat['performance_pct'], '66.7')
        # Qualité = 8 / (8+2) = 80.0%.
        self.assertEqual(resultat['qualite_pct'], '80.0')
        # TRS = 0.25 x 0.6667 x 0.8 = 13.3%.
        self.assertEqual(resultat['trs_pct'], '13.3')

    def test_sans_donnees_renvoie_zero_sans_crash(self):
        futur = self.jour + timedelta(days=365)
        resultat = oee_poste(self.company, self.poste.id, futur, futur)
        self.assertFalse(resultat['donnees'])
        self.assertEqual(resultat['trs_pct'], '0.0')

    def test_poste_introuvable_renvoie_none(self):
        self.assertIsNone(oee_poste(self.company, 999999, self.jour, self.jour))

    def test_isolation_tenant(self):
        autre = make_company('mrp-oee-2', 'MRP OEE 2')
        self.assertIsNone(oee_poste(autre, self.poste.id, self.jour, self.jour))

    def test_tendance_hebdomadaire_une_semaine(self):
        tendance = oee_tendance_hebdomadaire(
            self.company, self.poste.id, self.jour, self.jour)
        self.assertEqual(len(tendance), 1)
        annee, semaine, _ = self.operation.terminee_le.isocalendar()
        self.assertEqual(tendance[0]['annee'], annee)
        self.assertEqual(tendance[0]['semaine'], semaine)

    def test_comparaison_inter_postes(self):
        poste_vide = PosteDeCharge.objects.create(
            company=self.company, code='P-VIDE', nom='Poste vide')
        resultats = oee_tous_postes(self.company, self.jour, self.jour)
        ids = [r['poste_id'] for r in resultats]
        self.assertIn(self.poste.id, ids)
        self.assertIn(poste_vide.id, ids)
        # Trié décroissant : le poste avec données bat le poste vide (0%).
        self.assertEqual(resultats[0]['poste_id'], self.poste.id)


class OeeApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-oee-api-1', 'MRP OEE API 1')
        self.user = make_user(self.company, 'mrp-oee-api-user')
        self.api = auth(self.user)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-OEE-API', nom='Poste OEE API')

    def test_oee_endpoint(self):
        resp = self.api.get(f'/api/django/mrp/postes-charge/{self.poste.id}/oee/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('trs_pct', resp.data)
        self.assertIn('tendance_hebdomadaire', resp.data)

    def test_oee_tous_postes_endpoint(self):
        resp = self.api.get('/api/django/mrp/oee-postes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = [r['poste_id'] for r in resp.data]
        self.assertIn(self.poste.id, ids)

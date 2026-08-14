"""NTMFG8 — Terminal atelier MES : déclaration opérateur avec
pause/rebut/multi-poste.

Critère : démarrer/pauser/terminer une opération cumule le temps actif
correctement (pauses exclues), rebut déclaré crée le mouvement de stock,
terminal utilisable au doigt sur tablette."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.services import (
    confirmer_of, demarrer_operation, pauser_operation, reprendre_operation,
    terminer_operation,
)
from apps.stock.models import MouvementStock, Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit', quantite_stock=0):
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=0, tva=20,
        quantite_stock=quantite_stock)


def make_of_avec_operation(company):
    produit = make_produit(company, 'Composite MES', quantite_stock=100)
    poste = PosteDeCharge.objects.create(
        company=company, code='P-MES', nom='Poste MES')
    gamme = Gamme.objects.create(company=company, nom='Gamme MES', produit=produit)
    OperationGamme.objects.create(
        gamme=gamme, ordre=1, poste_charge=poste, libelle='Op MES',
        temps_unitaire_min=Decimal('1'))
    of = OrdreFabrication.objects.create(
        company=company, produit=produit, quantite=5, gamme=gamme)
    confirmer_of(of)
    of.refresh_from_db()
    return of, of.operations.first()


class DemarrerPauserTerminerTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-mes-1', 'MRP MES 1')
        self.of, self.operation = make_of_avec_operation(self.company)

    def test_demarrer_pose_demarree_le_et_statut(self):
        demarrer_operation(self.operation)
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.statut, 'en_cours')
        self.assertIsNotNone(self.operation.demarree_le)

    def test_demarrer_est_idempotent(self):
        demarrer_operation(self.operation)
        premiere = self.operation.demarree_le
        demarrer_operation(self.operation)  # Rejoué -> ne change pas l'horodatage.
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.demarree_le, premiere)

    def test_pauser_sans_demarrer_refuse(self):
        with self.assertRaises(ValueError):
            pauser_operation(self.operation)

    def test_cycle_avec_pause_exclut_le_temps_de_pause(self):
        # Démarre à T0, pause 5 min plus tard, reprend 15 min plus tard (donc
        # 10 min de pause), termine 5 min après la reprise.
        t0 = timezone.now() - timedelta(minutes=20)
        self.operation.demarree_le = t0
        self.operation.statut = 'en_cours'
        self.operation.save(update_fields=['demarree_le', 'statut'])

        from apps.mrp.models import PauseOperationOF
        pause = PauseOperationOF.objects.create(
            operation=self.operation, debut=t0 + timedelta(minutes=5),
            fin=t0 + timedelta(minutes=15))
        self.operation.statut = 'en_pause'
        self.operation.save(update_fields=['statut'])

        # Termine "maintenant" (t0 + 20min écoulées au total, 10min de pause).
        terminer_operation(self.operation, quantite_bonne=5)
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.statut, 'terminee')
        # Temps actif attendu ~ 20 - 10 = 10 min (tolérance d'exécution).
        self.assertGreaterEqual(self.operation.temps_reel_min, Decimal('9'))
        self.assertLessEqual(self.operation.temps_reel_min, Decimal('11'))
        # La pause déjà fermée n'est pas rouverte/retouchée par la clôture.
        pause.refresh_from_db()
        self.assertEqual(pause.fin, t0 + timedelta(minutes=15))

    def test_pause_ouverte_fermee_a_la_reprise(self):
        demarrer_operation(self.operation)
        pauser_operation(self.operation)
        self.operation.refresh_from_db()
        pause = self.operation.pauses.get()
        self.assertIsNone(pause.fin)
        reprendre_operation(self.operation)
        pause.refresh_from_db()
        self.assertIsNotNone(pause.fin)

    def test_terminer_deux_fois_refuse(self):
        demarrer_operation(self.operation)
        terminer_operation(self.operation, quantite_bonne=5)
        self.operation.refresh_from_db()
        with self.assertRaises(ValueError):
            terminer_operation(self.operation, quantite_bonne=5)

    def test_rebut_sans_motif_refuse(self):
        demarrer_operation(self.operation)
        with self.assertRaises(ValueError):
            terminer_operation(
                self.operation, quantite_bonne=3, quantite_rebut=2, motif_rebut='')

    def test_rebut_avec_motif_cree_mouvement_stock(self):
        demarrer_operation(self.operation)
        terminer_operation(
            self.operation, quantite_bonne=3, quantite_rebut=2,
            motif_rebut='defaut', user=None)
        self.operation.refresh_from_db()
        self.assertEqual(self.operation.quantite_rebut, Decimal('2'))
        self.assertEqual(self.operation.motif_rebut, 'defaut')
        mvt = MouvementStock.objects.filter(
            company=self.company, produit_id=self.of.produit_id,
            type_mouvement='rebut',
            reference=f'OF-{self.of.id}-OP-{self.operation.id}').first()
        self.assertIsNotNone(mvt)
        self.assertEqual(mvt.motif_rebut, 'defaut')
        self.assertEqual(mvt.quantite, 2)


class TerminalMesApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-mes-api-1', 'MRP MES API 1')
        self.user = make_user(self.company, 'mrp-mes-api-user')
        self.api = auth(self.user)
        self.of, self.operation = make_of_avec_operation(self.company)

    def test_cycle_complet_via_api(self):
        resp = self.api.post(
            f'/api/django/mrp/operations-of/{self.operation.id}/demarrer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'en_cours')

        resp = self.api.post(
            f'/api/django/mrp/operations-of/{self.operation.id}/pauser/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'en_pause')

        resp = self.api.post(
            f'/api/django/mrp/operations-of/{self.operation.id}/reprendre/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'en_cours')

        resp = self.api.post(
            f'/api/django/mrp/operations-of/{self.operation.id}/terminer/',
            {'quantite_bonne': 5, 'quantite_rebut': 0}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'terminee')

    def test_terminer_rebut_sans_motif_400(self):
        resp = self.api.post(
            f'/api/django/mrp/operations-of/{self.operation.id}/terminer/',
            {'quantite_bonne': 1, 'quantite_rebut': 1}, format='json')
        self.assertEqual(resp.status_code, 400)

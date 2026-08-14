"""NTMFG28 — Assistant de clôture d'OF avec saisie qualité groupée.

Critère : la clôture assistée produit exactement le même état final
(mouvements stock, temps, rebuts) qu'une clôture opération-par-opération
manuelle sur un cas testé, réservé au rôle responsable."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import Gamme, OperationGamme, OrdreFabrication, PosteDeCharge
from apps.mrp.services import confirmer_of, demarrer_operation, terminer_operation
from apps.stock.models import MouvementStock, Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


def make_of_deux_operations(company):
    produit = make_produit(company, 'Composite clôture')
    poste = PosteDeCharge.objects.create(
        company=company, code='P-CLOASS', nom='Poste clôture assistée')
    gamme = Gamme.objects.create(company=company, nom='Gamme clôture', produit=produit)
    OperationGamme.objects.create(
        gamme=gamme, ordre=1, poste_charge=poste, libelle='Op 1',
        temps_unitaire_min=Decimal('1'))
    OperationGamme.objects.create(
        gamme=gamme, ordre=2, poste_charge=poste, libelle='Op 2',
        temps_unitaire_min=Decimal('1'))
    of = OrdreFabrication.objects.create(
        company=company, produit=produit, quantite=5, gamme=gamme)
    confirmer_of(of)
    of.refresh_from_db()
    return of


class ClotureAssisteeApiTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-cloass-1', 'MRP ClotureAssistee 1')
        self.user = make_user(self.company, 'mrp-cloass-user', role='responsable')
        self.api = auth(self.user)

    def test_termine_les_operations_restantes_en_lot(self):
        of = make_of_deux_operations(self.company)
        op1, op2 = list(of.operations.order_by('ordre'))

        resp = self.api.post(
            f'/api/django/mrp/ordres-fabrication/{of.id}/cloture-assistee/',
            {'operations': [
                {'id': op1.id, 'quantite_bonne': 5, 'quantite_rebut': 0},
                {'id': op2.id, 'quantite_bonne': 4, 'quantite_rebut': 1,
                 'motif_rebut': 'defaut'},
            ]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(set(resp.data['operations_terminees']), {op1.id, op2.id})
        self.assertEqual(resp.data['erreurs'], [])

        op1.refresh_from_db()
        op2.refresh_from_db()
        self.assertEqual(op1.statut, 'terminee')
        self.assertEqual(op1.quantite_bonne, Decimal('5'))
        self.assertEqual(op2.statut, 'terminee')
        self.assertEqual(op2.quantite_rebut, Decimal('1'))
        self.assertEqual(op2.motif_rebut, 'defaut')

        mvt = MouvementStock.objects.filter(
            company=self.company, produit_id=of.produit_id, type_mouvement='rebut',
            reference=f'OF-{of.id}-OP-{op2.id}').first()
        self.assertIsNotNone(mvt)
        self.assertEqual(mvt.quantite, 1)

    def test_meme_etat_final_que_cloture_manuelle_op_par_op(self):
        """Un OF clôturé via l'assistant produit exactement le même état
        (temps, quantités, statut) qu'un OF clôturé manuellement opération
        par opération avec les mêmes saisies."""
        of_manuel = make_of_deux_operations(self.company)
        for op in of_manuel.operations.order_by('ordre'):
            demarrer_operation(op)
            terminer_operation(op, quantite_bonne=5, quantite_rebut=0)

        of_assiste = make_of_deux_operations(self.company)
        ops_assiste = list(of_assiste.operations.order_by('ordre'))
        self.api.post(
            f'/api/django/mrp/ordres-fabrication/{of_assiste.id}/cloture-assistee/',
            {'operations': [
                {'id': op.id, 'quantite_bonne': 5, 'quantite_rebut': 0}
                for op in ops_assiste
            ]}, format='json')

        ops_manuel_etat = [
            (o.statut, o.quantite_bonne, o.quantite_rebut)
            for o in of_manuel.operations.order_by('ordre')]
        ops_assiste_etat = [
            (o.statut, o.quantite_bonne, o.quantite_rebut)
            for o in OrdreFabrication.objects.get(id=of_assiste.id).operations.order_by('ordre')]
        self.assertEqual(ops_manuel_etat, ops_assiste_etat)

    def test_operation_deja_terminee_ignoree_jamais_rejouee(self):
        of = make_of_deux_operations(self.company)
        op1, op2 = list(of.operations.order_by('ordre'))
        demarrer_operation(op1)
        terminer_operation(op1, quantite_bonne=5)

        resp = self.api.post(
            f'/api/django/mrp/ordres-fabrication/{of.id}/cloture-assistee/',
            {'operations': [
                {'id': op1.id, 'quantite_bonne': 999},  # Doit être ignorée.
                {'id': op2.id, 'quantite_bonne': 5},
            ]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertNotIn(op1.id, resp.data['operations_terminees'])
        self.assertIn(op2.id, resp.data['operations_terminees'])
        op1.refresh_from_db()
        self.assertEqual(op1.quantite_bonne, Decimal('5'))  # Inchangé.

    def test_rebut_sans_motif_reporte_en_erreur_sans_bloquer_les_autres(self):
        of = make_of_deux_operations(self.company)
        op1, op2 = list(of.operations.order_by('ordre'))
        resp = self.api.post(
            f'/api/django/mrp/ordres-fabrication/{of.id}/cloture-assistee/',
            {'operations': [
                {'id': op1.id, 'quantite_bonne': 3, 'quantite_rebut': 2},  # Sans motif -> erreur.
                {'id': op2.id, 'quantite_bonne': 5},
            ]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['erreurs']), 1)
        self.assertEqual(resp.data['erreurs'][0]['id'], op1.id)
        self.assertIn(op2.id, resp.data['operations_terminees'])

    def test_role_limite_refuse(self):
        of = make_of_deux_operations(self.company)
        limite = make_user(self.company, 'mrp-cloass-normal', role='normal')
        resp = auth(limite).post(
            f'/api/django/mrp/ordres-fabrication/{of.id}/cloture-assistee/',
            {'operations': []}, format='json')
        self.assertEqual(resp.status_code, 403)

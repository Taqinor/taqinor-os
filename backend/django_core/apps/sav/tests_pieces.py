"""N46 (pièces consommées → stock) + N47 (renouvellement + rapport PDF)."""
import threading
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import MouvementStock, Produit
from apps.sav.models import (
    Ticket, PieceConsommee, ContratMaintenance, TicketActivity)
from core.test_utils import WideTeardownTimeoutMixin

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestSavPieces(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='piece-co', defaults={'nom': 'Piece Co'})[0]
        self.user = User.objects.create_user(
            username='piece_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='C')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-P-1', client=self.client_obj)
        self.produit = Produit.objects.create(
            company=self.company, nom='Carte', sku='CRT-1',
            prix_vente=Decimal('200'), quantite_stock=Decimal('10'))

    def _add(self, **body):
        return self.api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/pieces/',
            {'produit': self.produit.id, **body}, format='json')

    def test_add_piece_without_decrement_keeps_stock(self):
        r = self._add(quantite='2')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data['stock_decremente'])
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('10'))

    def test_add_piece_with_decrement_reduces_stock(self):
        r = self._add(quantite='3', decrement=True)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['stock_decremente'])
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('7'))

    def test_decrement_fractionnaire_409_rien_d_ecrit(self):
        """ERR-ENF11 (cron 41296444614) : quantité conforme, unité entière du stock."""
        r = self._add(quantite='0.71', decrement=True)
        self.assertEqual(r.status_code, 409, r.data)
        self.assertFalse(PieceConsommee.objects.filter(ticket=self.ticket).exists())
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('10'))

    def test_quantite_non_positive_ou_mal_formee_400(self):
        # api-fuzz-full : "0" était « conforme » au schéma puis refusé ; le
        # motif publié l'exclut désormais, et le serveur refuse pareil.
        for quantite in ('0', '-25.2', '0.00', 'abc', '1.234', [], True):
            r = self._add(quantite=quantite)
            self.assertEqual(r.status_code, 400, (quantite, r.data))
        r = self.api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/pieces/', [],
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertFalse(PieceConsommee.objects.filter(
            ticket=self.ticket).exists())

    def test_quantite_decimale_positive_acceptee(self):
        for quantite in ('0.5', '.25', '12.50'):
            r = self._add(quantite=quantite)
            self.assertEqual(r.status_code, 201, (quantite, r.data))

    def test_retrait_destination_et_quantite_hors_schema_400(self):
        url = f'/api/django/sav/tickets/{self.ticket.id}/pieces-retirees/'
        for corps in ({'destination': ']_C.exe'}, {'operation': 'zzz'},
                      {'quantite': '-25.2'}, {'numero_serie': 5}):
            r = self.api.post(
                url, {'produit': self.produit.id, **corps}, format='json')
            self.assertEqual(r.status_code, 400, (corps, r.data))

    def test_retrait_quantite_debordante_400_fractionnaire_stock_409(self):
        """api-fuzz 24/10 — au-delà des 8 entiers de la colonne : refus de forme
        (400, plus de 500) ; une quantité fractionnaire remise en stock
        occasion s'oppose par l'état du stock entier : 409."""
        url = f'/api/django/sav/tickets/{self.ticket.id}/pieces-retirees/'
        r = self.api.post(
            url, {'produit': self.produit.id, 'quantite': '8656376060.4',
                  'destination': 'stock_occasion'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        r = self.api.post(
            url, {'produit': self.produit.id, 'quantite': '0.9',
                  'destination': 'stock_occasion'}, format='json')
        self.assertEqual(r.status_code, 409, r.data)

    def test_decrement_over_stock_blocked(self):
        # ERR80 — décrémenter plus que le stock en main est refusé (jamais
        # négatif) et ne crée pas la pièce.
        r = self._add(quantite='99', decrement=True)
        self.assertEqual(r.status_code, 409, r.data)  # ENF11 : état du stock
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('10'))
        self.assertFalse(PieceConsommee.objects.filter(
            ticket=self.ticket).exists())

    def test_pose_concurrente_et_quarantaine(self):
        """ACSV52 : le stock est relu sous verrou (poses enchaînées 10 → 8 → 7,
        remise 7 → 8) et la part en quarantaine n'est jamais prélevée (409)."""
        from apps.stock.models import MouvementStock
        from apps.stock.services_wms import mettre_en_quarantaine
        premiere = self._add(quantite='2', decrement=True)
        seconde = self._add(quantite='1', decrement=True)
        self.assertEqual((premiere.status_code, seconde.status_code), (201, 201))
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('7'))
        avant_apres = list(MouvementStock.objects.filter(
            produit=self.produit).order_by('id').values_list(
            'quantite_avant', 'quantite_apres'))
        self.assertEqual(avant_apres, [(10, 8), (8, 7)])
        mettre_en_quarantaine(
            company=self.company, produit=self.produit, quantite=5)
        refus = self._add(quantite='3', decrement=True)  # 2 disponibles
        self.assertEqual(refus.status_code, 409, refus.data)
        self.assertEqual(PieceConsommee.objects.filter(
            ticket=self.ticket).count(), 2)
        retrait = self.api.delete(
            f'/api/django/sav/tickets/{self.ticket.id}/pieces/'
            f'{seconde.data["id"]}/')
        self.assertEqual(retrait.status_code, 204)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('8'))

    def test_remove_decremented_piece_restores_stock(self):
        r = self._add(quantite='3', decrement=True)
        pid = r.data['id']
        d = self.api.delete(
            f'/api/django/sav/tickets/{self.ticket.id}/pieces/{pid}/')
        self.assertEqual(d.status_code, 204)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('10'))
        self.assertFalse(PieceConsommee.objects.filter(id=pid).exists())

    def test_pose_meme_cle_une_seule_piece(self):
        """ACNC26 — une pose renvoyée avec la même Idempotency-Key ne crée
        qu'une pièce (et une seule SORTIE de stock)."""
        url = f'/api/django/sav/tickets/{self.ticket.id}/pieces/'
        corps = {'produit': self.produit.id, 'quantite': '3', 'decrement': True}
        r1 = self.api.post(url, corps, format='json', HTTP_IDEMPOTENCY_KEY='k1')
        r2 = self.api.post(url, corps, format='json', HTTP_IDEMPOTENCY_KEY='k1')
        self.assertEqual((r1.status_code, r2.status_code), (201, 201), r2.data)
        self.assertEqual(r1.data['id'], r2.data['id'])
        self.assertEqual(PieceConsommee.objects.filter(ticket=self.ticket).count(), 1)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('7'))
        self.assertEqual(MouvementStock.objects.filter(produit=self.produit).count(), 1)

    def test_add_piece_logs_activity(self):
        # L310 — l'ajout d'une pièce (avec décrément) journalise l'Historique.
        r = self._add(quantite='2', decrement=True)
        self.assertEqual(r.status_code, 201, r.data)
        note = TicketActivity.objects.filter(
            ticket=self.ticket, kind=TicketActivity.Kind.NOTE).first()
        self.assertIsNotNone(note)
        self.assertIn('Carte', note.body)
        self.assertIn('stock', note.body)

    def test_remove_piece_logs_activity(self):
        # L310 — le retrait d'une pièce journalise aussi l'Historique.
        r = self._add(quantite='1', decrement=True)
        pid = r.data['id']
        before = TicketActivity.objects.filter(ticket=self.ticket).count()
        self.api.delete(
            f'/api/django/sav/tickets/{self.ticket.id}/pieces/{pid}/')
        after = TicketActivity.objects.filter(ticket=self.ticket).count()
        self.assertEqual(after, before + 1)
        last = TicketActivity.objects.filter(
            ticket=self.ticket).order_by('-id').first()
        self.assertIn('retirée', last.body)

    def test_pieces_listed_with_designation(self):
        self._add(quantite='1')
        r = self.api.get(
            f'/api/django/sav/tickets/{self.ticket.id}/pieces/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]['produit_nom'], 'Carte')
        # Aucun prix d'achat exposé.
        self.assertNotIn('prix_achat', r.data[0])


class TestSavPiecesConcurrence(WideTeardownTimeoutMixin, TransactionTestCase):
    """ACSV110 — deux VRAIES connexions : A tient le verrou (SORTIE 5 → 4), B relit 4."""

    def setUp(self):
        self.company = Company.objects.create(nom='ACSV110', slug='acsv110-co')
        self.user = User.objects.create_user(
            username='acsv110_admin', password='x', role_legacy='admin', company=self.company)
        self.ticket = Ticket.objects.create(company=self.company, reference='SAV-ACSV110',
                                            client=Client.objects.create(company=self.company, nom='C'))
        self.produit = Produit.objects.create(company=self.company, nom='Carte', sku='CRT-ACSV110',
                                              prix_vente=Decimal('200'), quantite_stock=Decimal('5'))

    def _course(self, geste_b):
        from apps.stock import services as stock
        original, a_tient, b_tente, res = stock.verrouiller_produit, threading.Event(), threading.Event(), {}

        def fil_a():
            with transaction.atomic():
                p = original(self.produit.pk)
                stock.record_stock_movement(
                    company=self.company, produit=p, type_mouvement=stock.mouvement_type_sortie(),
                    quantite=1, quantite_avant=p.quantite_stock, quantite_apres=p.quantite_stock - 1,
                    reference='ACSV110-A', note='A', created_by=self.user)
                a_tient.set()
                b_tente.wait(5)  # B tente le verrou : A commite (B relit alors 4)
            connection.close()

        def fil_b():
            a_tient.wait(5)
            res['b'] = geste_b(auth(self.user)).status_code
            connection.close()
        with mock.patch.object(stock, 'verrouiller_produit',
                               side_effect=lambda pk: (b_tente.set(), original(pk))[1]):
            fils = [threading.Thread(target=fil_a), threading.Thread(target=fil_b)]
            for fil in fils:
                fil.start()
            for fil in fils:
                fil.join(15)
        self.produit.refresh_from_db()
        return res.get('b'), self.produit.quantite_stock, list(MouvementStock.objects.filter(
            produit=self.produit).order_by('id').values_list('quantite_avant', 'quantite_apres'))

    def test_deux_poses_concurrentes_stock_3(self):
        url = f'/api/django/sav/tickets/{self.ticket.id}/pieces/'
        self.assertEqual(self._course(lambda api: api.post(url, {
            'produit': self.produit.id, 'quantite': '1', 'decrement': True}, format='json')),
            (201, Decimal('3'), [(5, 4), (4, 3)]))

    def test_remise_concurrente_stock_5(self):
        piece = PieceConsommee.objects.create(
            company=self.company, ticket=self.ticket, produit=self.produit,
            quantite=Decimal('1'), stock_decremente=True, created_by=self.user)
        self.assertEqual(self._course(lambda api: api.delete(
            f'/api/django/sav/tickets/{self.ticket.id}/pieces/{piece.id}/')), (204, Decimal('5'), [(5, 4), (4, 5)]))

    def test_deux_retraits_croises_une_seule_entree(self):
        """ACNC26 — deux DELETE de la même pièce décrémentée lisent la pièce
        avant que le premier ne commite : une seule ENTRÉE (10 → 13), le second
        rend 404."""
        from apps.stock import services as stock
        Produit.objects.filter(pk=self.produit.pk).update(quantite_stock=Decimal('10'))
        piece = PieceConsommee.objects.create(
            company=self.company, ticket=self.ticket, produit=self.produit,
            quantite=Decimal('3'), stock_decremente=True, created_by=self.user)
        url = f'/api/django/sav/tickets/{self.ticket.id}/pieces/{piece.id}/'
        original, a_tient, b_tente, res = stock.verrouiller_produit, threading.Event(), threading.Event(), {}

        def verrou(pk):
            if threading.current_thread().name == 'A':
                a_tient.set()
                b_tente.wait(2)  # B a lu la pièce (non relue : il atteint ce verrou)
            else:
                b_tente.set()
            return original(pk)

        def fil(nom):
            if nom == 'B':
                a_tient.wait(5)
            res[nom] = auth(self.user).delete(url).status_code
            connection.close()
        with mock.patch.object(stock, 'verrouiller_produit', side_effect=verrou):
            fils = [threading.Thread(target=fil, args=(n,), name=n) for n in 'AB']
            for f in fils:
                f.start()
            for f in fils:
                f.join(15)
        self.produit.refresh_from_db()
        self.assertEqual(res, {'A': 204, 'B': 404})
        self.assertEqual(self.produit.quantite_stock, Decimal('13'))
        self.assertEqual(MouvementStock.objects.filter(produit=self.produit).count(), 1)


class TestMaintenanceRenewal(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='maint-co', defaults={'nom': 'Maint Co'})[0]
        self.user = User.objects.create_user(
            username='maint_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='C')

    def test_renouvellement_du_flag(self):
        past = date.today() - timedelta(days=1)
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite='annuel', date_debut=date.today(),
            date_renouvellement=past, actif=True)
        self.assertTrue(contrat.renouvellement_du())

    def test_renouvellement_not_due_without_date(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite='annuel', date_debut=date.today(), actif=True)
        self.assertFalse(contrat.renouvellement_du())

    def test_rapport_pdf(self):
        contrat = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            periodicite='annuel', date_debut=date.today(), actif=True)
        r = self.api.get(
            '/api/django/sav/contrats-maintenance/'
            f'{contrat.id}/rapport-pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

"""XSAV27 — Prêt / échange anticipé d'équipement (loaner).

Couvre :
  * sortir un prêt décrémente le stock exactement une fois (SORTIE) ;
  * retourner un prêt réintègre le stock exactement une fois (ENTRÉE),
    idempotent (un second retour ne mouvemente rien de plus) ;
  * jamais de stock négatif (refuse si aucune unité disponible) ;
  * alerte de dépassement : `en_retard` correct + `services.prets_en_retard`
    remonte les prêts EN_COURS dont la date prévue est dépassée.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xsav27 -v 2
"""
import threading
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav.models import PretEquipement, Ticket
from apps.sav.services import (
    PretEquipementError, creer_pret_equipement, prets_en_retard,
    retourner_pret_equipement,
)
from apps.stock.models import MouvementStock, Produit
from core.test_utils import WideTeardownTimeoutMixin

User = get_user_model()


def make_company(slug='sav-xsav27', nom='Sav Co XSAV27'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class XSAV27PretEquipementServiceTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='xsav27_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Test',
            email='xsav27-client@example.invalid')
        self.inst = Installation.objects.create(
            company=self.company, reference='CHT-XSAV27', client=self.client_obj)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur Prêt', sku='OND-XSAV27',
            prix_achat=3000, prix_vente=6000, quantite_stock=2)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV27-1',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)

    def test_sortie_decremente_le_stock_une_fois(self):
        pret = creer_pret_equipement(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            numero_serie='SN-PRET-1', date_sortie=date.today(),
            date_retour_prevue=date.today() + timedelta(days=14),
            user=self.admin)
        self.assertTrue(pret.stock_sorti)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 1)

    def test_stock_insuffisant_refuse(self):
        self.onduleur.quantite_stock = 0
        self.onduleur.save(update_fields=['quantite_stock'])
        with self.assertRaises(PretEquipementError):
            creer_pret_equipement(
                company=self.company, ticket=self.ticket,
                produit=self.onduleur, numero_serie='SN-PRET-2',
                date_sortie=date.today(), date_retour_prevue=None,
                user=self.admin)

    def test_retour_reintegre_stock_une_seule_fois(self):
        pret = creer_pret_equipement(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            numero_serie='SN-PRET-3', date_sortie=date.today(),
            date_retour_prevue=date.today() + timedelta(days=7),
            user=self.admin)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 1)

        retourner_pret_equipement(
            pret=pret, date_retour_reelle=date.today(), user=self.admin)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 2)

        # Idempotence : un second retour ne mouvemente rien de plus.
        pret.refresh_from_db()
        retourner_pret_equipement(
            pret=pret, date_retour_reelle=date.today(), user=self.admin)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 2)
        self.assertEqual(pret.statut, PretEquipement.Statut.RETOURNE)

    def test_alerte_depassement(self):
        pret_en_retard = creer_pret_equipement(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            numero_serie='SN-PRET-4', date_sortie=date.today() - timedelta(days=30),
            date_retour_prevue=date.today() - timedelta(days=5),
            user=self.admin)
        self.assertTrue(pret_en_retard.en_retard)

        retards = prets_en_retard(self.company)
        self.assertIn(pret_en_retard.id, [p.id for p in retards])

        # Un prêt retourné n'est jamais en retard, même si la date prévue
        # est dépassée.
        retourner_pret_equipement(
            pret=pret_en_retard, date_retour_reelle=date.today(),
            user=self.admin)
        self.assertFalse(pret_en_retard.en_retard)

    def test_endpoint_sortie_et_retour(self):
        api = auth(self.admin)
        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/prets-equipement/',
            {'produit': self.onduleur.id, 'numero_serie': 'SN-API-1',
             'date_retour_prevue': (date.today() + timedelta(days=10)).isoformat()})
        self.assertEqual(resp.status_code, 201, resp.content)
        pret_id = resp.data['id']

        resp = api.get(
            f'/api/django/sav/tickets/{self.ticket.id}/prets-equipement/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 1)

        resp = api.post(
            f'/api/django/sav/tickets/{self.ticket.id}/prets-equipement/'
            f'{pret_id}/retourner/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], PretEquipement.Statut.RETOURNE)
        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 2)

    def test_corps_mal_forme_400_pas_500(self):
        # api-fuzz-full : ``numero_serie`` numérique levait AttributeError (500).
        api = auth(self.admin)
        url = f'/api/django/sav/tickets/{self.ticket.id}/prets-equipement/'
        for corps in ({'produit': self.onduleur.id, 'numero_serie': 24027},
                      {'produit': self.onduleur.id, 'date_sortie': ''},
                      {'produit': self.onduleur.id,
                       'date_retour_prevue': '2026-1-5'},
                      [], {}):
            resp = api.post(url, corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.content))
        self.assertFalse(PretEquipement.objects.exists())

    def test_retourner_corps_non_objet_ou_date_illisible_400_pas_500(self):
        # api-fuzz ERR-ENF11-FUZZ-SAV : corps ``false`` -> ``bool`` sans
        # ``.get`` (500) ; la date publiée illisible = 400 nommé.
        api = auth(self.admin)
        pret = creer_pret_equipement(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            numero_serie='SN-PRET-RET', date_sortie=date.today(),
            date_retour_prevue=date.today() + timedelta(days=14),
            user=self.admin)
        url = (f'/api/django/sav/tickets/{self.ticket.id}/prets-equipement/'
               f'{pret.id}/retourner/')
        for corps in (False, [1], 7, {'date_retour_reelle': 'hier'},
                      {'date_retour_reelle': 20260105}):
            resp = api.post(url, corps, format='json')
            self.assertEqual(resp.status_code, 400, (corps, resp.content))
        pret.refresh_from_db()
        self.assertNotEqual(pret.statut, PretEquipement.Statut.RETOURNE)

    def test_pret_en_cours_bloque_cloture_annulation_suit_fusion(self):
        """ACSV67 : un prêt en cours refuse clôture et annulation (409) ; à la
        fusion, le prêt du doublon suit le principal ; retourné : clôture 200."""
        api = auth(self.admin)
        Ticket.objects.filter(pk=self.ticket.pk).update(
            statut=Ticket.Statut.RESOLU)
        pret = creer_pret_equipement(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            numero_serie='SN-PRET-67', date_sortie=date.today(),
            date_retour_prevue=date.today() + timedelta(days=14),
            user=self.admin)
        base = f'/api/django/sav/tickets/{self.ticket.id}'
        r = api.post(f'{base}/cloturer/', {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        # ConflitEtat (APIException) rend les éléments de liste en chaînes,
        # comme « interventions_ouvertes » (YSERV2).
        self.assertEqual(r.data['prets_en_cours'], [str(pret.id)])
        r = api.post(f'{base}/annuler/', {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.statut, Ticket.Statut.RESOLU)
        self.assertFalse(self.ticket.annule)
        doublon = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV27-2',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)
        pret_doublon = creer_pret_equipement(
            company=self.company, ticket=doublon, produit=self.onduleur,
            numero_serie='SN-PRET-67B', date_sortie=date.today(),
            date_retour_prevue=None, user=self.admin)
        r = api.post(f'{base}/fusionner/', {'doublon_id': doublon.id},
                     format='json')
        self.assertEqual(r.status_code, 200, r.data)
        pret_doublon.refresh_from_db()
        self.assertEqual(pret_doublon.ticket_id, self.ticket.id)
        for en_cours in (pret, pret_doublon):
            retourner_pret_equipement(
                pret=en_cours, date_retour_reelle=date.today(), user=self.admin)
        r = api.post(f'{base}/cloturer/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)

    def test_pret_en_cours_bloque_annulation_en_lot_et_patch(self):
        """ACSV108 : l'annulation EN LOT passe par la même porte (T en
        échec, U annulé) ; un PATCH ``{annule: true}`` ne change rien."""
        api = auth(self.admin)
        creer_pret_equipement(
            company=self.company, ticket=self.ticket, produit=self.onduleur,
            numero_serie='SN-PRET-108', date_sortie=date.today(),
            date_retour_prevue=None, user=self.admin)
        sans_pret = Ticket.objects.create(
            company=self.company, reference='SAV-XSAV27-108',
            client=self.client_obj, installation=self.inst,
            type=Ticket.Type.CORRECTIF, created_by=self.admin)
        r = api.post('/api/django/sav/tickets/actions-groupees/', {
            'ids': [self.ticket.id, sans_pret.id], 'operation': 'annuler'},
            format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['traites'], [sans_pret.id])
        self.assertEqual([e['id'] for e in r.data['echecs']], [self.ticket.id])
        self.assertIn("Impossible d'annuler", r.data['echecs'][0]['raison'])
        sans_pret.refresh_from_db()
        self.assertTrue(sans_pret.annule)
        r = api.patch(f'/api/django/sav/tickets/{self.ticket.id}/',
                      {'annule': True}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['annule'])
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.annule)
        self.assertTrue(self.ticket.prets_equipement.filter(
            statut=PretEquipement.Statut.EN_COURS).exists())


class XSAV27PretConcurrenceTest(WideTeardownTimeoutMixin, TransactionTestCase):
    """ACNC27 — deux VRAIES connexions (patron `TestSavPiecesConcurrence._course`
    de `tests_pieces.py`) : A tient le verrou et a écrit, B arrive pendant."""

    def setUp(self):
        self.company = make_company(slug='sav-acnc27', nom='Sav Co ACNC27')
        self.admin = User.objects.create_user(
            username='acnc27_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(company=self.company, nom='Client')
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-ACNC27-1',
            client=self.client_obj, type=Ticket.Type.CORRECTIF, created_by=self.admin)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur Prêt', sku='OND-ACNC27',
            prix_achat=3000, prix_vente=6000, quantite_stock=10)

    def _course(self, geste_a, geste_b):
        """A (atomic) joue `geste_a` puis attend que B tente le verrou produit
        (ou 3 s) avant de commiter ; B lance `geste_b` dès que A a écrit."""
        from apps.stock import services as stock
        original, a_tient, b_tente, res = stock.verrouiller_produit, threading.Event(), threading.Event(), {}

        def verrou(pk):
            if threading.current_thread().name == 'B':
                b_tente.set()
            return original(pk)

        def fil_a():
            with transaction.atomic():
                geste_a()
                a_tient.set()
                b_tente.wait(3)
            connection.close()

        def fil_b():
            a_tient.wait(5)
            res['b'] = geste_b(auth(self.admin)).status_code
            connection.close()
        with mock.patch.object(stock, 'verrouiller_produit', side_effect=verrou):
            fils = [threading.Thread(target=fil_a, name='A'), threading.Thread(target=fil_b, name='B')]
            for fil in fils:
                fil.start()
            for fil in fils:
                fil.join(15)
        self.produit.refresh_from_db()
        return res.get('b')

    def _poser_pret(self):
        return creer_pret_equipement(
            company=self.company, ticket=self.ticket, produit=self.produit,
            numero_serie='SN-A', date_sortie=date.today(),
            date_retour_prevue=None, user=self.admin)

    def test_deux_prets_simultanes_stock_8(self):
        url = f'/api/django/sav/tickets/{self.ticket.id}/prets-equipement/'
        statut = self._course(self._poser_pret, lambda api: api.post(
            url, {'produit': self.produit.id, 'numero_serie': 'SN-B'}, format='json'))
        self.assertEqual(statut, 201)
        self.assertEqual(self.produit.quantite_stock, 8)
        self.assertEqual(list(MouvementStock.objects.filter(produit=self.produit).order_by('id')
                              .values_list('quantite_avant', 'quantite_apres')), [(10, 9), (9, 8)])

    def test_deux_retours_croises_une_seule_entree(self):
        with transaction.atomic():
            pret = self._poser_pret()  # stock 10 → 9, prêt EN_COURS
        url = (f'/api/django/sav/tickets/{self.ticket.id}/prets-equipement/'
               f'{pret.id}/retourner/')

        def retour_a():
            relu = PretEquipement.objects.select_for_update().get(pk=pret.pk)
            retourner_pret_equipement(
                pret=relu, date_retour_reelle=date.today(), user=self.admin)
        statut = self._course(retour_a, lambda api: api.post(url, {}, format='json'))
        self.assertEqual(statut, 200)
        self.assertEqual(self.produit.quantite_stock, 10)
        pret.refresh_from_db()
        self.assertTrue(pret.stock_reintegre)
        self.assertEqual(pret.statut, PretEquipement.Statut.RETOURNE)
        self.assertEqual(MouvementStock.objects.filter(
            produit=self.produit, quantite_avant=9, quantite_apres=10).count(), 1)
        self.assertEqual(MouvementStock.objects.filter(produit=self.produit).count(), 2)

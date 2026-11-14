"""YSTCK5 — `expedier`/`livrer` sur une Livraison ventilent le grand livre.

Avant : `LivraisonViewSet.expedier`/`livrer`/`annuler` changeaient SEULEMENT le
statut — les `LivraisonLigne` ne réservaient/déplaçaient jamais rien. Ces
tests couvrent :

  * `expedier` transfère les lignes du dépôt vers l'emplacement van (total
    société inchangé — c'est un TRANSFERT, jamais une sortie) ;
  * `annuler` une livraison expédiée contre-transfère (van → dépôt) ;
  * idempotence : ré-expédier ne double pas le transfert ;
  * mode `direct_site` : jamais de transfert (le dépôt n'est jamais
    décrémenté) ;
  * aucun double mouvement avec la consommation chantier (`consume_
    reservations`, indépendante, sort à « Installé »).

Run :
    python manage.py test apps.installations.tests_ystck5_livraison_stock -v2
"""
import itertools
import threading
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import (
    Produit, EmplacementStock, StockEmplacement, TransfertStock)
from apps.installations.models import Installation, Livraison, LivraisonLigne
from core.test_utils import WideTeardownTimeoutMixin
from testkit.verrous import attendre_un_ecrivain_bloque

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'ystck5-co-{n}', defaults={'nom': f'YSTCK5 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ystck5-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='YSTCK5',
        email=f'ystck5-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-YSTCK5-{n}', client=client,
        statut=Installation.Statut.PLANIFIE)


def make_produit(company, quantite_stock=Decimal('20')):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=f'Onduleur {n}',
        prix_vente=Decimal('500'), quantite_stock=quantite_stock)


class TestExpedierVentileStock(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.produit = make_produit(self.company, quantite_stock=Decimal('20'))
        self.depot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal', is_principal=True)
        self.liv = Livraison.objects.create(
            company=self.company, reference='LIV-YSTCK5-0001',
            installation=self.inst, depot=self.depot,
            statut=Livraison.Statut.PLANIFIEE)
        LivraisonLigne.objects.create(
            livraison=self.liv, produit=self.produit,
            designation=self.produit.nom, quantite=4)

    def test_expedier_transfere_depot_vers_van(self):
        r = self.api.post(f'{BASE}/livraisons/{self.liv.id}/expedier/')
        self.assertEqual(r.status_code, 200, r.data)
        self.liv.refresh_from_db()
        self.assertTrue(self.liv.stock_mouvemente)
        self.produit.refresh_from_db()
        # Total société inchangé (transfert, pas une sortie).
        self.assertEqual(self.produit.quantite_stock, Decimal('20'))
        van = EmplacementStock.objects.get(
            company=self.company, is_principal=False)
        se = StockEmplacement.objects.get(produit=self.produit, emplacement=van)
        self.assertEqual(se.quantite, 4)

    def test_expedier_idempotent_ne_double_pas(self):
        self.api.post(f'{BASE}/livraisons/{self.liv.id}/expedier/')
        # Deuxième appel (ex. ré-enregistrement du même statut) : no-op stock.
        from apps.installations.services import ventiler_stock_livraison
        self.liv.refresh_from_db()
        applied = ventiler_stock_livraison(self.liv, self.user)
        self.assertEqual(applied, 0)
        van = EmplacementStock.objects.get(
            company=self.company, is_principal=False)
        se = StockEmplacement.objects.get(produit=self.produit, emplacement=van)
        self.assertEqual(se.quantite, 4)

    def test_annuler_contre_transfere(self):
        self.api.post(f'{BASE}/livraisons/{self.liv.id}/expedier/')
        r = self.api.post(f'{BASE}/livraisons/{self.liv.id}/annuler/')
        self.assertEqual(r.status_code, 200, r.data)
        self.liv.refresh_from_db()
        self.assertFalse(self.liv.stock_mouvemente)
        van = EmplacementStock.objects.get(
            company=self.company, is_principal=False)
        se = StockEmplacement.objects.filter(
            produit=self.produit, emplacement=van).first()
        self.assertEqual((se.quantite if se else 0), 0)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, Decimal('20'))

    def test_mode_direct_site_ne_transfere_jamais(self):
        self.liv.mode_acheminement = Livraison.ModeAcheminement.DIRECT_SITE
        self.liv.save(update_fields=['mode_acheminement'])
        r = self.api.post(f'{BASE}/livraisons/{self.liv.id}/expedier/')
        self.assertEqual(r.status_code, 200, r.data)
        self.liv.refresh_from_db()
        self.assertFalse(self.liv.stock_mouvemente)
        self.assertFalse(
            StockEmplacement.objects.filter(produit=self.produit).exists())

    def test_suppression_des_pieces_de_preuve_fermee(self):
        """ASUP20 — livraison livrée à preuve signée : 409 nommant la preuve,
        rien supprimé ; livraison planifiée sans preuve : 204 ; consentement
        GPS et provision GR/IR : 405, intacts (compte Directeur livré)."""
        from django.utils import timezone
        from apps.installations.models import (
            GpsConsentRecord, PreuveLivraison, ReceptionNonFacturee,
        )
        from apps.roles.models import Role
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=dict(CANONICAL_SYSTEM_ROLES)['Directeur'])
        directeur = User.objects.create_user(
            username=f'ystck5-dir-{next(_seq)}', password='x',
            company=self.company, role=role)
        api = auth(directeur)
        Livraison.objects.filter(pk=self.liv.pk).update(
            statut=Livraison.Statut.LIVREE)
        preuve = PreuveLivraison.objects.create(
            company=self.company, livraison=self.liv,
            signataire_nom='M. Client', horodatage=timezone.now())
        r = api.delete(f'{BASE}/livraisons/{self.liv.id}/')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('preuve de livraison est signée', r.data['detail'])
        self.assertTrue(PreuveLivraison.objects.filter(pk=preuve.pk).exists())
        brouillon = Livraison.objects.create(
            company=self.company, reference='LIV-YSTCK5-0002',
            installation=self.inst, statut=Livraison.Statut.PLANIFIEE)
        r = api.delete(f'{BASE}/livraisons/{brouillon.id}/')
        self.assertEqual(r.status_code, 204, getattr(r, 'data', None))
        consentement = GpsConsentRecord.objects.create(
            company=self.company, technicien=self.user)
        provision = ReceptionNonFacturee.objects.create(
            company=self.company, montant_provision=Decimal('100'),
            lettre=True)
        for url in (f'{BASE}/gps-consentements/{consentement.id}/',
                    f'{BASE}/receptions-non-facturees/{provision.id}/'):
            self.assertEqual(api.delete(url).status_code, 405, url)
        self.assertTrue(GpsConsentRecord.objects.filter(
            pk=consentement.pk).exists())
        self.assertTrue(ReceptionNonFacturee.objects.filter(
            pk=provision.pk).exists())


class AnnulerConcurrenceTests(WideTeardownTimeoutMixin, TransactionTestCase):
    """ACNC57 — deux VRAIES connexions (patron ``tests_ystck2_transfert_
    executer.py::ExecuterConcurrenceTests``) : A annule et tient sa transaction
    dans ``transfer_stock`` ; B annule la même livraison au même moment."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        inst = make_installation(self.company)
        self.produit = make_produit(self.company, quantite_stock=Decimal('10'))
        self.depot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt principal', is_principal=True)
        self.livs = []
        for n in (1, 2):
            liv = Livraison.objects.create(
                company=self.company, reference=f'LIV-ACNC57-{n}',
                installation=inst, depot=self.depot,
                statut=Livraison.Statut.PLANIFIEE)
            LivraisonLigne.objects.create(
                livraison=liv, produit=self.produit,
                designation=self.produit.nom, quantite=5)
            r = auth(self.user).post(f'{BASE}/livraisons/{liv.id}/expedier/')
            self.assertEqual(r.status_code, 200, r.data)
            self.livs.append(liv)

    def test_deux_annulations_croisees_un_seul_contre_transfert(self):
        from apps.stock import services as stock
        original = stock.transfer_stock
        a_tient, b_tente, b_fini, res = (
            threading.Event(), threading.Event(), threading.Event(), {})
        url = f'{BASE}/livraisons/{self.livs[0].id}/annuler/'

        def transfert_lent(**kwargs):
            if not a_tient.is_set():  # A : tient sa transaction ouverte
                a_tient.set()
                b_tente.wait(5)
                attendre_un_ecrivain_bloque(ou_bien=b_fini)
            return original(**kwargs)

        def fil(nom):
            if nom == 'b':
                a_tient.wait(5)
                b_tente.set()
            res[nom] = auth(self.user).post(url, {}, format='json').status_code
            if nom == 'b':
                b_fini.set()
            connection.close()

        with mock.patch.object(stock, 'transfer_stock', side_effect=transfert_lent):
            fils = [threading.Thread(target=fil, args=(n,)) for n in ('a', 'b')]
            for f in fils:
                f.start()
            for f in fils:
                f.join(20)
        self.assertEqual(sorted(res.values()), [200, 409], res)
        self.assertEqual(TransfertStock.objects.filter(
            company=self.company,
            note__startswith='Annulation livraison').count(), 1)
        van = EmplacementStock.objects.get(
            company=self.company, is_principal=False)
        quantite = {e: StockEmplacement.objects.get(
            produit=self.produit, emplacement=e).quantite
            for e in (van, self.depot)}
        self.assertEqual(quantite, {van: 5, self.depot: 5})
        liv = Livraison.objects.get(pk=self.livs[0].pk)
        self.assertEqual(liv.statut, Livraison.Statut.ANNULEE)
        self.assertFalse(liv.stock_mouvemente)

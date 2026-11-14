"""AUD118 — un bon de commande déjà facturé ne s'annule plus en silence.

``annuler`` ne refusait qu'un BC au statut LIVRE, alors que le bouton
« Facture » est proposé dès `confirme` et que le bouton Annuler restait visible
tant que le statut n'était ni `livre` ni `annule`. Rien n'était fait de la
facture : ni annulée, ni signalée, ni même détachée (``Facture.bon_commande``
est SET_NULL). Un BC annulé « par erreur de saisie » laissait en vie une
facture émise que plus aucun écran ne rattachait à son origine.

La voie correcte : annuler d'abord la FACTURE (action dédiée, qui émet
``facture_annulee`` et déclenche l'extourne), puis le bon de commande.
"""
import threading
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    BonCommande, Devis, Facture, LigneDevis, LivraisonBC)
from authentication.models import Company
from core.test_utils import WideTeardownTimeoutMixin
from testkit.verrous import attendre_un_ecrivain_bloque

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestAnnulerBcFacture(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD118 Co', slug=f'aud118-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'aud118_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD118', prenom='Client',
            telephone='+212600000118')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit', sku=f'AUD118-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=500)
        self.devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-AUD118-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Kit',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        self.bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-AUD118-{_nxt()}',
            devis=self.devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)

    def _facture(self, statut=Facture.Statut.EMISE):
        return Facture.objects.create(
            company=self.company, client=self.client_obj,
            bon_commande=self.bc, devis=self.devis,
            reference=f'FAC-AUD118-{_nxt()}', statut=statut,
            taux_tva=Decimal('20'))

    def _annuler(self):
        return self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/annuler/')

    def test_bc_facture_refuse_l_annulation_en_409(self):
        """ROUGE avant le correctif : 200, et la facture restait orpheline."""
        facture = self._facture()
        resp = self._annuler()
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertIn(facture.reference, resp.data['detail'])
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.CONFIRME)

    def test_apres_annulation_de_la_facture_le_bc_s_annule(self):
        facture = self._facture()
        facture.statut = Facture.Statut.ANNULEE
        facture.save(update_fields=['statut'])
        resp = self._annuler()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.ANNULE)

    def test_bc_sans_facture_s_annule_comme_avant(self):
        resp = self._annuler()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.ANNULE)

    def test_facture_active_distinct_de_has_facture(self):
        """L'écran masque « Annuler » sur `facture_active`, pas sur
        `has_facture` : une facture ANNULÉE ne doit plus rien bloquer."""
        facture = self._facture()
        resp = self.api.get('/api/django/ventes/bons-commande/')
        ligne = next(r for r in resp.data.get('results', resp.data)
                     if r['id'] == self.bc.id)
        self.assertTrue(ligne['has_facture'])
        self.assertTrue(ligne['facture_active'])

        facture.statut = Facture.Statut.ANNULEE
        facture.save(update_fields=['statut'])
        resp = self.api.get('/api/django/ventes/bons-commande/')
        ligne = next(r for r in resp.data.get('results', resp.data)
                     if r['id'] == self.bc.id)
        self.assertTrue(ligne['has_facture'])
        self.assertFalse(ligne['facture_active'])


class AnnulerBcConcurrenceTests(WideTeardownTimeoutMixin, TransactionTestCase):
    """ACNC62 (C-ACNC-VER2-100) — « Annuler » croisé avec « Créer la
    facture » / « Livrer partiellement » (deux VRAIES connexions) : A tient
    le verrou du BC après avoir écrit la facture (resp. la livraison), B
    annule et attend ; après le commit de A, B répond 409 et le BC reste
    confirmé. Mutant : retirer ``select_for_update`` d'``annuler`` ⇒ 200,
    BC annulé portant une facture vivante (resp. une livraison)."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACNC62 Co', slug=f'acnc62-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'acnc62_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='ACNC62', prenom='Client',
            telephone='+212600000162')
        devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-ACNC62-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        self.bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-ACNC62-{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)

    def _croiser(self, ecrire_sous_verrou):
        res, b_fini = {}, threading.Event()

        def annuler():
            api = APIClient()
            api.credentials(HTTP_AUTHORIZATION=(
                f'Bearer {AccessToken.for_user(self.user)}'))
            res['b'] = api.post(
                f'/api/django/ventes/bons-commande/{self.bc.id}/annuler/')
            b_fini.set()
            connection.close()

        fil = threading.Thread(target=annuler)
        with transaction.atomic():
            BonCommande.objects.select_for_update().get(pk=self.bc.pk)
            ecrire_sous_verrou()
            fil.start()
            self.assertTrue(attendre_un_ecrivain_bloque(ou_bien=b_fini))
        fil.join(20)
        self.assertEqual(res['b'].status_code, 409, res['b'].data)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.statut, BonCommande.Statut.CONFIRME)

    def test_annuler_croise_creer_facture(self):
        self._croiser(lambda: Facture.objects.create(
            company=self.company, client=self.client_obj,
            bon_commande=self.bc, reference=f'BROUILLON-ACNC62-{_nxt()}',
            statut=Facture.Statut.BROUILLON, taux_tva=Decimal('20')))
        self.assertTrue(Facture.objects.filter(bon_commande=self.bc).exclude(
            statut=Facture.Statut.ANNULEE).exists())

    def test_annuler_croise_livrer_partiel(self):
        self._croiser(lambda: LivraisonBC.objects.create(
            company=self.company, bon_commande=self.bc,
            date_livraison=date.today(), created_by=self.user))
        self.assertEqual(LivraisonBC.objects.filter(
            bon_commande=self.bc).count(), 1)

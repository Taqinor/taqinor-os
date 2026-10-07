"""ASTK180 / ASTK181 — confirmation fournisseur d'un BCF (portes jeton ET
compte, cœur partagé ``_appliquer_confirmation_bcf_fournisseur``).

ASTK180 (sonde FOUR-5) : brouillon 200, annulé 200, reçu 200 ; OTD avant
{écart 9,0 j ; à l'heure 0 %} → après {0,0 j ; 100 %}. Désormais : 409 pour
tout BCF non `envoye` ou déjà (partiellement) reçu, date inchangée, OTD
inchangé ; un BCF `envoye` sans réception reste confirmable (200).

Source réelle : services de confirmation et ``otd_stats`` réels, vue publique
réelle — aucun mock.

Run :
    python manage.py test apps.stock.test_astk_confirmation_bcf -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    ConfirmationBcfRefusee, confirmer_bcf_compte_fournisseur,
    generer_token_portail_fournisseur, otd_stats,
)
from authentication.models import Company

User = get_user_model()

PUBLIC = '/api/django/public/stock/portail-fournisseur/'
MSG_409 = 'Seul un bon de commande envoyé et non reçu peut être confirmé.'


class ConfirmationBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK180', slug='astk180-co')
        self.user = User.objects.create_user(
            username='astk180-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK180')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK180', sku='OND-ASTK180',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))
        self.token = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user).token
        self.anon = APIClient()
        self._seq = 0

    def _bcf(self, statut, quantite_recue=0):
        self._seq += 1
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK180-{self._seq}',
            fournisseur=self.fournisseur, statut=statut,
            date_livraison_prevue=datetime.date(2026, 10, 1),
            created_by=self.user)
        bc.lignes.create(
            produit=self.produit, quantite=2, quantite_recue=quantite_recue,
            prix_achat_unitaire=Decimal('1200'))
        return bc

    def _confirmer(self, bc, corps=None):
        return self.anon.post(
            f'{PUBLIC}{self.token}/bcf/{bc.id}/confirmer/',
            corps if corps is not None
            else {'date_confirmee_fournisseur': '2026-10-10'},
            format='json')


class ConfirmationTests(ConfirmationBase):
    def _assert_409_inchange(self, bc):
        rep = self._confirmer(bc)
        self.assertEqual(rep.status_code, 409, rep.data)
        self.assertEqual(rep.data['detail'], MSG_409)
        bc.refresh_from_db()
        self.assertIsNone(bc.date_confirmee_fournisseur)

    def test_brouillon_409(self):
        self._assert_409_inchange(
            self._bcf(BonCommandeFournisseur.Statut.BROUILLON))

    def test_annule_409(self):
        self._assert_409_inchange(
            self._bcf(BonCommandeFournisseur.Statut.ANNULE))

    def test_recu_409_otd_inchange(self):
        bc = self._bcf(BonCommandeFournisseur.Statut.RECU, quantite_recue=2)
        ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK180-1',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 10))
        otd_avant = otd_stats(self.company, self.fournisseur)
        self._assert_409_inchange(bc)
        self.assertEqual(otd_stats(self.company, self.fournisseur), otd_avant)

    def test_partiellement_recu_409(self):
        self._assert_409_inchange(
            self._bcf(BonCommandeFournisseur.Statut.ENVOYE, quantite_recue=1))

    def test_envoye_200(self):
        bc = self._bcf(BonCommandeFournisseur.Statut.ENVOYE)
        rep = self._confirmer(bc)
        self.assertEqual(rep.status_code, 200, rep.data)
        bc.refresh_from_db()
        self.assertEqual(bc.date_confirmee_fournisseur,
                         datetime.date(2026, 10, 10))
        # La date DEMANDÉE n'est jamais écrasée.
        self.assertEqual(bc.date_livraison_prevue, datetime.date(2026, 10, 1))

    def test_porte_compte_meme_garde(self):
        bc = self._bcf(BonCommandeFournisseur.Statut.RECU, quantite_recue=2)
        with self.assertRaises(ConfirmationBcfRefusee):
            confirmer_bcf_compte_fournisseur(
                self.company, self.fournisseur.id, bc.id,
                date_confirmee=datetime.date(2026, 10, 10))
        bc.refresh_from_db()
        self.assertIsNone(bc.date_confirmee_fournisseur)

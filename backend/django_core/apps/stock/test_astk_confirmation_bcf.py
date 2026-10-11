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

    def test_suggestions_sans_montant_pour_un_commercial(self):
        """ASTK240 — sans `prix_achat_voir`, suggestions-bcf (et son alias
        /achats/) sert le BCF du fournisseur SANS montant d'achat ; avec le
        code (compte légacy responsable), les montants sont servis — les deux
        formes sont celles du contrat suggestions_bcf.json."""
        import json
        from pathlib import Path
        from apps.roles.models import Role
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        contrat = json.loads((Path(__file__).resolve().parent / 'contract_samples'
                              / 'suggestions_bcf.json').read_text(encoding='utf-8'))
        bc = self._bcf(BonCommandeFournisseur.Statut.ENVOYE)
        BonCommandeFournisseur.objects.filter(pk=bc.pk).update(
            date_commande=datetime.date.today())
        commercial = User.objects.create_user(
            username='astk240-commercial', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='Commercial',
                permissions=dict(CANONICAL_SYSTEM_ROLES)['Commercial']))
        for user, modele in ((commercial, 'exemple_sans_prix_achat'),
                             (self.user, 'exemple')):
            api = APIClient()
            api.force_authenticate(user)
            for prefixe in ('stock', 'achats'):
                rep = api.get(f'/api/django/{prefixe}/factures-fournisseur/'
                              f'suggestions-bcf/', {'fournisseur': self.fournisseur.id})
                self.assertEqual(rep.status_code, 200, rep.data)
                self.assertEqual([s['reference'] for s in rep.data], [bc.reference])
                self.assertEqual(set(rep.data[0]),
                                 set(contrat[modele]['suggestions'][0]), user.username)

    def test_porte_compte_meme_garde(self):
        bc = self._bcf(BonCommandeFournisseur.Statut.RECU, quantite_recue=2)
        with self.assertRaises(ConfirmationBcfRefusee):
            confirmer_bcf_compte_fournisseur(
                self.company, self.fournisseur.id, bc.id,
                date_confirmee=datetime.date(2026, 10, 10))
        bc.refresh_from_db()
        self.assertIsNone(bc.date_confirmee_fournisseur)


class ValidationTests(ConfirmationBase):
    """ASTK181 (sonde FOUR-6 : 500 / 500 / 500) — parse de date, borne de
    100 caractères et corps non objet : 400 nommant le champ, BCF inchangé."""

    def setUp(self):
        super().setUp()
        self.bc = self._bcf(BonCommandeFournisseur.Statut.ENVOYE)

    def _assert_inchange(self):
        self.bc.refresh_from_db()
        self.assertIsNone(self.bc.date_confirmee_fournisseur)
        self.assertEqual(self.bc.numero_confirmation_fournisseur, '')

    def test_date_illisible_400(self):
        rep = self._confirmer(
            self.bc, {'date_confirmee_fournisseur': 'pas-une-date'})
        self.assertEqual(rep.status_code, 400, rep.data)
        self.assertEqual(rep.data, {
            'date_confirmee_fournisseur': ['Date invalide (AAAA-MM-JJ).']})
        self._assert_inchange()

    def test_date_impossible_400(self):
        rep = self._confirmer(
            self.bc, {'date_confirmee_fournisseur': '2026-02-31'})
        self.assertEqual(rep.status_code, 400, rep.data)
        self.assertIn('date_confirmee_fournisseur', rep.data)
        self._assert_inchange()

    def test_numero_trop_long_400(self):
        rep = self._confirmer(self.bc, {
            'date_confirmee_fournisseur': '2026-10-10',
            'numero_confirmation_fournisseur': 'x' * 101})
        self.assertEqual(rep.status_code, 400, rep.data)
        self.assertEqual(rep.data, {
            'numero_confirmation_fournisseur': ['100 caractères maximum.']})
        self._assert_inchange()

    def test_corps_liste_400(self):
        rep = self._confirmer(self.bc, [1])
        self.assertEqual(rep.status_code, 400, rep.data)
        self.assertEqual(rep.data, {'detail': 'Corps JSON attendu.'})
        self._assert_inchange()

    def test_saisie_valide_200(self):
        rep = self._confirmer(self.bc, {
            'date_confirmee_fournisseur': '2026-10-10',
            'numero_confirmation_fournisseur': 'x' * 100})
        self.assertEqual(rep.status_code, 200, rep.data)
        self.bc.refresh_from_db()
        self.assertEqual(self.bc.numero_confirmation_fournisseur, 'x' * 100)

"""ASTK4 — `CompanyScopedRelationsMixin` sur les sérialiseurs achats : toute
FK écrite (y compris `acheteur` / `recu_par` vers l'utilisateur) refuse l'id
d'une autre société exactement comme un id absent.

Rejoue TEN-6 (1, 2, 6), FACF-10 et FOUR-21 de l'audit stock du 2026-10-06 :
avant correction, BCF.acheteur = utilisateur de B → 201 et le PDF imprimait
« Salarie DeB » ; ligne de facture sur le produit de B → 201 ; avoir sur le
retour de B → 201 (référence de B exposée) ; PATCH catégorie de B → 200.

Chaque test compare la réponse pour l'id étranger à celle pour l'id
99999999 (id neutralisé), vérifie que l'erreur porte bien sur le champ visé
(l'id cité par le message « objet inexistant ») et qu'aucun libellé de B ne
fuit. Les sérialiseurs servis seulement en sortie (échéance, imputation,
jeton portail) sont éprouvés directement avec une requête en contexte.

Run:
    python manage.py test apps.stock.test_astk_fk_achats -v 2
"""
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.relations import PrimaryKeyRelatedField
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.parametres.models import ConditionPaiement
from apps.stock import serializers as S
from apps.stock.models import (
    AcompteFournisseur, AvoirFournisseur, BonCommandeFournisseur,
    CategorieFournisseur, ContactFournisseur, DocumentConformiteFournisseur,
    FactureFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    PaiementFournisseur, PrixFournisseur, Produit, ReceptionFournisseur,
    RetourFournisseur,
)

User = get_user_model()

ID_ABSENT = 99999999
SECRETS = ('Salarie DeB', 'PRODUIT-B-SECRET', 'RETB-SECRET', 'CAT-B-SECRET',
           'FOURNISSEUR-B-SECRET', 'FFB-SECRET', 'BCFB-SECRET')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _inexistant(pk):
    """Message DRF « objet inexistant » pour ``pk`` (langue active)."""
    gabarit = PrimaryKeyRelatedField.default_error_messages['does_not_exist']
    return str(gabarit).format(pk_value=pk)


def _sans_id(corps, pk):
    """Le message DRF « objet inexistant » cite l'id : on le remplace par un
    jeton pour comparer la réponse d'un id étranger à celle d'un id absent."""
    if isinstance(corps, dict):
        return {k: _sans_id(v, pk) for k, v in corps.items()}
    if isinstance(corps, (list, tuple)):
        return [_sans_id(v, pk) for v in corps]
    return '<INEXISTANT>' if str(corps) == _inexistant(pk) else str(corps)


class FkAchatsTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='astk4-a', slug='astk4-a')
        self.co_b = Company.objects.create(nom='astk4-b', slug='astk4-b')
        self.admin_a = User.objects.create_user(
            username='astk4-admin-a', password='x', company=self.co_a,
            role_legacy='admin')
        self.user_b = User.objects.create_user(
            username='astk4-salarie-b', password='x', company=self.co_b,
            first_name='Salarie', last_name='DeB', role_legacy='admin')
        self.api = _api(self.admin_a)
        self.fa = Fournisseur.objects.create(company=self.co_a, nom='FA')
        self.fb = Fournisseur.objects.create(
            company=self.co_b, nom='FOURNISSEUR-B-SECRET')
        self.pa = Produit.objects.create(
            company=self.co_a, nom='Produit A', sku='ASTK4-PA',
            prix_vente=Decimal('30'), prix_achat=Decimal('10'))
        self.pb = Produit.objects.create(
            company=self.co_b, nom='PRODUIT-B-SECRET', sku='ASTK4-PB',
            prix_vente=Decimal('30'), prix_achat=Decimal('10'))
        self.cat_b = CategorieFournisseur.objects.create(
            company=self.co_b, nom='CAT-B-SECRET')
        self.cond_b = ConditionPaiement.objects.create(
            company=self.co_b, libelle='COND-B', delai_jours=30)
        self.bc_a = BonCommandeFournisseur.objects.create(
            company=self.co_a, reference='BCFA-1', fournisseur=self.fa,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.ligne_a = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bc_a, produit=self.pa, quantite=5,
            prix_achat_unitaire=Decimal('10'))
        self.bc_b = BonCommandeFournisseur.objects.create(
            company=self.co_b, reference='BCFB-SECRET', fournisseur=self.fb,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.retour_b = RetourFournisseur.objects.create(
            company=self.co_b, reference='RETB-SECRET', fournisseur=self.fb)
        self.facture_b = FactureFournisseur.objects.create(
            company=self.co_b, reference='FFB-SECRET', fournisseur=self.fb,
            montant_ht=Decimal('100'), montant_tva=Decimal('20'),
            montant_ttc=Decimal('120'))

    # ── aides ────────────────────────────────────────────────────────────

    def _assert_comme_absent(self, r, r_absent, pk):
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r_absent.status_code, 400, r_absent.content)
        corps = r.content.decode()
        # L'erreur « objet inexistant » de cet id : elle a bien visé le champ.
        self.assertIn('<INEXISTANT>', str(_sans_id(r.json(), pk)))
        self.assertEqual(_sans_id(r.json(), pk),
                         _sans_id(r_absent.json(), ID_ABSENT))
        for secret in SECRETS:
            self.assertNotIn(secret, corps)

    def _post_compare(self, url, payload, champ, pk_etranger):
        r = self.api.post(url, {**payload, champ: pk_etranger}, format='json')
        r_absent = self.api.post(
            url, {**payload, champ: ID_ABSENT}, format='json')
        self._assert_comme_absent(r, r_absent, pk_etranger)

    def _serializer_compare(self, cls, payload, champ, pk_etranger):
        ctx = {'request': SimpleNamespace(user=self.admin_a)}
        ser = cls(data={**payload, champ: pk_etranger}, context=ctx)
        ser_absent = cls(data={**payload, champ: ID_ABSENT}, context=ctx)
        self.assertFalse(ser.is_valid())
        self.assertFalse(ser_absent.is_valid())
        self.assertIn(champ, ser.errors)
        self.assertIn('<INEXISTANT>',
                      str(_sans_id(ser.errors[champ], pk_etranger)))
        self.assertEqual(_sans_id(ser.errors[champ], pk_etranger),
                         _sans_id(ser_absent.errors[champ], ID_ABSENT))

    # ── BCF ──────────────────────────────────────────────────────────────

    def _bcf_payload(self, produit_id=None):
        return {
            'fournisseur': self.fa.pk,
            'lignes': [{'produit': produit_id or self.pa.pk, 'quantite': 1,
                        'prix_achat_unitaire': '10'}],
        }

    def test_bcf_acheteur_autre_societe(self):
        nb = BonCommandeFournisseur.objects.filter(company=self.co_a).count()
        self._post_compare('/api/django/stock/bons-commande-fournisseur/',
                           self._bcf_payload(), 'acheteur', self.user_b.pk)
        self.assertEqual(
            BonCommandeFournisseur.objects.filter(company=self.co_a).count(),
            nb)

    def test_bcf_fournisseur_autre_societe(self):
        self._post_compare('/api/django/stock/bons-commande-fournisseur/',
                           self._bcf_payload(), 'fournisseur', self.fb.pk)

    def test_bcf_ligne_produit_autre_societe(self):
        url = '/api/django/stock/bons-commande-fournisseur/'
        r = self.api.post(url, self._bcf_payload(self.pb.pk), format='json')
        r_absent = self.api.post(
            url, self._bcf_payload(ID_ABSENT), format='json')
        self._assert_comme_absent(r, r_absent, self.pb.pk)

    def test_bcf_patch_acheteur_autre_societe(self):
        url = f'/api/django/stock/bons-commande-fournisseur/{self.bc_a.pk}/'
        r = self.api.patch(url, {'acheteur': self.user_b.pk}, format='json')
        r_absent = self.api.patch(url, {'acheteur': ID_ABSENT}, format='json')
        self._assert_comme_absent(r, r_absent, self.user_b.pk)
        self.bc_a.refresh_from_db()
        self.assertIsNone(self.bc_a.acheteur_id)

    # ── Réception ────────────────────────────────────────────────────────

    def test_reception_recu_par_autre_societe(self):
        self._post_compare('/api/django/stock/receptions-fournisseur/', {
            'bon_commande': self.bc_a.pk, 'date_reception': '2026-10-06',
            'lignes': [{'ligne_commande': self.ligne_a.pk, 'quantite': 1}],
        }, 'recu_par', self.user_b.pk)
        self.assertFalse(ReceptionFournisseur.objects.exists())

    def test_reception_bcf_autre_societe(self):
        self._post_compare('/api/django/stock/receptions-fournisseur/', {
            'date_reception': '2026-10-06',
            'lignes': [{'ligne_commande': self.ligne_a.pk, 'quantite': 1}],
        }, 'bon_commande', self.bc_b.pk)

    # ── Facture, paiement, échéance ─────────────────────────────────────

    def test_facture_ligne_produit_autre_societe(self):
        url = '/api/django/stock/factures-fournisseur/'

        def _payload(produit_id):
            return {
                'fournisseur': self.fa.pk, 'ref_fournisseur': 'F-1',
                'montant_ht': '10', 'montant_tva': '2', 'montant_ttc': '12',
                'lignes': [{'produit': produit_id, 'designation': 'x',
                            'quantite': 1, 'prix_unitaire_ht': '10'}],
            }
        r = self.api.post(url, _payload(self.pb.pk), format='json')
        r_absent = self.api.post(url, _payload(ID_ABSENT), format='json')
        self._assert_comme_absent(r, r_absent, self.pb.pk)
        self.assertFalse(
            FactureFournisseur.objects.filter(company=self.co_a).exists())

    def test_facture_fournisseur_autre_societe(self):
        self._post_compare('/api/django/stock/factures-fournisseur/', {
            'montant_ht': '10', 'montant_tva': '2', 'montant_ttc': '12',
        }, 'fournisseur', self.fb.pk)

    def test_paiement_facture_autre_societe(self):
        self._post_compare('/api/django/stock/paiements-fournisseur/', {
            'montant': '10', 'date_paiement': '2026-10-06',
            'mode': 'virement',
        }, 'facture', self.facture_b.pk)
        self.assertFalse(PaiementFournisseur.objects.exists())

    def test_echeance_facture_autre_societe(self):
        self._serializer_compare(S.EcheanceFactureFournisseurSerializer, {
            'pourcentage': '50', 'montant': '60',
            'date_echeance': '2026-11-01',
        }, 'facture', self.facture_b.pk)

    # ── Avoir, imputation, acompte ──────────────────────────────────────

    def _avoir_payload(self):
        return {'fournisseur': self.fa.pk, 'montant_ht': '10',
                'montant_tva': '2', 'montant_ttc': '12'}

    def test_avoir_retour_etranger(self):
        self._post_compare('/api/django/stock/avoirs-fournisseur/',
                           self._avoir_payload(), 'retour', self.retour_b.pk)
        self.assertFalse(AvoirFournisseur.objects.exists())

    def test_avoir_facture_origine_etrangere(self):
        self._post_compare('/api/django/stock/avoirs-fournisseur/',
                           self._avoir_payload(), 'facture_origine',
                           self.facture_b.pk)
        self.assertFalse(AvoirFournisseur.objects.exists())

    def test_imputation_facture_etrangere(self):
        avoir = AvoirFournisseur.objects.create(
            company=self.co_a, reference='AVA-1', fournisseur=self.fa,
            montant_ht=Decimal('10'), montant_tva=Decimal('2'),
            montant_ttc=Decimal('12'))
        self._serializer_compare(S.ImputationAvoirFournisseurSerializer, {
            'avoir': avoir.pk, 'montant': '5',
        }, 'facture', self.facture_b.pk)

    def test_acompte_bcf_etranger(self):
        self._post_compare('/api/django/stock/acomptes-fournisseur/', {
            'montant': '10', 'date_versement': '2026-10-06',
        }, 'bon_commande', self.bc_b.pk)
        self.assertFalse(AcompteFournisseur.objects.exists())

    # ── Fournisseur, contact, conformité, jeton, prix ───────────────────

    def test_fournisseur_patch_categorie_etrangere(self):
        url = f'/api/django/stock/fournisseurs/{self.fa.pk}/'
        r = self.api.patch(url, {'categorie': self.cat_b.pk}, format='json')
        r_absent = self.api.patch(url, {'categorie': ID_ABSENT},
                                  format='json')
        self._assert_comme_absent(r, r_absent, self.cat_b.pk)
        self.fa.refresh_from_db()
        self.assertIsNone(self.fa.categorie_id)
        # Aucun PROTECT posé par A : la catégorie de B reste supprimable.
        self.cat_b.delete()

    def test_fournisseur_patch_condition_paiement_etrangere(self):
        url = f'/api/django/stock/fournisseurs/{self.fa.pk}/'
        r = self.api.patch(url, {'condition_paiement_ref': self.cond_b.pk},
                           format='json')
        r_absent = self.api.patch(url, {'condition_paiement_ref': ID_ABSENT},
                                  format='json')
        self._assert_comme_absent(r, r_absent, self.cond_b.pk)
        self.fa.refresh_from_db()
        self.assertIsNone(self.fa.condition_paiement_ref_id)

    def test_contact_fournisseur_etranger(self):
        self._post_compare('/api/django/stock/contacts-fournisseur/',
                           {'nom': 'Contact'}, 'fournisseur', self.fb.pk)
        self.assertFalse(ContactFournisseur.objects.exists())
        # Fournisseur B toujours supprimable (aucune ligne de A ne le tient).
        self.fb.delete()

    def test_document_conformite_fournisseur_etranger(self):
        self._serializer_compare(S.DocumentConformiteFournisseurSerializer, {
            'type_document': 'arf', 'reference': 'ARF-1',
        }, 'fournisseur', self.fb.pk)
        self.assertFalse(DocumentConformiteFournisseur.objects.exists())

    def test_jeton_portail_fournisseur_etranger(self):
        self._serializer_compare(S.PortailFournisseurTokenSerializer, {},
                                 'fournisseur', self.fb.pk)

    def test_prix_fournisseur_produit_etranger(self):
        self._post_compare('/api/django/stock/prix-fournisseurs/', {
            'fournisseur': self.fa.pk, 'prix_achat': '10',
        }, 'produit', self.pb.pk)
        self.assertFalse(PrixFournisseur.objects.exists())

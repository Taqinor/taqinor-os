"""WIR27 — Fiche fournisseur 360 (XPUR25) : agrégat `vue-360` + accessibilité
de la page.

`FournisseurFiche360.jsx` existait déjà avec 6 onglets codés contre de vrais
endpoints, mais son résumé + son onglet « Accords de prix » appelaient
`fournisseurs/{id}/vue-360/`, qui n'existait pas côté serveur (404). Ce
module construit l'action d'agrégat sur `FournisseurViewSet`
(`apps/stock/views/fournisseur.py`), routée automatiquement par le
`DefaultRouter` déjà enregistré (`apps/stock/urls.py` — aucun changement
requis, une `@action(detail=True, ...)` s'ajoute d'elle-même).

Couvre :
  * BCF ouverts (brouillon + envoyé, hors reçu/annulé) ;
  * réceptions attendues (BCF envoyés pas entièrement reçus) + en retard
    (date promise dépassée) ;
  * factures ouvertes + solde dû total ;
  * retours validés (hors annulés) + avoirs ;
  * conformité (XPUR1 — document obligatoire manquant/expiré) ;
  * accords de prix actifs (paliers XPUR14 dont le tarif parent est en
    vigueur) ;
  * garde de permission (lecture stock) + isolation multi-tenant.

Run:
    python manage.py test apps.stock.test_wir27_fournisseur_fiche_360 -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AvoirFournisseur, BonCommandeFournisseur, DocumentConformiteFournisseur,
    FactureFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    PalierPrixFournisseur, PrixFournisseur, Produit, RetourFournisseur,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Wir27Base(TestCase):
    def setUp(self):
        self.company = _company('wir27-co')
        self.user = _user(
            self.company, 'wir27-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur WIR27')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur WIR27', sku='OND-WIR27',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))

    def _url(self, fournisseur_id=None):
        fid = fournisseur_id or self.fournisseur.id
        return f'/api/django/stock/fournisseurs/{fid}/vue-360/'


class TestVue360Bcf(Wir27Base):
    def test_bcf_ouverts_compte_brouillon_et_envoye_hors_recu_annule(self):
        BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-WIR27-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.BROUILLON)
        BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-WIR27-2',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-WIR27-3',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-WIR27-4',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ANNULE)

        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['bcf_ouverts'], 2)

    def test_receptions_attendues_et_en_retard(self):
        hier = timezone.now().date() - timedelta(days=1)
        demain = timezone.now().date() + timedelta(days=1)

        bc_retard = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-WIR27-RETARD',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=hier)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc_retard, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1200'), quantite_recue=0)

        bc_a_temps = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-WIR27-ATEMPS',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=demain)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc_a_temps, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1200'), quantite_recue=0)

        bc_recu = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-WIR27-RECU',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE,
            date_livraison_prevue=hier)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc_recu, produit=self.produit, quantite=5,
            prix_achat_unitaire=Decimal('1200'), quantite_recue=5)

        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        # 2 BCF ENVOYÉS pas entièrement reçus (retard + à temps) — le BCF
        # entièrement reçu n'entre plus dans les réceptions attendues.
        self.assertEqual(resp.data['receptions_attendues'], 2)
        self.assertEqual(resp.data['bcf_en_retard'], 1)


class TestVue360Factures(Wir27Base):
    def test_factures_ouvertes_et_solde_total_du(self):
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-WIR27-1',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'),
            statut=FactureFournisseur.Statut.A_PAYER)
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-WIR27-2',
            fournisseur=self.fournisseur,
            montant_ht=Decimal('500'), montant_tva=Decimal('100'),
            montant_ttc=Decimal('600'),
            statut=FactureFournisseur.Statut.PAYEE)

        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['factures_ouvertes'], 1)
        self.assertEqual(
            Decimal(resp.data['solde_total_du']), Decimal('1200.00'))


class TestVue360RetoursAvoirs(Wir27Base):
    def test_compte_retours_valides_et_avoirs_hors_annules(self):
        RetourFournisseur.objects.create(
            company=self.company, reference='RET-WIR27-1',
            fournisseur=self.fournisseur,
            statut=RetourFournisseur.Statut.VALIDE)
        RetourFournisseur.objects.create(
            company=self.company, reference='RET-WIR27-2',
            fournisseur=self.fournisseur,
            statut=RetourFournisseur.Statut.ANNULE)
        AvoirFournisseur.objects.create(
            company=self.company, reference='AVF-WIR27-1',
            fournisseur=self.fournisseur, montant_ttc=Decimal('300'))

        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        # 1 retour validé (l'annulé ne compte pas) + 1 avoir = 2.
        self.assertEqual(resp.data['nb_retours_avoirs'], 2)


class TestVue360Conformite(Wir27Base):
    def test_conformite_ok_sans_document_obligatoire(self):
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['conformite_ok'])
        self.assertEqual(resp.data['conformite_documents_manquants'], 0)

    def test_conformite_signale_un_document_obligatoire_expire(self):
        DocumentConformiteFournisseur.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            type_document=DocumentConformiteFournisseur.Type.ARF,
            date_expiration=timezone.now().date() - timedelta(days=1),
            obligatoire=True)
        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(resp.data['conformite_ok'])
        self.assertEqual(resp.data['conformite_documents_manquants'], 1)


class TestVue360AccordsPrix(Wir27Base):
    def test_palier_en_vigueur_compte_accord_prix_actif(self):
        pf = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1200'))
        PalierPrixFournisseur.objects.create(
            prix_fournisseur=pf, qte_min=10, prix=Decimal('1100'))

        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['accords_prix_actifs'], 1)
        self.assertEqual(len(resp.data['accords_prix']), 1)
        self.assertEqual(
            resp.data['accords_prix'][0]['produit_id'], self.produit.id)
        self.assertEqual(
            Decimal(resp.data['accords_prix'][0]['prix_convenu']),
            Decimal('1100'))

    def test_palier_expire_ne_compte_pas(self):
        pf = PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=Decimal('1200'),
            date_fin=timezone.now().date() - timedelta(days=1))
        PalierPrixFournisseur.objects.create(
            prix_fournisseur=pf, qte_min=10, prix=Decimal('1100'))

        resp = self.api.get(self._url())
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['accords_prix_actifs'], 0)
        self.assertEqual(resp.data['accords_prix'], [])


class TestVue360PermissionsEtTenant(Wir27Base):
    def test_refuse_sans_droit_lecture_stock(self):
        readonly = _user(self.company, 'wir27-lecture', permissions=[])
        api = _api(readonly)
        resp = api.get(self._url())
        self.assertEqual(resp.status_code, 403, resp.data)

    def test_fournisseur_autre_societe_404(self):
        other = _company('wir27-co-2')
        other_f = Fournisseur.objects.create(company=other, nom='Autre Sté')
        resp = self.api.get(self._url(other_f.id))
        self.assertEqual(resp.status_code, 404, resp.data)

"""« Facturer » un devis accepté avec ses paiements déjà reçus (fondateur,
05/10/2026) — ``POST /api/django/ventes/devis/<id>/facturer-complet/``.

Cas réel : une cliente a signé et payé ~90 % en 1 à 3 versements ; il fallait
UN geste pour émettre sa facture complète ET y consigner ces versements.
Contrat : ``apps/ventes/contract_samples/devis_facturer_complet.json``.
"""
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    BonCommande, Devis, Facture, LigneDevis, Paiement,
)
from authentication.models import Company

User = get_user_model()
_CTR = [0]

CONTRAT = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'devis_facturer_complet.json')


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestFacturerComplet(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='FCP Co', slug=f'fcp-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'fcp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cliente', prenom='Signée',
            telephone='+212600000501')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit PV', sku=f'FCP-{_nxt()}',
            prix_vente=Decimal('125000'), quantite_stock=500)
        # 125 000 HT × 20 % = 150 000 TTC (palier d'arrondi neutre).
        self.devis = self._devis()

    def _devis(self, statut=Devis.Statut.ACCEPTE, company=None, client=None,
               user=None):
        company = company or self.company
        devis = Devis.objects.create(
            company=company, created_by=user or self.user,
            client=client or self.client_obj,
            reference=f'DEV-FCP-{_nxt()}', statut=statut,
            taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=self.produit if company == self.company
            else None, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('125000'),
            taux_tva=Decimal('20'))
        return devis

    def _url(self, devis=None):
        return (f'/api/django/ventes/devis/{(devis or self.devis).id}'
                f'/facturer-complet/')

    def _post(self, paiements, devis=None):
        return self.api.post(self._url(devis), {'paiements': paiements},
                             format='json')

    def _p(self, montant, jours, mode='virement', reference=''):
        return {'montant': montant,
                'date_paiement': (date.today()
                                  - timedelta(days=jours)).isoformat(),
                'mode_paiement': mode, 'reference': reference}

    # ── Chemin heureux ────────────────────────────────────────────────────

    def test_trois_paiements_reste_du_et_statut_partiel(self):
        resp = self._post([
            self._p('45000.00', 50, 'virement', 'VIR-0812'),
            self._p('45000.00', 30, 'cheque', 'CHQ-55120'),
            self._p('45000.00', 5),
        ])
        self.assertEqual(resp.status_code, 201, resp.data)
        data = resp.data
        self.assertEqual(data['statut'], 'partiellement_payee')
        self.assertEqual(data['total_ttc'], '150000.00')
        self.assertEqual(data['montant_paye'], '135000.00')
        self.assertEqual(data['montant_du'], '15000.00')
        self.assertEqual(len(data['paiements']), 3)
        self.assertEqual(data['paiements'][0]['reference'], 'VIR-0812')
        self.assertEqual(data['paiements'][1]['mode_paiement'], 'cheque')
        self.assertEqual(data['paiements'][2]['reference'], '')

        facture = Facture.objects.get(pk=data['facture_id'])
        self.assertEqual(facture.reference, data['facture_reference'])
        self.assertEqual(facture.devis_id, self.devis.id)
        self.assertEqual(facture.company_id, self.company.id)
        self.assertEqual(facture.type_facture, Facture.TypeFacture.COMPLETE)
        # Émise en base (statut de paiement servi à l'écran seulement).
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(facture.lignes.count(), 1)
        self.assertEqual(facture.paiements.count(), 3)
        self.assertEqual(facture.montant_du, Decimal('15000.00'))

    def test_forme_identique_au_contrat(self):
        resp = self._post([self._p('1000', 1)])
        self.assertEqual(resp.status_code, 201, resp.data)
        contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        exemple = contrat['exemple']
        self.assertEqual(set(resp.data), set(exemple))
        self.assertEqual(set(resp.data['paiements'][0]),
                         set(exemple['paiements'][0]))
        for cle in ('total_ttc', 'montant_paye', 'montant_du'):
            self.assertIsInstance(resp.data[cle], str)

    def test_sans_paiement(self):
        resp = self._post([])
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], 'emise')
        self.assertEqual(resp.data['montant_paye'], '0.00')
        self.assertEqual(resp.data['montant_du'], '150000.00')
        self.assertEqual(resp.data['paiements'], [])

    def test_corps_vide_vaut_zero_paiement(self):
        resp = self.api.post(self._url(), {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['paiements'], [])

    def test_paiement_integral_solde_la_facture(self):
        resp = self._post([self._p('100000', 20), self._p('50000.00', 2)])
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['statut'], 'payee')
        self.assertEqual(resp.data['montant_du'], '0.00')
        facture = Facture.objects.get(pk=resp.data['facture_id'])
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)

    def test_rattache_le_bon_de_commande_sans_facture(self):
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-FCP-{_nxt()}',
            devis=self.devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        resp = self._post([])
        self.assertEqual(resp.status_code, 201, resp.data)
        facture = Facture.objects.get(pk=resp.data['facture_id'])
        self.assertEqual(facture.bon_commande_id, bc.id)

    # ── Refus ─────────────────────────────────────────────────────────────

    def test_refuse_un_devis_non_accepte(self):
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        resp = self._post([], devis=devis)
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('accepté', resp.data['detail'])
        self.assertFalse(Facture.objects.filter(devis=devis).exists())

    def test_refuse_un_devis_deja_facture_en_nommant_la_reference(self):
        premiere = self._post([])
        self.assertEqual(premiere.status_code, 201, premiere.data)
        resp = self._post([self._p('1000', 1)])
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn(premiere.data['facture_reference'], resp.data['detail'])
        self.assertEqual(Facture.objects.filter(devis=self.devis).count(), 1)
        self.assertEqual(Paiement.objects.count(), 0)

    def test_refuse_un_devis_deja_facture_par_son_echeancier(self):
        tranche = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/',
            {}, format='json')
        self.assertEqual(tranche.status_code, 201, tranche.data)
        resp = self._post([])
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn(tranche.data['reference'], resp.data['detail'])

    def test_surpaiement_refuse_et_rien_n_est_cree(self):
        avant_factures = Facture.objects.count()
        resp = self._post([self._p('100000', 10), self._p('60000', 5)])
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('dépassent', resp.data['detail'])
        # Atomicité : ni facture, ni paiement.
        self.assertEqual(Facture.objects.count(), avant_factures)
        self.assertEqual(Paiement.objects.count(), 0)
        # Et le devis reste facturable ensuite.
        self.assertEqual(self._post([]).status_code, 201)

    def test_validation_des_lignes_de_paiement(self):
        futur = (date.today() + timedelta(days=3)).isoformat()
        cas = [
            [{'montant': '-5', 'date_paiement': date.today().isoformat(),
              'mode_paiement': 'virement'}],
            [{'montant': '100', 'date_paiement': futur,
              'mode_paiement': 'virement'}],
            [{'montant': '100', 'date_paiement': date.today().isoformat(),
              'mode_paiement': 'bitcoin'}],
            [{'montant': '100', 'date_paiement': 'hier',
              'mode_paiement': 'virement'}],
            [self._p('10', 1)] * 6,
        ]
        for paiements in cas:
            with self.subTest(paiements=paiements[:1]):
                resp = self._post(paiements)
                self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(Facture.objects.filter(devis=self.devis).exists())

    def test_isolation_societe(self):
        autre = Company.objects.create(nom='Autre', slug=f'fcp-autre-{_nxt()}')
        autre_user = User.objects.create_user(
            username=f'fcp_autre_{_nxt()}', password='x',
            role_legacy='responsable', company=autre)
        autre_client = Client.objects.create(
            company=autre, nom='Autre', telephone='+212600000502')
        devis_autre = self._devis(company=autre, client=autre_client,
                                  user=autre_user)
        resp = self._post([], devis=devis_autre)
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(Facture.objects.filter(devis=devis_autre).exists())


# ═══════════════════════════════════════════════════════════════════════════
# Groupe VNT — « Facturer la vente » : ``domain/facturation_vente.facturer_vente``
# (contrat ``devis_facturer.json``), goldens sur le panier RÉEL du devis 388.
# ═══════════════════════════════════════════════════════════════════════════
ECHEANCIER_30_60_10 = [
    {'type': 'acompte', 'libelle': 'Acompte', 'unite': 'pct',
     'pct_or_montant': 30},
    {'type': 'materiel', 'libelle': 'Livraison du matériel', 'unite': 'pct',
     'pct_or_montant': 60},
    {'type': 'solde', 'libelle': 'Solde', 'unite': 'pct',
     'pct_or_montant': 10}]


class _BaseVente(TestCase):
    def setUp(self):
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_user)
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _388(self, reference, echeancier=ECHEANCIER_30_60_10, **champs):
        from apps.ventes.tests.test_echeancier_somme_total import (
            creer_devis_388)
        return creer_devis_388(self.company, self.user, self.client_obj,
                               reference, echeancier, **champs)

    def _tranche(self, devis, reference, cle, ttc, ht, tva, statut='emise',
                 type_facture='acompte'):
        from apps.ventes.tests.test_echeancier_somme_total import (
            facture_tranche)
        return facture_tranche(devis, reference, cle, ttc, ht, tva,
                               statut=statut, type_facture=type_facture)

    def _acompte_14700(self, devis, statut='emise', reference='FAC-VNT-A1'):
        return self._tranche(devis, reference, 'acompte', '14700.00',
                             '12466.00', '2234.00', statut=statut)

    def _facturer(self, devis, **kwargs):
        from apps.ventes.domain.facturation_vente import facturer_vente
        kwargs.setdefault('user', self.user)
        return facturer_vente(devis, **kwargs)

    def _refus(self, devis, **kwargs):
        from apps.ventes.domain.facturation_vente import (
            FacturationVenteRefusee)
        with self.assertRaises(FacturationVenteRefusee) as ctx:
            self._facturer(devis, **kwargs)
        return ctx.exception


class FacturerVenteTrancheVNT26(_BaseVente):
    """VNT26 — natures ``intermediaire`` / ``solde`` : la facture naît
    BROUILLON (``BROUILLON-<id>``) depuis ``plan_facturation.prochaine``,
    jamais émise, 0 sortie de stock ; 409 ``version_remplacee`` /
    ``cle_inattendue`` / ``tranche_en_brouillon``."""

    def test_acompte_en_brouillon_bloque_la_tranche_materiel(self):
        devis = self._388('DEV-VNT26-BR')
        acompte = self._acompte_14700(devis, statut='brouillon', reference='')
        refus = self._refus(devis, nature='intermediaire',
                            cle_attendue='materiel')
        self.assertEqual(refus.status, 409)
        self.assertEqual(refus.corps['code'], 'tranche_en_brouillon')
        self.assertEqual(refus.corps['facture'],
                         {'id': acompte.id, 'reference': acompte.reference})
        self.assertEqual(Facture.objects.filter(devis=devis).count(), 1)

    def test_cle_attendue_differente_de_la_prochaine(self):
        devis = self._388('DEV-VNT26-CLE')
        self._acompte_14700(devis)
        refus = self._refus(devis, nature='solde', cle_attendue='solde')
        self.assertEqual(refus.status, 409)
        self.assertEqual(refus.corps['code'], 'cle_inattendue')
        self.assertEqual(refus.corps['cle_attendue'], 'materiel')

    def test_version_remplacee_nomme_le_successeur(self):
        v3 = self._388('DEV-VNT26-V3')
        v2 = self._388('DEV-VNT26-V2', is_active=False, superseded_by=v3)
        refus = self._refus(v2, nature='intermediaire',
                            cle_attendue='materiel')
        self.assertEqual(refus.status, 409)
        self.assertEqual(refus.corps['code'], 'version_remplacee')
        self.assertEqual(refus.corps['successeur'],
                         {'id': v3.id, 'reference': v3.reference})
        self.assertFalse(Facture.objects.filter(devis=v2).exists())

    def test_brouillon_cree_sans_numero_ni_sortie_de_stock(self):
        from core.numbering import est_reference_provisoire
        devis = self._388('DEV-VNT26-OK')
        self._acompte_14700(devis)
        stocks = {lg.produit_id: lg.produit.quantite_stock
                  for lg in devis.lignes.select_related('produit')}
        facture, paiements = self._facturer(
            devis, nature='intermediaire', cle_attendue='materiel')
        self.assertEqual(paiements, [])
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertTrue(est_reference_provisoire(facture.reference))
        self.assertEqual(facture.cle_tranche, 'materiel')
        self.assertEqual(facture.type_facture, 'intermediaire')
        self.assertEqual(facture.libelle, 'Livraison du matériel 60 %')
        # Golden 388 : 49 000 × 90 % − 14 700 = 29 400 (24 932,00 + 4 468,00).
        self.assertEqual(facture.montant_ttc, Decimal('29400.00'))
        self.assertEqual(facture.montant_ht, Decimal('24932.00'))
        self.assertEqual(facture.montant_tva, Decimal('4468.00'))
        for lg in devis.lignes.select_related('produit'):
            self.assertEqual(lg.produit.quantite_stock, stocks[lg.produit_id])

    def test_rien_a_facturer(self):
        devis = self._388('DEV-VNT26-FIN', echeancier=[
            {'type': 'solde', 'libelle': 'Solde', 'unite': 'pct',
             'pct_or_montant': 100}])
        self._tranche(devis, 'FAC-VNT26-T', 'solde', '49000.00',
                      '41553.33', '7446.67', type_facture='solde')
        refus = self._refus(devis, nature='solde', cle_attendue='solde')
        self.assertEqual(refus.status, 409)
        self.assertEqual(refus.corps['code'], 'tranche_deja_creee')
        refus = self._refus(devis, nature='solde')
        self.assertEqual(refus.status, 400)
        self.assertEqual(refus.corps['code'], 'rien_a_facturer')

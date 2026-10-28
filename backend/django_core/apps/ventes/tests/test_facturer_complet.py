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
        self.assertEqual(resp.status_code, 409, resp.data)  # CI #997 fuzz : refus d'état, 409
        self.assertIn('accepté', resp.data['detail'])
        self.assertFalse(Facture.objects.filter(devis=devis).exists())

    def test_refuse_un_devis_deja_facture_en_nommant_la_reference(self):
        premiere = self._post([])
        self.assertEqual(premiere.status_code, 201, premiere.data)
        resp = self._post([self._p('1000', 1)])
        self.assertEqual(resp.status_code, 409, resp.data)  # CI #997 fuzz : refus d'état, 409
        self.assertIn(premiere.data['facture_reference'], resp.data['detail'])
        self.assertEqual(Facture.objects.filter(devis=self.devis).count(), 1)
        self.assertEqual(Paiement.objects.count(), 0)

    def test_refuse_un_devis_deja_facture_par_son_echeancier(self):
        tranche = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/',
            {}, format='json')
        self.assertEqual(tranche.status_code, 201, tranche.data)
        resp = self._post([])
        self.assertEqual(resp.status_code, 409, resp.data)  # CI #997 fuzz : refus d'état, 409
        self.assertIn(tranche.data['reference'], resp.data['detail'])

    def test_vnt65_version_remplacee_refusee_409_nommee_aux_deux_portes(self):
        """VNT65 — les deux portes sont des enveloppes de « Facturer la
        vente » : une version REMPLACÉE est refusée (409 depuis CI #997, un
        refus d'état) nommant la tête de chaîne (elle rendait 201 sur
        ``generer-facture``), rien d'écrit."""
        v2 = self._devis()
        Devis.objects.filter(pk=self.devis.pk).update(
            is_active=False, superseded_by=v2)
        resp = self._post([])
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertIn(v2.reference, resp.data['detail'])
        tranche = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/',
            {}, format='json')
        self.assertEqual(tranche.status_code, 409, tranche.data)
        self.assertIn(v2.reference, tranche.data['detail'])
        self.assertFalse(Facture.objects.filter(devis=self.devis).exists())

    def test_generer_facture_corps_non_objet_400(self):
        """api-fuzz (ENF11) : ``[null, null]`` posté à ``generer-facture``
        levait une 500 (``list.get``) — le corps est validé par son
        sérialiseur déclaré : 400 ``validation_error``, rien n'est créé."""
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/',
            [None, None], format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertEqual(resp.data['error']['code'], 'validation_error')
        self.assertFalse(Facture.objects.filter(devis=self.devis).exists())

    def test_surpaiement_refuse_et_rien_n_est_cree(self):
        avant_factures = Facture.objects.count()
        resp = self._post([self._p('100000', 10), self._p('60000', 5)])
        self.assertEqual(resp.status_code, 409, resp.data)  # CI #997 fuzz : refus d'état, 409
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
            [{'montant': '100', 'date_paiement': date.today().isoformat(),
              'mode_paiement': 'bitcoin'}],
            [{'montant': '100', 'date_paiement': 'hier',
              'mode_paiement': 'virement'}],
            [self._p('10', 1)] * 6,
            # CI #997 fuzz — la ligne de paiement est PUBLIÉE : montant
            # décimal-chaîne (nombre JSON, 3 décimales refusés), référence
            # de 120 signes au plus.
            [self._p('10', 1) | {'montant': 10}],
            [self._p('10.005', 1)],
            [self._p('10', 1, reference='x' * 121)],
        ]
        for paiements in cas:
            resp = self._post(paiements)
            self.assertEqual(resp.status_code, 400, (paiements[:1], resp.data))
        # Une date FUTURE dépend du jour : refus d'état, 409.
        resp = self._post([{'montant': '100', 'date_paiement': futur,
                            'mode_paiement': 'virement'}])
        self.assertEqual(resp.status_code, 409, resp.data)
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

    def test_montant_tranche_refus_d_etat_409(self):
        # api-fuzz-full 27/10 (ENF11) : « pas une tranche » et un montant au
        # moins égal au prix convenu sont des refus d'ÉTAT (409) ; un montant
        # illisible reste un 400.
        from apps.ventes.domain.facturation_vente import (
            FacturationVenteRefusee, modifier_montant_tranche)
        devis = self._388('DEV-VNT67-ETAT')
        complete = self._tranche(devis, '', 'solde', '100.00', '83.33',
                                 '16.67', statut='brouillon',
                                 type_facture='complete')
        with self.assertRaises(FacturationVenteRefusee) as ctx:
            modifier_montant_tranche(complete, '50', user=self.user)
        self.assertEqual((ctx.exception.status, ctx.exception.corps['code']),
                         (409, 'pas_une_tranche'))
        tranche = self._acompte_14700(devis, statut='brouillon', reference='')
        with self.assertRaises(FacturationVenteRefusee) as ctx:
            modifier_montant_tranche(tranche, '9999999999', user=self.user)
        self.assertEqual((ctx.exception.status, ctx.exception.corps['code']),
                         (409, 'montant_invalide'))
        with self.assertRaises(FacturationVenteRefusee) as ctx:
            modifier_montant_tranche(tranche, 'abc', user=self.user)
        self.assertEqual(ctx.exception.status, 400)

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

    def test_devis_refuse_est_un_conflit_409(self):
        """Un devis non accepté est un refus d'ÉTAT (409), même corps."""
        devis = self._388('DEV-VNT26-REF')
        devis.statut = 'refuse'
        devis.save(update_fields=['statut'])
        refus = self._refus(devis, nature='solde')
        self.assertEqual(refus.status, 409)
        self.assertIn('Seul un devis accepté', refus.corps['detail'])

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


class FacturerVenteVerrouVNT27(_BaseVente):
    """VNT27 — verrou ordonné racine + version facturée ; la contrainte
    ``uq_facture_tranche_vivante`` (IntegrityError) devient 409
    ``tranche_deja_creee`` : jamais deux brouillons de la même tranche."""

    def test_double_clic_un_seul_brouillon(self):
        devis = self._388('DEV-VNT27-DBL')
        self._acompte_14700(devis)
        self._facturer(devis, nature='intermediaire', cle_attendue='materiel')
        refus = self._refus(devis, nature='intermediaire',
                            cle_attendue='materiel')
        self.assertEqual(refus.status, 409)
        self.assertEqual(refus.corps['code'], 'tranche_deja_creee')
        self.assertEqual(Facture.objects.filter(
            devis=devis, cle_tranche='materiel').count(), 1)

    def test_course_sur_l_insert_rend_409(self):
        from apps.ventes.domain.facturation_vente import (
            FacturationVenteRefusee, creer_brouillon_tranche)
        from apps.ventes.vente_facturation import plan_facturation
        devis = self._388('DEV-VNT27-RACE')
        self._acompte_14700(devis)
        tranche = plan_facturation(devis)['prochaine']
        creer_brouillon_tranche(devis, tranche, self.user)
        # Le second INSERT de la même clé (course entre deux requêtes qui ont
        # lu le même plan) heurte la contrainte : 409, jamais un 500.
        with self.assertRaises(FacturationVenteRefusee) as ctx:
            creer_brouillon_tranche(devis, tranche, self.user)
        self.assertEqual(ctx.exception.status, 409)
        self.assertEqual(ctx.exception.corps['code'], 'tranche_deja_creee')
        self.assertEqual(Facture.objects.filter(
            devis=devis, cle_tranche='materiel').count(), 1)

    def test_le_verrou_porte_sur_la_racine_et_la_version(self):
        from apps.ventes.domain.facturation_vente import verrouiller_vente
        v1 = self._388('DEV-VNT27-V1')
        v2 = self._388('DEV-VNT27-V2')
        Devis.objects.filter(pk=v1.pk).update(
            is_active=False, superseded_by=v2)
        Devis.objects.filter(pk=v2.pk).update(version_parent=v1)
        v2.refresh_from_db()
        verrous = verrouiller_vente(v2)
        self.assertEqual([d.pk for d in verrous], [v1.pk, v2.pk])


class FacturerVenteAcompteVNT28(_BaseVente):
    """VNT28 (D-VNT-3, arbitrage 9) — nature ``acompte`` : le montant tapé
    réécrit l'échéancier [acompte A en MAD, intermédiaires en %, dernière =
    reste en MAD] et le brouillon d'acompte existant est MODIFIÉ (sinon
    créé) ; jamais un second brouillon ; ``acompte#n`` seulement après
    l'émission du premier. Goldens du 388."""

    def _echeancier(self, devis):
        devis.refresh_from_db()
        return [(e['type'], e['unite'], Decimal(str(e['pct_or_montant'])))
                for e in devis.echeancier]

    def _acomptes(self, devis):
        return Facture.objects.filter(
            devis=devis, type_facture='acompte').exclude(statut='annulee')

    def test_acompte_libre_15000_ecrit_l_echeancier(self):
        from apps.ventes.tests.test_echeancier_somme_total import (
            VENT_ACOMPTE_15000)
        devis = self._388('DEV-VNT28-15K')
        facture, _p = self._facturer(devis, nature='acompte',
                                     montant_ttc='15000.00',
                                     cle_attendue='acompte')
        self.assertEqual(self._echeancier(devis), [
            ('acompte', 'montant', Decimal('15000')),
            ('materiel', 'pct', Decimal('60')),
            ('solde', 'montant', Decimal('4600'))])
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertEqual(facture.libelle, 'Acompte')
        self.assertEqual(facture.cle_tranche, 'acompte')
        self.assertEqual(facture.montant_ttc, Decimal('15000.00'))
        self.assertEqual(facture.montant_ht, Decimal('12720.41'))
        self.assertEqual(facture.montant_tva, Decimal('2279.59'))
        self.assertEqual(facture.ventilation_tva, VENT_ACOMPTE_15000)
        # Le plan suit l'échéancier écrit : 29 400 puis 4 600.
        from apps.ventes.vente_facturation import plan_facturation
        a_faire = [t['montant_ttc'] for t in plan_facturation(devis)[
            'tranches'] if t['statut'] == 'a_faire']
        self.assertEqual(a_faire, [Decimal('29400.00'), Decimal('4600.00')])

    def test_double_clic_un_seul_brouillon(self):
        devis = self._388('DEV-VNT28-DBL')
        premiere, _p = self._facturer(devis, nature='acompte',
                                      montant_ttc='15000.00')
        seconde, _p = self._facturer(devis, nature='acompte',
                                     montant_ttc='15000.00')
        self.assertEqual(premiere.pk, seconde.pk)
        self.assertEqual(self._acomptes(devis).count(), 1)

    def test_trente_pour_cent_vaut_14700(self):
        devis = self._388('DEV-VNT28-30')
        facture, _p = self._facturer(devis, nature='acompte',
                                     pourcentage='30')
        facture.refresh_from_db()
        self.assertEqual(facture.montant_ttc, Decimal('14700.00'))
        self.assertEqual(facture.montant_ht, Decimal('12466.00'))
        self.assertEqual(facture.montant_tva, Decimal('2234.00'))

    def test_retaper_un_montant_modifie_le_meme_brouillon(self):
        devis = self._388('DEV-VNT28-RETAPE')
        premiere, _p = self._facturer(devis, nature='acompte',
                                      montant_ttc='15000.00')
        seconde, _p = self._facturer(devis, nature='acompte',
                                     montant_ttc='14700.00')
        self.assertEqual(premiere.pk, seconde.pk)
        seconde.refresh_from_db()
        self.assertEqual(seconde.montant_ttc, Decimal('14700.00'))
        self.assertEqual(seconde.montant_ht, Decimal('12466.00'))
        self.assertEqual(self._acomptes(devis).count(), 1)

    def test_brouillon_preexistant_edite_jamais_double(self):
        devis = self._388('DEV-VNT28-AMET4')
        existant = self._acompte_14700(devis, statut='brouillon',
                                       reference='')
        facture, _p = self._facturer(devis, nature='acompte',
                                     montant_ttc='15000.00')
        self.assertEqual(facture.pk, existant.pk)
        existant.refresh_from_db()
        self.assertEqual(existant.montant_ttc, Decimal('15000.00'))
        self.assertEqual(existant.montant_ht, Decimal('12720.41'))
        self.assertEqual(self._acomptes(devis).count(), 1)

    def test_acompte_supplementaire_seulement_apres_emission(self):
        devis = self._388('DEV-VNT28-SUP')
        self._acompte_14700(devis)
        refus = self._refus(devis, nature='acompte', montant_ttc='300.00')
        self.assertEqual(refus.status, 409)
        self.assertEqual(refus.corps['code'], 'tranche_deja_creee')
        facture, _p = self._facturer(devis, nature='acompte',
                                     montant_ttc='300.00',
                                     cle_attendue='acompte#2')
        facture.refresh_from_db()
        self.assertEqual(facture.cle_tranche, 'acompte#2')
        self.assertEqual(facture.montant_ttc, Decimal('300.00'))
        # L'acompte émis (30 %) est intouché ; la dernière vaut le reste.
        self.assertEqual(self._echeancier(devis), [
            ('acompte', 'pct', Decimal('30')),
            ('acompte', 'montant', Decimal('300')),
            ('materiel', 'pct', Decimal('60')),
            ('solde', 'montant', Decimal('4600'))])

    def test_trace_corrige_apres_acceptation(self):
        from apps.ventes.models import DevisActivity
        devis = self._388('DEV-VNT28-TRACE')
        self._facturer(devis, nature='acompte', montant_ttc='15000.00')
        self.assertTrue(DevisActivity.objects.filter(
            devis=devis, field='correction_apres_acceptation').exists())


class FacturerVenteCompleteVNT29(_BaseVente):
    """VNT29 — nature ``complete`` : 409 ``deja_facture`` après une émise ;
    409 ``brouillons_a_remplacer`` (+ liste) sans drapeau ; avec
    ``remplacer_brouillons`` les brouillons sont ANNULÉS (jamais supprimés)
    et la complète naît brouillon au prix convenu."""

    def test_brouillon_d_acompte_sans_drapeau_409(self):
        devis = self._388('DEV-VNT29-SANS')
        acompte = self._acompte_14700(devis, statut='brouillon',
                                      reference='')
        refus = self._refus(devis, nature='complete')
        self.assertEqual(refus.status, 409)
        self.assertEqual(refus.corps['code'], 'brouillons_a_remplacer')
        self.assertEqual(refus.corps['brouillons'], [
            {'id': acompte.id, 'reference': acompte.reference,
             'total_ttc': '14700.00'}])
        acompte.refresh_from_db()
        self.assertEqual(acompte.statut, Facture.Statut.BROUILLON)

    def test_avec_drapeau_brouillon_annule_complete_a_49000(self):
        devis = self._388('DEV-VNT29-AVEC')
        acompte = self._acompte_14700(devis, statut='brouillon',
                                      reference='')
        facture, _p = self._facturer(devis, nature='complete',
                                     remplacer_brouillons=True)
        acompte.refresh_from_db()
        self.assertEqual(acompte.statut, Facture.Statut.ANNULEE)
        self.assertTrue(Facture.objects.filter(pk=acompte.pk).exists())
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertEqual(facture.type_facture, 'complete')
        self.assertEqual(facture.total_ttc, Decimal('49000.00'))

    def test_acompte_emis_409_deja_facture(self):
        devis = self._388('DEV-VNT29-EMIS')
        self._acompte_14700(devis)
        refus = self._refus(devis, nature='complete',
                            remplacer_brouillons=True)
        self.assertEqual(refus.status, 409)
        self.assertEqual(refus.corps['code'], 'deja_facture')
        self.assertFalse(Facture.objects.filter(
            devis=devis, type_facture='complete').exists())


class FacturerVenteEncaissementVNT30(_BaseVente):
    """VNT30 — ``emettre`` / ``paiements`` / ``utiliser_avances`` : émission
    (numéro légal) puis encaissement, Σ ≤ total ; les avances client non
    affectées se ventilent d'abord (réparation D-VNT-4)."""

    def _paiement(self, montant):
        return {'montant': montant, 'date_paiement': date.today().isoformat(),
                'mode_paiement': 'virement', 'reference': 'VIR-1012'}

    def test_acompte_15000_paye_15000(self):
        from core.numbering import est_reference_provisoire
        devis = self._388('DEV-VNT30-PAYE')
        facture, paiements = self._facturer(
            devis, nature='acompte', montant_ttc='15000.00', emettre=True,
            paiements=[self._paiement('15000.00')])
        facture.refresh_from_db()
        self.assertFalse(est_reference_provisoire(facture.reference))
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(facture.montant_du, Decimal('0'))
        self.assertEqual(len(paiements), 1)
        self.assertEqual(paiements[0].montant, Decimal('15000.00'))

    def test_paiements_superieurs_au_montant_400(self):
        devis = self._388('DEV-VNT30-TROP')
        refus = self._refus(devis, nature='acompte', pourcentage='30',
                            emettre=True,
                            paiements=[self._paiement('15000.00')])
        self.assertEqual(refus.status, 400)
        self.assertEqual(refus.corps['code'], 'paiements_invalides')
        # Rien n'est écrit : ni facture, ni numéro, ni échéancier.
        self.assertFalse(Facture.objects.filter(devis=devis).exists())
        self.assertEqual(Paiement.objects.count(), 0)

    def test_paiement_date_future_409(self):
        # api-fuzz-full 28/10 (ENF11) : la date future est conforme au schéma
        # (format date) ; le refus dépend du jour courant → 409, rien écrit.
        devis = self._388('DEV-VNT30-FUTUR')
        paiement = self._paiement('100.00')
        paiement['date_paiement'] = (
            date.today() + timedelta(days=3)).isoformat()
        refus = self._refus(devis, nature='acompte', montant_ttc='15000.00',
                            emettre=True, paiements=[paiement])
        self.assertEqual(refus.status, 409)
        self.assertEqual(refus.corps['code'], 'paiements_invalides')
        self.assertFalse(Facture.objects.filter(devis=devis).exists())

    def test_avance_14700_puis_paiement_300(self):
        from apps.ventes.domain.encaissements import enregistrer_avance
        devis = self._388('DEV-VNT30-AVANCE')
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal('14700'), date_paiement=date.today(),
            mode='virement', created_by=self.user)
        facture, paiements = self._facturer(
            devis, nature='acompte', montant_ttc='15000.00', emettre=True,
            utiliser_avances=True, paiements=[self._paiement('300.00')])
        facture.refresh_from_db()
        avance.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)
        self.assertEqual(facture.montant_paye, Decimal('15000.00'))
        self.assertEqual(avance.montant_disponible, Decimal('0'))
        self.assertEqual([p.montant for p in paiements], [Decimal('300.00')])

    def test_sans_emettre_reste_brouillon(self):
        devis = self._388('DEV-VNT30-BR')
        facture, paiements = self._facturer(
            devis, nature='acompte', montant_ttc='15000.00')
        self.assertEqual(facture.statut, Facture.Statut.BROUILLON)
        self.assertEqual(paiements, [])


class FacturerVenteEndpointVNT31(_BaseVente):
    """VNT31 — ``GET/POST devis/<id>/facturer/`` conforme au contrat
    ``devis_facturer.json`` ; ``emettre`` exige le code d'encaissement."""

    CONTRAT_VENTE = (Path(__file__).resolve().parents[1] / 'contract_samples'
                     / 'devis_facturer.json')

    def _url(self, devis):
        return f'/api/django/ventes/devis/{devis.id}/facturer/'

    def _contrat(self):
        return json.loads(self.CONTRAT_VENTE.read_text(encoding='utf-8'))

    def _role(self, nom, permissions):
        from apps.roles.models import Role
        user = User.objects.create_user(
            username=f'vnt31_{nom}_{_nxt()}', password='x',
            role_legacy='normal', company=self.company,
            role=Role.objects.create(company=self.company,
                                     nom=f'{nom} VNT31 {_nxt()}',
                                     permissions=list(permissions)))
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return user, api

    def _poster_en_tant_que(self, user, api, devis, corps):
        # Portée « équipe » d'un rôle Commercial : le devis est le sien.
        Devis.objects.filter(pk=devis.pk).update(created_by=user)
        return api.post(self._url(devis), corps, format='json')

    def test_apercu_get_388(self):
        devis = self._388('DEV-VNT31-GET')
        resp = self.api.get(self._url(devis))
        self.assertEqual(resp.status_code, 200, resp.data)
        apercu = self._contrat()['apercu_get']['reponse_200']
        self.assertEqual(set(resp.data), set(apercu))
        self.assertEqual(resp.data['acompte_propose'], '14700.00')
        self.assertEqual(len(resp.data['plan']), 3)
        self.assertEqual({t['statut'] for t in resp.data['plan']},
                         {'a_faire'})
        self.assertEqual(set(resp.data['plan'][0]), set(apercu['plan'][0]))
        self.assertEqual(set(resp.data['vente']), set(apercu['vente']))
        self.assertEqual(resp.data['vente']['prix_convenu_ttc'], '49000.00')
        self.assertEqual(resp.data['prochaine']['cle'], 'acompte')

    def test_post_acompte_15000_forme_du_contrat(self):
        devis = self._388('DEV-VNT31-POST')
        resp = self.api.post(self._url(devis), {
            'nature': 'acompte', 'montant_ttc': '15000.00',
            'cle_attendue': 'acompte'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        exemple = self._contrat()['exemple']
        self.assertEqual(set(resp.data), set(exemple))
        self.assertEqual(set(resp.data['facture']), set(exemple['facture']))
        self.assertEqual(set(resp.data['vente']), set(exemple['vente']))
        self.assertEqual(resp.data['facture']['total_ttc'], '15000.00')
        self.assertEqual(resp.data['facture']['nature'], 'acompte')
        self.assertEqual(resp.data['facture']['statut'], 'brouillon')
        self.assertEqual(resp.data['vente']['brouillons_ttc'], '15000.00')

    def test_refus_du_service_rendu_tel_quel(self):
        devis = self._388('DEV-VNT31-409')
        self._acompte_14700(devis)
        resp = self.api.post(self._url(devis), {
            'nature': 'solde', 'cle_attendue': 'solde'}, format='json')
        self.assertEqual(resp.status_code, 409, resp.data)
        self.assertEqual(resp.data['code'], 'cle_inattendue')
        self.assertEqual(resp.data['cle_attendue'], 'materiel')

    def test_nature_enumeration_publiee_est_celle_du_service(self):
        """ENF11 — la nature est une énumération PUBLIÉE (= ``NATURES``) ;
        hors liste = 400 du sérialiseur déclaré, aucune facture."""
        from apps.ventes.domain.facturation_vente import NATURES
        from apps.ventes.views import openapi_docs as D
        champ = D.FacturerVenteRequest.fields['nature']
        self.assertEqual(tuple(champ.choices), NATURES)
        devis = self._388('DEV-VNT31-NATURE')
        for brut in ('0', 'Acompte', '', 7):
            resp = self.api.post(self._url(devis), {'nature': brut},
                                 format='json')
            self.assertEqual(resp.status_code, 400, (brut, resp.data))
        self.assertFalse(Facture.objects.filter(devis=devis).exists())

    def test_paiement_publie_avec_montant_requis(self):
        """api-fuzz-full 27/10 (ENF11) — ``paiements: [{…sans montant…}]``
        était publié « objet quelconque » puis refusé 400 « Paiement n°1 :
        montant invalide. » : la forme lue par ``valider_paiements_saisis``
        est publiée (montant requis, motif ; date ; mode) et appliquée par
        le sérialiseur déclaré — 400 nommant le champ, aucune facture."""
        from apps.ventes.views import openapi_docs as D
        enfant = D.FacturerVenteRequest.fields['paiements'].child
        self.assertTrue(enfant.fields['montant'].required)
        self.assertEqual(set(enfant.fields), {
            'montant', 'date_paiement', 'mode_paiement', 'reference'})
        devis = self._388('DEV-VNT31-PAIEMENT')
        resp = self.api.post(self._url(devis), {
            'nature': 'acompte', 'montant_ttc': '15000.00', 'emettre': True,
            'paiements': [{'mode_paiement': 'virement',
                           'date_paiement': date.today().isoformat()}]},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('paiements', resp.data)
        self.assertFalse(Facture.objects.filter(devis=devis).exists())
        resp = self.api.post(self._url(devis), {
            'nature': 'acompte', 'montant_ttc': '15000.00', 'emettre': True,
            'paiements': [{'montant': '15000.00', 'mode_paiement': 'virement',
                           'date_paiement': date.today().isoformat()}]},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['facture']['statut'], 'payee')

    def test_emettre_exige_le_code_d_encaissement(self):
        from apps.roles.permissions_registre import (
            COMMERCIAL_PERMISSIONS, TECHNICIEN_PERMISSIONS)
        devis = self._388('DEV-VNT31-PERM')
        corps = {'nature': 'acompte', 'montant_ttc': '15000.00',
                 'emettre': True}
        resp = self._poster_en_tant_que(
            *self._role('Technicien', TECHNICIEN_PERMISSIONS), devis, corps)
        self.assertEqual(resp.status_code, 403, resp.data)
        resp = self._poster_en_tant_que(
            *self._role('Commercial sans encaisser', [
                c for c in COMMERCIAL_PERMISSIONS if c != 'encaisser']),
            devis, corps)
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertFalse(Facture.objects.filter(devis=devis).exists())
        resp = self._poster_en_tant_que(
            *self._role('Commercial', COMMERCIAL_PERMISSIONS), devis, corps)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['facture']['statut'], 'emise')

    def test_override_credit_passe_le_blocage_credit(self):
        """Comme ``generer-facture`` : blocage crédit XFAC28 → 403
        ``credit_hold`` ; ``override_credit`` (responsable/admin) émet."""
        from apps.parametres.models import CompanyProfile
        devis = self._388('DEV-VNT31-HOLD')
        profile = CompanyProfile.get(company=self.company)
        profile.credit_hold_actif = True
        profile.save(update_fields=['credit_hold_actif'])
        self.client_obj.plafond_credit = Decimal('1')
        self.client_obj.save(update_fields=['plafond_credit'])
        Facture.objects.create(
            company=self.company, reference=f'FAC-HOLD-{_nxt()}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('50000'),
            montant_tva=Decimal('10000'), montant_ttc=Decimal('60000'))
        corps = {'nature': 'acompte', 'montant_ttc': '15000.00',
                 'emettre': True}
        resp = self.api.post(self._url(devis), corps, format='json')
        self.assertEqual(resp.status_code, 403, resp.data)
        self.assertEqual(resp.data['code'], 'credit_hold')
        self.assertFalse(Facture.objects.filter(devis=devis).exists())
        resp = self.api.post(self._url(devis),
                             {**corps, 'override_credit': True},
                             format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['facture']['statut'], 'emise')


class AcompteAutomatiqueVNT62(_BaseVente):
    """VNT62 (AMET2 + AMET4, D-SIGN-AUTO = a) — l'acceptation fige
    l'échéancier puis pose UN brouillon d'acompte ; « Facturer l'acompte »
    modifie CE brouillon ; un avenant négocié n'en pose aucun."""

    def setUp(self):
        from unittest import mock
        super().setUp()
        for cible in ('apps.ventes.domain.cycle_vie._store_signed_pdf',
                      'apps.ventes.domain.cycle_vie._send_acceptance_emails'):
            patcher = mock.patch(cible)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _accepte(self, reference):
        from apps.ventes.domain.cycle_vie import accept_devis
        devis = self._388(reference, echeancier=None, statut='envoye')
        return accept_devis(devis=devis, user=self.user, nom='Client 388',
                            option='sans_batterie')

    def _brouillons_acompte(self, devis_ids):
        return Facture.objects.filter(
            devis_id__in=devis_ids, statut=Facture.Statut.BROUILLON,
            type_facture='acompte')

    def test_acceptation_fige_30_60_10_et_pose_le_brouillon_14700(self):
        devis = self._accepte('DEV-VNT62-10')
        devis.refresh_from_db()
        self.assertEqual([e['pct_or_montant'] for e in devis.echeancier],
                         [30, 60, 10])
        brouillons = list(self._brouillons_acompte([devis.pk]))
        self.assertEqual(len(brouillons), 1)
        self.assertEqual(Decimal(str(brouillons[0].total_ttc)),
                         Decimal('14700.00'))
        self.assertTrue(brouillons[0].reference.startswith('BROUILLON-'))

    def test_facturer_l_acompte_15000_modifie_le_meme_brouillon(self):
        devis = self._accepte('DEV-VNT62-20')
        auto = self._brouillons_acompte([devis.pk]).get()
        facture, _p = self._facturer(devis, nature='acompte',
                                     montant_ttc=Decimal('15000'))
        self.assertEqual(facture.pk, auto.pk)
        self.assertEqual(Decimal(str(facture.total_ttc)),
                         Decimal('15000.00'))
        self.assertEqual(self._brouillons_acompte([devis.pk]).count(), 1)

    def test_le_geste_facturer_l_acompte_reste_offert_sur_le_brouillon_auto(self):
        # Nocturne #726 (VNT82) — « Facturer l'acompte » REPREND le brouillon
        # automatique (test ci-dessus) : ``peut.facturer_acompte`` restait
        # faux dès qu'un brouillon existait, le bouton du panneau de vente
        # disparaissait et la fiche lead ne proposait plus que « Émettre ».
        from apps.ventes.vente_facturation import etat_vente
        devis = self._accepte('DEV-VNT62-50')
        etat = etat_vente(devis, self.user)
        self.assertEqual(etat['prochaine_action'], 'acompte')
        self.assertTrue(etat['peut']['facturer_acompte'], etat['peut'])
        self.assertFalse(etat['peut']['facturer_solde'])
        # Un AUTRE brouillon (tranche matériel) ferme bien le geste.
        self._facturer(devis, nature='acompte', montant_ttc=Decimal('14700'))
        acompte = self._brouillons_acompte([devis.pk]).get()
        acompte.statut = Facture.Statut.EMISE
        acompte.save(update_fields=['statut'])
        self._tranche(devis, '', 'materiel', '29400.00', '24932.00',
                      '4468.00', statut='brouillon',
                      type_facture='intermediaire')
        etat = etat_vente(devis, self.user)
        self.assertFalse(etat['peut']['facturer_acompte'])
        self.assertFalse(etat['peut']['facturer_solde'])

    def test_jamais_un_deuxieme_brouillon(self):
        from apps.ventes.domain.facturation_vente import (
            acompte_a_l_acceptation)
        devis = self._accepte('DEV-VNT62-30')
        self.assertIsNone(acompte_a_l_acceptation(devis, self.user))
        self.assertEqual(self._brouillons_acompte([devis.pk]).count(), 1)

    def test_avenant_negocie_aucun_brouillon_neuf(self):
        from apps.ventes.domain.negociation import appliquer_prix_negocie
        devis = self._accepte('DEV-VNT62-40')
        r = appliquer_prix_negocie(devis, prix_ttc='44100', user=self.user)
        ids = [devis.pk, r['devis_v2']['id']]
        # Le brouillon de la V1 est retiré par « Prix négocié », la V2
        # acceptée n'en pose pas de nouveau.
        self.assertEqual(self._brouillons_acompte(ids).count(), 0)

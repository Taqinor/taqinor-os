"""AFAC12 (C-AFAC-002) — annuler une facture qui porte de l'argent exige une
directive ``acompte`` (400 ``directive_acompte_requise``, contrat
``facture_annulation.json``) ; les avances ventilées suivent le transfert
ou entrent dans le remboursement ; un avoir actif bloque l'annulation.

Rejoue les sondes FBC-2 (« annuler {} 200 ; solde payé 0, restant 150 000…
nouvel acompte 45 000 ») et L2-C-AFAC-002 (facture complète : « payé 0,
restant 120 000… facturer-complet rejoué → 201 »). Endpoints, services et
modèles réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_annulation_argent"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
BASE = '/api/django/ventes'
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class AnnulationArgentTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC12 Co', slug=f'afac12-co-{_nxt()}')
        self.admin = User.objects.create_user(
            username=f'afac12_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Annulation', prenom='AFAC12',
            email=f'afac12-{_nxt()}@example.invalid')
        self.kit = Produit.objects.create(
            company=self.company, nom='Kit AFAC12', sku=f'AFAC12K-{_nxt()}',
            prix_vente=Decimal('0'), quantite_stock=100000)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    # ── fixtures ────────────────────────────────────────────────────────
    def _devis(self, ht='125000'):
        """Devis accepté @20 % (125 000 HT = 150 000 TTC), échéancier
        résidentiel 30/60/10."""
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-AFAC12-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.kit, designation='Centrale PV',
            quantite=Decimal('1'), prix_unitaire=Decimal(ht),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        return devis

    def _tranche(self, devis):
        from apps.ventes.models import Facture
        r = self.api.post(f'{BASE}/devis/{devis.id}/generer-facture/', {},
                          format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return Facture.objects.get(pk=r.data['id'])

    def _payer(self, facture, montant):
        from apps.ventes.models import Paiement
        return Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal(montant),
            date_paiement=date.today(), mode='virement',
            created_by=self.admin)

    def _avance_ventilee(self, facture, montant):
        from apps.ventes.domain.encaissements import (
            enregistrer_avance, ventiler_avance,
        )
        avance = enregistrer_avance(
            company=self.company, client=self.client_obj,
            montant=Decimal(montant), date_paiement=date.today(),
            mode='virement', created_by=self.admin)
        ventiler_avance(paiement=avance, facture=facture,
                        montant=Decimal(montant), user=self.admin)
        return avance

    def _annuler(self, facture, body=None):
        return self.api.post(f'{BASE}/factures/{facture.id}/annuler/',
                             body or {}, format='json')

    def _relire(self, obj):
        return type(obj).objects.get(pk=obj.pk)

    def _solde(self, devis):
        from apps.ventes.models import Devis
        from apps.ventes.utils.echeancier import solde_devis
        return solde_devis(Devis.objects.get(pk=devis.pk))

    # ── (a) acompte partiellement payé, sans directive ──────────────────
    def test_sans_directive_refuse(self):
        devis = self._devis()
        acompte = self._tranche(devis)
        self.assertEqual(Decimal(str(acompte.total_ttc)), Decimal('45000.00'))
        statut = acompte.statut
        self._payer(acompte, '20000')
        r = self._annuler(acompte)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['code'], 'directive_acompte_requise')
        self.assertIn('detail', r.data)
        self.assertEqual(r.data['argent_rattache']['paiements'], '20000.00')
        self.assertEqual(set(r.data['argent_rattache']),
                         {'paiements', 'affectations', 'notes_debit',
                          'retenues', 'avoirs_actifs'})
        acompte = self._relire(acompte)
        self.assertEqual(acompte.statut, statut)
        self.assertEqual(Decimal(str(acompte.montant_paye)),
                         Decimal('20000.00'))
        self.assertEqual(self._solde(devis)['paye'], Decimal('20000.00'))
        # La porte suivante facture le MATÉRIEL, jamais un nouvel acompte.
        suivante = self._tranche(devis)
        self.assertNotEqual(suivante.cle_tranche, acompte.cle_tranche)

    # ── (b) facture complète 120 000 payée 50 000 ───────────────────────
    def test_solde_devis_inchange_apres_refus(self):
        from apps.ventes.models import Facture, Paiement
        devis = self._devis(ht='100000')
        r = self.api.post(f'{BASE}/devis/{devis.id}/facturer-complet/',
                          {'paiements': []}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(pk=r.data['id'])
        self.assertEqual(Decimal(str(facture.total_ttc)),
                         Decimal('120000.00'))
        statut = facture.statut
        paiement = self._payer(facture, '50000')
        r = self._annuler(facture)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['code'], 'directive_acompte_requise')
        # CLAUSE PERSISTANCE — relu en base.
        facture = self._relire(facture)
        self.assertEqual(facture.statut, statut)
        self.assertEqual(Paiement.objects.get(pk=paiement.pk).facture_id,
                         facture.pk)
        solde = self._solde(devis)
        self.assertEqual(solde['paye'], Decimal('50000.00'))
        self.assertEqual(solde['restant'], Decimal('70000.00'))
        # CLAUSE CLIENT — le dû reste 70 000, jamais 120 000 réclamés.
        self.assertEqual(Decimal(str(facture.montant_du)),
                         Decimal('70000.00'))
        r = self.api.post(f'{BASE}/devis/{devis.id}/facturer-complet/',
                          {'paiements': []}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    # ── (c) avance ventilée ─────────────────────────────────────────────
    def test_affectation_suit_transfert(self):
        devis = self._devis()
        acompte = self._tranche(devis)
        materiel = self._tranche(devis)
        self._avance_ventilee(acompte, '10000')
        r = self._annuler(acompte)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['argent_rattache']['affectations'],
                         '10000.00')
        r = self._annuler(acompte, {'acompte': {
            'action': 'transferer', 'facture_cible': materiel.id}})
        self.assertEqual(r.status_code, 200, r.data)
        acompte, materiel = self._relire(acompte), self._relire(materiel)
        self.assertEqual(acompte.statut, 'annulee')
        self.assertEqual(acompte.affectations_paiement.count(), 0)
        self.assertEqual(materiel.affectations_paiement.count(), 1)
        self.assertEqual(Decimal(str(materiel.montant_paye)),
                         Decimal('10000.00'))
        self.assertEqual(Decimal(str(acompte.montant_paye)), Decimal('0'))
        self.assertEqual(self._solde(devis)['paye'], Decimal('10000.00'))

    def test_affectation_rendue_au_remboursement(self):
        from apps.ventes.models import Paiement
        devis = self._devis()
        acompte = self._tranche(devis)
        self._avance_ventilee(acompte, '10000')
        r = self._annuler(acompte, {'acompte': {'action': 'rembourser'}})
        self.assertEqual(r.status_code, 200, r.data)
        acompte = self._relire(acompte)
        self.assertEqual(acompte.statut, 'annulee')
        self.assertEqual(Decimal(str(acompte.montant_paye)), Decimal('0'))
        contre = Paiement.objects.get(facture=acompte, montant__lt=0)
        self.assertEqual(contre.montant, Decimal('-10000.00'))

    # ── (d) avoir actif ─────────────────────────────────────────────────
    def test_avoir_actif_refuse(self):
        devis = self._devis()
        acompte = self._tranche(devis)
        statut = acompte.statut
        r = self.api.post(
            f'{BASE}/factures/{acompte.id}/creer-avoir/',
            {'lignes': [{'designation': 'Geste', 'quantite': '1',
                         'prix_unitaire': '1000', 'taux_tva': '20',
                         'produit': self.kit.id}]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        avoir_id = r.data['id']
        r = self._annuler(acompte)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data['code'], 'avoir_actif')
        self.assertEqual(self._relire(acompte).statut, statut)
        r = self.api.post(f'{BASE}/avoirs/{avoir_id}/annuler/', {},
                          format='json')
        self.assertIn(r.status_code, (200, 201), r.data)
        r = self._annuler(acompte)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._relire(acompte).statut, 'annulee')

    def test_sans_argent_annule_comme_avant(self):
        devis = self._devis()
        acompte = self._tranche(devis)
        r = self._annuler(acompte)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._relire(acompte).statut, 'annulee')

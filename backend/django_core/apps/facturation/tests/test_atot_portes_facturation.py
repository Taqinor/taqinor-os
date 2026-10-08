"""ATOT2 (C-ATOT-001) — les quatre portes de facturation d'un devis (tranche,
BC, facture complète, consolidée) passent par UN prédicat
(`factures_du_devis`, FactureSource compris) et UNE garde
(`exiger_devis_facturable`) : aucune vente n'est facturée deux fois.

Rejoue la sonde V1 TFAC-1 : aujourd'hui `facturer-complet` puis
`generer-facture` = 201 « Livraison du matériel 60 % » (Σ 240 000 pour un
devis de 150 000) ; une consolidée puis chaque porte = 201. Endpoints réels,
aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_portes_facturation"
"""
from decimal import Decimal
from itertools import permutations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
PORTES = ('tranche', 'complete', 'bc', 'consolidee')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class PortesFacturationTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ATOT2 Co', slug=f'atot2-co-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Portes', prenom='ATOT2',
            email=f'atot2-{_nxt()}@example.invalid')
        # Produit de la ligne du devis : `LigneFacture.produit` est NOT NULL
        # et facturer-complet / consolider décomptent le stock (grand stock :
        # chaque sous-test facture un nouveau devis).
        from apps.stock.models import Produit
        self.kit = Produit.objects.create(
            company=self.company, nom='Kit ATOT2', sku=f'ATOT2K-{_nxt()}',
            prix_vente=Decimal('125000'), quantite_stock=100000)
        self.user = User.objects.create_user(
            username=f'atot2_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    # ── fixtures ────────────────────────────────────────────────────────
    def _devis(self):
        """Devis accepté 125 000 HT @20 % (TTC 150 000), échéancier
        résidentiel par défaut 30/60/10."""
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ATOT2-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.kit, designation='Centrale PV',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('125000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return devis

    def _porte(self, porte, devis):
        from apps.ventes.models import BonCommande
        if porte == 'tranche':
            return self.api.post(
                f'/api/django/ventes/devis/{devis.id}/generer-facture/',
                {}, format='json')
        if porte == 'complete':
            return self.api.post(
                f'/api/django/ventes/devis/{devis.id}/facturer-complet/',
                {'paiements': []}, format='json')
        if porte == 'bc':
            bc = BonCommande.objects.filter(devis=devis).first()
            if bc is None:
                bc = BonCommande.objects.create(
                    company=self.company, reference=f'BC-ATOT2-{_nxt()}',
                    devis=devis, client=self.client_obj,
                    statut=BonCommande.Statut.CONFIRME)
            return self.api.post(
                f'/api/django/ventes/bons-commande/{bc.id}/creer-facture/',
                {}, format='json')
        partenaire = self._devis()
        return self.api.post(
            '/api/django/ventes/factures/consolider/',
            {'devis_ids': [devis.id, partenaire.id]}, format='json')

    def _actives(self, devis):
        from apps.ventes.selectors_facturation import factures_du_devis
        return list(factures_du_devis(devis).order_by('id'))

    def _refs(self, devis):
        return [f.reference for f in self._actives(devis)]

    # ── les 12 ordres porte A puis porte B ─────────────────────────────
    def test_douze_ordres_seconde_porte_refusee(self):
        for porte_a, porte_b in permutations(PORTES, 2):
            with self.subTest(a=porte_a, b=porte_b):
                devis = self._devis()
                r1 = self._porte(porte_a, devis)
                self.assertEqual(r1.status_code, 201, r1.data)
                avant = self._refs(devis)
                self.assertEqual(len(avant), 1)
                r2 = self._porte(porte_b, devis)
                self.assertEqual(r2.status_code, 400, r2.data)
                self.assertIn(avant[0], str(r2.data))
                self.assertIn('avoir', str(r2.data))
                self.assertEqual(self._refs(devis), avant)

    def test_complete_puis_tranche_refuse(self):
        devis = self._devis()
        r1 = self._porte('complete', devis)
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self._porte('tranche', devis)
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertIn(r1.data['facture_reference'], r2.data['detail'])
        total = sum((Decimal(str(f.total_ttc)) for f in self._actives(devis)),
                    Decimal('0'))
        self.assertLessEqual(total, Decimal('150000.00'))

    def test_consolidee_puis_chaque_porte_refuse(self):
        from apps.ventes.models import Devis, Facture, FactureSource
        d1, d2, d3 = self._devis(), self._devis(), self._devis()
        r = self.api.post(
            '/api/django/ventes/factures/consolider/',
            {'devis_ids': [d1.id, d2.id, d3.id]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        consolidee = Facture.objects.get(pk=r.data['id'])
        nb = Facture.objects.count()
        for porte, devis in (('tranche', d1), ('complete', d2), ('bc', d3)):
            with self.subTest(porte=porte):
                resp = self._porte(porte, Devis.objects.get(pk=devis.pk))
                self.assertEqual(resp.status_code, 400, resp.data)
                self.assertIn(consolidee.reference, str(resp.data))
        self.assertEqual(Facture.objects.count(), nb)
        self.assertEqual(
            FactureSource.objects.filter(facture=consolidee).count(), 3)

    def test_tranches_successives_restent_ouvertes(self):
        devis = self._devis()
        for _ in range(3):
            r = self._porte('tranche', devis)
            self.assertEqual(r.status_code, 201, r.data)
        total = sum((Decimal(str(f.total_ttc)) for f in self._actives(devis)),
                    Decimal('0'))
        self.assertEqual(total, Decimal('150000.00'))

    def test_solde_porte_facturation(self):
        from apps.ventes.models import Devis
        from apps.ventes.utils.echeancier import solde_devis
        vierge = self._devis()
        self.assertEqual(solde_devis(vierge)['porte_facturation'], 'libre')

        en_tranche = self._devis()
        self._porte('tranche', en_tranche)
        solde = solde_devis(Devis.objects.get(pk=en_tranche.pk))
        self.assertEqual(solde['porte_facturation'], 'tranche')
        self.assertEqual(solde['tranches_facturees'], 1)

        complet = self._devis()
        self._porte('complete', complet)
        solde = solde_devis(Devis.objects.get(pk=complet.pk))
        self.assertEqual(solde['porte_facturation'], 'aucune')
        self.assertEqual(solde['tranches_facturees'], 0)

        consolide = self._devis()
        self._porte('consolidee', consolide)
        solde = solde_devis(Devis.objects.get(pk=consolide.pk))
        self.assertEqual(solde['porte_facturation'], 'aucune')

    def test_solde_api_expose_porte_en_texte(self):
        devis = self._devis()
        resp = self.api.get(f'/api/django/ventes/devis/{devis.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['solde']['porte_facturation'], 'libre')

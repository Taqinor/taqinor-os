"""APRF12 (C-APRF-004) — ``ca_devis_factures_par_clients``,
``montants_factures_par_devis`` et ``carnet_commande_par_mois`` lisent des
devis passés par ``devis_avec_totaux`` (APRF7) et des factures passées par
``factures_avec_montant_du`` (APRF11) : +10 devis sur un client n'ajoutent
aucune requête, montants égaux au centime.

Rejoue la sonde F V_VA (client à 6 devis, +10 clonés : 19 → 38 requêtes).
``CaptureQueriesContext`` à deux tailles, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_aprf12_ca_clients_en_lot"
"""
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

_CTR = [0]
JOUR = date(2026, 9, 15)


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class CaClientsEnLotTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(nom='APRF12', slug='aprf12-co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Groupe', prenom='APRF12',
            email='aprf12@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau', sku='APRF12-P',
            prix_vente=Decimal('1000'))
        self.devis_ids = []

    def _ajouter(self, n):
        from apps.ventes.models import Devis, Facture, LigneDevis, LigneFacture
        for _ in range(n):
            k = _nxt()
            devis = Devis.objects.create(
                company=self.company, reference=f'DEV-APRF12-{k}',
                client=self.client_obj, statut=Devis.Statut.ACCEPTE,
                taux_tva=Decimal('20'), date_acceptation=JOUR)
            LigneDevis.objects.create(
                devis=devis, produit=self.produit, designation='Panneau',
                quantite=Decimal('2'), prix_unitaire=Decimal('1000'),
                remise=Decimal('0'), taux_tva=Decimal('20'))
            self.devis_ids.append(devis.id)
            if k % 2:
                f = Facture.objects.create(
                    company=self.company, reference=f'FAC-APRF12-{k}',
                    client=self.client_obj, devis=devis,
                    statut=Facture.Statut.EMISE, taux_tva=Decimal('20'))
                LigneFacture.objects.create(
                    facture=f, designation='Panneau', quantite=Decimal('2'),
                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))

    def _mesurer(self):
        from apps.ventes.selectors_facturation import (
            ca_devis_factures_par_clients, carnet_commande_par_mois,
            montants_factures_par_devis,
        )
        with CaptureQueriesContext(connection) as ctx:
            ca = ca_devis_factures_par_clients(
                self.company, [self.client_obj.id])
            montants = montants_factures_par_devis(
                self.devis_ids, self.company)
            carnet = carnet_commande_par_mois(
                self.company, date(2026, 9, 1), date(2026, 9, 30))
        return len(ctx.captured_queries), ca, montants, carnet

    def test_requetes_constantes_et_montants_exacts(self):
        from apps.ventes.models import Devis, Facture
        self._ajouter(3)
        n_petit, _, _, _ = self._mesurer()
        self._ajouter(10)
        n_grand, ca, montants, carnet = self._mesurer()
        self.assertEqual(n_petit, n_grand)
        # Montants égaux au centime à la lecture sans préchargement.
        attendu_devis = sum(
            (Decimal(str(d.total_ttc)) for d in Devis.objects.filter(
                pk__in=self.devis_ids)), Decimal('0'))
        attendu_factures = sum(
            (Decimal(str(f.total_ttc)) for f in Facture.objects.filter(
                devis_id__in=self.devis_ids)), Decimal('0'))
        self.assertEqual(ca[self.client_obj.id]['ca_devis'], attendu_devis)
        self.assertEqual(ca[self.client_obj.id]['ca_factures'],
                         attendu_factures)
        self.assertEqual(sum((v['ttc'] for v in montants.values()),
                             Decimal('0')), attendu_factures)
        non_factures = sum(
            (Decimal(str(d.total_ttc)) for d in Devis.objects.filter(
                pk__in=self.devis_ids, factures__isnull=True)),
            Decimal('0'))
        self.assertEqual(carnet.get('2026-09', Decimal('0')), non_factures)

"""APRF24 (C-APRF-024) — « Chantiers à facturer » lit les factures de TOUS les
devis des jalons atteints en lot (`ventes.selectors.tranches_facturees`) :
+10 jalons ne coûtent aucune requête de plus, les tranches dues sont les mêmes,
et le verdict du lot égale `tranche_facturee` unitaire (annulées et brouillons
compris).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_aprf24_a_facturer_en_lot"
"""
import itertools
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.crm.models import Client
from apps.installations.models import Installation, JalonProjet
from apps.installations.services import chantiers_a_facturer
from apps.ventes.models import Devis, Facture
from apps.ventes.selectors import tranche_facturee, tranches_facturees
from authentication.models import Company

_seq = itertools.count(1)
TRANCHES = ('acompte', 'intermediaire', 'solde')


class AFacturerEnLotTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-aprf24', defaults={'nom': 'Co APRF24'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='APRF24',
            email='aprf24@example.invalid')

    def _jalon(self, motif):
        """Un chantier + devis accepté + jalon atteint (tranche tournante) ;
        `motif` : None | 'emise' | 'annulee' | 'brouillon'."""
        n = next(_seq)
        tranche = TRANCHES[n % 3]
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-APRF24-{n:04d}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        inst = Installation.objects.create(
            company=self.company, reference=f'CHT-APRF24-{n}',
            client=self.client_obj, devis=devis,
            statut=Installation.Statut.SIGNE)
        jalon = JalonProjet.objects.create(
            company=self.company, installation=inst,
            phase=JalonProjet.Phase.POSE, libelle=f'Pose {n}',
            tranche_echeancier=tranche, atteint=True)
        if motif:
            statut = {'emise': Facture.Statut.EMISE,
                      'annulee': Facture.Statut.ANNULEE,
                      'brouillon': Facture.Statut.BROUILLON}[motif]
            Facture.objects.create(
                company=self.company, reference=f'FAC-APRF24-{n:04d}',
                devis=devis, client=self.client_obj, type_facture=tranche,
                statut=statut)
        return jalon

    def _creer(self, nb):
        motifs = (None, 'emise', 'annulee', 'brouillon')
        return [self._jalon(motifs[i % 4]) for i in range(nb)]

    def _appel(self):
        with CaptureQueriesContext(connection) as ctx:
            res = chantiers_a_facturer(self.company)
        return len(ctx.captured_queries), res

    def test_requetes_identiques_quand_les_jalons_triplent(self):
        # Même MIX de cas (aucune / émise / annulée / brouillon) aux deux
        # tailles : le coût fixe du lot est le même, seul le nombre de jalons
        # change (4 puis 12).
        self._creer(4)
        n4, _ = self._appel()
        self._creer(8)
        n12, res = self._appel()
        self.assertEqual(n4, n12, (n4, n12))
        self.assertTrue(res)

    def test_tranches_dues_egales_au_verdict_unitaire(self):
        jalons = self._creer(8)
        attendu = sorted(
            j.id for j in jalons
            if not tranche_facturee(j.installation.devis, j.tranche_echeancier))
        _, res = self._appel()
        self.assertEqual(sorted(r['jalon_id'] for r in res), attendu)
        # Émise = facturée ; annulée et brouillon restent dus.
        dus = {r['jalon_id'] for r in res}
        for i, j in enumerate(jalons):
            self.assertEqual(j.id in dus, i % 4 != 1, (i, j.id))

    def test_lot_egal_unitaire_par_devis_et_tranche(self):
        jalons = self._creer(8)
        devis = [j.installation.devis for j in jalons]
        lot = tranches_facturees(devis)
        for d in devis:
            for tranche in TRANCHES:
                self.assertEqual(
                    tranche in lot[d.pk], tranche_facturee(d, tranche),
                    (d.pk, tranche))

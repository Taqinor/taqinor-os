"""APRF11 (C-APRF-025) — ``facturation.selectors.factures_avec_montant_du``
précharge TOUT ce que lit ``Facture.montant_du`` : le reste dû de 30 factures
coûte le même nombre de requêtes que celui de 3, au centime près des valeurs
lues sans préchargement ; les appelants adoptés (encours par tiers, état de
recouvrement d'un client, relevé portail) restent plats aux deux tailles.

Rejoue la sonde V_VB (`_ca_encaisse_ht` 7 → 57 requêtes, +5 par facture).
``CaptureQueriesContext`` à deux tailles, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_aprf11_montant_du_en_lot"
"""
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class MontantDuEnLotTests(TestCase):
    def _societe(self, n_factures):
        from apps.crm.models import Client
        from authentication.models import Company
        k = _nxt()
        company = Company.objects.create(nom=f'APRF11 {k}', slug=f'aprf11-{k}')
        client = Client.objects.create(
            company=company, nom='Client', prenom='APRF11',
            email=f'aprf11-{k}@example.invalid')
        for i in range(n_factures):
            self._facture_complete(company, client, i)
        return company, client

    def _facture_complete(self, company, client, i):
        """Facture avec TOUTES les relations que lit `montant_du`."""
        from apps.ventes.models import (
            AffectationPaiement, Avoir, Facture, LigneAvoir, LigneFacture,
            LigneNoteDebit, NoteDebit, Paiement, RetenueSubie,
        )
        n = _nxt()
        f = Facture.objects.create(
            company=company, reference=f'FAC-APRF11-{n}', client=client,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20'))
        LigneFacture.objects.create(
            facture=f, designation='Ligne', quantite=Decimal('1'),
            prix_unitaire=Decimal('10000'), taux_tva=Decimal('20'))
        p = Paiement.objects.create(
            company=company, facture=f, montant=Decimal('1000'),
            date_paiement=date(2026, 10, 1), mode=Paiement.Mode.VIREMENT)
        avance = Paiement.objects.create(
            company=company, client=client, facture=None,
            statut_affectation=Paiement.StatutAffectation.AFFECTE,
            montant=Decimal('500'), date_paiement=date(2026, 10, 1),
            mode=Paiement.Mode.VIREMENT)
        AffectationPaiement.objects.create(
            company=company, paiement=avance, facture=f,
            montant=Decimal('500'))
        avoir = Avoir.objects.create(
            company=company, reference=f'AVO-APRF11-{n}', facture=f,
            client=client, statut=Avoir.Statut.EMISE, taux_tva=Decimal('20'))
        LigneAvoir.objects.create(
            avoir=avoir, designation='Geste', quantite=Decimal('1'),
            prix_unitaire=Decimal('100'), remise=Decimal('0'))
        nd = NoteDebit.objects.create(
            company=company, reference=f'ND-APRF11-{n}', facture=f,
            client=client, statut=NoteDebit.Statut.EMISE,
            taux_tva=Decimal('20'))
        LigneNoteDebit.objects.create(
            note_debit=nd, designation='Complément', quantite=Decimal('1'),
            prix_unitaire=Decimal('200'), taux_tva=Decimal('20'))
        RetenueSubie.objects.create(
            company=company, facture=f, paiement=p, taux=Decimal('75'),
            base=Decimal('2000'), montant=Decimal('150'))
        if i % 2:
            # Une facture sur deux a des montants FIGÉS (tranche).
            Facture.objects.filter(pk=f.pk).update(
                montant_ht=Decimal('10000'), montant_tva=Decimal('2000'),
                montant_ttc=Decimal('12000'))

    def _lire(self, company):
        from apps.facturation.selectors import factures_avec_montant_du
        from apps.ventes.models import Facture
        with CaptureQueriesContext(connection) as ctx:
            valeurs = [
                (f.pk, f.montant_du, f.montant_paye, f.total_ttc)
                for f in factures_avec_montant_du(
                    Facture.objects.filter(company=company).order_by('pk'))]
        return len(ctx.captured_queries), valeurs

    def test_constant_3_30(self):
        from apps.ventes.models import Facture
        petit, _ = self._societe(3)
        grand, _ = self._societe(30)
        n_petit, _ = self._lire(petit)
        n_grand, valeurs = self._lire(grand)
        self.assertEqual(n_petit, n_grand)
        # Mêmes montants que la lecture SANS préchargement, au centime.
        for pk, du, paye, ttc in valeurs:
            f = Facture.objects.get(pk=pk)
            self.assertEqual((f.montant_du, f.montant_paye, f.total_ttc),
                             (du, paye, ttc))

    def test_appelants_constants(self):
        from apps.ventes.selectors_facturation import (
            encours_clients_par_tiers, etat_recouvrement_client,
            releve_client_portail,
        )

        def _compter(company, client):
            with CaptureQueriesContext(connection) as ctx:
                encours_clients_par_tiers(company)
                etat_recouvrement_client(company, client.id)
                releve_client_portail(client)
            return len(ctx.captured_queries)

        petit = _compter(*self._societe(3))
        grand = _compter(*self._societe(30))
        self.assertEqual(petit, grand)

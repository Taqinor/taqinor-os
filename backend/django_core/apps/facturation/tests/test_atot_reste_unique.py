"""ATOT7 (C-ATOT-005) — `solde_devis.restant` et l'annulation « rembourser /
transférer » lisent la définition unique du payé et du reste
(`Facture.montant_paye`, `montant_du`) : plus d'avoir de révision compté deux
fois, plus de paiement rejeté remboursé.

Rejoue les sondes V1 TFAC-5 (restant 120 000 au lieu de 135 000 après une
révision à la baisse) et TFAC-9 (paiement négatif −45 000 d'un chèque jamais
encaissé). Services et endpoints réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_reste_unique"
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class ResteUniqueTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='ATOT7 Co', slug=f'atot7-co-{_nxt()}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Reste', prenom='ATOT7',
            email=f'atot7-{_nxt()}@example.invalid')
        self.admin = User.objects.create_user(
            username=f'atot7_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        # La ligne produit du devis porte son produit du catalogue
        # (`LigneFacture.produit` est NOT NULL : sans lui, facturer-complet → 500).
        from apps.stock.models import Produit
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit ATOT7', sku=f'ATOT7-{_nxt()}',
            prix_vente=Decimal('125000'), quantite_stock=10)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _devis(self):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ATOT7-{_nxt()}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel')
        self.ligne = LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Centrale PV',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('125000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return devis

    def _complete(self, devis):
        from apps.ventes.models import Facture
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/facturer-complet/',
            {'paiements': []}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return Facture.objects.get(pk=r.data['facture_id'])

    def _solde(self, devis):
        from apps.ventes.models import Devis
        from apps.ventes.utils.echeancier import solde_devis
        return solde_devis(Devis.objects.get(pk=devis.pk))

    def test_restant_revision_baisse(self):
        from apps.ventes.models import Avoir, Facture
        devis = self._devis()
        for _ in range(3):
            r = self.api.post(
                f'/api/django/ventes/devis/{devis.id}/generer-facture/',
                {}, format='json')
            self.assertEqual(r.status_code, 201, r.data)
        solde_facture = Facture.objects.filter(devis=devis).order_by('-id')[0]
        # Révision V2 : 112 500 HT = 135 000 TTC ; avoir de révision 15 000.
        self.ligne.prix_unitaire = Decimal('112500')
        self.ligne.save(update_fields=['prix_unitaire'])
        Avoir.objects.create(
            company=self.company, reference=f'AV-ATOT7-{_nxt()}',
            facture=solde_facture, client=self.client_obj,
            statut=Avoir.Statut.EMISE, taux_tva=Decimal('20.00'),
            montant_ht=Decimal('12500.00'), montant_tva=Decimal('2500.00'),
            montant_ttc=Decimal('15000.00'), motif='Révision V2')
        solde = self._solde(devis)
        self.assertEqual(solde['total_ttc'], Decimal('135000.00'))
        self.assertEqual(solde['restant'], Decimal('135000.00'))

    def test_restant_note_debit_et_ras(self):
        from apps.ventes.models import NoteDebit, RetenueSubie
        devis = self._devis()
        facture = self._complete(devis)
        NoteDebit.objects.create(
            company=self.company, reference=f'ND-ATOT7-{_nxt()}',
            facture=facture, client=self.client_obj,
            statut=NoteDebit.Statut.EMISE, taux_tva=Decimal('20.00'),
            montant_ht=Decimal('1000.00'), montant_tva=Decimal('200.00'),
            montant_ttc=Decimal('1200.00'), motif='Pénalité')
        self.assertEqual(self._solde(devis)['restant'], Decimal('151200.00'))
        RetenueSubie.objects.create(
            company=self.company, facture=facture, taux=Decimal('75.00'),
            base=Decimal('4000.00'), montant=Decimal('3000.00'))
        facture.refresh_from_db()
        solde = self._solde(devis)
        self.assertEqual(solde['restant'], Decimal('148200.00'))
        self.assertEqual(solde['restant'], facture.montant_du)

    def _rejeter(self, facture, montant):
        from apps.ventes.domain.recouvrement import rejeter_paiement
        from apps.ventes.models import Paiement
        paiement = Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal(montant),
            date_paiement=date.today(), mode='cheque')
        rejeter_paiement(paiement=paiement, motif='Chèque impayé',
                         user=self.admin)
        return paiement

    def test_rembourser_ignore_paiement_rejete(self):
        from apps.ventes.models import Facture, Paiement
        facture = self._complete(self._devis())
        self._rejeter(facture, '45000')
        self.api.post(
            f'/api/django/ventes/factures/{facture.id}/annuler/',
            {'acompte': {'action': 'rembourser'}}, format='json')
        facture = Facture.objects.get(pk=facture.pk)
        self.assertFalse(Paiement.objects.filter(
            facture=facture, montant__lt=0).exists())
        self.assertEqual(Decimal(str(facture.montant_paye)), Decimal('0.00'))

    def test_transferer_ignore_paiement_rejete(self):
        from apps.ventes.models import Devis, Facture, Paiement
        devis = self._devis()
        acompte_r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/',
            {}, format='json')
        materiel_r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/',
            {}, format='json')
        acompte = Facture.objects.get(pk=acompte_r.data['id'])
        cible = Facture.objects.get(pk=materiel_r.data['id'])
        rejete = self._rejeter(acompte, '45000')
        bon = Paiement.objects.create(
            company=self.company, facture=acompte, montant=Decimal('10000'),
            date_paiement=date.today(), mode='virement')
        r = self.api.post(
            f'/api/django/ventes/factures/{acompte.id}/annuler/',
            {'acompte': {'action': 'transferer', 'facture_cible': cible.id}},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        rejete.refresh_from_db()
        bon.refresh_from_db()
        self.assertEqual(rejete.facture_id, acompte.id)
        self.assertEqual(bon.facture_id, cible.id)
        cible = Facture.objects.get(pk=cible.pk)
        self.assertEqual(Decimal(str(cible.montant_paye)), Decimal('10000.00'))
        self.assertTrue(Devis.objects.filter(pk=devis.pk).exists())

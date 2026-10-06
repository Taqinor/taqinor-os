"""ASTK26 — une facture fournisseur réglée (paiement / acompte / avoir imputé)
voit ses montants, fournisseur, devise, lien BCF et lignes verrouillés ; toute
édition permise recalcule son statut.

Rejoue FACF-4 (audit stock 06/10/2026) : PATCH montant_ttc 1500 sur une
facture payée → 200, statut « payee » gardé, solde_du=500, absente des
comptes à payer ; PATCH 400 → 200, solde_du=0.

Source réelle : services de recalcul réels (aucun mock).

Run :
    python manage.py test apps.stock.test_astk_facture_verrou -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    FactureFournisseur, Fournisseur, PaiementFournisseur,
)
from apps.stock.services import recompute_facture_fournisseur_statut
from authentication.models import Company

User = get_user_model()

URL = '/api/django/stock/factures-fournisseur/'


class FactureVerrouTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK26', slug='astk26-co')
        self.user = User.objects.create_user(
            username='astk26-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK26', type='service')
        self.autre_fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Autre ASTK26', type='service')
        self.payee = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK26-1',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 9, 1),
            montant_ttc=Decimal('1000'))
        PaiementFournisseur.objects.create(
            company=self.company, facture=self.payee,
            montant=Decimal('1000'), date_paiement=datetime.date(2026, 9, 5))
        recompute_facture_fournisseur_statut(self.payee)
        self.payee.refresh_from_db()
        self.assertEqual(self.payee.statut, FactureFournisseur.Statut.PAYEE)
        self.non_reglee = FactureFournisseur.objects.create(
            company=self.company, reference='FF-ASTK26-2',
            fournisseur=self.fournisseur,
            date_facture=datetime.date(2026, 9, 2),
            montant_ttc=Decimal('500'))

    def _patch(self, facture, body):
        return self.api.patch(f'{URL}{facture.pk}/', body, format='json')

    def test_facture_payee_verrouillee(self):
        for body in ({'montant_ttc': '1500'}, {'montant_ttc': '400'},
                     {'fournisseur': self.autre_fournisseur.pk}):
            rep = self._patch(self.payee, body)
            self.assertEqual(rep.status_code, 400, (body, rep.data))
            self.assertIn('montants verrouillés', str(rep.data))
        # Retirer / poser le lien BCF ne déverrouille rien.
        rep = self._patch(self.payee, {'bon_commande': None})
        self.assertEqual(rep.status_code, 400, rep.data)
        rep = self._patch(self.payee, {'montant_ttc': '1500'})
        self.assertEqual(rep.status_code, 400)
        # Persistance : relue intacte, cohérente avec les comptes à payer.
        self.payee.refresh_from_db()
        self.assertEqual(self.payee.montant_ttc, Decimal('1000'))
        self.assertEqual(self.payee.statut, FactureFournisseur.Statut.PAYEE)
        self.assertEqual(self.payee.solde_du, Decimal('0'))
        self.assertEqual(self.payee.fournisseur_id, self.fournisseur.pk)
        cap = self.api.get(f'{URL}comptes-a-payer/').data['results']
        self.assertNotIn(self.payee.pk, [f['id'] for f in cap])

    def test_champ_non_monetaire_reste_editable(self):
        rep = self._patch(self.payee, {'note': 'archivée',
                                       'montant_ttc': '1000.00'})
        self.assertEqual(rep.status_code, 200, rep.data)
        self.payee.refresh_from_db()
        self.assertEqual(self.payee.note, 'archivée')

    def test_statut_recalcule(self):
        # Non réglée : 700 accepté, solde_du recalculé.
        rep = self._patch(self.non_reglee, {'montant_ttc': '700'})
        self.assertEqual(rep.status_code, 200, rep.data)
        self.non_reglee.refresh_from_db()
        self.assertEqual(self.non_reglee.montant_ttc, Decimal('700'))
        self.assertEqual(self.non_reglee.solde_du, Decimal('700'))
        self.assertEqual(self.non_reglee.statut,
                         FactureFournisseur.Statut.A_PAYER)
        # Statut faux en base (hérité) : une édition permise le recalcule.
        FactureFournisseur.objects.filter(pk=self.non_reglee.pk).update(
            statut=FactureFournisseur.Statut.PAYEE)
        rep = self._patch(self.non_reglee, {'note': 'relance'})
        self.assertEqual(rep.status_code, 200, rep.data)
        self.non_reglee.refresh_from_db()
        self.assertEqual(self.non_reglee.statut,
                         FactureFournisseur.Statut.A_PAYER)
        cap = self.api.get(f'{URL}comptes-a-payer/').data['results']
        ligne = [f for f in cap if f['id'] == self.non_reglee.pk][0]
        self.assertEqual(Decimal(ligne['solde_du']), Decimal('700'))

    def test_patch_devise_reapplique_contre_valeur(self):
        rep = self._patch(self.non_reglee, {
            'devise': 'EUR', 'taux_change': '10.5',
            'montant_ttc_devise': '100'})
        self.assertEqual(rep.status_code, 200, rep.data)
        self.non_reglee.refresh_from_db()
        self.assertEqual(self.non_reglee.montant_ttc, Decimal('1050.00'))
        rep = self._patch(self.non_reglee, {'taux_change': '11'})
        self.assertEqual(rep.status_code, 200, rep.data)
        self.non_reglee.refresh_from_db()
        self.assertEqual(self.non_reglee.montant_ttc, Decimal('1100.00'))

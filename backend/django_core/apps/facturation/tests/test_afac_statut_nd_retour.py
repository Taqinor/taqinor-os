"""AFAC29 (C-AFAC-027) — le statut de paiement est re-dérivé (service unique
d'ATOT8, `recalculer_statut_paiement`) après `creer-note-debit` et
`retour-client` : une note de débit sur une facture payée la rouvre au
recouvrement ; un retour qui solde une facture émise la passe payée.

Rejoue FCOR-4 (payée + ND → reste `payee`, GET `montant_du '0.00'` ; retour
total → `emise`, dû 0). Endpoints réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_statut_nd_retour"
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class StatutNdRetourTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC29 Co', slug=f'afac29-co-{_nxt()}')
        self.admin = User.objects.create_user(
            username=f'afac29_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Statut', prenom='AFAC29',
            email=f'afac29-{_nxt()}@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Complément', sku=f'AFAC29-{_nxt()}',
            prix_vente=Decimal('1000'), quantite_stock=10)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _payer(self, facture, montant):
        from apps.ventes.models import Paiement
        Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal(montant),
            date_paiement=date(2026, 10, 1), mode='virement',
            created_by=self.admin)

    def test_nd_sur_payee_rouvre(self):
        from apps.ventes.models import Facture
        ttc = Decimal('10000')
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC29-{_nxt()}',
            client=self.client_obj, statut='payee', taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc,
            date_echeance=timezone.now().date() - timedelta(days=5))
        self._payer(facture, '10000')
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-note-debit/',
            {'motif': 'Complément', 'lignes': [{
                'produit': self.produit.id, 'designation': 'Complément',
                'quantite': '1', 'prix_unitaire': '1000',
                'taux_tva': '20'}]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        facture.refresh_from_db()
        self.assertIn(facture.statut, ('emise', 'en_retard'))
        lu = self.api.get(f'/api/django/ventes/factures/{facture.id}/')
        self.assertEqual(Decimal(lu.data['montant_du']), Decimal('1200.00'))
        relances = self.api.get('/api/django/ventes/relances/')
        self.assertEqual(relances.status_code, 200)
        self.assertIn(facture.id, [x['id'] for x in relances.data])

    def test_retour_qui_solde_passe_payee(self):
        from core.events import facture_payee
        from apps.ventes.models import Facture, LigneFacture
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC29-{_nxt()}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20'))
        LigneFacture.objects.create(
            facture=facture, produit=self.produit, designation='Complément',
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20'))
        self._payer(facture, '600')
        recus = []

        def _recepteur(sender, instance=None, **kwargs):
            recus.append(instance.pk)

        facture_payee.connect(_recepteur, weak=False)
        try:
            r = self.api.post(
                f'/api/django/ventes/factures/{facture.id}/retour-client/',
                {'motif': 'Retour total', 'restocker': False,
                 'lignes': [{'produit': self.produit.id, 'quantite': 1}]},
                format='json')
        finally:
            facture_payee.disconnect(_recepteur)
        self.assertEqual(r.status_code, 201, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, 'payee')
        self.assertEqual(recus, [facture.id])

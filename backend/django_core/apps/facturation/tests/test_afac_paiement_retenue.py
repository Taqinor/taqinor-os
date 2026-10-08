"""AFAC30 (C-AFAC-028 + C-AFAC-029) — `paiement-avec-retenue` valide son
entrée (400 sous le champ, jamais 500) et calcule la RAS sur son ASSIETTE
fiscale (RAS-TVA = TVA × taux, RAS-IS = HT × taux, moins les RAS déjà
constatées, plafonnée) : le reste non couvert reste DÛ ; la RAS d'un
paiement rejeté ne compte plus.

Rejoue FCOR-5 (retenue 70 000 pour 20 000 de TVA, facture payée), L2-C-AFAC-
028 (RAS-IS 0 % sur 1 MAD → tout le reste en RAS) et FCOR-6 (500 sur entrées
invalides, `zzz` → 201). Endpoints réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_paiement_retenue"
"""
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


class PaiementRetenueTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC30 Co', slug=f'afac30-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac30_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        client = Client.objects.create(
            company=self.company, nom='RAS', prenom='AFAC30',
            email=f'afac30-{_nxt()}@example.invalid')
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC30-{_nxt()}',
            client=client, statut='emise', taux_tva=Decimal('20'),
            montant_ht=Decimal('100000'), montant_tva=Decimal('20000'),
            montant_ttc=Decimal('120000'))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.url = (f'/api/django/ventes/paiements/factures/'
                    f'{self.facture.id}/paiement-avec-retenue/')

    def _corps(self, **extra):
        corps = {'montant': '50000', 'date_paiement': '2026-10-08',
                 'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '75'}
        corps.update(extra)
        return {k: v for k, v in corps.items() if v is not None}

    def _facture(self):
        from apps.ventes.models import Facture
        return Facture.objects.get(pk=self.facture.pk)

    def test_ras_tva_sur_assiette(self):
        from apps.ventes.models import RetenueSubie
        r = self.api.post(self.url, self._corps(), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        retenue = RetenueSubie.objects.get(facture=self.facture)
        self.assertEqual(retenue.montant, Decimal('15000.00'))
        facture = self._facture()
        self.assertEqual(facture.statut, 'emise')
        self.assertEqual(facture.montant_du, Decimal('55000.00'))
        # Rejouer : Σ RAS-TVA reste plafonnée à TVA × taux.
        r2 = self.api.post(self.url, self._corps(montant='10000'),
                           format='json')
        self.assertEqual(r2.status_code, 201, r2.data)
        total = sum(RetenueSubie.objects.filter(
            facture=self.facture).values_list('montant', flat=True))
        self.assertEqual(total, Decimal('15000.00'))

    def test_ras_is_taux_zero(self):
        from apps.ventes.models import RetenueSubie
        r = self.api.post(self.url, self._corps(
            montant='1', type_retenue='ras_is', taux='0'), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            RetenueSubie.objects.get(facture=self.facture).montant,
            Decimal('0.00'))
        facture = self._facture()
        self.assertEqual(facture.montant_du, Decimal('119999.00'))
        self.assertNotEqual(facture.statut, 'payee')

    def test_ras_paiement_rejete_exclue(self):
        from apps.ventes.models import Paiement
        r = self.api.post(self.url, self._corps(), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        paiement = Paiement.objects.get(pk=r.data['paiement']['id'])
        rejet = self.api.post(
            f'/api/django/ventes/paiements/{paiement.id}/rejeter/',
            {'motif': 'Virement rejeté'}, format='json')
        self.assertIn(rejet.status_code, (200, 201), rejet.data)
        facture = self._facture()
        self.assertEqual(facture.retenues_subies_total, Decimal('0'))
        self.assertEqual(facture.montant_du, Decimal('120000.00'))

    def test_entrees_invalides_400(self):
        from apps.ventes.models import Paiement, RetenueSubie
        cas = [
            ('montant', {'montant': 'abc'}),
            ('montant', {'montant': None}),
            ('taux', {'taux': 'abc'}),
            ('date_paiement', {'date_paiement': None}),
            ('type_retenue', {'type_retenue': 'zzz'}),
            ('mode', {'mode': 'zzz'}),
        ]
        for champ, extra in cas:
            r = self.api.post(self.url, self._corps(**extra), format='json')
            self.assertEqual(r.status_code, 400, (champ, r.data))
            self.assertIn(champ, r.data, (champ, r.data))
        self.assertFalse(Paiement.objects.filter(
            facture=self.facture).exists())
        self.assertFalse(RetenueSubie.objects.filter(
            facture=self.facture).exists())

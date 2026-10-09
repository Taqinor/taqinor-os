"""AFAC34 (C-AFAC-030, D-AFAC-C6 option a) — l'abandon de créance est un
ENREGISTREMENT ``AbandonCreance`` cumulatif et réversible (reprise MANUELLE),
sommé dans ``Facture.abandon_montant`` (lu par ``decomposition_du`` /
``montant_du``) ; le plafond d'avoir compte les abandons actifs.

Rejoue la sonde FCOR-7 (abandon 480 écrasé par 720, dû 480 sur une facture
payée ; paiement tardif → 400 « (0.00 MAD) » ; avoir total → 201 sur une
facture abandonnée). Endpoints, services et migration réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_abandon_creance"
"""
import importlib
from decimal import Decimal

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]
BASE = '/api/django/ventes/factures/'


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class AbandonCreanceTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC34 Co', slug=f'afac34-co-{_nxt()}')
        self.admin = User.objects.create_user(
            username=f'afac34_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Abandon', prenom='AFAC34',
            email=f'afac34-{_nxt()}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _facture(self):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC34-{_nxt():04d}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=Decimal('1000'),
            montant_tva=Decimal('200'), montant_ttc=Decimal('1200'))

    def _payer(self, facture, montant):
        return self.api.post(
            f'{BASE}{facture.id}/enregistrer-paiement/',
            {'montant': montant, 'date_paiement': str(timezone.localdate()),
             'mode': 'cheque'}, format='json')

    def _abandonner(self, facture):
        return self.api.post(f'{BASE}{facture.id}/abandonner-solde/',
                             {'motif': 'irrecouvrable'}, format='json')

    def _relire(self, facture):
        from apps.ventes.models import Facture
        return Facture.objects.get(pk=facture.pk)

    def _cheque_puis_abandon(self):
        from apps.ventes.models import Paiement
        f = self._facture()
        self.assertEqual(self._payer(f, '720').status_code, 201)
        r = self._abandonner(f)
        self.assertEqual(r.status_code, 200, r.data)
        return f, Paiement.objects.get(facture=f)

    def test_second_abandon_cumule(self):
        from apps.ventes.models import AbandonCreance, Facture
        f, cheque = self._cheque_puis_abandon()
        r = self.api.post(
            f'/api/django/ventes/paiements/{cheque.id}/rejeter/',
            {'motif': 'Chèque impayé'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._relire(f).montant_du, Decimal('720.00'))
        self.assertEqual(self._abandonner(f).status_code, 200)
        # CLAUSE PERSISTANCE : deux enregistrements actifs, Σ = 1 200.
        actifs = AbandonCreance.objects.filter(
            facture=f, annule_le__isnull=True).order_by('id')
        self.assertEqual([a.montant for a in actifs],
                         [Decimal('480.00'), Decimal('720.00')])
        relue = self._relire(f)
        self.assertEqual(relue.abandon_montant, Decimal('1200.00'))
        self.assertEqual(relue.montant_du, Decimal('0'))
        self.assertEqual(relue.statut, Facture.Statut.PAYEE)

    def test_reprise_puis_paiement_tardif(self):
        from apps.ventes.models import AbandonCreance, Facture
        f, _cheque = self._cheque_puis_abandon()
        self.assertEqual(self._relire(f).statut, Facture.Statut.PAYEE)
        # Sans reprise : un paiement tardif dépasse le reste (0.00).
        self.assertEqual(self._payer(f, '480').status_code, 400)
        r = self.api.post(f'{BASE}{f.id}/reprendre-abandon/',
                          {'motif': 'Le client a finalement payé'},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        abandon = AbandonCreance.objects.get(facture=f)
        self.assertIsNotNone(abandon.annule_le)
        relue = self._relire(f)
        self.assertEqual(relue.montant_du, Decimal('480.00'))
        self.assertIn(relue.statut,
                      (Facture.Statut.EMISE, Facture.Statut.EN_RETARD))
        self.assertEqual(self._payer(f, '480').status_code, 201)
        relue = self._relire(f)
        self.assertEqual(relue.montant_du, Decimal('0'))
        self.assertEqual(relue.statut, Facture.Statut.PAYEE)

    def test_reprise_sans_motif_refusee(self):
        f, _cheque = self._cheque_puis_abandon()
        r = self.api.post(f'{BASE}{f.id}/reprendre-abandon/', {},
                          format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_plafond_avoir_compte_abandons(self):
        from apps.ventes.models import Avoir
        f = self._facture()
        self.assertEqual(self._abandonner(f).status_code, 200)
        r = self.api.post(f'{BASE}{f.id}/creer-avoir/',
                          {'motif': 'Avoir total'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn("L'avoir dépasse le montant restant", r.data['detail'])
        self.assertFalse(Avoir.objects.filter(facture=f).exists())

    def test_migration_recopie_abandons_existants(self):
        from apps.ventes.models import AbandonCreance
        f = self._facture()
        type(f).objects.filter(pk=f.pk).update(
            abandon_montant=Decimal('300.00'), abandon_motif='liquidation',
            abandon_auto=False, abandon_par=self.admin,
            abandon_date=timezone.now())
        migration = importlib.import_module(
            'apps.ventes.migrations.0136_afac34_abandon_creance')
        migration.recopier_abandons(django_apps, None)
        enreg = AbandonCreance.objects.get(facture=f)
        self.assertEqual(enreg.montant, Decimal('300.00'))
        self.assertEqual(enreg.motif, 'liquidation')
        self.assertEqual(enreg.created_by_id, self.admin.id)
        self.assertIsNone(enreg.annule_le)

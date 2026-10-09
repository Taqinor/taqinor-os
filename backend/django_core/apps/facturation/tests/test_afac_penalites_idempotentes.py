"""AFAC50 (C-AFAC-040 a) — ``facturer-penalites`` est idempotent par
(facture d'origine, niveau) : liaison durable ``FacturePenalite`` (contrainte
d'unicité) + verrou sur la facture d'origine. Un second appel répond 409 sans
créer ni numéroter de facture ; une facture de pénalités ANNULÉE libère le
niveau ; un niveau supérieur ouvre une nouvelle facture.

Rejoue la sonde FREC-8 (deux POST ⇒ 201 + 201, deux factures émises de
1 415,07). APIClient, émission réelle via ``emettre_facture``, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_penalites_idempotentes"
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class PenalitesIdempotentesTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture, FollowupLevel
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'AFAC50 {n}', slug=f'afac50-{n}')
        self.admin = User.objects.create_user(
            username=f'afac50-admin-{n}', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Pénalités', prenom='AFAC50',
            email=f'afac50-{n}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        today = timezone.now().date()
        self.facture = Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC50-{n:04d}',
            client=self.client_obj, statut=Facture.Statut.EN_RETARD,
            montant_ht=Decimal('83333.33'), montant_tva=Decimal('16666.67'),
            montant_ttc=Decimal('100000'), created_by=self.admin,
            date_echeance=today - timedelta(days=35))
        self.n1 = FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Mise en demeure',
            delai_jours=30, taux_interet_annuel=Decimal('12.00'),
            frais_fixes=Decimal('100.00'))

    def _post(self):
        return self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            'facturer-penalites/', {}, format='json')

    def _penalites(self):
        from apps.ventes.models import Facture
        return Facture.objects.filter(
            company=self.company, libelle__startswith='Pénalités de retard')

    def test_second_appel_409(self):
        from apps.ventes.models import FacturePenalite, FactureActivity
        r1 = self._post()
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self._post()
        self.assertEqual(r2.status_code, 409, r2.data)
        self.assertIn(r1.data['reference'], r2.data['detail'])
        # CLAUSE PERSISTANCE : une seule facture, une liaison, une entrée.
        self.assertEqual(self._penalites().count(), 1)
        self.assertEqual(FacturePenalite.objects.filter(
            facture_origine=self.facture).count(), 1)
        self.assertEqual(FactureActivity.objects.filter(
            facture=self.facture, field='penalite').count(), 1)

    def test_appels_concurrents_une_seule_facture(self):
        """Filet de la course : la contrainte d'unicité (facture, niveau)
        refuse une seconde liaison, même si deux requêtes passaient le
        contrôle d'existence en même temps."""
        from apps.ventes.models import FacturePenalite
        r1 = self._post()
        self.assertEqual(r1.status_code, 201, r1.data)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FacturePenalite.objects.create(
                company=self.company, facture_origine=self.facture,
                niveau=self.n1.ordre, facture_penalite_id=r1.data['id'])
        self.assertEqual(self._penalites().count(), 1)

    def test_refacturation_apres_annulation(self):
        from apps.ventes.models import Facture, FacturePenalite
        r1 = self._post()
        self.assertEqual(r1.status_code, 201, r1.data)
        Facture.objects.filter(pk=r1.data['id']).update(
            statut=Facture.Statut.ANNULEE)
        r2 = self._post()
        self.assertEqual(r2.status_code, 201, r2.data)
        liaison = FacturePenalite.objects.get(facture_origine=self.facture)
        self.assertEqual(liaison.facture_penalite_id, r2.data['id'])

    def test_niveau_superieur_nouvelle_facture(self):
        from apps.ventes.models import FacturePenalite, FollowupLevel
        self.assertEqual(self._post().status_code, 201)
        FollowupLevel.objects.create(
            company=self.company, ordre=2, nom='Contentieux',
            delai_jours=31, taux_interet_annuel=Decimal('12.00'),
            frais_fixes=Decimal('200.00'))
        r = self._post()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self._penalites().count(), 2)
        self.assertEqual(sorted(FacturePenalite.objects.filter(
            facture_origine=self.facture).values_list('niveau', flat=True)),
            [1, 2])

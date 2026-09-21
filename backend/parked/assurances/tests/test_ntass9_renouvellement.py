"""NTASS9 — Renouvellement de police (versioning léger).

Critère d'acceptation : renouveler une police DÉCENNALE clone garanties+actifs
et démarre un échéancier propre, l'ancienne reste consultable en lecture
seule."""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.assurances.models import (
    ActifCouvert, EcheancePrime, GarantiePolice, Assureur, PoliceAssurance,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RenouvellementPoliceTests(TestCase):
    def setUp(self):
        self.company = make_company('assurances-p9', 'P9')
        self.user = make_user(self.company, 'assur-p9')
        self.assureur = Assureur.objects.create(
            company=self.company, raison_sociale='Saham Assurance')
        self.police = PoliceAssurance.objects.create(
            company=self.company, assureur=self.assureur,
            numero_police='DEC-2026-060',
            type_police=PoliceAssurance.TypePolice.DECENNALE,
            date_effet=datetime.date(2026, 1, 1),
            date_echeance=datetime.date(2027, 1, 1),
            prime_annuelle_ht=Decimal('12000.00'),
            tacite_reconduction=False)
        GarantiePolice.objects.create(
            company=self.company, police=self.police,
            libelle_garantie='Dommages aux tiers',
            plafond_indemnisation=Decimal('1000000.00'))
        GarantiePolice.objects.create(
            company=self.company, police=self.police,
            libelle_garantie='Effondrement',
            plafond_indemnisation=Decimal('500000.00'))
        ActifCouvert.objects.create(
            company=self.company, police=self.police,
            type_actif=ActifCouvert.TypeActif.SITE, actif_libelle='Siège social')

    def test_renouveler_clone_garanties_actifs_et_echeancier(self):
        api = auth(self.user)
        resp = api.post(
            f'/api/django/assurances/polices/{self.police.id}/renouveler/')
        self.assertEqual(resp.status_code, 201, resp.data)
        nouvelle_id = resp.data['id']
        nouvelle = PoliceAssurance.objects.get(id=nouvelle_id)

        self.assertEqual(nouvelle.date_effet, datetime.date(2027, 1, 2))
        self.assertEqual(nouvelle.date_echeance, datetime.date(2028, 1, 2))
        self.assertEqual(nouvelle.police_precedente_id, self.police.id)
        self.assertEqual(
            GarantiePolice.objects.filter(police=nouvelle).count(), 2)
        self.assertEqual(
            ActifCouvert.objects.filter(police=nouvelle).count(), 1)
        self.assertEqual(
            EcheancePrime.objects.filter(police=nouvelle).count(), 1)

        # L'ancienne police reste consultable en lecture seule, résiliée.
        self.police.refresh_from_db()
        self.assertEqual(self.police.statut, PoliceAssurance.Statut.RESILIEE)
        resp = api.get(f'/api/django/assurances/polices/{self.police.id}/')
        self.assertEqual(resp.status_code, 200)

    def test_tacite_reconduction_refuse_le_renouvellement(self):
        self.police.tacite_reconduction = True
        self.police.save(update_fields=['tacite_reconduction'])
        api = auth(self.user)
        resp = api.post(
            f'/api/django/assurances/polices/{self.police.id}/renouveler/')
        self.assertEqual(resp.status_code, 400)

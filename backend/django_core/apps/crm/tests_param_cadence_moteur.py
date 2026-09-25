"""PARAM-CADENCE — le moteur lit la chaîne de la société dans Paramètres.

Décision fondateur du 25/09/2026 : « cette cadence doit être dans Paramètres,
pour qu'une autre société ou nous puissions tout y changer ». Côté GABARIT :
``apps/parametres/tests_param_cadence_cle.py``. Ici, côté MOTEUR.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead
from apps.parametres.models_relance import CADENCES_MOTEUR

User = get_user_model()


class JamaisUnPlanTests(TestCase):
    """« Après l'appel » et « Visite technique » sont les gabarits des étapes
    que le moteur pose — jamais un plan qu'on démarre sur un lead."""

    def test_le_demarrage_d_une_cadence_moteur_est_refuse(self):
        company = Company.objects.create(nom='PCAD Plan', slug='pcad-plan')
        responsable = User.objects.create_user(
            username='pcad-plan-resp', password='pw',
            role_legacy='responsable', company=company)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(responsable)}')
        lead = Lead.objects.create(company=company, nom='Plan',
                                   owner=responsable)
        for cadence in CADENCES_MOTEUR:
            resp = api.post(
                f'/api/django/crm/leads/{lead.pk}/relance/initialiser/',
                {'cadence': cadence}, format='json')
            self.assertEqual(resp.status_code, 400, resp.data)
            self.assertIn('cadence', resp.data)
        self.assertFalse(lead.relance_etapes.exists())

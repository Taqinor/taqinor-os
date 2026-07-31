"""NTUX13 — Duplication d'un ChecklistTemplate
(POST checklist-templates/<id>/dupliquer/).

Le duplicata (en-tête + étapes) est TOUJOURS non protégé et sans
`type_installation` auto-sélectionné, même si la source l'était/l'avait —
seul le template « Défaut » système reste protégé/unique par ce type.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.installations.models import ChecklistEtapeModele, ChecklistTemplate
from apps.installations.services import dupliquer_checklist_template

User = get_user_model()


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDupliquerChecklistTemplate(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='ntux13-cht-co', defaults={'nom': 'NTUX13 Checklist Co'})[0]
        self.admin = User.objects.create_user(
            username='ntux13_cht_admin', password='x', role_legacy='admin',
            company=self.co)
        self.source = ChecklistTemplate.objects.create(
            company=self.co, nom='Résidentiel', type_installation='residentiel',
            ordre=1, actif=True, protege=False)
        ChecklistEtapeModele.objects.create(
            company=self.co, template=self.source, cle='pose',
            libelle='Pose', ordre=1, capture_serie=True)
        ChecklistEtapeModele.objects.create(
            company=self.co, template=self.source, cle='mes',
            libelle='Mise en service', ordre=2)

    def test_service_copies_header_and_etapes(self):
        copie = dupliquer_checklist_template(self.source, user=self.admin)
        self.assertNotEqual(copie.pk, self.source.pk)
        self.assertEqual(copie.nom, 'Résidentiel (copie)')
        self.assertIsNone(copie.type_installation)
        self.assertFalse(copie.protege)
        self.assertEqual(copie.etapes.count(), 2)
        cles = set(copie.etapes.values_list('cle', flat=True))
        self.assertEqual(cles, {'pose', 'mes'})
        # Étapes de la copie sont bien des lignes DISTINCTES de la source.
        self.assertEqual(
            self.source.etapes.count(), 2,
            'la duplication ne doit jamais toucher les étapes de la source')

    def test_duplicating_protected_default_is_never_protected(self):
        self.source.protege = True
        self.source.save(update_fields=['protege'])
        copie = dupliquer_checklist_template(self.source, user=self.admin)
        self.assertFalse(copie.protege)

    def test_endpoint_dupliquer(self):
        api = _auth(self.admin)
        resp = api.post(
            f'/api/django/installations/checklist-templates/{self.source.pk}/dupliquer/')
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(data['nom'], 'Résidentiel (copie)')
        self.assertEqual(len(data['etapes']), 2)

"""AUD817 — ``/core/corbeille/{id}/restaurer/`` était ouvert à TOUT utilisateur
authentifié, y compris un rôle strictement en lecture.

Constat d'origine : ``TrashViewSet.permission_classes = [IsAuthenticated]``
sans ``get_permissions``, donc l'``@action restaurer`` héritait de la garde
générique de la classe au lieu du patron ``declared_action_permissions``
(``core/permissions.py``) déjà disponible dans le dépôt. Un compte lecture
seule pouvait ainsi remettre en circulation un enregistrement que la direction
avait volontairement supprimé.

Après correctif : l'action déclare ``IsResponsableOrAdmin`` et la vue honore
cette déclaration ; la LISTE reste 200 pour tout utilisateur authentifié.
"""
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from apps.roles.models import Role
from core.models import DeletionRecord
from core.views import TrashViewSet

User = get_user_model()


class Aud817CorbeilleRestaurerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AUD817 SARL')
        # Rôle STRICTEMENT lecture (que des permissions ``*_voir``) : c'est
        # exactement le profil qui obtenait 200 sur ``restaurer/``.
        cls.role_viewer = Role.objects.create(
            company=cls.company, nom='Lecture seule AUD817',
            permissions=['crm_voir', 'ventes_voir'])
        cls.viewer = User.objects.create_user(
            username='aud817_viewer', password='x', company=cls.company,
            role=cls.role_viewer)
        cls.responsable = User.objects.create_user(
            username='aud817_resp', password='x', company=cls.company,
            role_legacy='responsable')
        cls.factory = APIRequestFactory()

    def setUp(self):
        # Entrée de corbeille GÉNÉRIQUE : le content_type pointe un modèle sans
        # méthode ``restore`` — ``core.trash.restaurer`` ferme alors l'entrée
        # proprement. Ce test porte sur la GARDE, pas sur la restauration.
        self.record = DeletionRecord.objects.create(
            company=self.company,
            content_type=ContentType.objects.get_for_model(Company),
            object_id=self.company.pk,
            label='Objet supprimé AUD817',
        )

    def _restaurer(self, acteur):
        req = self.factory.post(f'/corbeille/{self.record.pk}/restaurer/')
        force_authenticate(req, user=acteur)
        return TrashViewSet.as_view(
            {'post': 'restaurer'})(req, pk=self.record.pk)

    def test_viewer_lecture_seule_ne_restaure_plus(self):
        resp = self._restaurer(self.viewer)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.record.refresh_from_db()
        self.assertIsNone(self.record.restored_at)

    def test_responsable_restaure_toujours(self):
        resp = self._restaurer(self.responsable)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_liste_reste_ouverte_au_viewer(self):
        req = self.factory.get('/corbeille/')
        force_authenticate(req, user=self.viewer)
        resp = TrashViewSet.as_view({'get': 'list'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

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
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core.models import DeletionRecord
from core.views import TrashViewSet

Role = django_apps.get_model('roles', 'Role')

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

    def test_restauration_exige_ux_corbeille_restaurer(self):
        """APFS42 (C-APFS-041) — même garde que la corbeille transverse : palier
        + ``ux_corbeille_restaurer`` ; un lead réellement soft-supprimé reste
        supprimé après chaque 403 ; le record d'une autre société : 404."""
        from django.core.management import call_command
        Lead = django_apps.get_model('crm', 'Lead')  # core n'importe aucune app
        call_command('init_roles', verbosity=0)
        roles = {r.nom: r for r in Role.objects.filter(company=self.company)}
        lead = Lead.objects.create(company=self.company, nom='Lead APFS42')

        def restaurer(nom):
            lead.refresh_from_db()
            lead.soft_delete()
            record = DeletionRecord.objects.filter(
                object_id=lead.pk, restored_at__isnull=True).latest('pk')
            user = User.objects.create_user(
                username=f'apfs42_{nom.replace(" ", "_").lower()}', password='x',
                company=self.company, role=roles[nom])
            req = self.factory.post(f'/corbeille/{record.pk}/restaurer/')
            force_authenticate(req, user=user)
            return TrashViewSet.as_view({'post': 'restaurer'})(req, pk=record.pk)
        for nom in ('Admin RH', 'Technicien', 'Commercial terrain', 'Commercial',
                    'Admin Ventes', 'Viewer'):
            with self.subTest(role=nom):
                self.assertEqual(restaurer(nom).status_code, status.HTTP_403_FORBIDDEN)
                self.assertTrue(Lead.all_objects.get(pk=lead.pk).is_deleted)
        for nom in ('Directeur', 'Administrateur', 'Commercial responsable'):
            with self.subTest(role=nom):
                resp = restaurer(nom)
                self.assertEqual(resp.status_code, status.HTTP_200_OK)
                self.assertTrue(resp.data['restored'])
        autre = Company.objects.create(nom='AUD817 Autre')
        record_b = DeletionRecord.objects.create(
            company=autre, content_type=ContentType.objects.get_for_model(Company),
            object_id=autre.pk, label='B')
        req = self.factory.post(f'/corbeille/{record_b.pk}/restaurer/')
        force_authenticate(req, user=self.responsable)
        resp = TrashViewSet.as_view({'post': 'restaurer'})(req, pk=record_b.pk)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_annuler_ferme_aussi_l_entree_de_la_corbeille_commune(self):
        """ASUP15 (C-ASUP-011) — « Annuler » (core.trash.restaurer) ferme aussi
        l'entrée de /parametres/corbeille ; la purge retire les DeletionRecord
        de plus de 30 jours, restaurés ou non. Mutant : ne pas s'abonner ⇒
        l'entrée commune reste ouverte."""
        from datetime import timedelta

        from django.utils import timezone

        from core.trash import purger_deletion_records, restaurer
        Lead = django_apps.get_model('crm', 'Lead')  # core n'importe aucune app
        ElementSupprime = django_apps.get_model('trash', 'ElementSupprime')
        lead = Lead.objects.create(company=self.company, nom='Lead ASUP15')
        lead.soft_delete(user=self.responsable)
        entree = ElementSupprime.objects.get(object_id=lead.pk, restaure_le__isnull=True)
        ct = ContentType.objects.get_for_model(Company)
        il_y_a_31j = timezone.now() - timedelta(days=31)
        vieux = [DeletionRecord.objects.create(company=self.company, content_type=ct,
                                               object_id=self.company.pk, label=f'vieux {i}') for i in range(2)]
        DeletionRecord.objects.filter(pk=vieux[0].pk).update(created_at=il_y_a_31j, restored_at=il_y_a_31j)
        DeletionRecord.objects.filter(pk=vieux[1].pk).update(created_at=il_y_a_31j)
        restaurer(DeletionRecord.objects.get(object_id=lead.pk, content_type__model='lead'))
        entree.refresh_from_db()
        self.assertIsNotNone(entree.restaure_le)
        self.assertEqual(purger_deletion_records(), 2)
        self.assertFalse(DeletionRecord.objects.filter(pk__in=[v.pk for v in vieux]).exists())
        self.assertTrue(DeletionRecord.objects.filter(object_id=lead.pk, content_type__model='lead').exists())
        self.assertFalse(Lead.all_objects.get(pk=lead.pk).is_deleted)

    def test_liste_reste_ouverte_au_viewer(self):
        req = self.factory.get('/corbeille/')
        force_authenticate(req, user=self.viewer)
        resp = TrashViewSet.as_view({'get': 'list'})(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

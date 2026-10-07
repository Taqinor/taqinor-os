"""ALEA13 — ``supprimer_photo`` supprime aussi la pièce jointe et le fichier.

Rejoue la sonde V4 LVIS-9 : après DELETE, l'``Attachment`` restait sur le
lead (photo fantôme dans le panneau pièces jointes). Le stockage est le
backend de test configuré du projet (MinIO en CI), jamais un mock de
``records``.
"""
from django.contrib.contenttypes.models import ContentType

from apps.records.models import Attachment
from apps.records.storage import fetch_attachment
from apps.visites import services
from apps.visites.models import VisiteMedia, VisiteTerrain
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase


class PhotoSupprimeeTests(VisiteTerrainBase):
    def _pieces_du_lead(self):
        ct = ContentType.objects.get(app_label='crm', model='lead')
        return Attachment.objects.filter(content_type=ct,
                                         object_id=self.lead.id)

    def _photo(self, visite_id):
        resp = self.poster_photo(visite_id, 'general_facade')
        self.assertEqual(resp.status_code, 200, resp.data)
        return VisiteMedia.objects.filter(visite_id=visite_id).latest('id')

    def test_delete_supprime_attachment(self):
        visite_id = self.creer_visite()
        media = self._photo(visite_id)
        attachment_id = media.attachment_id
        cle = media.attachment.file_key
        self.assertTrue(self._pieces_du_lead().filter(
            pk=attachment_id).exists())

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.api.delete(
                f'/api/django/visites/visites/{visite_id}/photos/{media.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(VisiteMedia.objects.filter(pk=media.id).exists())
        self.assertFalse(Attachment.objects.filter(pk=attachment_id).exists())
        self.assertFalse(self._pieces_du_lead().exists())
        # L'objet de stockage a été effacé par le service de records.
        donnees, message = fetch_attachment(cle)
        self.assertIsNone(donnees)
        self.assertTrue(message)
        # Persistance : la visite rouverte ne liste plus la photo.
        detail = self.api.get(f'/api/django/visites/visites/{visite_id}/')
        ids = [photo['id'] for cat in detail.data['checklist']
               for slot in cat['slots'] for photo in slot['photos']]
        self.assertNotIn(media.id, ids)

    def test_delete_visite_validee_toujours_refuse(self):
        visite_id = self.creer_visite()
        media = self._photo(visite_id)
        VisiteTerrain.objects.filter(pk=visite_id).update(
            statut=VisiteTerrain.Statut.VALIDEE)
        resp = self.api.delete(
            f'/api/django/visites/visites/{visite_id}/photos/{media.id}/')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertTrue(VisiteMedia.objects.filter(pk=media.id).exists())
        self.assertTrue(
            Attachment.objects.filter(pk=media.attachment_id).exists())

    def test_photo_remplacee_ne_garde_pas_sa_piece_jointe(self):
        """Décision ALEA13 : la photo remplacée (ALEA12) perd sa pièce
        jointe, comme une photo supprimée."""
        visite_id = self.creer_visite()
        media = self._photo(visite_id)
        media.a_refaire = True
        media.save(update_fields=['a_refaire'])
        attachment_id = media.attachment_id
        nouvelle = self._photo(visite_id)
        self.assertNotEqual(nouvelle.id, media.id)
        self.assertFalse(VisiteMedia.objects.filter(pk=media.id).exists())
        self.assertFalse(Attachment.objects.filter(pk=attachment_id).exists())
        self.assertTrue(
            Attachment.objects.filter(pk=nouvelle.attachment_id).exists())

    def test_service_unique_de_suppression(self):
        visite_id = self.creer_visite()
        media = self._photo(visite_id)
        attachment_id = media.attachment_id
        services.supprimer_media(media)
        self.assertFalse(Attachment.objects.filter(pk=attachment_id).exists())

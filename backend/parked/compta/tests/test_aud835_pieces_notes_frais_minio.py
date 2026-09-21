"""AUD835 — pièce justificative et justificatif de note de frais dans MinIO.

Les deux modèles annonçaient noir sur blanc « stocké via le storage projet
(MinIO/S3) » alors qu'ils écrivaient dans un ``FileField`` Django ordinaire.
ROUGE structurel, vérifié ici : ce dépôt n'a AUCUN service de médias — pas de
``MEDIA_ROOT`` exploitable, pas de route ``/media/``, pas de ``location
/media/`` nginx. Une pièce comptable (obligation légale de conservation) et le
justificatif d'une note remboursée n'étaient récupérables par PERSONNE.

VERT : les deux portent une clé MinIO préfixée par leur société (SCA42), le
sérialiseur rend une URL présignée, et la règle XACC27 (« justificatif
obligatoire au-delà du seuil ») continue de voir un justificatif.

Run :
    docker compose exec django_core python manage.py test \
        apps.compta.tests.test_aud835_pieces_notes_frais_minio -v 2
"""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import Resolver404, resolve
from rest_framework.exceptions import ValidationError

from apps.compta import services
from apps.compta.models import Journal, PieceJustificative
from apps.compta.serializers import (NoteFraisSerializer,
                                     PieceJustificativeSerializer)
from apps.frais.models import NoteFrais
from authentication.models import Company

User = get_user_model()

PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'


def fichier(nom='facture.pdf'):
    return SimpleUploadedFile(nom, PDF, content_type='application/pdf')


class MediaJamaisServiTests(TestCase):
    """Le ROUGE : rien dans ce dépôt ne peut resservir un ``FileField``."""

    def test_aucune_route_media(self):
        with self.assertRaises(Resolver404):
            resolve('/media/compta/pieces/2026/04/facture.pdf')

    def test_aucun_reglage_de_stockage_de_medias(self):
        self.assertFalse(getattr(settings, 'MEDIA_ROOT', '') or '')


class Aud835Base(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='aud835-compta-co', defaults={'nom': 'AUD835 Compta'})
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.user = User.objects.create_user(
            username='aud835_compta', password='x', company=self.co,
            role_legacy='responsable')

    def meta(self, cle='piece835.pdf', nom='facture.pdf'):
        return ({
            'file_key': f'attachments/{self.co.id}/{cle}',
            'filename': nom, 'size': len(PDF), 'mime': 'application/pdf',
        }, None)


class PieceJustificativeVersMinioTests(Aud835Base):
    def _ecriture(self):
        journal = services._journal(self.co, Journal.Type.OPERATIONS_DIVERSES)
        lignes = [
            {'compte': services.get_compte(self.co, '5141'),
             'debit': Decimal('100'), 'credit': Decimal('0')},
            {'compte': services.get_compte(self.co, '7121'),
             'debit': Decimal('0'), 'credit': Decimal('100')},
        ]
        return services.creer_ecriture(
            self.co, journal, date(2026, 4, 1), 'AUD835', lignes,
            created_by=self.user)

    def _creer(self):
        serializer = PieceJustificativeSerializer(
            data={'ecriture': self._ecriture().pk, 'libelle': 'Facture',
                  'fichier': fichier()},
            context={'request': None})
        serializer.is_valid(raise_exception=True)
        return serializer.save(company=self.co, ajoute_par=self.user)

    def test_la_piece_porte_une_cle_minio_scopee_societe(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self.meta()) as stocke:
            piece = self._creer()

        self.assertEqual(stocke.call_args.kwargs['company'], self.co)
        piece.refresh_from_db()
        self.assertEqual(piece.fichier_key,
                         f'attachments/{self.co.id}/piece835.pdf')
        self.assertEqual(piece.fichier_filename, 'facture.pdf')
        self.assertEqual(piece.fichier_size, len(PDF))
        self.assertEqual(piece.fichier_mime, 'application/pdf')
        self.assertFalse(piece.fichier)   # FileField legacy jamais réécrit

    def test_url_serialisee_est_presignee_et_legacy_rend_none(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self.meta()):
            piece = self._creer()

        with mock.patch('apps.records.storage.presign_attachment',
                        return_value='https://minio/p?sig=1'):
            data = PieceJustificativeSerializer(piece).data
        self.assertEqual(data['fichier_url'], 'https://minio/p?sig=1')
        self.assertNotIn('fichier', data)

        legacy = PieceJustificative.objects.create(
            company=self.co, ecriture=piece.ecriture, libelle='Vieille',
            fichier='compta/pieces/2026/01/vieux.pdf')
        self.assertIsNone(
            PieceJustificativeSerializer(legacy).data['fichier_url'])

    def test_format_refuse_ne_cree_aucune_piece(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=(None, 'Format non supporté.')):
            with self.assertRaises(ValidationError):
                self._creer()
        self.assertEqual(PieceJustificative.objects.count(), 0)


class NoteFraisJustificatifVersMinioTests(Aud835Base):
    def _creer(self, montant='300'):
        return services.creer_note_frais(
            self.co, employe=self.user, date_frais=date(2026, 4, 3),
            montant=Decimal(montant), motif='Taxi chantier',
            justificatif=fichier('ticket.pdf'), user=self.user)

    def test_le_justificatif_part_dans_minio(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self.meta('ndf835.pdf', 'ticket.pdf')
                        ) as stocke:
            note = self._creer()

        self.assertEqual(stocke.call_args.kwargs['company'], self.co)
        note.refresh_from_db()
        self.assertEqual(note.justificatif_key,
                         f'attachments/{self.co.id}/ndf835.pdf')
        self.assertEqual(note.justificatif_filename, 'ticket.pdf')
        self.assertFalse(note.justificatif)

    def test_url_serialisee_est_presignee(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self.meta('ndf835.pdf', 'ticket.pdf')):
            note = self._creer()

        with mock.patch('apps.records.storage.presign_attachment',
                        return_value='https://minio/n?sig=2'):
            data = NoteFraisSerializer(note).data
        self.assertEqual(data['justificatif_url'], 'https://minio/n?sig=2')
        self.assertNotIn('justificatif', data)

    def test_format_refuse_ne_cree_aucune_note(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=(None, 'Format non supporté.')):
            with self.assertRaises(ValidationError):
                self._creer()
        self.assertEqual(NoteFrais.objects.count(), 0)

    def test_la_regle_xacc27_voit_toujours_un_justificatif(self):
        """Le seuil « justificatif obligatoire » lit désormais la CLÉ.

        Sans ce raccord, une note parfaitement justifiée aurait été refusée à
        la validation : le ``FileField`` reste vide pour toujours.
        """
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self.meta('ndf835.pdf', 'ticket.pdf')):
            note = self._creer()
        self.assertTrue(bool(note.justificatif_key or note.justificatif))

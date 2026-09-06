"""AUD835 — le PDF constructeur d'une fiche technique va dans MinIO.

ROUGE structurel : aucun ``MEDIA_ROOT`` exploitable, aucune route ``/media/``,
aucune ``location /media/`` nginx — le PDF déposé dans le ``FileField``
n'était téléchargeable par personne. VERT : clé MinIO préfixée par la société
+ URL présignée ; une fiche antérieure à la bascule rend ``None``.

Run :
    docker compose exec django_core python manage.py test \
        apps.stock.test_aud835_fiche_technique_minio -v 2
"""
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import Resolver404, resolve
from rest_framework.exceptions import ValidationError

from apps.stock.models import FicheTechnique, Produit
from apps.stock.serializers import FicheTechniqueSerializer
from authentication.models import Company

PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'


class MediaJamaisServiTests(TestCase):
    def test_aucune_route_media(self):
        with self.assertRaises(Resolver404):
            resolve('/media/stock/fiches_techniques/2026/04/fiche.pdf')

    def test_aucun_reglage_de_stockage_de_medias(self):
        self.assertFalse(getattr(settings, 'MEDIA_ROOT', '') or '')


class FicheTechniquePdfVersMinioTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='aud835-stock-co', defaults={'nom': 'AUD835 Stock'})[0]
        self.produit = Produit.objects.create(
            company=self.co, nom='Module 550 Wc', sku='MOD550',
            prix_achat=Decimal('600'), prix_vente=Decimal('900'),
            quantite_stock=1)

    def _meta(self):
        return ({
            'file_key': f'attachments/{self.co.id}/fiche835.pdf',
            'filename': 'fiche.pdf', 'size': len(PDF),
            'mime': 'application/pdf',
        }, None)

    def _creer(self):
        serializer = FicheTechniqueSerializer(data={
            'produit': self.produit.pk,
            'pdf': SimpleUploadedFile('fiche.pdf', PDF, 'application/pdf'),
        })
        serializer.is_valid(raise_exception=True)
        return serializer.save(company=self.co)

    def test_le_pdf_porte_une_cle_minio_scopee_societe(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self._meta()) as stocke:
            fiche = self._creer()

        self.assertEqual(stocke.call_args.kwargs['company'], self.co)
        fiche.refresh_from_db()
        self.assertEqual(fiche.pdf_key,
                         f'attachments/{self.co.id}/fiche835.pdf')
        self.assertEqual(fiche.pdf_filename, 'fiche.pdf')
        self.assertEqual(fiche.pdf_size, len(PDF))
        self.assertEqual(fiche.pdf_mime, 'application/pdf')
        self.assertFalse(fiche.pdf)

    def test_url_presignee_et_fiche_historique_sans_cle(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self._meta()):
            fiche = self._creer()

        with mock.patch('apps.records.storage.presign_attachment',
                        return_value='https://minio/f?sig=3'):
            data = FicheTechniqueSerializer(fiche).data
        self.assertEqual(data['pdf_url'], 'https://minio/f?sig=3')
        self.assertNotIn('pdf', data)

        autre = Produit.objects.create(
            company=self.co, nom='Onduleur 5 kW', sku='OND5',
            prix_achat=Decimal('600'), prix_vente=Decimal('900'),
            quantite_stock=1)
        legacy = FicheTechnique.objects.create(
            company=self.co, produit=autre,
            pdf='stock/fiches_techniques/2026/01/vieux.pdf')
        self.assertIsNone(FicheTechniqueSerializer(legacy).data['pdf_url'])

    def test_format_refuse_ne_cree_aucune_fiche(self):
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=(None, 'Format non supporté.')):
            with self.assertRaises(ValidationError):
                self._creer()
        self.assertEqual(FicheTechnique.objects.count(), 0)

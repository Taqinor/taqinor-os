"""AUD835 — les 8 pièces jointes de la flotte vont dans MinIO.

Devis de réparation, attestation d'assurance, carte grise, autorisation de
circulation, constat amiable, PV d'infraction, photo de signalement et charte
véhicule : huit ``FileField`` qui écrivaient sur le disque du conteneur, sans
``MEDIA_ROOT`` exploitable, sans route ``/media/``, sans ``location /media/``
nginx (ROUGE structurel vérifié ici). En tentant de récupérer une attestation
d'assurance par l'URL renvoyée, la requête échouait : le document n'était
récupérable par PERSONNE en production.

VERT : chaque champ porte sa clé MinIO préfixée par la société (SCA42) et son
``<champ>_url`` présigné ; le ``FileField`` legacy n'est plus jamais écrit.

Run :
    docker compose exec django_core python manage.py test \
        apps.flotte.tests.test_aud835_pieces_flotte_minio -v 2
"""
import datetime
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import Resolver404, resolve

from apps.flotte import serializers as flotte_serializers
from apps.flotte.models import ActifFlotte, Vehicule
from authentication.models import Company

User = get_user_model()

PDF = b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'

#: (sérialiseur, champ, données minimales de création) — les 8 champs gelés
#: par ARC26 pour ``apps/flotte/models.py``.
CAS = [
    ('OrdreReparationSerializer', 'devis_fichier',
     {'date_ouverture': '2026-04-01'}),
    ('AssuranceVehiculeSerializer', 'attestation',
     {'assureur': 'Wafa', 'numero_police': 'P-1',
      'date_echeance': '2026-12-31'}),
    ('CarteGriseVehiculeSerializer', 'carte_grise_fichier',
     {'numero_carte_grise': 'CG-1'}),
    ('CarteGriseVehiculeSerializer', 'autorisation_fichier',
     {'numero_carte_grise': 'CG-2'}),
    ('SinistreSerializer', 'constat_fichier',
     {'date_sinistre': '2026-04-02', 'description': 'Accrochage'}),
    ('InfractionSerializer', 'pv_fichier',
     {'date_infraction': '2026-04-03'}),
    ('SignalementVehiculeSerializer', 'photo',
     {'description': 'Pneu lisse'}),
]


class MediaJamaisServiTests(TestCase):
    def test_aucune_route_media(self):
        with self.assertRaises(Resolver404):
            resolve('/media/flotte/assurances/attestations/2026/04/a.pdf')

    def test_aucun_reglage_de_stockage_de_medias(self):
        self.assertFalse(getattr(settings, 'MEDIA_ROOT', '') or '')


class PiecesFlotteVersMinioTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='aud835-flotte-co', defaults={'nom': 'AUD835 Flotte'})[0]
        self.user = User.objects.create_user(
            username='aud835_flotte', password='x', company=self.co,
            role_legacy='admin')

    def _actif(self, immat):
        vehicule = Vehicule.objects.create(
            company=self.co, immatriculation=immat, energie='diesel')
        return ActifFlotte.objects.create(company=self.co, vehicule=vehicule)

    def _meta(self, champ):
        return ({
            'file_key': f'attachments/{self.co.id}/{champ}.pdf',
            'filename': f'{champ}.pdf', 'size': len(PDF),
            'mime': 'application/pdf',
        }, None)

    def test_les_sept_pieces_dactif_partent_dans_minio(self):
        for index, (nom_serializer, champ, extra) in enumerate(CAS):
            with self.subTest(champ=champ):
                serializer_cls = getattr(flotte_serializers, nom_serializer)
                donnees = dict(extra)
                donnees['actif_flotte'] = self._actif(f'AUD835-{index}').pk
                donnees[champ] = SimpleUploadedFile(
                    f'{champ}.pdf', PDF, 'application/pdf')
                serializer = serializer_cls(data=donnees)
                serializer.is_valid(raise_exception=True)

                with mock.patch('apps.records.storage.store_attachment',
                                return_value=self._meta(champ)) as stocke:
                    objet = serializer.save(company=self.co)

                self.assertEqual(stocke.call_args.kwargs['company'], self.co)
                objet.refresh_from_db()
                self.assertEqual(getattr(objet, f'{champ}_key'),
                                 f'attachments/{self.co.id}/{champ}.pdf')
                self.assertEqual(getattr(objet, f'{champ}_filename'),
                                 f'{champ}.pdf')
                self.assertEqual(getattr(objet, f'{champ}_size'), len(PDF))
                self.assertEqual(getattr(objet, f'{champ}_mime'),
                                 'application/pdf')
                # Le FileField legacy n'est plus jamais écrit.
                self.assertFalse(getattr(objet, champ))

                with mock.patch('apps.records.storage.presign_attachment',
                                return_value='https://minio/x?sig=9'):
                    data = serializer_cls(objet).data
                self.assertEqual(data[f'{champ}_url'], 'https://minio/x?sig=9')
                self.assertNotIn(champ, data)

    def test_la_charte_vehicule_part_aussi_dans_minio(self):
        """8ᵉ champ : ``CharteVehicule.document`` (pas d'``actif_flotte``)."""
        serializer = flotte_serializers.CharteVehiculeSerializer(data={
            'document': SimpleUploadedFile('charte.pdf', PDF,
                                           'application/pdf'),
        })
        serializer.is_valid(raise_exception=True)
        with mock.patch('apps.records.storage.store_attachment',
                        return_value=self._meta('document')):
            charte = serializer.save(company=self.co, version=1)

        charte.refresh_from_db()
        self.assertEqual(charte.document_key,
                         f'attachments/{self.co.id}/document.pdf')
        self.assertFalse(charte.document)

        with mock.patch('apps.records.storage.presign_attachment',
                        return_value='https://minio/c?sig=8'):
            data = flotte_serializers.CharteVehiculeSerializer(charte).data
        self.assertEqual(data['document_url'], 'https://minio/c?sig=8')

    def test_ligne_historique_sans_cle_rend_none(self):
        from apps.flotte.models import AssuranceVehicule

        legacy = AssuranceVehicule.objects.create(
            company=self.co, actif_flotte=self._actif('AUD835-legacy'),
            assureur='Wafa', numero_police='P-legacy',
            date_echeance=datetime.date(2026, 12, 31),
            attestation='flotte/assurances/attestations/2026/01/vieux.pdf')
        data = flotte_serializers.AssuranceVehiculeSerializer(legacy).data
        self.assertIsNone(data['attestation_url'])

"""ACAL299 — effacer un fichier du magasin des rendus de toiture.

``apps.ventes.services.supprimer_fichier_toiture(cle)`` supprime l'objet
déposé par ``stocker_image_toiture`` (bucket des PDF), refuse toute clé hors
``roofs/`` et ignore une clé vide. Magasin RÉEL de la pile de test (MinIO,
même client que ``upload_roof_image``) : aucun mock du magasin sous test.

Run :
    python manage.py test apps.ventes.tests.test_acal_supprimer_fichier_toiture -v2
"""
import uuid

from django.test import SimpleTestCase

from apps.ventes import services

#: Un PNG minimal (signature reconnue par ``type_image_toiture``).
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 32


class SupprimerFichierToitureTest(SimpleTestCase):
    def _cle(self):
        return 'roofs/0/photos/acal299-%s.png' % uuid.uuid4().hex

    def test_supprime_l_objet_depose(self):
        cle = self._cle()
        services.stocker_image_toiture(PNG, cle, content_type='image/png')
        self.assertEqual(services.lire_fichier_toiture(cle), PNG)

        services.supprimer_fichier_toiture(cle)

        self.assertIsNone(services.lire_fichier_toiture(cle))
        # Idempotent : un objet déjà absent n'est pas une erreur.
        services.supprimer_fichier_toiture(cle)

    def test_cle_hors_roofs_refusee(self):
        for cle in ('devis/1/DEV-1.pdf', 'pdfs/x.pdf', '/roofs/1/x.png',
                    'roofs/../devis/1.pdf', 'roofsx/1.png'):
            with self.subTest(cle=cle):
                with self.assertRaises(ValueError):
                    services.supprimer_fichier_toiture(cle)

    def test_cle_vide_no_op(self):
        self.assertIsNone(services.supprimer_fichier_toiture(''))
        self.assertIsNone(services.supprimer_fichier_toiture(None))

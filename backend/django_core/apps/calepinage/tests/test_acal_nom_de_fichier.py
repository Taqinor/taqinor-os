"""ACAL234 — un Content-Disposition VALIDE pour tout titre de calepinage.

Constat C-ACAL-132 : un titre en arabe (ou « Villa Salé ») passait dans
``nom_de_fichier`` (``isalnum`` garde ces lettres), puis la valeur
``attachment; filename="…"`` non latin-1 était encodée par Django en mot RFC
2047 (``=?utf-8?b?…?=``) qui REMPLAÇAIT l'en-tête entier : le navigateur
proposait un fichier sans nom ni extension. Désormais UNE fonction
(``views/sorties.py::en_tete_de_telechargement``, RFC 6266) porte le nom de
toutes les pièces : ``filename*=utf-8''…`` pour un nom non ASCII, le même
``filename="…"`` qu'avant pour un nom ASCII.

Run :
    python manage.py test apps.calepinage.tests.test_acal_nom_de_fichier -v2
"""
import copy
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.calepinage.services.planche import nom_de_fichier
from apps.calepinage.views.sorties import (
    MIME_PDF, en_tete_de_telechargement, reponse_de_fichier,
)
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

from .acal_livrables_helpers import calepinage_simule_reel, patch_materiel

User = get_user_model()

BASE = '/api/django/calepinage/calepinages/'
TITRE_ARABE = 'فيلا الرباط'


class _Pivot:
    def __init__(self, titre, pk=5):
        self.titre = titre
        self.pk = pk


def _en_tete(titre, extension='pdf'):
    reponse = reponse_de_fichier(
        b'%PDF-1.4', mime=MIME_PDF,
        nom_fichier=nom_de_fichier(_Pivot(titre), extension))
    return reponse['Content-Disposition']


def _nom_annonce(en_tete):
    """Le nom que le navigateur lira (``filename*`` d'abord, RFC 6266)."""
    if "filename*=utf-8''" in en_tete:
        return unquote(en_tete.split("filename*=utf-8''", 1)[1])
    return en_tete.split('filename="', 1)[1].rstrip('"')


class EnTeteTest(SimpleTestCase):
    def test_titre_arabe_garde_l_en_tete_attachment(self):
        en_tete = _en_tete(TITRE_ARABE)
        self.assertTrue(en_tete.startswith('attachment;'), en_tete)
        self.assertNotIn('=?utf-8?', en_tete.lower())
        self.assertIn("filename*=utf-8''", en_tete)
        nom = _nom_annonce(en_tete)
        self.assertTrue(nom.startswith('calepinage-5-'), nom)
        self.assertTrue(nom.endswith('.pdf'), nom)
        self.assertIn('الرباط', nom)

    def test_titre_accentue_decode_en_utf8(self):
        en_tete = _en_tete('Villa Salé')
        self.assertTrue(en_tete.startswith('attachment;'), en_tete)
        self.assertNotIn('=?utf-8?', en_tete.lower())
        self.assertEqual(_nom_annonce(en_tete), 'calepinage-5-villa-salé.pdf')

    def test_titre_ascii_inchange(self):
        self.assertEqual(_en_tete('Villa Anfa'),
                         'attachment; filename="calepinage-5-villa-anfa.pdf"')


class MemeFonctionPourLesExportsTest(TestCase):
    """``export-projet.json`` et ``export-csv`` : LA même fonction d'en-tête."""

    def setUp(self):
        societe = Company.objects.create(nom='ACAL234', slug='acal234')
        role = Role.objects.create(company=societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = User.objects.create_user(username='acal234', password='x',
                                        company=societe, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        lead = Lead.objects.create(company=societe, nom='Toiture 234')
        pivot = calepinage_simule_reel()
        self.calepinage = Calepinage.objects.create(
            company=societe, lead_id=lead.pk, titre=TITRE_ARABE,
            roof_layout=copy.deepcopy(pivot.roof_layout),
            resultat=copy.deepcopy(pivot.resultat),
            layout_hash=pivot.layout_hash or '',
            version_moteur=pivot.version_moteur or '')

    def _get(self, chemin, **parametres):
        with patch_materiel():
            return self.api.get(f'{BASE}{self.calepinage.pk}/{chemin}',
                                parametres)

    def test_export_projet_et_export_csv_utilisent_la_meme_fonction(self):
        projet = self._get('export-projet.json/')
        self.assertEqual(projet.status_code, 200,
                         getattr(projet, 'data', projet.content[:300]))
        self.assertEqual(
            projet['Content-Disposition'],
            en_tete_de_telechargement(
                nom_de_fichier(self.calepinage, 'export-projet.json')))
        self.assertNotIn('=?utf-8?', projet['Content-Disposition'].lower())
        self.assertTrue(
            _nom_annonce(projet['Content-Disposition']).endswith('.json'))

        csv = self._get('export-csv/', quoi='horaire')
        self.assertEqual(csv.status_code, 200,
                         getattr(csv, 'data', csv.content[:300]))
        self.assertEqual(
            csv['Content-Disposition'],
            en_tete_de_telechargement(
                nom_de_fichier(self.calepinage, 'csv', quoi='horaire')))
        # Le nom du CSV ne porte pas le titre : le même qu'avant ACAL234.
        self.assertEqual(
            csv['Content-Disposition'],
            'attachment; filename="calepinage-%s-horaire.csv"'
            % self.calepinage.pk)

    def test_planche_d_un_titre_arabe_garde_nom_et_extension(self):
        reponse = self._get('planche.pdf/')
        if reponse.status_code != 200:
            self.skipTest('planche indisponible sur ce poste : %s'
                          % getattr(reponse, 'data', reponse.status_code))
        en_tete = reponse['Content-Disposition']
        self.assertTrue(en_tete.startswith('attachment;'), en_tete)
        self.assertNotIn('=?utf-8?', en_tete.lower())
        self.assertTrue(_nom_annonce(en_tete).endswith('.pdf'))

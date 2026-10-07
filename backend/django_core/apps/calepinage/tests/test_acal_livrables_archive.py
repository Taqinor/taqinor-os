"""ACAL119 (D-ACAL-25, C-ACAL-099) — un calepinage ARCHIVÉ : ses LECTURES
sont servies (200, chaque pièce porte la mention « archivé », CALX325) et
TOUTE écriture est refusée 409 en le nommant — jamais 404 pour un archivé de
sa propre société ; « Restaurer » reste la seule écriture admise.

Calepinage simulé par les VRAIS écrivains
(``acal_livrables_helpers.calepinage_simule_reel``), enregistré en base ;
client HTTP réel. Le matériel est le seam documenté (``patch_materiel``).

Run :
    python manage.py test apps.calepinage.tests.test_acal_livrables_archive -v2
"""
import copy
from html import escape

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.calepinage.services.archivage import MESSAGE_ARCHIVE, archiver
from apps.calepinage.services.documents.gabarit_document import (
    MENTION_ARCHIVE,
)
from apps.crm.models import Lead
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

from .acal_livrables_helpers import (
    calepinage_simule_reel, exiger_bibliotheques_pdf, patch_materiel,
)

User = get_user_model()

BASE = '/api/django/calepinage/calepinages/'

#: Les lectures d'un archivé : 200 (un calepinage de SA société).
LECTURES = ('', 'layout/', 'resultat/', 'documents/', 'versions/',
            'variantes/', 'planche.svg')

#: Les écritures : 409 nommé, rien n'est écrit.
ECRITURES = (
    ('post', 'layout/', {'roof_layout': {'version': 2, 'zones': []}}),
    ('post', 'layout/section/', {'section': 'zones', 'valeur': []}),
    ('post', 'variantes/', {'nom': 'Variante B'}),
    ('post', 'simuler/', {}),
    ('post', 'generer-devis/', {}),
    ('post', 'sync-devis/', {}),
    ('post', 'entree-electrique/', {'module_produit': 1}),
    ('patch', '', {'titre': 'Renommé'}),
    ('post', 'roof-image/', {}),
    ('post', 'photos/', {}),
    ('post', 'enregistrer-pertes/', {'pertes': []}),
)


def _date(moment):
    return timezone.localtime(moment).strftime('%d/%m/%Y')


class LivrablesArchiveTest(TestCase):
    def setUp(self):
        societe = Company.objects.create(nom='ACAL119', slug='acal119')
        role = Role.objects.create(company=societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='acal119', password='x', company=societe, role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        lead = Lead.objects.create(company=societe, nom='Toiture 119')
        pivot = calepinage_simule_reel()
        self.calepinage = Calepinage.objects.create(
            company=societe, lead_id=lead.pk, titre='QA-ACAL archivé',
            roof_layout=copy.deepcopy(pivot.roof_layout),
            resultat=copy.deepcopy(pivot.resultat),
            layout_hash=pivot.layout_hash or '',
            version_moteur=pivot.version_moteur or '')
        archiver(self.calepinage, user=self.user)
        self.calepinage.refresh_from_db()
        self.mention = MENTION_ARCHIVE.format(
            date=_date(self.calepinage.archive_le))

    def _url(self, suffixe=''):
        return f'{BASE}{self.calepinage.pk}/{suffixe}'

    @tag('pdf')
    def test_rapport_d_un_archive_servi_avec_mention(self):
        exiger_bibliotheques_pdf()
        import fitz

        with patch_materiel():
            reponse = self.api.get(self._url('rapport-etude.pdf'))
        self.assertEqual(reponse.status_code, 200,
                         getattr(reponse, 'data', None))
        octets = b''.join(reponse.streaming_content) if getattr(
            reponse, 'streaming', False) else reponse.content
        document = fitz.open(stream=octets, filetype='pdf')
        try:
            texte = ' '.join(page.get_text() for page in document)
        finally:
            document.close()
        self.assertIn('archivée le', ' '.join(texte.split()))
        self.assertIn(_date(self.calepinage.archive_le), texte)

    def test_lectures_servies_200(self):
        for suffixe in LECTURES:
            with self.subTest(route=suffixe or 'détail'):
                with patch_materiel():
                    reponse = self.api.get(self._url(suffixe))
                self.assertEqual(reponse.status_code, 200,
                                 getattr(reponse, 'data', None))
        # La planche (pièce produite) porte la mention « archivée ».
        with patch_materiel():
            planche = self.api.get(self._url('planche.svg'))
        texte = b''.join(planche.streaming_content).decode('utf-8') if \
            getattr(planche, 'streaming', False) else \
            planche.content.decode('utf-8')
        self.assertIn(escape(self.mention), texte)
        # La LISTE, elle, écarte toujours l'archivé.
        liste = self.api.get(BASE)
        lignes = liste.data.get('results', liste.data) if isinstance(
            liste.data, dict) else liste.data
        self.assertNotIn(self.calepinage.pk, [ligne['id'] for ligne in lignes])

    def test_ecritures_refusees_409_nommees(self):
        avant = Calepinage.objects.get(pk=self.calepinage.pk)
        for methode, suffixe, corps in ECRITURES:
            with self.subTest(route=f'{methode.upper()} {suffixe}'):
                with patch_materiel():
                    reponse = getattr(self.api, methode)(
                        self._url(suffixe), corps, format='json')
                self.assertEqual(reponse.status_code, 409,
                                 getattr(reponse, 'data', None))
                self.assertEqual(reponse.data['detail'], MESSAGE_ARCHIVE)
        apres = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertEqual(apres.roof_layout, avant.roof_layout)
        self.assertEqual(apres.resultat, avant.resultat)
        self.assertEqual(apres.titre, avant.titre)
        self.assertEqual(Calepinage.objects.count(), 1)

    def test_dupliquer_un_archive_permis(self):
        """ACAL187 — une source ARCHIVÉE se duplique (sans cible) : la copie
        est créée, la source n'est pas écrite et reste archivée."""
        avant = Calepinage.objects.get(pk=self.calepinage.pk)
        reponse = self.api.post(self._url('dupliquer/'), {}, format='json')
        self.assertEqual(reponse.status_code, 201,
                         getattr(reponse, 'data', None))
        self.assertEqual(reponse.data['source'], self.calepinage.pk)
        apres = Calepinage.objects.get(pk=self.calepinage.pk)
        self.assertIsNotNone(apres.archive_le)
        self.assertEqual(apres.roof_layout, avant.roof_layout)
        self.assertEqual(Calepinage.objects.count(), 2)

    def test_restaurer_reste_permis(self):
        reponse = self.api.post(self._url('restaurer-corbeille/'))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data, {'calepinage': self.calepinage.pk,
                                        'archive': False})
        reponse = self.api.patch(self._url(), {'titre': 'Renommé'},
                                 format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

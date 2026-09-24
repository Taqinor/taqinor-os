"""CALX318 — le document as-built (prévu, posé, écarts, photos).

Ce qui est prouvé ici :

* 3 pans dont 1 relevé ⇒ 1 écart imprimé (le pan relevé) et 2 mentions
  ``MENTION_SANS_SAISIE`` (les deux pans non relevés) ;
* ``ecart_total`` n'est PAS affiché tant qu'AUCUN pan n'a été relevé ;
* AUCUN import de ``apps.installations`` dans le fichier (règle fondateur
  12/09/2026 : le module chantier ne garde QUE son cœur) ;
* aucun montant ;
* en base (CI) : ``GET …/document-asbuilt.pdf/`` borné société et
  permission.

Run (pur, sans base) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx318_document_asbuilt.py
"""
import pathlib
import unittest
from html import escape
from types import SimpleNamespace
from unittest import mock

from django.test import tag

from apps.calepinage.services.asbuilt import MENTION_SANS_SAISIE
from apps.calepinage.services.documents import mise_en_page
from apps.calepinage.services.documents.document_asbuilt import (
    CODE_DOCUMENT,
    construire_document,
    html_de_document,
    html_du_document_asbuilt,
    rendre_document_asbuilt,
)

from .test_api_liste import BaseApiCalepinage, url_detail

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
SOURCE = (RACINE_APP / 'services' / 'documents' / 'document_asbuilt.py') \
    .read_text(encoding='utf-8')

#: Un calepinage NON ENREGISTRÉ, sans société — même patron que ``NU`` dans
#: ``test_calx297_rapport_etude.py``.
NU = SimpleNamespace(company=None, client_id=None, lead_id=None, pk=None,
                     titre='Villa Anfa', layout_hash='', version_moteur='')
SITE = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle'}
IDENTITE = {'titre_document': 'Document as-built', 'projet': 'Villa Anfa',
            'client': 'Mme Bennani', 'produit_le': '23/09/2026'}
STYLES = {'nom_affiche': 'Soleil Atlas', 'logo_url': '',
          'couleur_primaire': '', 'couleur_secondaire': ''}

#: 3 pans, 1 SEUL relevé (Pan Sud) — les deux autres n'ont AUCUNE saisie.
ECARTS_3_PANS_1_RELEVE = {
    'calepinage': None,
    'source_prevu': 'variante retenue',
    'pans': [
        {'pan': 'Pan Sud', 'prevu': 12, 'pose': 11, 'ecart': -1,
         'ecarts_position': 'Une rangée décalée vers le faîtage',
         'releve_le': '2026-09-19', 'mention': ''},
        {'pan': 'Pan Nord', 'prevu': 6, 'pose': None, 'ecart': None,
         'ecarts_position': '', 'releve_le': None,
         'mention': MENTION_SANS_SAISIE},
        {'pan': 'Pan Est', 'prevu': 4, 'pose': None, 'ecart': None,
         'ecarts_position': '', 'releve_le': None,
         'mention': MENTION_SANS_SAISIE},
    ],
    'pans_releves': 1,
    'total_prevu': 22,
    'total_pose': 11,
    'ecart_total': -1,
}

#: AUCUN pan relevé — ``ecart_total`` doit rester ``None``.
ECARTS_AUCUN_RELEVE = {
    'calepinage': None,
    'source_prevu': 'document du calepinage',
    'pans': [
        {'pan': 'Pan Sud', 'prevu': 12, 'pose': None, 'ecart': None,
         'ecarts_position': '', 'releve_le': None,
         'mention': MENTION_SANS_SAISIE},
    ],
    'pans_releves': 0,
    'total_prevu': 12,
    'total_pose': None,
    'ecart_total': None,
}


def document(**options):
    options.setdefault('ecarts', ECARTS_3_PANS_1_RELEVE)
    options.setdefault('photos', [])
    options.setdefault('svg_planche', '')
    options.setdefault('site', SITE)
    options.setdefault('identite', IDENTITE)
    options.setdefault('styles', STYLES)
    return construire_document(NU, **options)


class AucunImportInstallationsTest(unittest.TestCase):
    def test_aucun_import_apps_installations(self):
        # On vérifie l'absence d'une INSTRUCTION d'import (la doctrine, elle,
        # est légitimement CITÉE en prose dans la docstring du module).
        self.assertNotIn('import apps.installations', SOURCE)
        self.assertNotIn('from apps.installations', SOURCE)
        self.assertNotIn('from apps import installations', SOURCE)


class TableEcartsTest(unittest.TestCase):
    def setUp(self):
        self.html = html_de_document(document())

    def test_3_pans_dont_1_releve_1_ecart_imprime_et_2_mentions(self):
        # Le seul écart CHIFFRÉ imprimé est celui de « Pan Sud » (-1) : les
        # deux autres pans impriment « — » dans la cellule Écart.
        self.assertEqual(
            self.html.count('<td class="num">-1</td>'), 1)
        self.assertEqual(self.html.count(escape(MENTION_SANS_SAISIE)), 2)

    def test_le_pan_relevee_porte_sa_date_et_ses_ecarts_de_position(self):
        self.assertIn('2026-09-19', self.html)
        self.assertIn('Une rangée décalée vers le faîtage', self.html)

    def test_ecart_total_affiche_quand_au_moins_un_pan_est_releve(self):
        self.assertIn('Écart total : -1 module(s)', self.html)

    def test_la_source_du_prevu_est_publiee(self):
        self.assertIn('variante RETENUE', self.html)


class EcartTotalAbsentTest(unittest.TestCase):
    def test_ecart_total_absent_tant_qu_aucun_pan_n_est_releve(self):
        html = html_de_document(document(ecarts=ECARTS_AUCUN_RELEVE))
        self.assertNotIn('Écart total :', html)
        self.assertIn('Écart total non affiché', html)


class PhotosTest(unittest.TestCase):
    def test_sans_photo_la_mention_est_imprimee(self):
        html = html_de_document(document(photos=[]))
        self.assertIn('Aucune photo de site déposée', html)

    def test_une_photo_legendee_et_datee_est_imprimee(self):
        photos = [{'genre': 'drone', 'legende': 'Vue toiture',
                  'prise_le': '2026-09-01', 'url': 'https://minio/x.jpg'}]
        html = html_de_document(document(photos=photos))
        self.assertIn('Vue toiture', html)
        self.assertIn('2026-09-01', html)
        self.assertIn('<img src="https://minio/x.jpg"', html)


class SansPlancheTest(unittest.TestCase):
    def test_sans_planche_aucune_section_planche_n_est_imprimee(self):
        html = html_de_document(document(svg_planche=''))
        self.assertNotIn('data-section="planche"', html)

    def test_avec_planche_le_svg_est_embarque(self):
        html = html_de_document(
            document(svg_planche='<svg><rect/></svg>'))
        self.assertIn('data-section="planche"', html)
        self.assertIn('<svg><rect/></svg>', html)


class AucunMontantTest(unittest.TestCase):
    def test_aucun_mot_de_montant(self):
        html = html_de_document(document())
        mots_de_montant = (
            'MAD', 'DH', 'prix', 'coût', 'cout', 'montant', 'remise',
            'marge', 'TTC', 'HT', '€')
        for mot in mots_de_montant:
            self.assertNotIn(mot, html, mot)


class MiseEnPageTest(unittest.TestCase):
    def test_le_document_porte_son_code_et_sa_garde(self):
        agrege = document()
        self.assertEqual(agrege['code'], CODE_DOCUMENT)
        html = html_de_document(agrege)
        self.assertEqual(html.count('class="page-de-garde"'), 1)
        self.assertIn('Document as-built', html)

    def test_l_apercu_et_le_pdf_partagent_une_seule_fonction(self):
        self.assertIs(mise_en_page('document_asbuilt'),
                      html_du_document_asbuilt)


class RenduPartageTest(unittest.TestCase):
    def test_le_pdf_passe_par_la_plomberie_partagee(self):
        options = dict(ecarts=ECARTS_3_PANS_1_RELEVE, photos=[],
                       svg_planche='', site=SITE, identite=IDENTITE,
                       styles=STYLES)
        with mock.patch('core.pdf.render_pdf',
                        return_value=b'%PDF-simule') as rendu:
            octets = rendre_document_asbuilt(NU, **options)
        self.assertEqual(octets, b'%PDF-simule')
        self.assertEqual(rendu.call_args.kwargs['html'],
                         html_du_document_asbuilt(NU, **options))


@tag('pdf')
class RenduReelTest(unittest.TestCase):
    """WeasyPrint réel — étiqueté ``pdf`` (hors du palier CI — routeur M4)."""

    def setUp(self):
        try:
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 — bibliothèque native absente
            self.skipTest('WeasyPrint indisponible sur ce poste')

    def test_un_document_simule_rend_un_pdf_non_vide(self):
        octets = rendre_document_asbuilt(
            NU, ecarts=ECARTS_3_PANS_1_RELEVE, photos=[], svg_planche='',
            site=SITE, identite=IDENTITE, styles=STYLES)
        self.assertGreater(len(octets), 0)


PDF = b'%PDF-1.7 asbuilt simule'


class EndpointAsBuiltEnBaseTest(BaseApiCalepinage):
    """``GET …/document-asbuilt.pdf/`` — câblage, société, permission (CI)."""

    def setUp(self):
        super().setUp()
        from apps.calepinage.models import Calepinage

        from .test_cal171_planche import LAYOUT

        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT, layout_hash='a' * 64)
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Chez la voisine',
            roof_layout=LAYOUT)

    def _url(self, calepinage):
        return f'{url_detail(calepinage.pk)}document-asbuilt.pdf/'

    def test_le_pdf_se_telecharge_borne_societe(self):
        with mock.patch('core.pdf.render_pdf', return_value=PDF) as rendu:
            reponse = self.api.get(self._url(self.calepinage))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.content, PDF)
        self.assertEqual(rendu.call_args.kwargs['company'], self.company)

    def test_une_autre_societe_est_introuvable(self):
        reponse = self.api.get(self._url(self.etranger))
        self.assertEqual(reponse.status_code, 404)

    def test_sans_permission_de_lecture_c_est_403(self):
        reponse = self.api_sans.get(self._url(self.calepinage))
        self.assertEqual(reponse.status_code, 403)

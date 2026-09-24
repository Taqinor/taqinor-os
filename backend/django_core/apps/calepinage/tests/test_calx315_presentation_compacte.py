"""CALX315 — la présentation compacte : synthèse INTERNE à deux pages, sans
aucun montant.

Ce qui est prouvé ici :

* les totaux (modules, kWc, pans) sont LUS de la géométrie SEULE
  (``pans_du_layout``) : AUCUNE simulation requise ;
* la mention « ne vaut pas offre de prix » est présente, en toutes lettres ;
* le texte imprimé ne contient AUCUN mot de la famille montant (MAD, €, prix,
  coût, marge, remise…) ;
* un calepinage non simulé produit la page 1 ET une page 2 qui NOMME ce qui
  manque, sans jamais refuser le document ;
* une clé de coût dans le résultat est refusée à l'entrée (pare-feu repris de
  ``note_calcul``) ;
* ``@tag('pdf')`` : le PDF rendu compte EXACTEMENT deux pages, simulé comme
  non simulé ;
* en base (CI) : ``GET …/presentation-compacte.pdf/`` borné société et
  permission.

Run (pur, sans base) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx315_presentation_compacte.py  # noqa: E501
"""
import copy
import json
import pathlib
import unittest
from html import escape
from types import SimpleNamespace
from unittest import mock

from django.test import tag

from apps.calepinage.services.documents import mise_en_page
from apps.calepinage.services.documents.presentation_compacte import (
    CODE_DOCUMENT,
    MENTION_PAS_UN_DEVIS,
    MOTIF_SANS_RESULTAT,
    construire_presentation,
    html_de_presentation,
    html_de_presentation_compacte,
    rendre_presentation_compacte,
    totaux_de_pose,
)
from apps.calepinage.services.rapport import RapportRefuse

from .test_api_liste import BaseApiCalepinage, url_detail
from .test_cal171_planche import LAYOUT

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLON = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))

#: Un calepinage NON ENREGISTRÉ, sans société — même patron que ``NU`` dans
#: ``test_calx297_rapport_etude.py``.
NU = SimpleNamespace(company=None, pk=None, titre='Villa Anfa',
                     roof_layout=LAYOUT, resultat=None, layout_hash='',
                     version_moteur='')
STYLES = {'nom_affiche': 'Soleil Atlas', 'logo_url': '',
          'couleur_primaire': '', 'couleur_secondaire': ''}

#: Les mots de la famille montant, en JETONS ENTIERS — même vocabulaire que
#: les autres pièces du lot 6.
MOTS_DE_MONTANT = ('MAD', 'DH', 'prix', 'coût', 'cout', 'montant', 'remise',
                   'marge', 'TTC', 'HT', '€')


def resultat():
    return copy.deepcopy(ECHANTILLON['exemple'])


def presentation(**options):
    options.setdefault('resultat', resultat())
    options.setdefault('roof_layout', LAYOUT)
    options.setdefault('svg_planche', '')
    options.setdefault('styles', STYLES)
    return construire_presentation(NU, **options)


def _layout_avec_kwc():
    # ``LAYOUT`` (partagé avec ``test_cal171_planche``) ne porte pas de
    # ``kwc`` sur sa géométrie (fixture de planche, pas de dimensionnement) —
    # ce module y ajoute la SEULE clé qui manque, pour prouver que
    # ``totaux_de_pose`` la lit quand elle est SOURCÉE.
    donnees = copy.deepcopy(LAYOUT)
    donnees['zones'][0]['geometry']['kwc'] = 8.64
    return donnees


class TotauxDePoseTest(unittest.TestCase):
    def test_lus_de_la_geometrie_seule_aucune_simulation_requise(self):
        totaux = totaux_de_pose(_layout_avec_kwc())
        self.assertGreater(totaux['total_modules'], 0)
        self.assertEqual(totaux['total_kwc'], 8.64)
        self.assertGreaterEqual(totaux['nombre_pans'], 1)

    def test_sans_kwc_source_le_total_kwc_n_est_pas_invente(self):
        # ``LAYOUT`` seul, SANS ``kwc`` sur la géométrie : jamais un kWc
        # deviné depuis le nombre de modules.
        totaux = totaux_de_pose(LAYOUT)
        self.assertGreater(totaux['total_modules'], 0)
        self.assertIsNone(totaux['total_kwc'])

    def test_sans_conception_les_totaux_sont_a_zero(self):
        totaux = totaux_de_pose(None)
        self.assertEqual(totaux['total_modules'], 0)
        self.assertIsNone(totaux['total_kwc'])
        self.assertEqual(totaux['nombre_pans'], 0)


class ConstruirePresentationTest(unittest.TestCase):
    def test_le_code_document_est_publie(self):
        self.assertEqual(presentation()['code'], CODE_DOCUMENT)

    def test_une_cle_de_cout_est_refusee_a_l_entree(self):
        donnees = resultat()
        donnees['pose']['prix_achat_total'] = 12345
        with self.assertRaises(RapportRefuse) as capture:
            presentation(resultat=donnees)
        self.assertIn('prix_achat', capture.exception.champ)

    def test_un_resultat_absent_ou_vide_ne_refuse_jamais(self):
        for vide in (None, {}):
            with self.subTest(resultat=vide):
                document = presentation(resultat=vide)
                self.assertFalse(document['resultat'])


class MiseEnPagePage1Test(unittest.TestCase):
    def test_les_totaux_et_le_tableau_des_pans_sont_imprimes(self):
        html = html_de_presentation(presentation())
        self.assertIn('data-section="pose"', html)
        self.assertIn('presentation-pans', html)

    def test_le_plan_embarque_apparait_quand_fourni(self):
        html = html_de_presentation(
            presentation(svg_planche='<svg><rect/></svg>'))
        self.assertIn('<svg><rect/></svg>', html)


class MiseEnPagePage2Test(unittest.TestCase):
    def test_avec_resultat_la_production_mensuelle_et_le_pr_sont_imprimes(
            self):
        html = html_de_presentation(presentation())
        self.assertIn('data-section="production"', html)
        self.assertIn('presentation-mensuelle', html)
        self.assertIn('Ratio de performance', html)
        self.assertIn("Taux d'autoconsommation", html)

    def test_sans_resultat_la_page_2_nomme_ce_qui_manque_sans_refuser(self):
        html = html_de_presentation(presentation(resultat=None))
        self.assertIn('data-section="production"', html)
        self.assertIn(escape(MOTIF_SANS_RESULTAT), html)

    def test_exactement_une_coupure_de_page_entre_page_1_et_page_2(self):
        html = html_de_presentation(presentation())
        self.assertEqual(html.count('page-break-after:always'), 1)
        # Aucune page de garde : cette pièce n'a QUE deux pages.
        self.assertEqual(html.count('class="page-de-garde"'), 0)


def _sans_la_mention(html):
    """``html`` privé de la mention de pied — SEULE occurrence légitime du
    mot « prix » (« ne vaut PAS offre de prix » DIT explicitement l'absence
    de prix ; le reste de la pièce n'en porte aucun)."""
    return html.replace(escape(MENTION_PAS_UN_DEVIS), '')


class MentionEtMontantTest(unittest.TestCase):
    def test_la_mention_ne_vaut_pas_offre_de_prix_est_presente(self):
        html = html_de_presentation(presentation())
        self.assertIn(escape(MENTION_PAS_UN_DEVIS), html)
        self.assertIn('ne vaut pas offre de prix', html)

    def test_aucun_mot_de_montant_hors_la_mention(self):
        html = _sans_la_mention(html_de_presentation(presentation()))
        for mot in MOTS_DE_MONTANT:
            self.assertNotIn(mot, html, mot)

    def test_aucun_mot_de_montant_sans_resultat_non_plus(self):
        html = _sans_la_mention(
            html_de_presentation(presentation(resultat=None)))
        for mot in MOTS_DE_MONTANT:
            self.assertNotIn(mot, html, mot)


class MiseEnPageRegistreeTest(unittest.TestCase):
    def test_l_apercu_et_le_pdf_partagent_une_seule_fonction(self):
        self.assertIs(mise_en_page('presentation_compacte'),
                      html_de_presentation_compacte)


class RenduPartageTest(unittest.TestCase):
    def test_le_pdf_passe_par_la_plomberie_partagee(self):
        options = dict(resultat=resultat(), roof_layout=LAYOUT,
                       svg_planche='', styles=STYLES)
        with mock.patch('core.pdf.render_pdf',
                        return_value=b'%PDF-simule') as rendu:
            octets = rendre_presentation_compacte(NU, **options)
        self.assertEqual(octets, b'%PDF-simule')
        self.assertEqual(
            rendu.call_args.kwargs['html'],
            html_de_presentation_compacte(NU, **options))


@tag('pdf')
class RenduReelTest(unittest.TestCase):
    """WeasyPrint + PyMuPDF réels — étiqueté ``pdf`` (hors du palier CI —
    routeur M4)."""

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 — bibliothèques natives absentes
            self.skipTest('WeasyPrint ou PyMuPDF indisponible sur ce poste')

    def test_un_calepinage_simule_rend_exactement_deux_pages(self):
        from apps.calepinage.services.pack_technique import compter_pages

        octets = rendre_presentation_compacte(
            NU, resultat=resultat(), roof_layout=LAYOUT, svg_planche='',
            styles=STYLES)
        self.assertEqual(compter_pages(octets), 2)

    def test_un_calepinage_non_simule_rend_aussi_exactement_deux_pages(self):
        from apps.calepinage.services.pack_technique import compter_pages

        octets = rendre_presentation_compacte(
            NU, resultat=None, roof_layout=LAYOUT, svg_planche='',
            styles=STYLES)
        self.assertEqual(compter_pages(octets), 2)

    def test_le_texte_extrait_ne_porte_aucun_mot_de_montant(self):
        import fitz

        octets = rendre_presentation_compacte(
            NU, resultat=resultat(), roof_layout=LAYOUT, svg_planche='',
            styles=STYLES)
        document = fitz.open(stream=octets, filetype='pdf')
        try:
            texte = '\n'.join(page.get_text() for page in document)
        finally:
            document.close()
        self.assertIn('offre de prix', texte)
        # Seule occurrence légitime de « prix » : la mention elle-même
        # (répétée en pied sur chaque page) — retirée avant le balayage.
        texte_sans_mention = texte.replace(MENTION_PAS_UN_DEVIS, '')
        for mot in MOTS_DE_MONTANT:
            self.assertNotIn(mot, texte_sans_mention, mot)


PDF = b'%PDF-1.7 presentation simulee'


class EndpointPresentationEnBaseTest(BaseApiCalepinage):
    """``GET …/presentation-compacte.pdf/`` — câblage, société, permission
    (CI)."""

    def setUp(self):
        super().setUp()
        from apps.calepinage.models import Calepinage

        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT, layout_hash='a' * 64, resultat=resultat())
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Chez la voisine',
            roof_layout=LAYOUT)

    def _url(self, calepinage):
        return f'{url_detail(calepinage.pk)}presentation-compacte.pdf/'

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

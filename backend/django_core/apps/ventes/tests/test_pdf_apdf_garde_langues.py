"""APDF46 (C-APDF-004, C-APDF-002) — garde de la classe « libellé de gabarit
resté en français / glyphe illisible ».

Un devis par marché (résidentiel, commercial, industriel, agricole) est RENDU
pour de vrai dans chaque format (défaut, une-page, include_etude,
devis_final) en anglais puis en arabe (``generate_premium_devis_pdf`` :
registre des renderers et repli legacy, MinIO en mémoire —
``test_pdf_apdf_identite.rendre_pdf``), puis lu par PyMuPDF : aucun libellé de
la liste ``LIBELLES_GABARIT_FR`` (données saisies exclues : les désignations
et le client du devis d'essai n'en contiennent aucun), aucun caractère
U+1F000+ (pictogramme sans police), et en arabe aucun ``@font-face``
« Noto Sans Arabic » vendorisé dans le HTML remis à WeasyPrint (APDF6).
Couvre APDF6, APDF8 à APDF11 et APDF15.

Test-du-test : remettre un seul libellé français en dur (ex. « Prochaines
étapes » dans ``residential/trust.py``) ⇒ le cas correspondant échoue.
"""
import re
from unittest import mock

from django.test import TestCase, tag

from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)
from apps.ventes.tests.test_pdf_apdf_garde_identite import MARCHES
from apps.ventes.tests.test_pdf_apdf_identite import rendre_pdf

#: LA liste des libellés de gabarit français (une constante) : les 19 de la
#: sonde PDEV-2 (résidentiel APDF8 + une-page APDF9) et trois puces / titres
#: (APDF9, APDF10). Écrits TELS QU'IMPRIMÉS (les titres mis en capitales par
#: CSS le sont aussi à l'extraction) et comparés à la casse près : la phrase
#: de méthode « … production annuelle × part autoconsommée … » (donnée du
#: builder) n'est pas le libellé « PRODUCTION ANNUELLE » du une-page.
LIBELLES_GABARIT_FR = (
    # APDF8 — devis résidentiel premium.
    "Valable jusqu", "Votre installation solaire",
    "Consultez votre proposition interactive", "Bonjour", "kWc installés",
    "Le détail de votre projet", "VOTRE ÉQUIPEMENT", "Pourquoi",
    "NOS GARANTIES", "Prochaines étapes", "Validité de l",
    "Bon pour accord", "La preuve, en ligne",
    # APDF9 — une-page legacy.
    "Consultez votre", "DEVIS N°", "PUISSANCE CRÊTE", "PRODUCTION ANNUELLE",
    "ÉCONOMIE ANNUELLE", "PRIX PAR KWC", "Validité : jusqu", "Siège : ",
    # APDF9 / APDF10 — titre des clauses et puces CGV par défaut.
    "Acompte à la commande", "Tarifs de référence",
    "CLAUSES PARTICULIÈRES",
)

FORMATS = {
    'defaut': {},
    'onepage': {'pdf_mode': 'onepage'},
    'include_etude': {'include_etude': True},
    'devis_final': {'devis_final': True},
}

FONT_FACE_ARABE = re.compile(
    r"@font-face\s*\{[^}]*Noto Sans Arabic", re.IGNORECASE)


def rendu_et_html(devis, options):
    """(octets du PDF, HTML remis à WeasyPrint) — ``weasyprint.HTML`` est
    ESPIONNÉ (le vrai rendu a lieu), jamais remplacé."""
    import weasyprint
    vrai, recus = weasyprint.HTML, []

    def espion(*args, **kwargs):
        recus.append(kwargs.get('string') or (args[0] if args else ''))
        return vrai(*args, **kwargs)

    with mock.patch('weasyprint.HTML', espion):
        pdf = rendre_pdf(devis, options)
    return pdf, '\n'.join(str(h) for h in recus)


def texte_pdf_normalise(octets):
    import fitz
    doc = fitz.open(stream=octets, filetype='pdf')
    try:
        texte = '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()
    return texte.replace('\xa0', ' ').replace(' ', ' ')


@tag('pdf')
class GardeLanguesTests(TestCase):

    def setUp(self):
        self.company = make_company(slug='apdf46-co', nom='APDF46')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, marche):
        lignes, etude, mode = MARCHES[marche]
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           reference=f'DEV-APDF46-{marche[:4].upper()}',
                           etude_params=dict(etude) if etude else None)
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        return devis

    def test_aucun_libelle_fr_ni_glyphe_marche_format_langue(self):
        rendus = []
        for marche in MARCHES:
            devis = self._devis(marche)
            for nom, options in FORMATS.items():
                for langue in ('en', 'ar'):
                    with self.subTest(marche=marche, format=nom,
                                      langue=langue):
                        pdf, html = rendu_et_html(
                            devis, dict(options, langue_sortie=langue))
                        texte = texte_pdf_normalise(pdf)
                        rendus.append((marche, nom, langue))
                        self.assertEqual(
                            [lib for lib in LIBELLES_GABARIT_FR
                             if lib in texte], [])
                        self.assertEqual(
                            [hex(ord(c)) for c in set(texte)
                             if ord(c) >= 0x1F000], [])
                        if langue == 'ar':
                            self.assertIsNone(FONT_FACE_ARABE.search(html))
        self.assertEqual(len(rendus), len(MARCHES) * len(FORMATS) * 2,
                         rendus)

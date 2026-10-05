"""ACAL226 - le rapport d'etude SERVI est pagine, sommaire, annexes.

ACAL227 - et il se termine (avant les fiches constructeur) par le schema
unifilaire NATIF du calepinage ; sans schema, aucune page vide et le motif
est dit dans la section electrique ; la piece schema du dossier
reglementaire sort de la MEME fonction (``bloc_schema_unifilaire``).

Un calepinage simule par les VRAIS ecrivains ; WeasyPrint et PyMuPDF REELS
(``@tag('pdf')``, hors du palier CI leger - meme regime que
``test_calx306_pages_rapport.py``). Les fiches constructeur sont injectees par
le seam DOCUMENTE de ``rendre_rapport_avec_annexes`` (``recuperer_pdf``) : le
stockage MinIO n'est pas l'objet de ces essais.

Run :
    python manage.py test apps.calepinage.tests.test_acal_rapport_etude_servi
"""
import unittest
from html import escape
from unittest import mock

from django.test import tag

from apps.calepinage.services.documents import mise_en_page
from apps.calepinage.services.rapport import (
    construire_rapport, html_du_rapport, rendre_rapport,
)
from apps.calepinage.services.rapport import systeme
from apps.calepinage.services.rapport.mise_en_page import pages_attendues

from .acal_livrables_helpers import (
    calepinage_simule_reel, exiger_bibliotheques_pdf, patch_materiel,
)
from .test_acal_sld_conception_reelle import BaseConceptionReelle

OPTIONS = dict(site={}, identite={}, styles={}, etat={})
ANNEXE_AVEC_PDF = {'famille': 'onduleur', 'designation': 'ONDULEUR-ESSAI',
                   'pdf_key': 'fiches/onduleur.pdf', 'pdf_filename': 'o.pdf',
                   'motif': ''}
ANNEXE_SANS_PDF = {'famille': 'panneau', 'designation': 'MODULE-ESSAI',
                   'pdf_key': None, 'pdf_filename': '',
                   'motif': systeme.MENTION_PDF_ABSENT}


def _pdf_constructeur(texte, pages=2):
    import fitz

    document = fitz.open()
    for rang in range(pages):
        page = document.new_page()
        page.insert_text((72, 72), '%s page %d' % (texte, rang + 1))
    octets = document.tobytes()
    document.close()
    return octets


def _texte(octets):
    import fitz

    document = fitz.open(stream=octets, filetype='pdf')
    try:
        return [page.get_text() for page in document]
    finally:
        document.close()


@tag('pdf')
class RapportEtudeServiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 - bibliotheques natives absentes
            raise unittest.SkipTest('WeasyPrint ou PyMuPDF indisponible')
        cls.pivot = calepinage_simule_reel()

    def setUp(self):
        materiel = patch_materiel()
        materiel.start()
        self.addCleanup(materiel.stop)

    def test_pdf_servi_contient_sommaire_et_annexes(self):
        octets = rendre_rapport(self.pivot, **OPTIONS)
        pages = _texte(octets)
        self.assertIn('Sommaire', pages[1])           # sommaire en page 2
        rapport = construire_rapport(self.pivot, **OPTIONS)
        attendues = pages_attendues(rapport)
        self.assertEqual(len(pages), sum(attendues.values()))

        annexe = _pdf_constructeur('FICHE-CONSTRUCTEUR')
        with mock.patch.object(systeme, 'annexes_pdf',
                               return_value=[ANNEXE_AVEC_PDF]):
            fusionne, manques = systeme.rendre_rapport_avec_annexes(
                self.pivot, octets,
                recuperer_pdf=lambda cle: (annexe, None))
        textes = _texte(fusionne)
        self.assertEqual(manques, [])
        # une page separatrice + les deux pages du PDF constructeur
        self.assertEqual(len(textes), len(pages) + 1 + 2)
        self.assertTrue(any('FICHE-CONSTRUCTEUR page 1' in t for t in textes))

    def test_fiche_sans_pdf_n_ajoute_aucune_page(self):
        octets = rendre_rapport(self.pivot, **OPTIONS)
        with mock.patch.object(systeme, 'annexes_pdf',
                               return_value=[ANNEXE_SANS_PDF]):
            fusionne, manques = systeme.rendre_rapport_avec_annexes(
                self.pivot, octets)
        self.assertEqual(len(_texte(fusionne)), len(_texte(octets)))
        self.assertEqual(len(manques), 1)
        self.assertIn(systeme.MENTION_PDF_ABSENT, manques[0])
        # ... et elle est DITE dans la section systeme du rapport.
        with mock.patch(
                'apps.calepinage.services.rapport._annexes_du_calepinage',
                return_value=[ANNEXE_SANS_PDF]):
            html = html_du_rapport(self.pivot, paginer=False, **OPTIONS)
        self.assertIn(systeme.MENTION_PDF_ABSENT, html)

    def test_apercu_html_et_pdf_partagent_la_meme_mise_en_page(self):
        self.assertIs(mise_en_page('rapport_etude'), html_du_rapport)
        import core.pdf

        with mock.patch.object(core.pdf, 'render_pdf',
                               wraps=core.pdf.render_pdf) as rendu:
            rendre_rapport(self.pivot, **OPTIONS)
        html_pdf = rendu.call_args_list[-1].kwargs['html']
        self.assertEqual(html_pdf, html_du_rapport(self.pivot, **OPTIONS))
        self.assertIn('Sommaire', html_pdf)


def _pages(octets):
    from apps.calepinage.services.pack_technique import compter_pages

    return compter_pages(octets)


def _sans_espaces(texte):
    return ' '.join(str(texte).split())


@tag('pdf')
class SchemaJointAuRapportTest(BaseConceptionReelle):
    """ACAL227 - calepinage reel (Produit et fiches en base, aucune
    doublure du schema ni du materiel)."""

    def setUp(self):
        exiger_bibliotheques_pdf()
        super().setUp()
        self._norme_francaise()

    def _corps_seul(self, calepinage):
        import core.pdf

        return core.pdf.render_pdf(
            html=html_du_rapport(calepinage, **OPTIONS),
            company=calepinage.company)

    def test_schema_unifilaire_joint_au_rapport(self):
        from apps.calepinage.services.rapport.electrique import (
            bloc_schema_unifilaire,
        )

        schema, motif = bloc_schema_unifilaire(self.calepinage)
        self.assertIsNone(motif)
        octets = rendre_rapport(self.calepinage, **OPTIONS)
        self.assertEqual(
            _pages(octets),
            _pages(self._corps_seul(self.calepinage)) + _pages(schema))
        # Le schema FERME le rapport (aucune fiche constructeur ici).
        nombre = _pages(schema)
        self.assertEqual(_texte(octets)[-nombre:], _texte(schema))

    def test_sans_schema_aucune_page_vide_et_motif_dit(self):
        from apps.calepinage.models import Calepinage
        from apps.calepinage.services.electrique import enregistrer_entree
        from apps.calepinage.services.rapport.electrique import (
            MOTIF_SCHEMA_INDISPONIBLE,
        )

        # Module designe, onduleur NON designe : le schema ne se dessine pas.
        muet = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Sans onduleur',
            roof_layout=self.calepinage.roof_layout)
        enregistrer_entree(muet, {
            'module_produit': self.module.pk,
            'temperature_min_c': -5.0, 'temperature_max_c': 70.0,
        })
        octets = rendre_rapport(muet, **OPTIONS)
        self.assertEqual(_pages(octets), _pages(self._corps_seul(muet)))
        html = html_du_rapport(muet, paginer=False, **OPTIONS)
        debut = html.index('data-section="electrique"')
        section = html[debut:html.index('</section>', debut)]
        self.assertIn('data-motif="schema_unifilaire"', section)
        # Le HTML échappe l'apostrophe du motif (``html.escape``) : on le
        # cherche tel que la section l'émet.
        self.assertIn(escape(MOTIF_SCHEMA_INDISPONIBLE[:-1]), section)
        self.assertIn(MOTIF_SCHEMA_INDISPONIBLE[:-1],
                      _sans_espaces(' '.join(_texte(octets))))

    def test_dossier_reglementaire_reutilise_la_meme_piece_schema(self):
        from apps.calepinage.services.rapport import electrique
        from apps.calepinage.services.reglementaire import _rendus_du_module

        with mock.patch.object(electrique, 'bloc_schema_unifilaire',
                               wraps=electrique.bloc_schema_unifilaire) as fn:
            octets = rendre_rapport(self.calepinage, **OPTIONS)
            piece = _rendus_du_module(
                self.calepinage, self.company)['schema_unifilaire']()
        self.assertEqual(fn.call_count, 2)
        nombre = _pages(piece)
        self.assertEqual(_texte(octets)[-nombre:], _texte(piece))

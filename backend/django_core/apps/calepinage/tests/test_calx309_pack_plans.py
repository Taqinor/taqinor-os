"""CALX309 — le plan de toiture et le plan de masse ENTRENT dans le dossier
technique.

Le Constat était vérifié : ``SPEC_PIECES`` déclarait quatre pièces
(``services/pack_technique.py:50-55``) mais ``_rendus`` n'en mappait que
deux — le dossier technique sortait donc TOUJOURS amputé du plan de toiture
et du plan de masse, alors que les deux rendus EXISTAIENT déjà et étaient
servis en HTTP (``services/planche.rendre_plan_pdf``,
``views/sorties.py:250-266``).

Deux niveaux d'essais, comme CAL181 (``test_cal181_pack.py``) :

1. PUR, verrouille le bug EXACT du Constat — ``_rendus`` (fonction privée,
   c'est SA fuite que le Constat documente) doit déclarer un rendu pour
   CHACUN des quatre codes de ``SPEC_PIECES``, plus précisément pour
   ``plan_toiture`` et ``plan_masse``.
2. PUR mais RÉEL — ``rendre_pieces`` exerce le CÂBLAGE de production
   (``rendus=None``, donc ``_rendus`` par défaut). ``planche`` et
   ``note_calcul`` sont mockés (leurs propres essais couvrent déjà leur
   rendu ; ``note_calcul`` lit en base la société — hors de portée d'un essai
   pur ici) ; le plan de toiture ET le plan de masse traversent leur VRAI
   chemin (``rendre_plan_pdf`` → ``rendre_plan_svg`` →
   ``geometrie_de_planche``, tous purs) — seul ``core.pdf.render_pdf``
   (WeasyPrint, absent de certains postes) est mocké, même patron que
   ``test_cal174_endpoints_planche.py``. Le plan de masse SANS parcelle lève
   donc sa VRAIE ``PlancheRefusee`` (``services/planche.py``), et c'est ELLE
   que ``rendre_pieces`` reporte en signalement — aucun motif réinventé ici.

Run :
    python manage.py test apps.calepinage.tests.test_calx309_pack_plans -v2
"""
from unittest import mock, skipUnless

from django.test import SimpleTestCase

from apps.calepinage.services import pack_technique
from apps.calepinage.services.pack_technique import SPEC_PIECES, rendre_pieces

from .test_cal171_planche import LAYOUT
from .test_cal173_empreinte import FauxCalepinage
from .test_cal194_plans import layout_avec_parcelle

try:
    import fitz  # PyMuPDF
    _FITZ = True
except ImportError:  # pragma: no cover - dépend de l'environnement
    fitz = None
    _FITZ = False


def pdf_de(pages):
    """Un VRAI PDF de ``pages`` pages — même fabrique que CAL181."""
    document = fitz.open()
    for _ in range(pages):
        document.new_page()
    octets = document.tobytes()
    document.close()
    return octets


class RendusDeclareLesQuatrePiecesTest(SimpleTestCase):
    """Le bug EXACT du Constat, verrouillé : ``_rendus`` doit déclarer un
    rendu pour CHAQUE code de ``SPEC_PIECES`` — un écart y ramènerait le
    dossier technique amputé, en silence, comme avant CALX309.
    """

    def test_les_quatre_codes_de_spec_pieces_ont_tous_un_rendu(self):
        rendus = pack_technique._rendus(FauxCalepinage(), 'societe-essai')
        codes_declares = {code for code, _libelle, _oblig in SPEC_PIECES}
        self.assertEqual(set(rendus), codes_declares)

    def test_le_plan_de_toiture_et_le_plan_de_masse_sont_branches(self):
        rendus = pack_technique._rendus(FauxCalepinage(), 'societe-essai')
        self.assertIn('plan_toiture', rendus)
        self.assertIn('plan_masse', rendus)


@skipUnless(_FITZ, 'PyMuPDF absent de cet environnement')
class DossierTechniqueAvecEtSansParcelleTest(SimpleTestCase):
    """``rendre_pieces`` avec le câblage RÉEL (``rendus=None``)."""

    def setUp(self):
        patch_planche = mock.patch(
            'apps.calepinage.services.planche.rendre_planche_pdf',
            return_value=pdf_de(1))
        patch_note = mock.patch(
            'apps.calepinage.services.note_calcul.rendre_note_calcul',
            return_value=pdf_de(2))
        # CALX326 — ``_rendus`` branche désormais TROIS pièces de plus
        # (rapport d'étude, plan de câblage, rapport d'ombrage) : ce test ne
        # les exerce pas (leur propre câblage est verrouillé par
        # ``test_calx326_pack_etendu.py``), donc elles sont mockées comme
        # ``planche``/``note_calcul`` ci-dessus, plutôt que de laisser leur
        # VRAI refus (aucun résultat/chaîne/ombrage sur ``FauxCalepinage``)
        # ajouter trois signalements imprévus ici.
        patch_rapport = mock.patch(
            'apps.calepinage.services.rapport.rendre_rapport',
            return_value=pdf_de(1))
        patch_cablage = mock.patch(
            'apps.calepinage.services.documents.plan_cablage'
            '.rendre_plan_cablage_pdf', return_value=pdf_de(1))
        patch_ombrage = mock.patch(
            'apps.calepinage.services.rapport_ombrage.rendre_rapport_ombrage',
            return_value=pdf_de(1))
        # Seul WeasyPrint est mocké — le plan de toiture/masse garde son VRAI
        # chemin (SVG + parcelle) jusqu'ici, même patron que
        # test_cal174_endpoints_planche.py.
        patch_render_pdf = mock.patch('core.pdf.render_pdf',
                                      return_value=pdf_de(1))
        for patch in (patch_planche, patch_note, patch_rapport,
                      patch_cablage, patch_ombrage, patch_render_pdf):
            patch.start()
            self.addCleanup(patch.stop)

    def test_avec_parcelle_le_dossier_compte_quatre_pieces(self):
        calepinage = FauxCalepinage(roof_layout=layout_avec_parcelle())
        pieces, signalements = rendre_pieces(calepinage,
                                             company='societe-essai')
        self.assertEqual(
            [code for code, _l, _o, _p in pieces],
            ['planche', 'note_calcul', 'plan_toiture', 'plan_masse',
             'rapport_etude', 'plan_cablage', 'rapport_ombrage'])
        # `pages` (posé par `rendre_pieces` via `compter_pages`, ARC11) doit
        # correspondre au VRAI comptage des octets rendus — ici de VRAIS PDF
        # PyMuPDF (fabriqués par les mocks), pas une valeur inventée.
        for _code, _libelle, octets, pages in pieces:
            self.assertEqual(pack_technique.compter_pages(octets), pages)
        self.assertEqual(sum(pages for _c, _l, _o, pages in pieces), 8)
        self.assertEqual(signalements, [])

    def test_sans_parcelle_le_dossier_compte_trois_pieces_et_signale(self):
        calepinage = FauxCalepinage(roof_layout=LAYOUT)  # aucune parcelle
        pieces, signalements = rendre_pieces(calepinage,
                                             company='societe-essai')
        self.assertEqual(
            [code for code, _l, _o, _p in pieces],
            ['planche', 'note_calcul', 'plan_toiture', 'rapport_etude',
             'plan_cablage', 'rapport_ombrage'])
        self.assertEqual(sum(pages for _c, _l, _o, pages in pieces), 7)
        self.assertEqual(len(signalements), 1)
        self.assertIn('parcelle', signalements[0].lower())

"""ACAL235 - la mention conception verrouillee / archivee sur TOUS les PDF.

L'etat est LU par ``gabarit_document.etat_de_conception`` (verrou du devis
lie, corbeille) - ici les trois lectures (verrou, archive, entree de corbeille)
sont les seams documentes de ``test_calx325_mention_verrou.py`` : les sept
pieces sont comparees sur le TEXTE qu'elles impriment (pied de planche SVG,
corps HTML de la note et de la presentation), sans rendu PDF.

Run :
    python manage.py test apps.calepinage.tests.test_acal_mention_etat_pdf -v2
"""
import copy
import datetime
import json
import pathlib
from html import escape
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services.documents.gabarit_document import (
    MENTION_ARCHIVE, MENTION_VERROUILLE,
)
from apps.calepinage.services.documents.plan_cablage import (
    _rendre_plan_cablage_svg,
)
from apps.calepinage.services.documents.presentation_compacte import (
    _construire_presentation, _html_de_presentation,
)
from apps.calepinage.services.note_calcul import (
    _construire_note_calcul, _html_de_note_calcul,
)
from apps.calepinage.services.planche import (
    CONTENU_MASSE, CONTENU_TOITURE, rendre_plan_pose_svg, rendre_plan_svg,
    rendre_planche_svg,
)

from .acal_livrables_helpers import LAYOUT_PLANCHE_SIMULABLE, patch_materiel
from .test_cal173_empreinte import MOMENT

ECHANTILLON = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'calepinage_resultat.json').read_text(encoding='utf-8'))['exemple']
ENVOI = datetime.datetime(2026, 9, 12, 9, 0, tzinfo=datetime.timezone.utc)
ARCHIVAGE = datetime.datetime(2026, 9, 20, 9, 0,
                              tzinfo=datetime.timezone.utc)
VERROUILLE = escape(MENTION_VERROUILLE.format(date='12/09/2026'))
ARCHIVE = escape(MENTION_ARCHIVE.format(date='20/09/2026'))


def calepinage():
    layout = copy.deepcopy(LAYOUT_PLANCHE_SIMULABLE)
    layout['parcelle'] = {'vertices': [[-7.6002, 33.4998], [-7.5997, 33.4998],
                                       [-7.5997, 33.5003],
                                       [-7.6002, 33.5003]]}
    return SimpleNamespace(
        pk=7, company_id=1, company=None, client_id=None, lead_id=None,
        titre='Villa essai', roof_layout=layout, layout_hash='a' * 64,
        version_moteur='calepinage-1.0.0', resultat=None, devis_id=None,
        devis=SimpleNamespace(date_envoi=ENVOI), archive_le=ARCHIVAGE)


def etat_lu(verrouille, archive):
    """Les deux lectures de ``etat_de_conception``, bornees aux seams (la
    date d'archivage est ``archive_le`` du pivot, ACAL118)."""
    return (
        mock.patch('apps.calepinage.services.verrou.est_verrouille',
                   return_value=verrouille),
        mock.patch('apps.calepinage.services.archivage.est_archive',
                   return_value=archive),
    )


def sept_rendus_texte(cal):
    """``code -> texte imprime`` des sept pieces PDF du module."""
    from apps.calepinage.services.documents.gabarit_document import (
        etat_de_conception,
    )

    etat = etat_de_conception(cal)
    note = _construire_note_calcul(copy.deepcopy(ECHANTILLON),
                                   site={'ville': 'x'}, etat=etat)
    presentation = _construire_presentation(
        cal, resultat=copy.deepcopy(ECHANTILLON),
        roof_layout=cal.roof_layout, svg_planche='', styles={}, etat=etat)
    with patch_materiel():
        plan_pose = rendre_plan_pose_svg(cal, moment=MOMENT)
        # Le plan de câblage REFUSE une conception sans chaîne publiée
        # (CALX310) : l'affectation est celle du résultat SERVI, matériel
        # connu — jamais une liste vide injectée.
        plan_cablage = _rendre_plan_cablage_svg(cal, moment=MOMENT)
    return {
        'planche': rendre_planche_svg(cal, moment=MOMENT),
        'plan_pose': plan_pose,
        'plan_toiture': rendre_plan_svg(cal, contenu=CONTENU_TOITURE,
                                        moment=MOMENT),
        'plan_masse': rendre_plan_svg(cal, contenu=CONTENU_MASSE,
                                      moment=MOMENT),
        'note_calcul': _html_de_note_calcul(note),
        'plan_cablage': plan_cablage,
        'presentation_compacte': _html_de_presentation(presentation),
    }


def _lus(verrouille, archive):
    verrou, archivage = etat_lu(verrouille, archive)
    with verrou, archivage:
        return sept_rendus_texte(calepinage())


class MentionsSurLesSeptPiecesTest(SimpleTestCase):
    def test_chaque_pdf_porte_la_mention_verrouille(self):
        for code, texte in _lus(True, False).items():
            with self.subTest(piece=code):
                self.assertIn(VERROUILLE, texte)
                self.assertNotIn('archivée le', texte)

    def test_chaque_pdf_porte_la_mention_archive(self):
        for code, texte in _lus(False, True).items():
            with self.subTest(piece=code):
                self.assertIn(ARCHIVE, texte)
                self.assertNotIn('verrouillée depuis', texte)

    def test_conception_courante_sans_mention(self):
        for code, texte in _lus(False, False).items():
            with self.subTest(piece=code):
                self.assertNotIn('verrouillée depuis', texte)
                self.assertNotIn('archivée le', texte)

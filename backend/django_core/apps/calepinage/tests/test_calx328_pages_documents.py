"""CALX328 — verrouiller le nombre de pages attendu de CHAQUE document.

Le Constat était vérifié : le SEUL contrôle de pages du dépôt compare la
fusion du dossier technique à la somme de ses pièces
(``services/pack_technique.py`` ``rendre_pieces``/``pages_attendues``) —
AUCUNE pièce n'a de nombre de pages ATTENDU en soi, donc une section vide
qui grossit un document (garde dupliquée, boucle de rendu) ne se voit pas.

Deux niveaux d'essais, comme CALX306/CALX315/CALX297/CALX316/CALX318 :

1. PUR (ici, exécutable partout, ``python -m pytest``) — la déclaration
   ``INTERVALLES`` elle-même est bien formée (borne basse ⩽ borne haute, un
   motif non vide par document, les six documents du lot couverts).
2. RÉEL (WeasyPrint + PyMuPDF, ``@tag('pdf')``, hors du palier CI léger —
   image de production) — pour CHAQUE document : le compte de pages du PDF
   RENDU tombe dans son intervalle déclaré (présentation compacte : EXACTEMENT
   deux pages, densité adaptative, CALX315) ; ET aucune page — sur AUCUN des
   six documents — n'a un texte extrait VIDE (une section omise imprime son
   motif, jamais un blanc : ``services/rapport/__init__.py`` ``_html_section``,
   même règle partout dans le module).

Les fixtures (calepinage NU, résultat de l'exemple du contrat, gabarit,
écarts, roof_layout d'ombrage) sont les MÊMES que celles déjà posées par
CALX297/CALX315/CALX316/CALX317/CALX318 — aucune n'est réinventée ici.

Run (structure, pur, sans WeasyPrint) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx328_pages_documents.py -q

Run (avec rendu réel, image prod dotée de WeasyPrint) :
    python manage.py test \
        apps.calepinage.tests.test_calx328_pages_documents -v2
"""
import copy
import json
import pathlib
import unittest
from types import SimpleNamespace

from django.test import tag

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLON = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))

SITE = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle',
        'source': 'roof_point', 'pin': None, 'outline': None}
IDENTITE = {'titre_document': 'Document', 'projet': 'Villa Anfa',
            'client': 'Mme Bennani', 'produit_le': '23/09/2026'}
STYLES = {'nom_affiche': 'Soleil Atlas', 'logo_url': '',
          'couleur_primaire': '', 'couleur_secondaire': ''}

#: Même matrice 12×24 « plate » que ``test_calx317_rapport_ombrage.py`` —
#: une conception sans ombrage n'a pas besoin de valeurs variées pour publier
#: un rapport.
MATRICE_12X24 = [[0.6] * 24 for _ in range(12)]
#: Un ``roof_layout`` valide (matrice + zones, même patron que
#: ``AvertissementSansCourseDuSoleilTest`` de CALX317) — les zones VIDES
#: suffisent : le rapport d'ombrage retombe sur la méthode CALCULÉE.
ROOF_LAYOUT_OMBRAGE = {'shading12x24': MATRICE_12X24, 'zones': []}

#: Gabarit « manuel » minimal, deux champs texte — même patron que
#: ``GABARIT_CONSIGNES`` de CALX316.
GABARIT_MANUEL = SimpleNamespace(intitule='Manuel standard', champs=[
    {'code': 'consignes_securite', 'libelle': 'Consignes de sécurité',
     'type': 'texte',
     'texte': ("Couper l'onduleur {{onduleurs}} avant toute intervention. "
               "{{nombre_chaines}} chaîne(s).")},
    {'code': 'consignes_arret', 'libelle': "Consignes d'arrêt",
     'type': 'texte', 'texte': 'Modules retenus : {{modules}}.'},
])

#: Écarts prévu/posé, 2 pans — même forme que ``ECARTS_3_PANS_1_RELEVE`` de
#: CALX318, réduite à deux pans (un relevé, un non relevé).
ECARTS_ASBUILT = {
    'calepinage': None,
    'source_prevu': 'variante retenue',
    'pans': [
        {'pan': 'Pan Sud', 'prevu': 12, 'pose': 11, 'ecart': -1,
         'ecarts_position': 'Une rangée décalée vers le faîtage',
         'releve_le': '2026-09-19', 'mention': ''},
        {'pan': 'Pan Nord', 'prevu': 6, 'pose': None, 'ecart': None,
         'ecarts_position': '', 'releve_le': None,
         'mention': 'Aucun relevé de terrain saisi pour ce pan.'},
    ],
    'pans_releves': 1,
    'total_prevu': 18,
    'total_pose': 11,
    'ecart_total': -1,
}


def _resultat():
    return copy.deepcopy(ECHANTILLON['exemple'])


#: ``INTERVALLES[code] = (min_pages, max_pages, motif)`` — un intervalle
#: DÉCLARÉ avec son motif, jamais un chiffre nu. Les cinq documents dont la
#: mise en page est un FLUX CONTINU (aucun ``page-break-before`` entre
#: sections, à la différence de la version paginée de CALX306) : le compte
#: réel dépend de la densité de contenu, d'où un intervalle plutôt qu'un
#: nombre exact.
INTERVALLES = {
    'note_calcul': (
        1, 6,
        "sept sections en flux continu (garde, verdict de preuve, site, "
        "pose, chaînes, pertes, production, avertissements) sans saut de "
        "page forcé : jamais vide, jamais une dérive à des dizaines de "
        "pages pour l'exemple du contrat."),
    'rapport_etude': (
        2, 10,
        "dix blocs (garde + neuf sections) en flux continu — jamais un "
        "document d'une seule page pour neuf sections, jamais au-delà de "
        "dix pages pour l'exemple du contrat."),
    'rapport_ombrage': (
        1, 6,
        "garde, un bloc par pan (deux pans dans l'exemple), la matrice "
        "12×24, ses moyennes mensuelles et le profil d'horizon, en flux "
        "continu : jamais vide, jamais une pile de pages pour deux pans."),
    'document_asbuilt': (
        1, 5,
        "garde et table d'écarts pour deux pans (aucune photo dans "
        "l'exemple) : jamais vide, jamais plusieurs pages par pan pour un "
        "relevé aussi modeste."),
    'manuel_proprietaire': (
        1, 5,
        "garde et une section par champ de gabarit renseigné (deux champs "
        "texte dans l'exemple) : jamais vide, jamais au-delà de cinq pages "
        "pour un gabarit aussi modeste."),
}

#: La présentation compacte est un cas À PART : densité ADAPTATIVE conçue
#: pour ne JAMAIS déborder de deux pages (CALX315) — un nombre EXACT, pas un
#: intervalle.
PAGES_PRESENTATION_COMPACTE = 2

#: Les six documents du lot 6 que CALX328 verrouille.
DOCUMENTS_VERROUILLES = tuple(INTERVALLES) + ('presentation_compacte',)


class DeclarationDesIntervallesTest(unittest.TestCase):
    """PUR — la déclaration elle-même est bien formée. Tourne PARTOUT, sans
    WeasyPrint : c'est le contrat que le rendu réel (ci-dessous) doit tenir.
    """

    def test_les_six_documents_du_lot_sont_couverts(self):
        self.assertEqual(set(DOCUMENTS_VERROUILLES),
                         {'note_calcul', 'rapport_etude', 'rapport_ombrage',
                          'document_asbuilt', 'manuel_proprietaire',
                          'presentation_compacte'})

    def test_chaque_intervalle_est_borne_bas_inferieur_ou_egal_au_haut(self):
        for code, (minimum, maximum, motif) in INTERVALLES.items():
            with self.subTest(document=code):
                self.assertGreaterEqual(minimum, 1)
                self.assertLessEqual(minimum, maximum)
                self.assertTrue(motif.strip(), 'motif vide pour %s' % code)

    def test_la_presentation_compacte_est_un_compte_exact_pas_un_intervalle(
            self):
        self.assertEqual(PAGES_PRESENTATION_COMPACTE, 2)


@tag('pdf')
class RenduReelPagesTest(unittest.TestCase):
    """WeasyPrint + PyMuPDF réels — étiqueté ``pdf`` (hors du palier CI —
    routeur M4). Chaque document est rendu avec les MÊMES fixtures pures
    (aucune base) que CALX297/CALX315/CALX316/CALX317/CALX318."""

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 — bibliothèques natives absentes
            self.skipTest('WeasyPrint ou PyMuPDF indisponible sur ce poste')

    # ── Le rendu de chacun des six documents, fixtures PURES ────────────────

    def _octets_note_calcul(self):
        from apps.calepinage.services.note_calcul import rendre_note_calcul

        nu = SimpleNamespace(company=None, pk=None, titre='Villa Anfa',
                             resultat=_resultat())
        return rendre_note_calcul(nu, site=SITE, identite=IDENTITE,
                                  styles=STYLES)

    def _octets_rapport_etude(self):
        from apps.calepinage.services.rapport import rendre_rapport

        nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                             titre='Villa Anfa', resultat=None, pk=None)
        return rendre_rapport(nu, resultat=_resultat(), site=SITE,
                              identite=IDENTITE, styles=STYLES)

    def _octets_rapport_ombrage(self):
        from apps.calepinage.services.rapport_ombrage import (
            rendre_rapport_ombrage,
        )

        nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                             titre='Villa Anfa', pk=None,
                             roof_layout=ROOF_LAYOUT_OMBRAGE)
        return rendre_rapport_ombrage(nu, resultat=_resultat(), site=SITE,
                                      identite=IDENTITE, styles=STYLES,
                                      etat={})

    def _octets_document_asbuilt(self):
        from apps.calepinage.services.documents.document_asbuilt import (
            rendre_document_asbuilt,
        )

        nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                             titre='Villa Anfa', pk=None, layout_hash='',
                             version_moteur='')
        return rendre_document_asbuilt(
            nu, ecarts=ECARTS_ASBUILT, photos=[], svg_planche='', site=SITE,
            identite=IDENTITE, styles=STYLES)

    def _octets_manuel_proprietaire(self):
        from apps.calepinage.services.documents.manuel_proprietaire import (
            rendre_manuel,
        )

        nu = SimpleNamespace(company=None, client_id=None, lead_id=None,
                             titre='Villa Anfa', pk=None, resultat=None)
        return rendre_manuel(nu, resultat=_resultat(), gabarit=GABARIT_MANUEL,
                             site=SITE, identite=IDENTITE, styles=STYLES)

    def _octets_presentation_compacte(self):
        from apps.calepinage.services.documents.presentation_compacte import (
            rendre_presentation_compacte,
        )

        from .test_cal171_planche import LAYOUT

        nu = SimpleNamespace(company=None, pk=None, titre='Villa Anfa',
                             resultat=None, layout_hash='',
                             version_moteur='')
        return rendre_presentation_compacte(
            nu, resultat=_resultat(), roof_layout=LAYOUT, svg_planche='',
            styles=STYLES)

    def _tous_les_documents(self):
        return {
            'note_calcul': self._octets_note_calcul(),
            'rapport_etude': self._octets_rapport_etude(),
            'rapport_ombrage': self._octets_rapport_ombrage(),
            'document_asbuilt': self._octets_document_asbuilt(),
            'manuel_proprietaire': self._octets_manuel_proprietaire(),
            'presentation_compacte': self._octets_presentation_compacte(),
        }

    # ── Le compte de pages tombe dans l'intervalle DÉCLARÉ ──────────────────

    def test_presentation_compacte_deux_pages_exactement(self):
        from apps.calepinage.services.pack_technique import compter_pages

        pages = compter_pages(self._octets_presentation_compacte())
        self.assertEqual(
            pages, PAGES_PRESENTATION_COMPACTE,
            'densité adaptative (CALX315) : jamais une page, jamais trois — '
            'obtenu %d' % pages)

    def test_chaque_document_a_intervalle_est_dans_sa_fourchette(self):
        from apps.calepinage.services.pack_technique import compter_pages

        octets_par_code = {
            'note_calcul': self._octets_note_calcul,
            'rapport_etude': self._octets_rapport_etude,
            'rapport_ombrage': self._octets_rapport_ombrage,
            'document_asbuilt': self._octets_document_asbuilt,
            'manuel_proprietaire': self._octets_manuel_proprietaire,
        }
        for code, (minimum, maximum, motif) in INTERVALLES.items():
            with self.subTest(document=code):
                pages = compter_pages(octets_par_code[code]())
                self.assertGreaterEqual(
                    pages, minimum,
                    '« %s » : %d page(s), attendu ⩾ %d — %s'
                    % (code, pages, minimum, motif))
                self.assertLessEqual(
                    pages, maximum,
                    '« %s » : %d page(s), attendu ⩽ %d — %s'
                    % (code, pages, maximum, motif))

    # ── AUCUNE page blanche, sur AUCUN des six documents ────────────────────

    def test_aucune_page_blanche_sur_aucun_des_six_documents(self):
        import fitz

        from apps.calepinage.services.pack_technique import compter_pages

        for code, octets in self._tous_les_documents().items():
            with self.subTest(document=code):
                self.assertGreater(compter_pages(octets), 0,
                                   '« %s » : PDF illisible ou vide' % code)
                document = fitz.open(stream=octets, filetype='pdf')
                try:
                    for numero, page in enumerate(document, start=1):
                        texte = page.get_text().strip()
                        self.assertTrue(
                            texte,
                            '« %s » : la page %d n’a AUCUN texte extrait — '
                            'une section omise doit imprimer son motif, '
                            'jamais un blanc.' % (code, numero))
                finally:
                    document.close()


if __name__ == '__main__':  # pragma: no cover
    unittest.main()

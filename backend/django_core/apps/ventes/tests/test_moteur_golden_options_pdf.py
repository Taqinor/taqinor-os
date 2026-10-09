"""SPL160 (b) — golden de CARACTÉRISATION DIRECTE de ``clean_pdf_options``
(capture seule, aucun déplacement).

Correction CODE-FACTS : le hachage de ``build_quote_data`` (SPL160 (a)) ne voit
pas toute la liste blanche (un drapeau qui ne change pas le dict de rendu d'une
fixture passerait inaperçu). Ce module caractérise donc la fonction ELLE-MÊME
sur une matrice d'entrées brutes — chaque clé de ``DEFAULT_PDF_OPTIONS``,
valeurs invalides, jeton de partage valide / invalide / trop court / trop long
contre ``_SHARE_TOKEN_RE``, ``langue_sortie`` « xx », ``variante_option`` hors
``VARIANTES_PDF``, entrée non-dict — et fige ``DEFAULT_PDF_OPTIONS``,
``LANGUES_SORTIE_PDF`` et ``VARIANTES_PDF`` verbatim dans
``golden/moteur/options_pdf.json``.

Capture : ``UPDATE_GOLDEN=1`` (une fois, sur la pointe de main au démarrage de
la scission) ; une tâche SPL ne re-capture JAMAIS. Golden absent ⇒ rouge.
Aucun mock : la vraie fonction est appelée.
"""
import json
import os
from pathlib import Path

from django.test import SimpleTestCase

GOLDEN = (Path(__file__).resolve().parent / 'golden' / 'moteur'
          / 'options_pdf.json')

JETON_OK = 'Ab3_-xY9' * 2          # 16 caractères admis
MATRICE = [
    ('vide', {}),
    ('none', None),
    ('pdf_mode_onepage', {'pdf_mode': 'onepage'}),
    ('pdf_mode_full', {'pdf_mode': 'full'}),
    ('pdf_mode_invalide', {'pdf_mode': 'trois_pages'}),
    ('show_monthly_faux', {'show_monthly': False}),
    ('show_monthly_chaine', {'show_monthly': 'non'}),
    ('devis_final_vrai', {'devis_final': True}),
    ('devis_final_zero', {'devis_final': 0}),
    ('include_etude_vrai', {'include_etude': True}),
    ('include_annexe_none', {'include_annexe_technique': None}),
    ('include_annexe_faux', {'include_annexe_technique': False}),
    ('include_annexe_un', {'include_annexe_technique': 1}),
    ('include_calepinage_none', {'include_calepinage': None}),
    ('include_calepinage_vrai', {'include_calepinage': True}),
    ('include_calepinage_chaine_vide', {'include_calepinage': ''}),
    ('include_note_calcul_vrai', {'include_note_calcul': True}),
    ('kit_agrege_vrai', {'kit_agrege': True}),
    ('variante_sans', {'variante_option': 'sans'}),
    ('variante_avec', {'variante_option': 'avec'}),
    ('variante_les_deux', {'variante_option': 'les_deux'}),
    ('variante_hors_liste', {'variante_option': 'mixte'}),
    ('langue_en', {'langue_sortie': 'en'}),
    ('langue_ar', {'langue_sortie': 'ar'}),
    ('langue_xx', {'langue_sortie': 'xx'}),
    ('jeton_valide', {'share_token': JETON_OK}),
    ('jeton_invalide', {'share_token': 'jeton invalide!'}),
    ('jeton_trop_court', {'share_token': 'abc1234'}),
    ('jeton_trop_long', {'share_token': 'a' * 129}),
    ('jeton_non_chaine', {'share_token': 12345678}),
    ('cle_inconnue', {'payment_mode': 'custom', 'custom_acompte': 50}),
    ('drapeau_serveur_ignore', {'_embed_roof_render': True,
                                '_embed_calepinage_planche': True,
                                'watermark': True}),
    ('tout_ensemble', {'pdf_mode': 'onepage', 'show_monthly': False,
                       'devis_final': True, 'include_etude': True,
                       'include_annexe_technique': True,
                       'include_calepinage': False,
                       'include_note_calcul': True, 'kit_agrege': True,
                       'variante_option': 'avec', 'langue_sortie': 'ar',
                       'share_token': JETON_OK}),
    ('entree_liste', ['pdf_mode', 'onepage']),
    ('entree_chaine', 'onepage'),
]


def capturer(clean_pdf_options, default_pdf_options, langues, variantes):
    """Le dict golden (fonction appelée réellement, exception = son type)."""
    cas = {}
    for nom, entree in MATRICE:
        try:
            cas[nom] = clean_pdf_options(entree)
        except Exception as exc:  # noqa: BLE001 — caractérisation
            cas[nom] = '<%s>' % type(exc).__name__
    return {
        'DEFAULT_PDF_OPTIONS': dict(default_pdf_options),
        'LANGUES_SORTIE_PDF': list(langues),
        'VARIANTES_PDF': list(variantes),
        'cas': cas,
    }


def _source():
    from apps.ventes.quote_engine import builder as b
    return capturer(b.clean_pdf_options, b.DEFAULT_PDF_OPTIONS,
                    b.LANGUES_SORTIE_PDF, b.VARIANTES_PDF)


class MoteurGoldenOptionsPdfTests(SimpleTestCase):

    def test_options_pdf_identiques_au_golden(self):
        reel = json.loads(json.dumps(_source(), sort_keys=True, default=str))
        if os.environ.get('UPDATE_GOLDEN') == '1':
            GOLDEN.parent.mkdir(parents=True, exist_ok=True)
            GOLDEN.write_text(json.dumps(reel, sort_keys=True, indent=2,
                                         ensure_ascii=False) + '\n',
                              encoding='utf-8')
        self.assertTrue(GOLDEN.is_file(),
                        'golden options_pdf.json non capturé : lancer une '
                        'fois UPDATE_GOLDEN=1 (voir la docstring)')
        attendu = json.loads(GOLDEN.read_text(encoding='utf-8'))
        self.assertEqual(reel, attendu)

    def test_matrice_couvre_chaque_cle_par_defaut(self):
        from apps.ventes.quote_engine.builder import DEFAULT_PDF_OPTIONS
        couvertes = set()
        for _nom, entree in MATRICE:
            if isinstance(entree, dict):
                couvertes |= set(entree)
        self.assertEqual(set(DEFAULT_PDF_OPTIONS) - couvertes, set())

"""CAD126 — « sur votre toit » ne part plus à un pompage au bord d'un forage.

Constat de l'audit L3 du 21/09/2026 : les textes sont 100 % résidentiels —
« vos panneaux posés sur votre toit » (``valeur_j1``, ``reveil_a1``,
``reveil_a3``), « la décision se prend en famille » (``dimanche_famille``),
« orientation du toit, charpente » (``visite_proposition`` /
``visite_confirmation``) — et partent sans filtre à tout
``type_installation``. Pour un pompage agricole il n'y a littéralement pas de
toit, et ``valeur_j1`` demande « votre facture », sans objet pour une
exploitation au butane. Pour un industriel, « en famille » ne correspond à
aucun processus d'achat — et le round 2 précise le vrai défaut :
``dimanche_famille`` EST filtré par l'étiquette « décision à plusieurs », donc
c'est un industriel TAGUÉ qui le reçoit.

Les variantes sont PAR EXCEPTION (jamais une matrice 27 × langues × segments)
et les textes sont RE-DÉRIVÉS de ``docs/crm/messages_meryem.md`` — la source
de vérité — comme le fait ``tests_mry12_messages_relance`` pour les textes de
base. Un écart entre le guide et le code casse ici.
"""
import pathlib

from django.test import SimpleTestCase

from apps.parametres.models_messages import (
    CLES_VARIANTES_SEGMENT, MESSAGE_TEMPLATE_DEFAULTS,
    MESSAGE_TEMPLATE_VARIANTES_SEGMENT, SEGMENTS_B2B, SEGMENT_POMPAGE,
    variante_segment,
)
from apps.parametres.tests_mry12_messages_relance import _convertir

#: Les mots qui MENTENT à un pompage ou à une entreprise. Le Done de la tâche
#: porte exactement sur eux.
MOTS_QUI_MENTENT = ('toit', 'famille', 'facture')

#: Les segments à qui ces mots ne doivent plus être affirmés.
SEGMENTS_EXPOSES = (SEGMENT_POMPAGE,) + tuple(SEGMENTS_B2B)

#: Étiquette du guide → segments concernés.
ETIQUETTES = {'POMPAGE': (SEGMENT_POMPAGE,), 'B2B': tuple(SEGMENTS_B2B)}


def _guide():
    ici = pathlib.Path(__file__).resolve()
    for parent in ici.parents:
        candidat = parent / 'docs' / 'crm' / 'messages_meryem.md'
        if candidat.exists():
            return candidat
    raise AssertionError(
        "docs/crm/messages_meryem.md introuvable — c'est la SOURCE DE VÉRITÉ "
        'des textes de relance, elle ne peut pas disparaître.')


def _variantes_du_guide():
    """``{etiquette: {cle: texte converti}}``, re-dérivé du guide."""
    lignes = _guide().read_text(
        encoding='utf-8').replace('\r\n', '\n').split('\n')
    trouvees = {etiquette: {} for etiquette in ETIQUETTES}
    cle = None
    for ligne in lignes:
        if ligne.startswith('### '):
            cle = ligne[4:].split(' ')[0].strip()
            continue
        for etiquette in ETIQUETTES:
            prefixe = etiquette + ' : '
            if cle and ligne.startswith(prefixe):
                trouvees[etiquette][cle] = _convertir(
                    ligne[len(prefixe):].strip())
    return trouvees


class LesVariantesSuiventLeGuideTests(SimpleTestCase):
    """Anti-divergence : le code ne s'écarte jamais du texte validé."""

    def setUp(self):
        self.guide = _variantes_du_guide()

    def test_le_guide_porte_bien_des_variantes(self):
        """Anti-faux-vert : un parseur muet rendrait tous les tests verts."""
        self.assertTrue(self.guide['POMPAGE'])
        self.assertTrue(self.guide['B2B'])

    def test_chaque_variante_du_guide_est_celle_du_code(self):
        for etiquette, segments in ETIQUETTES.items():
            for cle, texte in self.guide[etiquette].items():
                for segment in segments:
                    with self.subTest(etiquette=etiquette, cle=cle,
                                      segment=segment):
                        self.assertEqual(variante_segment(cle, segment),
                                         texte)

    def test_le_code_n_invente_aucune_variante_absente_du_guide(self):
        du_guide = {cle for textes in self.guide.values() for cle in textes}
        self.assertEqual(CLES_VARIANTES_SEGMENT, du_guide)

    def test_toute_cle_a_variante_existe_au_catalogue(self):
        for cle in CLES_VARIANTES_SEGMENT:
            with self.subTest(cle=cle):
                self.assertIn(cle, MESSAGE_TEMPLATE_DEFAULTS)


class AucunMotQuiMentTests(SimpleTestCase):
    """LE Done, paramétré par segment."""

    def test_les_mots_qui_mentent_sont_bien_dans_les_textes_DE_BASE(self):
        """Anti-faux-vert : si les textes de base ne les contenaient plus, ces
        tests passeraient sans rien prouver."""
        base = ' '.join(
            MESSAGE_TEMPLATE_DEFAULTS[cle] for cle in CLES_VARIANTES_SEGMENT
        ).lower()
        for mot in MOTS_QUI_MENTENT:
            with self.subTest(mot=mot):
                self.assertIn(mot, base)

    def test_aucune_cle_exposee_n_affirme_ces_mots_a_un_segment_expose(self):
        """AGR510 — la garde est passée PAR SEGMENT : chaque segment est
        vérifié sur les clés de SA table, et sur les textes de base qu'il
        reçoit pour les clés communes à tous les segments exposés (sans
        variante pour lui, c'est le texte de base qui part). Aucun mot n'est
        retiré de ``MOTS_QUI_MENTENT``."""
        communes = set.intersection(*(
            set(MESSAGE_TEMPLATE_VARIANTES_SEGMENT[s])
            for s in SEGMENTS_EXPOSES))
        self.assertTrue(communes)  # anti-faux-vert
        for segment in SEGMENTS_EXPOSES:
            cles = set(MESSAGE_TEMPLATE_VARIANTES_SEGMENT[segment]) | communes
            for cle in sorted(cles):
                texte = variante_segment(cle, segment)
                if texte is None:
                    # Pas de variante pour ce couple : le texte de base part,
                    # il ne doit alors contenir aucun mot piégé non plus.
                    texte = MESSAGE_TEMPLATE_DEFAULTS[cle]
                bas = texte.lower()
                for mot in MOTS_QUI_MENTENT:
                    with self.subTest(segment=segment, cle=cle, mot=mot):
                        self.assertNotIn(mot, bas)


class Agr510PompageTests(SimpleTestCase):
    """AGR510 — plus de facture, de toit, de promesse d'économie ni de
    « chez vous » pour un pompage ; « accord AVANT les travaux » pour la
    FDA, sans aucun chiffre."""

    def _tous_les_textes(self):
        from apps.parametres.models_messages import (
            MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
        )
        textes = dict(MESSAGE_TEMPLATE_DEFAULTS)
        textes.update({f'darija:{c}': t for c, t in
                       MESSAGE_TEMPLATE_DEFAULTS_DARIJA.items()})
        for segment, table in MESSAGE_TEMPLATE_VARIANTES_SEGMENT.items():
            textes.update({f'{segment}:{c}': t for c, t in table.items()})
        try:
            from apps.parametres.models_messages import (
                MESSAGE_TEMPLATE_VARIANTES_SEGMENT_DARIJA,
            )
        except ImportError:
            MESSAGE_TEMPLATE_VARIANTES_SEGMENT_DARIJA = {}
        for segment, table in MESSAGE_TEMPLATE_VARIANTES_SEGMENT_DARIJA.items():
            textes.update({f'darija-{segment}:{c}': t
                           for c, t in table.items()})
        return textes

    def test_les_cles_pompage_ont_leur_variante(self):
        for cle in ('valeur_j1', 'reveil_a1', 'reveil_a2', 'reveil_a3',
                    'rappel_plus_tard', 'debrief_visite', 'j4_preuve',
                    'visite_proposition'):
            with self.subTest(cle=cle):
                self.assertIsNotNone(variante_segment(cle, SEGMENT_POMPAGE))

    def test_aucune_variante_agricole_ne_promet_une_economie(self):
        for cle, texte in MESSAGE_TEMPLATE_VARIANTES_SEGMENT[
                SEGMENT_POMPAGE].items():
            with self.subTest(cle=cle):
                self.assertNotIn('économi', texte.lower())
                self.assertNotIn('chez vous', texte.lower())
                self.assertNotIn('3d', texte.lower())

    def test_aucun_texte_ne_dit_rembours_ni_un_pourcentage(self):
        import re
        pourcentage = re.compile(r'\d\s*%')
        for cle, texte in self._tous_les_textes().items():
            with self.subTest(cle=cle):
                self.assertNotIn('rembours', texte.lower())
                self.assertIsNone(pourcentage.search(texte))

    def test_dossier_fda_accord_avant_les_travaux_sans_chiffre(self):
        import re
        texte = MESSAGE_TEMPLATE_DEFAULTS['dossier_fda']
        self.assertIn('avant les travaux', texte)
        self.assertIsNone(re.search(r'\d', texte))

    def test_visite_proposition_pompage_mesure_l_eau(self):
        self.assertIn("mesurer le niveau et le débit de l'eau",
                      variante_segment('visite_proposition', SEGMENT_POMPAGE))

    def test_rappel_plus_tard_garde_ses_crochets(self):
        texte = variante_segment('rappel_plus_tard', SEGMENT_POMPAGE)
        self.assertIn('[jour]', texte)
        self.assertIn('[heure]', texte)

    def test_le_residentiel_garde_EXACTEMENT_ses_textes(self):
        """On ne casse pas le cas majoritaire pour servir les exceptions."""
        for cle in CLES_VARIANTES_SEGMENT:
            with self.subTest(cle=cle):
                self.assertIsNone(variante_segment(cle, 'residentiel'))
                self.assertIsNone(variante_segment(cle, ''))
                self.assertIsNone(variante_segment(cle, None))


class PortéeDesVariantesTests(SimpleTestCase):
    def test_industriel_et_commercial_partagent_les_MEMES_textes(self):
        for cle in MESSAGE_TEMPLATE_VARIANTES_SEGMENT['industriel']:
            with self.subTest(cle=cle):
                self.assertEqual(variante_segment(cle, 'industriel'),
                                 variante_segment(cle, 'commercial'))

    def test_aucune_matrice_complete_n_a_ete_fabriquee(self):
        """« uniquement les clés qui mentent » : la liste reste courte."""
        self.assertLess(len(CLES_VARIANTES_SEGMENT),
                        len(MESSAGE_TEMPLATE_DEFAULTS) // 2)

    def test_les_variantes_gardent_les_placeholders_du_texte_de_base(self):
        """Un placeholder perdu ferait disparaître le nom du conseiller."""
        import re
        for cle in CLES_VARIANTES_SEGMENT:
            attendus = set(re.findall(r'\{(\w+)\}',
                                      MESSAGE_TEMPLATE_DEFAULTS[cle]))
            for segment in SEGMENTS_EXPOSES:
                texte = variante_segment(cle, segment)
                if texte is None:
                    continue
                with self.subTest(cle=cle, segment=segment):
                    self.assertEqual(set(re.findall(r'\{(\w+)\}', texte)),
                                     attendus)

    def test_aucun_prenom_code_en_dur_dans_une_variante(self):
        for textes in MESSAGE_TEMPLATE_VARIANTES_SEGMENT.values():
            for cle, texte in textes.items():
                with self.subTest(cle=cle):
                    self.assertNotIn('Meryem', texte)
                    self.assertNotIn('Reda', texte)
                    self.assertNotIn('TAQINOR', texte)

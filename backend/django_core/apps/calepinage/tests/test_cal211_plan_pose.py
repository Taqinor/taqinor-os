"""CAL211 — le plan de pose de l'équipe terrain : aucun montant, l'empreinte.

L'app terrain a ses PDF (assemblage, livraison) mais aucun plan d'implantation :
l'équipe travaille sans la planche. Cette variante lui donne ce qu'il lui faut —
repères de RANGÉE, SENS DE POSE, LISTE DES CHAÎNES — et rien d'autre.

Ce qui est prouvé (essais PURS) :

* le plan de pose ne porte AUCUN montant, ni `prix_achat` : la garde REFUSE le
  document plutôt que de filtrer en silence ;
* il porte l'empreinte du calepinage (CAL173), donc il reste rattachable à sa
  conception ;
* les repères de rangée viennent de la SEULE définition de « rangée » du module
  (celle de CAL179) — deux définitions feraient diverger le plan de l'équipe et
  le tableau du bureau d'études ;
* l'emplacement des onduleurs n'est PAS dessiné : la donnée n'existe pas, et un
  onduleur posé à un endroit plausible enverrait une équipe percer le mauvais
  mur. Le bandeau le dit en toutes lettres.

Run :
    python manage.py test apps.calepinage.tests.test_cal211_plan_pose -v2
"""
import copy
import html
import json
import math
import pathlib
import re
import textwrap
from unittest import mock

from html import escape

from django.test import SimpleTestCase

from apps.calepinage.services.rangees import rangees_du_pan
from apps.calepinage.services.planche import (
    CARACTERES_PAR_LIGNE_LEGENDE, CONTENU_IMPLANTATION, CONTENU_POSE, CONTENU_TOITURE, GRIS_MODULE,
    PlanDePoseRefuse,
    geometrie_de_planche,
    _lignes_de_chaines, _rendre_plan_pose_svg, svg_de_planche,
    _verifier_absence_d_argent,
)

from .acal_livrables_helpers import (
    LAYOUT_PLANCHE_SIMULABLE, MATERIEL, calepinage_simule_reel,
    patch_materiel, texte_des_lignes_svg,
)
from .test_cal171_planche import LAYOUT
from .test_cal173_empreinte import MOMENT, FauxCalepinage

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
RESULTAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))['exemple']


def calepinage_de_pose():
    """ACAL216 - un calepinage SIMULE par les vrais ecrivains : le plan de
    pose lit le resultat SERVI, jamais le contrat colle dans la colonne."""
    simule = calepinage_simule_reel(LAYOUT_PLANCHE_SIMULABLE)
    calepinage = FauxCalepinage(roof_layout=simule.roof_layout)
    calepinage.resultat = simule.resultat
    return calepinage


def plan_de_pose_svg(calepinage, **options):
    """Le plan de pose, materiel injecte (le stock n'a pas de base ici)."""
    with patch_materiel():
        return _rendre_plan_pose_svg(calepinage, moment=MOMENT, **options)


class AucunMontantTest(SimpleTestCase):
    def test_le_plan_de_pose_ne_porte_aucun_montant(self):
        svg = plan_de_pose_svg(calepinage_de_pose())
        for interdit in ('prix', 'prix_achat', 'MAD', 'montant', 'Tarif'):
            self.assertNotIn(interdit.lower(), svg.lower())

    def test_la_garde_refuse_un_document_qui_porterait_un_prix(self):
        with self.assertRaises(PlanDePoseRefuse) as capture:
            _verifier_absence_d_argent('<svg><text>Module 720 Wc — 1 200 MAD'
                                       '</text></svg>')
        self.assertIn('montant', str(capture.exception).lower())

    def test_un_resultat_qui_charrie_un_prix_fait_refuser_le_plan(self):
        avec_prix = copy.deepcopy(MATERIEL)
        avec_prix['designations']['onduleur'] = 'ONDULEUR 10 kW (prix sur demande)'
        calepinage = calepinage_de_pose()
        with mock.patch(
                'apps.calepinage.services.electrique.resoudre_materiel',
                return_value=avec_prix):
            with self.assertRaises(PlanDePoseRefuse):
                _rendre_plan_pose_svg(calepinage, moment=MOMENT)


class EmpreinteEtCheminTest(SimpleTestCase):
    def test_le_plan_de_pose_porte_l_empreinte_du_calepinage(self):
        svg = plan_de_pose_svg(calepinage_de_pose())
        self.assertIn('calepinage aaaaaaaaaaaa', svg)
        self.assertIn('moteur calepinage-1.0.0', svg)

    def test_le_titre_nomme_la_piece(self):
        svg = plan_de_pose_svg(calepinage_de_pose())
        self.assertIn('Plan de pose', svg)


class ReperesDePoseTest(SimpleTestCase):
    def setUp(self):
        self.geometrie = geometrie_de_planche(LAYOUT)
        self.svg = svg_de_planche(self.geometrie, contenu=CONTENU_POSE)

    def test_les_reperes_de_rangee_sont_sur_le_plan(self):
        self.assertIn('>R1</text>', self.svg)

    def test_la_numerotation_est_celle_du_tableau(self):
        # UNE seule définition de « rangée » : celle de CAL179.
        pan = self.geometrie['pans'][0]
        numeros = set(rangees_du_pan(pan['modules'],
                                     pan['azimut_deg']).values())
        for numero in numeros:
            self.assertIn('>R%d</text>' % numero, self.svg)

    def test_le_sens_de_pose_est_trace_quand_il_est_deductible(self):
        # Deux modules alignés -> une flèche ; la rangée d'un seul module n'en
        # porte aucune (il n'y a pas de sens à déduire).
        self.assertIn('stroke-dasharray="1 0.8"', self.svg)

    def test_un_pan_d_un_seul_module_ne_trace_aucun_sens(self):
        layout = copy.deepcopy(LAYOUT)
        layout['zones'][0]['geometry']['panels'] = [{'cx': 1.0, 'cy': 1.0}]
        svg = svg_de_planche(geometrie_de_planche(layout),
                             contenu=CONTENU_POSE)
        self.assertIn('>R1</text>', svg)
        self.assertNotIn('stroke-dasharray="1 0.8"', svg)

    def test_les_reperes_n_apparaissent_pas_sur_les_autres_plans(self):
        toiture = svg_de_planche(self.geometrie, contenu=CONTENU_TOITURE)
        self.assertNotIn('>R1</text>', toiture)


MOTIF_Z2 = ("Le retrait de rive laisse 0,9 m utiles : moins qu'un module "
            "(1,13 m).")


def layout_pan_vide(motif=True, modules_z2=False):
    """ACAL550 - deux pans ; ``z2`` sans module, avec ou sans motif."""
    layout = layout_pan_existant()
    layout['zones'][0].pop('existant', None)
    layout['zones'][0].pop('anneeMiseEnService', None)
    if not modules_z2:
        layout['zones'][1]['geometry']['panels'] = []
    if motif:
        layout['motifsPansVides'] = {
            'z2': {'code': 'retrait_rive', 'message': MOTIF_Z2,
                   'mesures': {'retraitM': 0.5}},
            'fantome': {'code': 'inconnue', 'message': 'Pan inexistant.',
                        'mesures': {}}}
    return layout


class MotifDePanVideTest(SimpleTestCase):
    """ACAL550 - la cause d'un pan sans module, au centre de ce pan."""

    def svg(self, layout, contenu=CONTENU_POSE):
        return svg_de_planche(geometrie_de_planche(layout), contenu=contenu)

    def test_pan_vide_avec_motif_le_message_est_dans_le_svg_de_pose(self):
        geometrie = geometrie_de_planche(layout_pan_vide())
        vide = [p for p in geometrie['pans'] if p['repere'] == 'z2'][0]
        self.assertEqual(vide['motif_vide'], MOTIF_Z2)
        self.assertIn('>%s</text>' % html.escape(MOTIF_Z2),
                      svg_de_planche(geometrie, contenu=CONTENU_POSE))

    def test_pan_garni_avec_motif_perime_n_imprime_rien(self):
        layout = layout_pan_vide(modules_z2=True)
        geometrie = geometrie_de_planche(layout)
        for pan in geometrie['pans']:
            self.assertIsNone(pan['motif_vide'])
        self.assertNotIn(MOTIF_Z2.split(' : ')[0], self.svg(layout))

    def test_sans_motif_le_svg_est_celui_d_aujourd_hui(self):
        avec = self.svg(layout_pan_vide(motif=False))
        sans_cle = layout_pan_vide(motif=False)
        self.assertNotIn('motifsPansVides', sans_cle)
        self.assertEqual(avec, self.svg(sans_cle))
        self.assertNotIn('retrait de rive', avec)

    def test_un_motif_sans_pan_est_ignore(self):
        self.assertNotIn('Pan inexistant', self.svg(layout_pan_vide()))

    def test_les_autres_contenus_n_impriment_pas_le_motif(self):
        for contenu in (CONTENU_TOITURE, CONTENU_IMPLANTATION):
            self.assertNotIn('retrait de rive',
                             self.svg(layout_pan_vide(), contenu))


def layout_pan_existant(annee=2019):
    """ACAL575 - Pan A existant (10 modules) puis Pan B neuf (6 modules)."""
    layout = copy.deepcopy(LAYOUT)
    zone_a = layout['zones'][0]
    zone_a['obstacles'] = []
    zone_a['existant'] = True
    if annee is not None:
        zone_a['anneeMiseEnService'] = annee
    zone_a['geometry']['panels'] = [
        {'cx': 1.0 + 2.5 * k, 'cy': 1.0 + 2.0 * r}
        for r in range(2) for k in range(5)]
    zone_b = copy.deepcopy(zone_a)
    zone_b.update(id='z2', label='Pan B')
    zone_b.pop('existant')
    zone_b.pop('anneeMiseEnService', None)
    zone_b['geometry']['panels'] = [
        {'cx': 1.0 + 2.5 * k, 'cy': 6.0 + 2.0 * r}
        for r in range(2) for k in range(3)]
    layout['zones'].append(zone_b)
    return layout


class ModulesExistantsTest(SimpleTestCase):
    """ACAL575 - les modules d'un pan existant sont teintes et legendes."""

    def svg(self, layout):
        return svg_de_planche(geometrie_de_planche(layout),
                              contenu=CONTENU_POSE)

    def test_dix_existants_grises_six_neufs_verts_et_la_legende_le_dit(self):
        svg = self.svg(layout_pan_existant())
        self.assertEqual(len(re.findall(
            r'<polygon [^>]*stroke="#2e7d32"', svg)), 6)
        gris = re.findall(r'<polygon [^>]*stroke="%s"[^>]*>' % GRIS_MODULE,
                          svg)
        self.assertEqual(len(gris), 10)
        self.assertTrue(all('stroke-dasharray' in g for g in gris))
        # R3-21 — la légende se COUPE à la largeur du bandeau : chaque ligne coupée est un <text>.
        for ligne in textwrap.wrap('Module existant (déjà posé) — mis en service en 2019',
                                   CARACTERES_PAR_LIGNE_LEGENDE, break_long_words=False):
            self.assertIn('%s<' % escape(ligne), svg)

    def test_sans_annee_saisie_la_legende_n_en_invente_pas(self):
        svg = self.svg(layout_pan_existant(annee=None))
        self.assertIn('Module existant (déjà posé)<', svg)
        self.assertNotIn('mis en service', svg)

    def test_un_pan_sans_la_cle_est_rendu_comme_avant(self):
        svg = self.svg(LAYOUT)
        self.assertNotIn(GRIS_MODULE, svg)
        self.assertNotIn('Module existant', svg)

    def test_la_geometrie_publie_les_deux_cles_additives(self):
        pans = geometrie_de_planche(layout_pan_existant())['pans']
        self.assertEqual([(p['existant'], p['annee_mise_en_service'])
                          for p in pans], [(True, 2019), (False, None)])


def layout_six_modules():
    """ACAL590 - un pan (``z1``) de 6 modules en paysage, 2 rangees de 3."""
    layout = copy.deepcopy(LAYOUT)
    layout['zones'][0]['obstacles'] = []
    layout['zones'][0]['geometry']['panels'] = [
        {'cx': 1.0 + 2.5 * k, 'cy': 1.0 + 2.0 * r}
        for r in range(2) for k in range(3)]
    return layout


def affectation(*chaines):
    """``[(chaine, [cle de module, ...]), ...]`` -> la table publiee."""
    return [{'module': cle, 'pan': cle.partition('#')[0], 'chaine': chaine,
             'onduleur': 1, 'mppt': 1, 'source': 'automatique'}
            for chaine, cles in chaines for cle in cles]


def texte_de_svg(svg):
    """Le texte lu d'une feuille : balises retirees, lignes recollees."""
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', svg)).split())


def modules_dessines(svg):
    """Les polygones de MODULE (trait fin 0,15) d'une feuille de pan."""
    return re.findall(r'<polygon [^>]*stroke-width="0.15"[^>]*>', svg)


def fleches(svg):
    """Les polylignes des fleches de chaine d'une feuille, dans l'ordre."""
    return re.findall(r'<g class="fleche-chaine"[^>]*><polyline points="'
                      r'([^"]+)"', svg)


class FeuilleDePanTest(SimpleTestCase):
    """ACAL590 - une feuille A4 par pan : teintes, numeros, fleches de chaine.

    « + » au premier numero, « − » au dernier (ACAL1719), la polarite se
    verifie sur site (meme convention et meme legende que le plan de cablage,
    ACAL643)."""

    def feuilles(self, layout, table):
        from apps.calepinage.services.planche_pan import _svgs_de_pans

        return _svgs_de_pans(layout, table, pied='calepinage aaaaaaaaaaaa')

    def deux_chaines(self):
        return affectation((1, ['z1#1', 'z1#2', 'z1#3']),
                           (2, ['z1#4', 'z1#5', 'z1#6']))

    def test_deux_chaines_deux_teintes_six_numeros_deux_fleches(self):
        from apps.calepinage.services.documents.plan_cablage import (
            LEGENDE_SENS)

        feuilles = self.feuilles(layout_six_modules(), self.deux_chaines())
        self.assertEqual(len(feuilles), 1)
        svg = feuilles[0]
        self.assertIn('viewBox="0 0 297 210"', svg)
        self.assertIn('Pan Sud — plan de pose', svg)
        modules = modules_dessines(svg)
        self.assertEqual(len(modules), 6)
        self.assertEqual(len({re.search(r'fill="([^"]+)"', m).group(1)
                              for m in modules}), 2)
        for numero in range(1, 7):
            self.assertIn('>%d</text>' % numero, svg)
        # ACAL1719 — « + » au premier module, « − » au dernier, par chaîne.
        self.assertEqual(svg.count('>+</text>'), 2)
        self.assertEqual(svg.count('>−</text>'), 2)
        self.assertNotIn('début', texte_de_svg(svg))
        self.assertIn(LEGENDE_SENS, texte_de_svg(svg))
        self.assertEqual(svg.count('class="fleche-chaine"'), 2)
        self.assertIn('calepinage aaaaaaaaaaaa', svg)

    def test_la_fleche_suit_le_rang_publie_de_la_chaine(self):
        """ACAL1719 (revue) - la fleche suit le rang du module dans sa chaine
        (l'ordre de l'affectation publiee, l'attribut N du DXF), comme le plan
        de cablage : une table a l'envers donne la fleche a l'envers."""
        dans_l_ordre = self.feuilles(layout_six_modules(), affectation(
            (1, ['z1#1', 'z1#2', 'z1#3'])))[0]
        a_l_envers = self.feuilles(layout_six_modules(), affectation(
            (1, ['z1#3', 'z1#2', 'z1#1'])))[0]
        self.assertEqual(len(fleches(dans_l_ordre)), 1)
        self.assertEqual(fleches(a_l_envers)[0].split(),
                         list(reversed(fleches(dans_l_ordre)[0].split())))

    def test_le_bout_seul_sur_son_pan_garde_son_signe(self):
        """ACAL1719 (revue) - le dernier module d'une chaine, seul sur son
        pan : pas de fleche, mais son « − » (et la legende du sens)."""
        from apps.calepinage.services.documents.plan_cablage import (
            LEGENDE_SENS)

        layout = layout_six_modules()
        zone_b = copy.deepcopy(layout['zones'][0])
        zone_b.update(id='z2', label='Pan B')
        zone_b['geometry']['panels'] = [{'cx': 1.0, 'cy': 1.0},
                                        {'cx': 3.5, 'cy': 1.0}]
        layout['zones'].append(zone_b)
        table = affectation((1, ['z1#1', 'z1#2', 'z1#3', 'z2#1']))
        feuille_a, feuille_b = self.feuilles(layout, table)
        self.assertEqual((feuille_a.count('>+</text>'),
                          feuille_a.count('>−</text>')), (1, 0))
        self.assertEqual(fleches(feuille_b), [])
        self.assertEqual((feuille_b.count('>+</text>'),
                          feuille_b.count('>−</text>')), (0, 1))
        self.assertIn('class="bout-chaine"', feuille_b)
        self.assertIn(LEGENDE_SENS, texte_de_svg(feuille_b))

    def test_un_module_non_affecte_reste_en_contour_gris_seul(self):
        table = affectation((1, ['z1#1', 'z1#2', 'z1#3', 'z1#4', 'z1#5']))
        svg = self.feuilles(layout_six_modules(), table)[0]
        neutres = [m for m in modules_dessines(svg) if 'fill="none"' in m]
        self.assertEqual(len(neutres), 1)
        self.assertEqual(svg.count('class="fleche-chaine"'), 1)

    def test_sans_chaine_les_modules_sont_neutres_et_la_mention_est_la(self):
        from apps.calepinage.services.planche import MENTION_NON_CHAINE

        svg = self.feuilles(layout_six_modules(), [])[0]
        self.assertEqual(len(modules_dessines(svg)), 6)
        self.assertTrue(all('fill="none"' in m
                            for m in modules_dessines(svg)))
        self.assertIn(MENTION_NON_CHAINE, svg)
        self.assertNotIn('>+</text>', svg)
        self.assertNotIn('class="fleche-chaine"', svg)
        self.assertNotIn('polarité', svg)

    def test_une_chaine_a_cheval_sur_deux_pans_a_une_fleche_par_pan(self):
        layout = layout_six_modules()
        zone_b = copy.deepcopy(layout['zones'][0])
        zone_b.update(id='z2', label='Pan B')
        zone_b['geometry']['panels'] = [{'cx': 1.0, 'cy': 1.0},
                                        {'cx': 3.5, 'cy': 1.0}]
        layout['zones'].append(zone_b)
        table = affectation((1, ['z1#1', 'z1#2', 'z2#1', 'z2#2']))
        feuille_a, feuille_b = self.feuilles(layout, table)
        for feuille in (feuille_a, feuille_b):
            self.assertEqual(len(fleches(feuille)), 1)
        # ACAL1719 — « + » sur le pan du premier module, « − » sur le dernier.
        self.assertEqual((feuille_a.count('>+</text>'),
                          feuille_a.count('>−</text>')), (1, 0))
        self.assertEqual((feuille_b.count('>+</text>'),
                          feuille_b.count('>−</text>')), (0, 1))
        self.assertIn('suite sur Pan B', feuille_a)
        self.assertIn('suite sur Pan Sud', feuille_b)

    def test_un_pan_sans_module_n_a_pas_de_feuille(self):
        layout = layout_six_modules()
        vide = copy.deepcopy(layout['zones'][0])
        vide.update(id='z2', label='Pan vide')
        vide['geometry']['panels'] = []
        layout['zones'].append(vide)
        self.assertEqual(len(self.feuilles(layout, self.deux_chaines())), 1)
        sans_module = copy.deepcopy(layout)
        sans_module['zones'][0]['geometry']['panels'] = []
        self.assertEqual(self.feuilles(sans_module, []), [])

    def test_aucun_montant_sur_la_feuille(self):
        svg = self.feuilles(layout_six_modules(), self.deux_chaines())[0]
        for interdit in ('prix', 'prix_achat', 'mad', 'montant'):
            self.assertNotIn(interdit, svg.lower())

    def test_le_pdf_ajoute_les_pages_a4_apres_les_feuilles_a3(self):
        from apps.calepinage.services.planche import html_de_planche
        from apps.calepinage.services.planche_pan import feuilles_de_pans

        calepinage = calepinage_de_pose()
        svg = plan_de_pose_svg(calepinage)
        with patch_materiel():
            style, pages = feuilles_de_pans(calepinage, moment=MOMENT)
        self.assertIn('@page pan{size:A4 landscape', style)
        self.assertEqual(pages.count('class="feuille-pan"'), 1)
        avant = html_de_planche(svg)
        apres = html_de_planche(svg, style, pages)
        self.assertNotIn('feuille-pan', avant)
        self.assertTrue(apres.index('</svg>') < apres.index('class="feuille-pan"'))
        self.assertEqual(apres.count('<svg'), avant.count('<svg') + 1)


class BandeauDansLaPageTest(SimpleTestCase):
    """T4-V1-006 — page 1 du plan de pose : le bandeau de droite était coupé
    par le bord de la feuille (« Onduleur Huawei … 5kW Monophas », « Chaîne 1 :
    152,4 V à vide maxi à froid (4,18 °C, météo type d »). Le PDF RÉEL est rendu
    et lu par PyMuPDF : chaque mot tient dans la page, chaque phrase est entière."""

    LIGNES = (
        'Onduleur Huawei Onduleur réseau Huawei 5kW Monophasé — emplacement '
        ': à définir sur site',
        'Chaîne 1 : 152,4 V à vide maxi à froid (4,18 °C, météo type du site)',
    )

    def test_chaque_mot_du_bandeau_tient_dans_la_page_et_les_phrases_sont_entieres(self):
        import fitz

        from core.pdf import render_pdf

        from apps.calepinage.services.planche import html_de_planche

        svg = svg_de_planche(geometrie_de_planche(LAYOUT), titre='Plan de pose',
                             bandeau=self.LIGNES, contenu=CONTENU_POSE)
        document = fitz.open(stream=render_pdf(html=html_de_planche(svg)),
                             filetype='pdf')
        page = document[0]
        mots = page.get_text('words')
        dehors = [m[4] for m in mots if m[2] > page.rect.width + 0.5]
        self.assertEqual(dehors, [])
        texte = ' '.join(m[4] for m in mots)
        for ligne in self.LIGNES:
            self.assertIn(ligne, texte)
        # La mention d'échelle, en bas : aucun trait du dessin (cote, toit) ne la
        # traverse.
        mention = page.search_for('Échelle du tracé')[0]
        mention.x1 = mention.x0 + 140 * 72 / 25.4  # la phrase entière (≈ 140 mm)
        traversants = [d['rect'] for d in page.get_drawings()
                       if d['rect'].width < page.rect.width - 1  # fond de page
                       and fitz.Rect(d['rect']).intersects(mention)]
        self.assertEqual(traversants, [])


class TitreDuBandeauRepliTest(SimpleTestCase):
    """ACAL1717 — un titre long (« Plan de pose — F2-DOCS-a Villa Essaouira 2
    pans ») se replie aux mots dans le bandeau : aucune ligne ne dépasse sa
    largeur et le titre se relit entier."""

    TITRE = 'Plan de pose — F2-DOCS-a Villa Essaouira 2 pans'

    def test_un_titre_long_est_replie_et_se_relit_entier(self):
        from apps.calepinage.services.planche import (
            CARACTERES_PAR_LIGNE_TITRE_BANDEAU,
        )

        svg = svg_de_planche(geometrie_de_planche(LAYOUT), titre=self.TITRE,
                             contenu=CONTENU_POSE)
        lignes = re.findall(
            r'<text[^>]*font-size="5" font-weight="bold"[^>]*>([^<]*)</text>', svg)
        self.assertGreater(len(lignes), 1)
        self.assertTrue(all(len(x) <= CARACTERES_PAR_LIGNE_TITRE_BANDEAU
                            for x in lignes), lignes)
        self.assertEqual(html.unescape(' '.join(lignes)), self.TITRE)


def pan_de_10_sur_6(pose='portrait'):
    """ACAL591 - un pan rectangulaire de 10 x 6 m (repere local, metres),
    plein sud, a plat, module 1,7 x 1,1 m dont la pose est ``pose``."""
    return {'repere': 'z1', 'libelle': 'Pan Sud',
            'points': [(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)],
            'module_m': (1.7, 1.1), 'azimut_deg': 180.0, 'pente_deg': 0.0,
            'orientation_modules': pose, 'orientations_par_module': {},
            'modules': []}


#: ACAL1065 - un point [lng, lat] AU CENTRE du pan z1 de LAYOUT, un autre loin.
DANS_LE_PAN = [-7.59995, 33.50005]
HORS_PAN = [-7.5, 33.6]


def layout_avec_reperes(*reperes):
    layout = layout_six_modules()
    layout['reperesChantier'] = [dict(r) for r in reperes]
    return layout


def ancre(rayon, point=None, texte='Ancrage nord'):
    return {'id': 'r1', 'type': 'ancre_antichute', 'texte': texte,
            'rayonM': rayon, 'point': point or DANS_LE_PAN}


class ReperesDeChantierSurLaFeuilleTest(SimpleTestCase):
    """ACAL1065 - les repères saisis, sur la feuille A4 de leur pan."""

    def feuilles(self, layout):
        from apps.calepinage.services.planche_pan import _svgs_de_pans

        return _svgs_de_pans(layout, affectation(
            (1, ['z1#1', 'z1#2', 'z1#3'])), pied='calepinage aaaaaaaaaaaa')

    def cercles(self, svg):
        return [float(r) for r in re.findall(
            r'<circle [^>]*r="([\d.]+)"[^>]*stroke-dasharray', svg)]

    def test_ancre_de_2_m_cercle_a_l_echelle_texte_et_legende(self):
        layout = layout_avec_reperes(ancre(2.0))
        svg = self.feuilles(layout)[0]
        rayons = self.cercles(svg)
        self.assertEqual(len(rayons), 1)
        # Même transformation que les modules : r(mm) / 2 m == mm par m.
        module = modules_dessines(svg)[0]
        abscisses = [float(p.split(',')[0]) for p in re.search(
            r'points="([^"]+)"', module).group(1).split()]
        etendue = max(abscisses) - min(abscisses)
        cotes = geometrie_de_planche(layout)['pans'][0]['module_m']
        self.assertTrue(any(abs(rayons[0] / 2.0 - etendue / m) < 0.01
                            for m in cotes), (rayons, etendue, cotes))
        texte = texte_de_svg(svg)
        self.assertIn('Ancrage nord', texte)
        self.assertIn("Repères saisis par l'équipe d'étude — rayon saisi, "
                      "non calculé", texte)
        self.assertIn('Triangle : ancre antichute', texte)

    def test_sans_rayon_saisi_aucun_cercle(self):
        svg = self.feuilles(layout_avec_reperes(ancre(None)))[0]
        self.assertEqual(self.cercles(svg), [])
        self.assertIn('Ancrage nord', texte_de_svg(svg))

    def test_hors_pan_liste_sur_la_derniere_feuille(self):
        svg = self.feuilles(layout_avec_reperes(
            ancre(2.0, HORS_PAN, 'Echelle'), ancre(None)))[-1]
        self.assertIn('Repère hors pan : Echelle', texte_de_svg(svg))
        self.assertEqual(len(self.cercles(svg)), 0)

    def test_sans_repere_la_feuille_est_celle_d_avant(self):
        sans = self.feuilles(layout_six_modules())
        vide = layout_six_modules()
        vide['reperesChantier'] = []
        self.assertEqual(self.feuilles(vide), sans)
        self.assertNotIn('Repères saisis', texte_de_svg(sans[0]))

    def test_un_repere_ne_change_pas_l_empreinte_du_document(self):
        from apps.calepinage.services.layout import empreinte_document

        seul = layout_six_modules()
        avec = layout_avec_reperes(ancre(2.0))
        avec.pop('reperesChantier')
        self.assertEqual(empreinte_document(seul), empreinte_document(avec))


def modules_aux_marges(pan, centres):
    from apps.calepinage.services.planche import coins_du_module

    pan['modules'] = list(centres)
    return [{'centre': c, 'coins': coins_du_module(pan, c)}
            for c in centres]


#: Marges voulues N 0,50 / S 0,60 / E 0,40 / O 0,30 pour un module PORTRAIT
#: (1,1 le long de la rangee, 1,7 dans la pente) : 4 modules aux quatre coins.
CENTRES_AUX_MARGES = [(0.85, 1.45), (9.05, 1.45), (0.85, 4.65), (9.05, 4.65)]


class DistancesAuxRivesTest(SimpleTestCase):
    """ACAL591 - les quatre distances du champ aux rives, MESUREES."""

    def mesures(self, pan, modules):
        from apps.calepinage.services.planche_pan import _distances_aux_rives

        return _distances_aux_rives(pan, modules)

    def test_quatre_cotes_egales_aux_marges_d_un_module_portrait(self):
        pan = pan_de_10_sur_6('portrait')
        distances, motif = self.mesures(
            pan, modules_aux_marges(pan, CENTRES_AUX_MARGES))
        self.assertEqual(motif, '')
        for cote, marge in (('N', 0.50), ('S', 0.60), ('E', 0.40),
                            ('O', 0.30)):
            self.assertAlmostEqual(distances[cote]['distance'], marge,
                                   places=6, msg=cote)

    def test_un_module_paysage_a_les_memes_centres_autres_marges(self):
        # Meme centres, pose paysage (1,7 le long de la rangee, 1,1 dans la
        # pente) : les marges se mesurent sur le rectangle ROTATIF, pas sur
        # un rectangle suppose portrait.
        pan = pan_de_10_sur_6('landscape')
        distances, _ = self.mesures(
            pan, modules_aux_marges(pan, CENTRES_AUX_MARGES))
        self.assertAlmostEqual(distances['O']['distance'], 0.85 - 0.85,
                               places=6)
        self.assertAlmostEqual(distances['S']['distance'], 1.45 - 0.55,
                               places=6)

    def test_une_marge_est_la_plus_petite_distance_parallele_a_l_axe(self):
        pan = pan_de_10_sur_6('portrait')
        centres = CENTRES_AUX_MARGES + [(5.0, 4.15)]
        distances, _ = self.mesures(pan, modules_aux_marges(pan, centres))
        # Le module central monte a y = 5,0 : il serre le nord a 1,0 ; la
        # marge nord reste la plus petite des distances, 0,50.
        self.assertAlmostEqual(distances['N']['distance'], 0.50, places=6)

    def test_champ_au_contact_des_rives_ouest_et_nord(self):
        """ACAL1712 — deux modules portrait (1,1 × 1,7) posés x 0..2,2, y 4,3..6,0 :
        le champ TOUCHE l'ouest et le nord (0,00), l'est est à 10 − 2,2 = 7,80 et le
        sud à 4,30 (mutant : compter la rive de départ, t ≈ 0 ⇒ E = S = 0)."""
        pan = pan_de_10_sur_6('portrait')
        distances, _ = self.mesures(
            pan, modules_aux_marges(pan, [(0.55, 5.15), (1.65, 5.15)]))
        for cote, attendu in (('N', 0.0), ('O', 0.0), ('E', 7.8), ('S', 4.3)):
            self.assertAlmostEqual(distances[cote]['distance'], attendu,
                                   places=6, msg=cote)
            # Jamais « −0,00 » : une distance nulle est un zéro positif.
            self.assertEqual(math.copysign(1.0, distances[cote]['distance']), 1.0)

    def test_orientation_non_enregistree_aucune_distance_et_motif_nomme(self):
        pan = pan_de_10_sur_6('portrait')
        modules = modules_aux_marges(pan, CENTRES_AUX_MARGES)
        modules[0]['coins'] = None
        distances, motif = self.mesures(pan, modules)
        self.assertEqual(distances, {})
        self.assertIn('orientation du module non enregistrée : distances '
                      'non calculées', motif)


class CotesDesZonesInterditesTest(SimpleTestCase):
    """ACAL591 - une cote d'emprise par zone interdite qui recoupe le pan."""

    def cotes(self, zone_points, coins=True):
        from apps.calepinage.services.planche_pan import _cotes_des_zones

        pan = pan_de_10_sur_6('portrait')
        modules = modules_aux_marges(pan, CENTRES_AUX_MARGES)
        if not coins:
            modules[0]['coins'] = None
        zone = {'repere': 'ZONE-1', 'libelle': 'Cheminee', 'nature': '',
                'points': zone_points}
        return _cotes_des_zones(pan, modules, [zone])

    def test_emprise_et_distance_au_module_le_plus_proche(self):
        # x 4..6, y 1..2 : emprise 2 x 1 ; les modules du bas se tiennent a
        # x 0,3..1,4 et 8,5..9,6 : le plus proche est a droite, 8,5 - 6 =
        # 2,5 m, les ordonnees se chevauchant.
        (cote,) = self.cotes([(4.0, 1.0), (6.0, 1.0), (6.0, 2.0),
                              (4.0, 2.0)])
        self.assertAlmostEqual(cote['largeur_m'], 2.0, places=6)
        self.assertAlmostEqual(cote['hauteur_m'], 1.0, places=6)
        self.assertFalse(cote['recouvre'])
        self.assertAlmostEqual(cote['distance_m'], 2.5, places=6)

    def test_une_zone_qui_recouvre_un_module_le_dit(self):
        (cote,) = self.cotes([(0.5, 1.0), (2.0, 1.0), (2.0, 2.0),
                              (0.5, 2.0)])
        self.assertTrue(cote['recouvre'])
        self.assertIsNone(cote['distance_m'])

    def test_une_zone_hors_du_pan_n_a_pas_de_cote(self):
        self.assertEqual(self.cotes([(20.0, 1.0), (22.0, 1.0), (22.0, 2.0),
                                     (20.0, 2.0)]), [])

    def test_sans_emprise_de_module_pas_de_distance_ni_de_recouvrement(self):
        (cote,) = self.cotes([(4.0, 1.0), (6.0, 1.0), (6.0, 2.0),
                              (4.0, 2.0)], coins=False)
        self.assertAlmostEqual(cote['largeur_m'], 2.0, places=6)
        self.assertIsNone(cote['distance_m'])
        self.assertFalse(cote['recouvre'])


class FeuilleCoteeTest(SimpleTestCase):
    """ACAL591 - les cotes et la mention sont imprimees sur la feuille."""

    def test_quatre_cotes_nommees_et_mention_de_projection(self):
        from apps.calepinage.services.planche_pan import _feuille_de_pan

        pan = pan_de_10_sur_6('portrait')
        modules = [dict(m, pan='z1', chaine=None, couleur=None, rang=None,
                        module='z1#%d' % (i + 1))
                   for i, m in enumerate(
                       modules_aux_marges(pan, CENTRES_AUX_MARGES))]
        zone = {'repere': 'ZONE-1', 'libelle': 'Cheminee', 'nature': '',
                'points': [(4.0, 1.0), (6.0, 1.0), (6.0, 2.0), (4.0, 2.0)]}
        svg = _feuille_de_pan(pan, modules, [], [pan], '', [zone])
        for cote, valeur in (('N', '0,50 m'), ('S', '0,60 m'),
                             ('E', '0,40 m'), ('O', '0,30 m')):
            self.assertIn('data-cote="%s"' % cote, svg)
            self.assertIn('>%s</text>' % valeur, svg)
        self.assertIn('Distances mesurées en plan, projection horizontale '
                      'du pan', texte_de_svg(svg))
        self.assertIn('Cheminee', svg)
        self.assertIn('2,00 m', svg)

    def test_champ_au_contact_quatre_lettres_distinctes_dans_la_feuille(self):
        """ACAL1712 — champ au contact des rives ouest et nord : quatre cotes
        justes, aucune « −0,00 », chaque lettre sur son propre bord et dans la
        feuille (jamais empilées au même point, jamais x < 0)."""
        from apps.calepinage.services.planche_pan import _feuille_de_pan

        pan = pan_de_10_sur_6('portrait')
        modules = [dict(m, pan='z1', chaine=None, couleur=None, rang=None,
                        module='z1#%d' % (i + 1))
                   for i, m in enumerate(
                       modules_aux_marges(pan, [(0.55, 5.15), (1.65, 5.15)]))]
        svg = _feuille_de_pan(pan, modules, [], [pan], '', [])
        texte = texte_de_svg(svg)
        for ligne in ('N : 0,00 m', 'O : 0,00 m', 'E : 7,80 m', 'S : 4,30 m'):
            self.assertIn(ligne, texte)
        self.assertNotIn('−0,00', texte)
        self.assertNotIn('-0,00', texte)
        lettres = dict(
            (cote, (float(x), float(y))) for cote, x, y in re.findall(
                r'<g data-cote="(\w)">.*?<text x="([-\d.]+)" y="([-\d.]+)" '
                r'font-size="3.2" font-weight="bold"', svg))
        self.assertEqual(sorted(lettres), ['E', 'N', 'O', 'S'])
        self.assertEqual(len(set(lettres.values())), 4, lettres)
        for cote, (x, y) in lettres.items():
            self.assertGreaterEqual(x, 0.0, cote)
            self.assertGreaterEqual(y, 0.0, cote)


def boites_de_textes(svg):
    """ACAL1935 — la boîte (x0, y0, x1, y1, texte) de chaque ``<text>`` du SVG : largeur ≈ 0,6 × le corps
    par caractère (DejaVu Sans, comme les autres gardes de ce module), hauteur = le corps ; un texte
    tourné de −90° (cote verticale) échange les deux dimensions."""
    boites = []
    for m in re.finditer(r'<text ([^>]*)>([^<]*)</text>', svg):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
        corps = float(attrs.get('font-size', 3.2))
        x, y = float(attrs['x']), float(attrs['y'])
        texte = html.unescape(m.group(2))
        largeur, hauteur = 0.6 * corps * len(texte), corps
        ancre = attrs.get('text-anchor', 'start')
        debut = {'start': 0.0, 'middle': -largeur / 2.0, 'end': -largeur}[ancre]
        if 'rotate(-90' in attrs.get('transform', ''):
            boites.append((x - hauteur, y - debut - largeur, x, y - debut, texte))
        else:
            boites.append((x + debut, y - hauteur, x + debut + largeur, y, texte))
    return boites


class CotesDeRiveSansChevauchementTest(SimpleTestCase):
    """ACAL1935 — sur la page d'un pan, ni une cote de rive ni sa lettre N/E/S/O n'en recoupe une autre, et
    aucun texte ne sort de la feuille (x ≥ 0) : « 0,00 m » tourné coupé à x = −1,8, « 0,82 m » sur le E."""

    def feuille(self, centres):
        from apps.calepinage.services.planche_pan import _feuille_de_pan

        pan = pan_de_10_sur_6('portrait')
        modules = [dict(m, pan='z1', chaine=None, couleur=None, rang=None, module='z1#%d' % (i + 1))
                   for i, m in enumerate(modules_aux_marges(pan, centres))]
        return _feuille_de_pan(pan, modules, [], [pan], '', [])

    def verifier(self, svg):
        groupes = re.findall(r'<g data-cote="\w">.*?</g>', svg)
        boites = [b for g in groupes for b in boites_de_textes(g)]
        self.assertEqual(len(boites), 8)
        for x0, y0, x1, y1, texte in boites_de_textes(svg):
            self.assertGreaterEqual(x0, 0.0, texte)
            self.assertGreaterEqual(y0, 0.0, texte)
        for i, a in enumerate(boites):
            for b in boites[i + 1:]:
                recoupe = a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
                self.assertFalse(recoupe, (a, b))

    def test_champ_au_contact_des_rives(self):
        self.verifier(self.feuille([(0.55, 5.15), (1.65, 5.15)]))

    def test_champ_aux_marges_ordinaires(self):
        self.verifier(self.feuille(CENTRES_AUX_MARGES))


class EncartFixationDuPanTest(SimpleTestCase):
    """ACAL592 - l'encart « Fixation de ce pan » de la feuille A4."""

    def feuille(self, fixation):
        from apps.calepinage.services.planche_pan import _svgs_de_pans

        return texte_de_svg(_svgs_de_pans(
            layout_six_modules(), [], pied='', fixation=fixation)[0])

    def ligne(self, composant, quantite, unite, manquant=None):
        return {'composant': composant, 'role': composant,
                'quantite': quantite, 'unite': unite, 'manquant': manquant}

    def test_l_encart_liste_les_composants_dans_l_ordre(self):
        texte = self.feuille({'z1': [
            self.ligne('Rail aluminium', 6.5, 'm'),
            self.ligne('Pince de milieu', 8, 'u')]})
        self.assertIn('Fixation de ce pan', texte)
        self.assertLess(texte.index('Rail aluminium : 6,5 m'),
                        texte.index('Pince de milieu : 8 u'))
        self.assertIn("Arrondi par pan : la somme peut dépasser la commande "
                      "du projet", texte)

    def test_sans_unite_u_pas_de_note_d_arrondi(self):
        texte = self.feuille({'z1': [self.ligne('Rail aluminium', 6.5, 'm')]})
        self.assertNotIn('Arrondi par pan', texte)

    def test_une_quantite_absente_imprime_son_manquant_jamais_zero(self):
        texte = self.feuille({'z1': [self.ligne(
            'Crochet', None, 'u', "« Entraxe » non saisi : la quantité "
            "n'est pas calculée.")]})
        self.assertIn("Crochet : « Entraxe » non saisi", texte)
        self.assertNotIn('Crochet : 0', texte)

    def test_sans_nomenclature_l_encart_est_absent(self):
        for fixation in (None, {}, {'z2': []}):
            self.assertNotIn('Fixation de ce pan', self.feuille(fixation))

    def test_aucune_mention_de_prix(self):
        texte = self.feuille({'z1': [self.ligne('Rail', 6.5, 'm')]})
        for interdit in ('prix', 'mad', 'montant'):
            self.assertNotIn(interdit, texte.lower())


class ListeDesChainesTest(SimpleTestCase):
    def test_les_chaines_sont_recopiees_du_moteur(self):
        lignes = _lignes_de_chaines(RESULTAT)
        chainage = RESULTAT['electrique']['chainage']
        self.assertIn('Chaînes : %s' % chainage['chaines'], lignes)
        self.assertIn('Modules par chaîne : %s'
                      % chainage['modules_par_chaine'], lignes)

    def test_les_onduleurs_sont_listes_avec_leurs_mppt(self):
        lignes = _lignes_de_chaines(RESULTAT)
        self.assertTrue(any('ONDULEUR-ESSAI-1' in ligne and 'MPPT' in ligne
                            for ligne in lignes))

    def test_l_emplacement_des_onduleurs_n_est_jamais_invente(self):
        # La donnée n'existe ni dans le layout ni dans le résultat : on le DIT
        # plutôt que de poser un onduleur à un endroit plausible.
        lignes = _lignes_de_chaines(RESULTAT)
        self.assertTrue(any('non relevé' in ligne for ligne in lignes))

    def test_sans_resultat_aucune_ligne_n_est_fabriquee(self):
        self.assertEqual(_lignes_de_chaines(None), ())
        self.assertEqual(_lignes_de_chaines({}), ())

    def test_la_liste_paraît_dans_le_bandeau_du_plan(self):
        from apps.calepinage import selectors

        calepinage = calepinage_de_pose()
        svg = plan_de_pose_svg(calepinage)
        with patch_materiel():
            servi = selectors.resultat_servi(calepinage)
        chainage = servi['electrique']['chainage']
        self.assertIn('Chaînes : %s' % chainage['chaines'], svg)
        self.assertIn('Onduleur', svg)


class TensionsDesChainesSurLePlanTest(SimpleTestCase):
    """ACAL889 — une ligne de tension à froid par chaîne + la consigne."""

    SERVIES = {
        1: {'voc_froid_v': 343.0, 'temperature_froide_c': -5.0,
            'temperature_source': 'saisie', 'vmp_chaud_v': 216.0},
        2: {'voc_froid_v': None, 'temperature_froide_c': -5.0,
            'temperature_source': 'saisie', 'vmp_chaud_v': None}}
    CONSIGNE = "Couper l'AC avant le DC : les chaînes restent sous tension."

    def _rendre(self, servies, consigne=''):
        cible = 'apps.calepinage.services.tensions_chaines.chaines_servies'
        reglage = ('apps.calepinage.services.documents.plan_cablage.'
                   '_consigne_dc_de_societe')
        with mock.patch(cible, return_value=servies),                 mock.patch(reglage, return_value=consigne):
            return plan_de_pose_svg(calepinage_de_pose())

    def test_une_ligne_par_chaine_avec_la_temperature_citee(self):
        svg = self._rendre(self.SERVIES)
        lu = texte_des_lignes_svg(svg)  # T4-V1-006 — lignes coupées à la largeur du bandeau
        self.assertIn('Chaîne 1 : 343 V à vide maxi à froid (−5 °C, saisie)',
                      lu)
        self.assertIn('Chaîne 2 : tension non calculée : fiche incomplète',
                      lu)
        self.assertNotIn('216', svg)  # jamais la tension à chaud

    def test_la_consigne_de_la_societe_est_imprimee_mot_pour_mot(self):
        svg = self._rendre(self.SERVIES, self.CONSIGNE)
        self.assertIn(self.CONSIGNE, texte_des_lignes_svg(svg))
        self.assertNotIn('Couper', self._rendre(self.SERVIES, ''))

    def test_electrique_non_chaine_garde_la_mention_existante(self):
        with mock.patch('apps.calepinage.selectors.resultat_servi',
                        return_value={}):
            svg = self._rendre(self.SERVIES, self.CONSIGNE)
        self.assertIn('Électrique non chaîné', svg)
        self.assertNotIn('à vide maxi à froid', svg)

    def test_les_tensions_sont_celles_du_serveur_pas_un_second_calcul(self):
        from apps.calepinage.services.electrique import evaluation_electrique

        calepinage = calepinage_de_pose()
        with patch_materiel():
            servies = evaluation_electrique(calepinage)['chaines']
            svg = _rendre_plan_pose_svg(calepinage, moment=MOMENT)
        for ligne in servies:
            if ligne['voc_froid_v'] is not None:
                self.assertIn(
                    'Chaîne %s : %s V à vide maxi à froid' % (
                        ligne['chaine'],
                        ('%g' % ligne['voc_froid_v']).replace('.', ',')),
                    texte_des_lignes_svg(svg))


class PiedsDeChassisTest(SimpleTestCase):
    """ACAL580 — le nombre de pieds de châssis (portée saisie) sur le plan de pose."""

    PORTEE = {'valeurM': 2.4, 'source': 'notice du système, p. 4'}

    def test_toit_plat_a_portee_saisie_sept_pieds(self):
        from apps.calepinage.services.planche import _ligne_des_pieds

        from .test_calx359_bom_fixation import layout as layout_d_un_pan

        document = layout_d_un_pan([(1.0 + 1.15 * k, 1.0) for k in range(12)])
        document['zones'][0]['porteeEntrePieds'] = dict(self.PORTEE)
        self.assertEqual(_ligne_des_pieds(document), (
            'Pieds de châssis : 7 (portée saisie 2,4 m — notice du système, p. 4)',))

    def test_sans_portee_le_plan_d_aujourd_hui(self):
        from apps.calepinage.services.planche import _ligne_des_pieds

        self.assertEqual(_ligne_des_pieds(copy.deepcopy(LAYOUT)), ())

    def test_la_ligne_est_imprimee_sur_le_plan_de_pose(self):
        calepinage = calepinage_de_pose()
        for zone in calepinage.roof_layout['zones']:
            zone['porteeEntrePieds'] = dict(self.PORTEE)
        self.assertIn('Pieds de châssis : ', texte_de_svg(plan_de_pose_svg(calepinage)))

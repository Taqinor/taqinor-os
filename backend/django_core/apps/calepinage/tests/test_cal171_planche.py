"""CAL171 — la planche se compose de la géométrie STOCKÉE, ou elle refuse.

Ces essais sont PURS : ils ne touchent ni la base ni WeasyPrint. C'est
délibéré — la composition du SVG est là où les erreurs se logent (repère
retourné, obstacle pivoté, emprise inventée), et elle doit rester vérifiable
partout, y compris sur un poste sans bibliothèque graphique. Le rendu PDF
lui-même n'ajoute rien à vérifier ici : il délègue à ``core.pdf.render_pdf``
(ARC11), déjà couvert par ses propres essais.

Run :
    python manage.py test apps.calepinage.tests.test_cal171_planche -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.planche import (
    PlancheRefusee, _dimensions_module, _echelle_de_dessin, coins_du_module,
    geometrie_de_planche,
    html_de_planche, nom_de_fichier, svg_de_planche, texte_de_longueur,
)

#: Un document de conception minimal mais RÉEL : contour en ``[lat, lng]``,
#: pan en ``[lng, lat]``, un obstacle relevé et deux modules posés.
LAYOUT = {
    'version': 2,
    'outline': [[33.5, -7.6], [33.5, -7.5999], [33.5001, -7.5999],
                [33.5001, -7.6]],
    'panelWatt': 720,
    'zones': [{
        'id': 'z1',
        'label': 'Pan Sud',
        'vertices': [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001],
                     [-7.6, 33.5001]],
        'obstacles': [{'id': 'obs-1', 'centerLng': -7.59995,
                       'centerLat': 33.50005, 'lengthM': 0.8, 'widthM': 1.2,
                       'type': 'cheminee', 'provenance': 'RELEVE'}],
        'geometry': {
            'azimuthDeg': 180.0, 'tiltDeg': 15.0, 'count': 2,
            'panelOrientation': 'landscape',
            'origin': [-7.6, 33.5],
            'panels': [{'cx': 1.0, 'cy': 1.0}, {'cx': 3.5, 'cy': 1.0}],
        },
    }],
}


class GeometrieDePlancheTest(SimpleTestCase):
    def test_refuse_un_calepinage_sans_conception(self):
        for vide in (None, {}, {'zones': []}, {'outline': []}):
            with self.assertRaises(PlancheRefusee) as capture:
                geometrie_de_planche(vide)
            self.assertEqual(capture.exception.champ, 'roof_layout')
            self.assertIn('conception', str(capture.exception).lower())

    def test_projette_le_contour_et_les_pans_en_metres(self):
        geometrie = geometrie_de_planche(LAYOUT)
        self.assertEqual(len(geometrie['contour']), 4)
        self.assertEqual(len(geometrie['pans']), 1)
        x0, y0, x1, y1 = geometrie['etendue']
        # 0,0001° de latitude ≈ 11,1 m ; l'étendue doit être de cet ordre et
        # JAMAIS de l'ordre du degré (repère non projeté).
        self.assertGreater(x1 - x0, 5.0)
        self.assertLess(x1 - x0, 30.0)
        self.assertGreater(y1 - y0, 5.0)
        self.assertLess(y1 - y0, 30.0)

    def test_les_modules_sont_les_centres_reellement_poses(self):
        pan = geometrie_de_planche(LAYOUT)['pans'][0]
        self.assertEqual(len(pan['modules']), 2)
        # L'écart entre les deux centres est celui du document (3,5 - 1,0).
        self.assertAlmostEqual(pan['modules'][1][0] - pan['modules'][0][0],
                               2.5, places=6)
        self.assertAlmostEqual(pan['modules'][1][1], pan['modules'][0][1],
                               places=6)

    def test_l_obstacle_garde_son_orientation_nord_sud(self):
        obstacle = geometrie_de_planche(LAYOUT)['obstacles'][0]
        # ``lengthM`` est l'étendue NORD-SUD, ``widthM`` l'EST-OUEST : les
        # confondre pivoterait l'obstacle de 90°.
        self.assertAlmostEqual(obstacle['hauteur'], 0.8, places=6)
        self.assertAlmostEqual(obstacle['largeur'], 1.2, places=6)

    def test_un_pan_sans_azimut_ne_se_voit_pas_attribuer_zero(self):
        layout = {'outline': LAYOUT['outline'],
                  'zones': [{'id': 'z1',
                             'vertices': LAYOUT['zones'][0]['vertices']}]}
        pan = geometrie_de_planche(layout)['pans'][0]
        self.assertIsNone(pan['azimut_deg'])
        self.assertIsNone(pan['pente_deg'])


def _toit_plat_au_curseur(avec_tables):
    """D-ACAL-149 — un toit plat qui porte la valeur du curseur (22)."""
    import copy

    layout = copy.deepcopy(LAYOUT)
    layout['zones'][0].update(roofType='flat', pitchDeg=22)
    if not avec_tables:
        del layout['zones'][0]['geometry']['tiltDeg']
    return layout


class PenteDuToitPlatTest(SimpleTestCase):
    """D-ACAL-149 — sans ``tiltDeg``, la planche lit 0 pour un toit plat ;
    ``toit_plat_corrige=False`` (devis envoyé avant la coupure) rend la
    planche d'avant à l'octet près."""

    def test_toit_plat_sans_tables_lit_zero(self):
        pan = geometrie_de_planche(_toit_plat_au_curseur(False))['pans'][0]
        self.assertEqual(pan['pente_deg'], 0.0)
        svg = svg_de_planche(geometrie_de_planche(_toit_plat_au_curseur(False)))
        self.assertIn('inclinaison 0°', svg)
        self.assertNotIn('inclinaison 22°', svg)

    def test_les_tables_posees_priment_toujours(self):
        for corrige in (True, False):
            pan = geometrie_de_planche(_toit_plat_au_curseur(True),
                                       toit_plat_corrige=corrige)['pans'][0]
            self.assertEqual(pan['pente_deg'], 15.0)

    def test_devis_ferme_rend_la_planche_d_avant_a_l_octet(self):
        """Avant D-ACAL-149 la planche ne lisait pas ``roofType`` : le même
        document SANS ``roofType`` est la référence d'hier."""
        hier = _toit_plat_au_curseur(False)
        del hier['zones'][0]['roofType']
        ferme = geometrie_de_planche(_toit_plat_au_curseur(False),
                                     toit_plat_corrige=False)
        self.assertEqual(ferme['pans'][0]['pente_deg'], 22.0)
        self.assertEqual(svg_de_planche(ferme, titre='T', pied='p'),
                         svg_de_planche(geometrie_de_planche(hier), titre='T', pied='p'))


class DimensionsModuleTest(SimpleTestCase):
    def test_dimensions_sourcees_par_le_kit_declare(self):
        self.assertEqual(_dimensions_module({'panelWatt': 720}),
                         (2.384, 1.303))

    def test_puissance_inconnue_ne_produit_aucune_dimension(self):
        # Une emprise plausible mais non sourcée se lirait comme une emprise
        # mesurée : on préfère l'absence.
        self.assertIsNone(_dimensions_module({'panelWatt': 615}))
        self.assertIsNone(_dimensions_module({}))


class LegendeEtEchelleR321Test(SimpleTestCase):
    """R3-21 — la légende tient dans le bandeau, la mention d'échelle ne
    chevauche pas les graduations de la barre."""

    def test_un_libelle_long_se_coupe_a_la_largeur_du_bandeau(self):
        import re

        from apps.calepinage.services.planche import (
            CARACTERES_PAR_LIGNE_LEGENDE, LIBELLE_MODULE_SANS_POSE,
            _legende_svg,
        )

        morceaux, fin = _legende_svg(
            0.0, 0.0, [('#000', '#fff', LIBELLE_MODULE_SANS_POSE)])
        textes = [re.sub('<[^>]+>', '', m) for m in morceaux if '<text' in m]
        lignes = textes[1:]  # la première est le titre « LÉGENDE »
        self.assertGreater(len(lignes), 1)
        self.assertTrue(all(len(t) <= CARACTERES_PAR_LIGNE_LEGENDE
                            for t in lignes), lignes)
        self.assertEqual(' '.join(lignes).replace('&#x27;', "'"),
                         LIBELLE_MODULE_SANS_POSE)
        self.assertGreater(fin, 5.0 + 4.6)  # la hauteur suit les lignes

    def test_la_mention_d_echelle_est_au_dessus_de_la_barre(self):
        import re

        svg = svg_de_planche(geometrie_de_planche(LAYOUT))
        mention = re.search(
            r'<text x="[\d.]+" y="([\d.]+)" font-size="3" fill="[^"]+">'
            r'Échelle du tracé', svg)
        barre = re.search(r'<g><rect x="[\d.]+" y="([\d.]+)" '
                          r'width="[\d.]+" height="1.6"', svg)
        self.assertTrue(mention and barre)
        self.assertLess(float(mention.group(1)), float(barre.group(1)))


class SvgDePlancheTest(SimpleTestCase):
    def setUp(self):
        self.svg = svg_de_planche(geometrie_de_planche(LAYOUT),
                                  titre='Toiture atelier')

    def test_le_svg_est_un_a3_paysage_autonome(self):
        self.assertTrue(self.svg.lstrip().startswith('<?xml'))
        self.assertIn('width="420mm" height="297mm"', self.svg)
        self.assertIn('viewBox="0 0 420 297"', self.svg)
        self.assertTrue(self.svg.rstrip().endswith('</svg>'))

    def test_aucun_acces_reseau_dans_le_document(self):
        # La seule URL admise est l'espace de noms SVG, qui n'est jamais
        # RÉSOLU par un rendu : c'est un identifiant, pas une ressource.
        corps = self.svg.replace('http://www.w3.org/2000/svg', '')
        for interdit in ('http://', 'https://', '<image', '@import', 'url('):
            self.assertNotIn(interdit, corps)

    def test_le_dessin_reste_dans_les_marges_de_la_feuille(self):
        import re

        coordonnees = [float(v) for v in
                       re.findall(r'(?:x1|x2|y1|y2)="([-\d.]+)"', self.svg)]
        coordonnees += [float(c) for couple in
                        re.findall(r'points="([^"]+)"', self.svg)
                        for point in couple.split()
                        for c in point.split(',')]
        self.assertTrue(coordonnees)
        self.assertGreaterEqual(min(coordonnees), 0.0)
        self.assertLessEqual(max(coordonnees), 420.0)

    def test_les_cotes_sont_en_metres_a_la_francaise(self):
        self.assertIn(' m<', self.svg)
        self.assertEqual(texte_de_longueur(12.345), '12,35 m')

    def test_les_deux_modules_sont_dessines(self):
        # Emprise sourcée (720 Wc) -> deux polygones de module.
        self.assertGreaterEqual(self.svg.count('stroke="#2e7d32"'), 2)

    def test_le_titre_est_echappe(self):
        svg = svg_de_planche(geometrie_de_planche(LAYOUT),
                             titre='Toiture <script>')
        self.assertNotIn('<script>', svg)
        self.assertIn('&lt;script&gt;', svg)

    def test_l_echelle_tient_dans_la_zone_de_dessin(self):
        etendue = geometrie_de_planche(LAYOUT)['etendue']
        echelle = _echelle_de_dessin(etendue)
        largeur_mm = (etendue[2] - etendue[0]) * echelle
        self.assertLessEqual(round(largeur_mm, 3),
                             420.0 - 2 * 12.0 - 84.0 + 0.001)
        self.assertGreater(echelle, 0.0)


class _Pivot:
    """Un calepinage sans base, à l'état de conception voulu (ACAL1006)."""

    def __init__(self, etat):
        self.pk, self.roof_layout, self.etat_conception = 9, LAYOUT, etat

    def __str__(self):
        return 'Calepinage 9'


class ConceptionRapideTest(SimpleTestCase):
    """ACAL1008 — rien d'un calepinage « rapide » ne sort côté client ;
    un calepinage « complet » sort comme aujourd'hui (mutant : ignorer
    l'état ⇒ les trois sorties du rapide passent, échec)."""

    def test_planche_refusee_puis_acceptee_une_fois_verifiee(self):
        from apps.calepinage.selectors_devis import MOTIF_CONCEPTION_RAPIDE
        from apps.calepinage.services.planche import planche_svg_ou_vide, rendre_planche_svg

        with self.assertRaises(PlancheRefusee) as capture:
            rendre_planche_svg(_Pivot('rapide'), pied='pied')
        self.assertEqual(str(capture.exception), MOTIF_CONCEPTION_RAPIDE)
        self.assertEqual(capture.exception.champ, 'etat_conception')
        self.assertEqual(planche_svg_ou_vide(_Pivot('rapide')), '')
        complet = rendre_planche_svg(_Pivot('complet'), pied='pied')
        self.assertEqual(complet, svg_de_planche(geometrie_de_planche(LAYOUT), titre='Calepinage 9', pied='pied'))

    def test_rendement_de_la_pose_jamais_servi(self):
        from apps.calepinage.selectors_devis import productible_pose_du_calepinage

        self.assertIsNone(productible_pose_du_calepinage(_Pivot('rapide'), tolerance_kwc_ratio=0.05))

    def test_annexe_du_site_omise(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.ventes import calepinage_options as co

        devis = SimpleNamespace(pk=5, company=object(), roof_layout=None, statut='brouillon')
        layout = {'zones': [{'azimut_deg': 180, 'inclinaison_deg': 15}]}
        with mock.patch('apps.calepinage.selectors.calepinage_du_devis', return_value=_Pivot('rapide')):
            self.assertIsNone(co.parametres_site_publics(devis, layout, {'productible_ville': 'Casablanca'}))
        # D4 : un devis déjà envoyé (ou accepté, refusé, expiré) garde son annexe.
        for statut in ('envoye', 'accepte', 'refuse', 'expire'):
            envoye = SimpleNamespace(pk=5, company=object(), roof_layout=None, statut=statut)
            with mock.patch('apps.calepinage.selectors.calepinage_du_devis', return_value=_Pivot('rapide')), \
                    mock.patch.object(co, '_ombrage_mesure', return_value=False):
                annexe = co.parametres_site_publics(envoye, layout, {'productible_ville': 'Casablanca'})
            self.assertEqual((annexe or {}).get('irradiation'), {'source': 'PVGIS', 'ville': 'Casablanca'}, statut)
        with mock.patch('apps.calepinage.selectors.calepinage_du_devis', return_value=_Pivot('complet')), \
                mock.patch.object(co, '_ombrage_mesure', return_value=False):
            annexe = co.parametres_site_publics(devis, layout, {'productible_ville': 'Casablanca'})
        self.assertEqual(annexe['irradiation'], {'source': 'PVGIS', 'ville': 'Casablanca'})


class EnveloppeHtmlTest(SimpleTestCase):
    def test_le_html_porte_le_svg_et_le_format_a3(self):
        html = html_de_planche('<svg/>')
        self.assertIn('size:A3 landscape', html)
        self.assertIn('<svg/>', html)

    def test_le_nom_de_fichier_est_assaini(self):
        class Faux:
            pk = 41
            titre = 'Toiture / atelier «Bouskoura»'

        nom = nom_de_fichier(Faux(), 'pdf')
        self.assertTrue(nom.startswith('calepinage-41-'))
        self.assertTrue(nom.endswith('.pdf'))
        self.assertNotIn('/', nom)
        self.assertNotIn(' ', nom)


# ── ACAL601 — chaque module dans son vrai sens ──────────────────────────────

def _layout_de_48_modules(pose, pas=1.323):
    import copy

    layout = copy.deepcopy(LAYOUT)
    geometrie = layout['zones'][0]['geometry']
    geometrie['panelOrientation'] = pose
    geometrie['count'] = 48
    geometrie['panels'] = [{'cx': 1.0 + pas * i, 'cy': 1.0}
                           for i in range(48)]
    return layout


def _se_recouvrent(a, b):
    """Deux rectangles alignés sur les axes (azimut 180°) : recouvrement ?"""
    ax = [p[0] for p in a]
    ay = [p[1] for p in a]
    bx = [p[0] for p in b]
    by = [p[1] for p in b]
    return (min(ax) < max(bx) - 1e-9 and min(bx) < max(ax) - 1e-9
            and min(ay) < max(by) - 1e-9 and min(by) < max(ay) - 1e-9)


class EmpriseVraieDesModulesTest(SimpleTestCase):
    def _coins(self, pose, **modifs):
        pan = dict(geometrie_de_planche(_layout_de_48_modules(pose))['pans'][0],
                   **modifs)
        return pan, [coins_du_module(pan, c) for c in pan['modules']]

    def test_48_modules_portrait_au_pas_de_1_323_ne_se_recouvrent_pas(self):
        pan, coins = self._coins('portrait')
        self.assertEqual(len(coins), 48)
        for carre in coins:
            largeur = max(p[0] for p in carre) - min(p[0] for p in carre)
            hauteur = max(p[1] for p in carre) - min(p[1] for p in carre)
            self.assertAlmostEqual(largeur, 1.303, places=3)
            # 2,384 x cos(15 deg) dans la pente (le LAYOUT du fichier est a 15).
            self.assertAlmostEqual(hauteur, 2.384 * 0.9659258, places=3)
        for i, a in enumerate(coins):
            for b in coins[i + 1:]:
                self.assertFalse(_se_recouvrent(a, b))

    def test_pente_de_30_degres_donne_2_065_m_dans_la_pente(self):
        _pan, coins = self._coins('portrait', pente_deg=30.0)
        hauteur = (max(p[1] for p in coins[0]) - min(p[1] for p in coins[0]))
        self.assertAlmostEqual(hauteur, 2.065, places=3)

    def test_paysage_le_grand_cote_le_long_de_la_rangee(self):
        _pan, coins = self._coins('landscape')
        largeur = max(p[0] for p in coins[0]) - min(p[0] for p in coins[0])
        self.assertAlmostEqual(largeur, 2.384, places=3)

    def test_pose_mixte_lit_l_orientation_de_chaque_module(self):
        layout = _layout_de_48_modules('mixed')
        panneaux = layout['zones'][0]['geometry']['panels']
        panneaux[0]['orient'] = 'portrait'
        panneaux[1]['orient'] = 'landscape'
        pan = geometrie_de_planche(layout)['pans'][0]
        premier, deuxieme, troisieme = (
            coins_du_module(pan, c) for c in pan['modules'][:3])
        self.assertAlmostEqual(max(p[0] for p in premier)
                               - min(p[0] for p in premier), 1.303, places=3)
        self.assertAlmostEqual(max(p[0] for p in deuxieme)
                               - min(p[0] for p in deuxieme), 2.384, places=3)
        self.assertIsNone(troisieme)  # sans `orient` : jamais devine

    def test_sans_pose_azimut_ou_pente_le_module_reste_un_cercle(self):
        for retrait in ({'orientation_modules': None}, {'azimut_deg': None},
                        {'pente_deg': None}):
            _pan, coins = self._coins('portrait', **retrait)
            self.assertEqual(coins, [None] * 48)
        layout = _layout_de_48_modules('diagonale')
        pan = geometrie_de_planche(layout)['pans'][0]
        self.assertIsNone(pan['orientation_modules'])
        self.assertIsNone(coins_du_module(pan, pan['modules'][0]))

    def test_la_planche_dessine_les_rectangles_ou_dit_la_pose_absente(self):
        svg = svg_de_planche(
            geometrie_de_planche(_layout_de_48_modules('portrait')))
        self.assertNotIn('r="0.7"', svg)
        self.assertNotIn('orientation non enregistrée', svg)
        layout = _layout_de_48_modules('portrait')
        del layout['zones'][0]['geometry']['panelOrientation']
        svg = svg_de_planche(geometrie_de_planche(layout))
        self.assertIn('r="0.7"', svg)
        # R3-21 : la légende est coupée à la largeur du bandeau.
        for morceau in ('Module posé — orientation non',
                        'enregistrée (figuré par son centre) ;',
                        'ouvrir et enregistrer le calepinage'):
            self.assertIn(morceau, svg)


# ── ACAL603 — les cotes générales mesurent le TOIT seul ─────────────────────

def _layout_avec_obstacles_hors_rive():
    import copy

    layout = copy.deepcopy(LAYOUT)
    zone = layout['zones'][0]
    # Une lucarne à cheval sur la rive ouest et une cheminée au nord.
    zone['obstacles'] += [
        {'id': 'obs-2', 'centerLng': -7.60000, 'centerLat': 33.50005,
         'lengthM': 2.0, 'widthM': 3.0, 'type': 'lucarne',
         'provenance': 'RELEVE'},
        {'id': 'obs-3', 'centerLng': -7.59995, 'centerLat': 33.50010,
         'lengthM': 4.0, 'widthM': 1.0, 'type': 'cheminee',
         'provenance': 'RELEVE'}]
    return layout


class CotesDuToitSeulTest(SimpleTestCase):
    def test_un_obstacle_a_cheval_sur_la_rive_ne_change_pas_les_cotes(self):
        base = geometrie_de_planche(LAYOUT)
        large = geometrie_de_planche(_layout_avec_obstacles_hors_rive())
        # La boîte entière grandit, l'emprise du toit non.
        self.assertGreater(large['etendue'][2] - large['etendue'][0],
                           base['etendue'][2] - base['etendue'][0])
        self.assertEqual(large['etendue_toit'], base['etendue_toit'])
        x0, y0, x1, y1 = large['etendue_toit']
        svg = svg_de_planche(large)
        self.assertIn('>%s</text>' % texte_de_longueur(x1 - x0), svg)
        self.assertIn('>%s</text>' % texte_de_longueur(y1 - y0), svg)
        e0, f0, e1, f1 = large['etendue']
        self.assertNotIn('>%s</text>' % texte_de_longueur(e1 - e0), svg)
        self.assertNotIn('>%s</text>' % texte_de_longueur(f1 - f0), svg)

    def test_sans_contour_ni_pan_repli_sur_l_etendue(self):
        from apps.calepinage.services.planche import _etendue_du_toit

        geometrie = dict(geometrie_de_planche(LAYOUT), contour=[])
        geometrie['pans'] = [dict(p, points=[]) for p in geometrie['pans']]
        geometrie['etendue_toit'] = _etendue_du_toit(geometrie)
        self.assertIsNone(geometrie['etendue_toit'])
        x0, y0, x1, y1 = geometrie['etendue']
        self.assertIn('>%s</text>' % texte_de_longueur(x1 - x0),
                      svg_de_planche(geometrie))


# ── ACAL1969 — motif `orientation_nord` d'un pan vide (contrat du document) ──

class MotifOrientationNordTest(SimpleTestCase):
    """Le schéma v2 accepte `orientation_nord` (exemple du contrat), refuse un
    code inconnu en NOMMANT le champ, et la planche (ACAL550) l'imprime."""

    def setUp(self):
        import copy
        import json
        import pathlib

        chemin = (pathlib.Path(__file__).resolve().parents[1]
                  / 'contract_samples' / 'roof_layout_v2.schema.json')
        schema = json.loads(chemin.read_text(encoding='utf-8'))
        self.motif = copy.deepcopy(
            schema['exemple_motifs_pans_vides']['pan-nord-pente'])
        self.document = copy.deepcopy(schema['exemple'])
        self.document['motifsPansVides'] = {'pan-nord-pente': self.motif}

    def test_orientation_nord_conforme_au_schema(self):
        from apps.calepinage.services.io_layout import valider_document

        self.assertEqual(self.motif['code'], 'orientation_nord')
        valider_document(self.document)

    def test_code_inconnu_refuse_en_nommant_le_champ(self):
        from apps.calepinage.services.io_layout import (
            ImportLayoutRefuse, valider_document)

        self.motif['code'] = 'autre'
        with self.assertRaises(ImportLayoutRefuse) as capture:
            valider_document(self.document)
        self.assertEqual(capture.exception.champ,
                         'motifsPansVides.pan-nord-pente.code')

    def test_la_planche_imprime_le_motif_d_un_pan_nord_vide(self):
        import copy

        from apps.calepinage.services.planche import CONTENU_POSE

        layout = copy.deepcopy(LAYOUT)
        geometrie = layout['zones'][0]['geometry']
        geometrie.update(azimuthDeg=0.0, tiltDeg=22.0, count=0, panels=[])
        layout['motifsPansVides'] = {'z1': self.motif}
        planche = geometrie_de_planche(layout)
        self.assertEqual(planche['pans'][0]['motif_vide'], self.motif['message'])
        # Le plan de pose (CAL211) est la feuille qui imprime le motif.
        self.assertIn(self.motif['message'],
                      svg_de_planche(planche, contenu=CONTENU_POSE))


# ── ACAL984 — une conception, trois documents, une seule vérité ─────────────

def _layout_croise(pose):
    """LAYOUT à 30° : 6 modules en deux rangées, pas de 2,6 m (aucun recouvrement
    possible en portrait comme en paysage)."""
    import copy

    layout = copy.deepcopy(LAYOUT)
    geometrie = layout['zones'][0]['geometry']
    geometrie.update(tiltDeg=30.0, panelOrientation=pose, count=6)
    geometrie['panels'] = [{'cx': 1.5 + 2.6 * (i % 3), 'cy': 1.5 + 3.5 * (i // 3)}
                           for i in range(6)]
    return layout


def _boite(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


class CroisementDesDocumentsTest(SimpleTestCase):
    """ACAL984 — planche, DXF et plan de câblage dessinent la MÊME conception :
    mêmes emprises (1 mm), échelle imprimée = échelle mesurée, un seul tracé
    TOITURE par contour. L'échec nomme le document et le module."""

    def _attendues(self, geometrie, pose):
        """Boîtes ATTENDUES, calculées des cotes du kit et des centres
        stockés — sans passer par ``coins_du_module``."""
        import math

        long_, court = 2.384, 1.303
        rangee, pente = (court, long_) if pose == 'portrait' else (long_, court)
        demi_x, demi_y = rangee / 2.0, pente * math.cos(math.radians(30)) / 2.0
        return [(c[0] - demi_x, c[1] - demi_y, c[0] + demi_x, c[1] + demi_y)
                for c in geometrie['pans'][0]['modules']]

    @staticmethod
    def _planche(geometrie):
        """Boîtes des modules lues DANS le SVG, ramenées en mètres avec
        l'échelle MESURÉE sur la barre ; + (échelle mesurée, rang imprimé)."""
        import re

        from apps.calepinage.services.planche import (
            VERT_MODULE, _transformation,
        )

        svg = svg_de_planche(geometrie)
        barre = re.search(r'<g><rect x="[\d.]+" y="[\d.]+" width="([\d.]+)" '
                          r'height="1.6"', svg)
        metres = re.search(r'<text x="[\d.]+" y="[\d.]+" font-size="3" '
                           r'text-anchor="end" fill="[^"]+">([\d,]+) m</text>',
                           svg)
        rang = re.search(r'Échelle du tracé 1/(\d+)', svg)
        assert barre and metres and rang, 'planche : barre ou mention absente'
        echelle = 2.0 * float(barre.group(1)) / float(
            metres.group(1).replace(',', '.'))
        vers_feuille, _interne = _transformation(geometrie['etendue'])
        ox, oy = vers_feuille((0.0, 0.0))
        boites = []
        for brut in re.findall(r'<polygon points="([^"]+)" fill="[^"]+" '
                               r'stroke="%s"' % VERT_MODULE, svg):
            pts = [tuple(float(c) for c in couple.split(','))
                   for couple in brut.split()]
            boites.append(_boite([((x - ox) / echelle, (oy - y) / echelle)
                                  for x, y in pts]))
        return boites, echelle, int(rang.group(1))

    def _verifier(self, nom, boites, attendues):
        self.assertEqual(len(boites), len(attendues), '%s : compte' % nom)
        for rang, (lue, voulue) in enumerate(
                zip(sorted(boites), sorted(attendues)), start=1):
            for a, b in zip(lue, voulue):
                self.assertAlmostEqual(
                    a, b, delta=0.001,
                    msg='%s, module %d : %s au lieu de %s' % (nom, rang, lue, voulue))
        for i, a in enumerate(boites):
            for b in boites[i + 1:]:
                self.assertFalse(
                    _se_recouvrent(
                        [(a[0], a[1]), (a[2], a[3])],
                        [(b[0], b[1]), (b[2], b[3])]),
                    '%s : deux modules se recouvrent' % nom)

    def test_planche_dxf_et_cablage_ont_les_emprises_de_la_conception(self):
        import io

        import ezdxf

        from apps.calepinage.services.documents.plan_cablage import (
            _plan_de_cablage,
        )
        from apps.calepinage.services.export_dxf import (
            CALQUE_MODULES, CALQUE_TOITURE, octets_dxf,
        )

        for pose in ('portrait', 'landscape'):
            layout = _layout_croise(pose)
            geometrie = geometrie_de_planche(layout)
            attendues = self._attendues(geometrie, pose)
            self.assertEqual(len(attendues), 6, pose)

            boites, echelle, rang = self._planche(geometrie)
            self._verifier('planche %s' % pose, boites, attendues)
            # (3) l'échelle mesurée dans le SVG est l'imprimée.
            self.assertLessEqual(abs(1000.0 / echelle - rang), 0.5,
                                 'planche %s : 1/%d imprimé, 1/%.1f dessiné'
                                 % (pose, rang, 1000.0 / echelle))

            dxf = ezdxf.read(io.StringIO(octets_dxf(geometrie).decode('utf-8')))
            modules = [e for e in dxf.modelspace()
                       if e.dxf.layer == CALQUE_MODULES]
            self._verifier('DXF %s' % pose,
                           [_boite([(p[0], p[1]) for p in e.get_points()])
                            for e in modules], attendues)
            # (4) un seul tracé TOITURE : le pan est égal au contour.
            self.assertEqual(
                len([e for e in dxf.modelspace()
                     if e.dxf.layer == CALQUE_TOITURE]), 1,
                'DXF %s : TOITURE en double' % pose)

            affectation = [{'module': 'z1#%d' % r, 'pan': 'Pan Sud',
                            'chaine': 1, 'onduleur': 1, 'mppt': 1,
                            'source': 'automatique'} for r in range(1, 7)]
            plan = _plan_de_cablage(layout, affectation)
            self._verifier('câblage %s' % pose,
                           [_boite(m['coins']) for m in plan['modules']],
                           attendues)

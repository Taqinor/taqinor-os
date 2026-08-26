"""CORRECTION #8 — le calepinage PAR OPTION.

CE QUE CES TESTS PROTÈGENT, ET POURQUOI CHACUN EXISTE.

1. **Aucun panneau hors du toit du client.** C'est LA garantie du chantier :
   un dessin dérivé montre l'installation à une autre taille, jamais un toit
   fabriqué. Chaque test d'extension revérifie, panneau par panneau, que le
   centre ajouté tombe dans le polygone RÉEL — un jour où la trame sera lue
   autrement, c'est ce test qui rougira.
2. **Le retrait est déterministe.** Deux ouvertures de la même page doivent
   donner le MÊME dessin, et l'ordre doit être celui qu'on a écrit : dernière
   zone, dernière rangée, ``u`` le plus grand d'abord. Un ordre instable
   (dict, set, tri par flottant) ferait « bouger » les panneaux d'une carte à
   l'autre sous les yeux du client.
3. **Les trous ne se rebouchent pas.** L'emplacement que le commercial a
   contourné (une cheminée) reste vide dans TOUS les dessins : ce toit-là est
   le sien, pas un re-pavage.
4. **Ce que le toit refuse est DIT, pas dessiné.** ``plafonne`` existe pour
   qu'une carte ne prétende jamais poser 40 panneaux sur un toit qui en tient
   24.
5. **Aucun chiffre du devis ne déteint sur une autre taille.** Un layout
   dérivé ne porte ni ``result``, ni ``pans``, ni ``kwc``, ni
   ``neededPanels`` : ce sont les totaux de l'installation VENDUE.
6. **Les gardes sont celles des blocs voisins.** Même case de section que le
   calepinage officiel (``roof3d``), servi aux deux niveaux, best-effort,
   société par société.
7. **La forme SERVIE est celle du CONTRAT** (PACT10) — sans quoi la page et le
   serveur repartiraient chacun avec la leur.

Run:
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_calepinage_options -v 2
"""
import json
import math
import uuid
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes import calepinage_options as co
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'calepinage_options.json')

# ── Un toit SYNTHÉTIQUE, mais aux vraies conventions ────────────────────────
# Origine posée sur Casablanca ; le repère ENU est celui du calepineur.
_OLNG, _OLAT = -7.58, 33.57
_DEG2M = math.pi / 180 * 6378137.0
_COSLAT = math.cos(_OLAT * math.pi / 180)
#: Le pas de grille du toit d'essai (m) — assez proche d'un vrai calepinage
#: paysage pour que les tolérances du module soient éprouvées pour de bon.
_PAS_U, _PAS_V = 2.4, 1.2


def _lnglat(x, y):
    """ENU (m) → [lng, lat] autour de l'origine d'essai."""
    return [_OLNG + x / (_DEG2M * _COSLAT), _OLAT + y / _DEG2M]


def toit(rangees=3, colonnes=6, demi_largeur=12.0, demi_hauteur=8.0,
         obstacles=None, trou=None, mode=None):
    """Un ``roof_layout`` ASSAINI (forme ``_safe_roof_layout``) d'une zone.

    Azimut 0 ⇒ visée plein Nord : ``u = (-1, 0)`` et ``s = (0, 1)``, donc
    ``x = -u`` et ``y = v``. Les panneaux sont posés sur une grille régulière,
    exactement comme le calepineur les émet.

    ``trou`` retire une cellule par son indice ``(rangée, colonne)`` — c'est
    la cheminée que le commercial a contournée à la main.
    """
    panneaux = []
    for r in range(rangees):
        for c in range(colonnes):
            if trou == (r, c):
                continue
            uu = -6.0 + c * _PAS_U
            vv = -2.0 + r * _PAS_V
            panneaux.append({'cx': round(-uu, 3), 'cy': round(vv, 3)})
    geometrie = {
        'azimuthDeg': 0, 'tiltDeg': 15, 'family': 'south', 'flush': False,
        'count': len(panneaux), 'origin': [_OLNG, _OLAT], 'panels': panneaux,
    }
    if mode:
        geometrie['mode'] = mode
    return {
        'zones': [{
            'id': 'z1', 'label': 'Pan Sud',
            'vertices': [_lnglat(-demi_largeur, -demi_hauteur),
                         _lnglat(demi_largeur, -demi_hauteur),
                         _lnglat(demi_largeur, demi_hauteur),
                         _lnglat(-demi_largeur, demi_hauteur)],
            'obstacles': obstacles or [], 'roofType': 'flat',
            'pitchDeg': 0, 'facingAzimuthDeg': 0,
            'neededPanels': 20, 'geometry': geometrie,
        }],
        'pans': [{'label': 'Pan Sud', 'orientation': 'Sud', 'azimut_deg': 0,
                  'inclinaison_deg': 15, 'nb_panneaux': len(panneaux),
                  'kwc': 12.78, 'roof_type': 'flat'}],
        'result': {'panels': len(panneaux), 'kwc': 12.78, 'annualKwh': 21000},
    }


def obstacle(x, y, nord_sud, est_ouest, type_=None):
    """Un obstacle au format builder, positionné en ENU.

    ``lengthM`` = étendue NORD-SUD, ``widthM`` = étendue EST-OUEST — la
    convention de ``apps/web/src/lib/obstacles.ts`` (``obstacleRing`` :
    ``dLat = lengthM/2``, ``dLng = widthM/2 / cosLat``). Les paramètres sont
    NOMMÉS dans cet ordre pour qu'aucun test ne puisse les intervertir par
    inadvertance.
    """
    centre = _lnglat(x, y)
    brut = {'id': f'o-{x}-{y}', 'centerLng': centre[0], 'centerLat': centre[1],
            'lengthM': nord_sud, 'widthM': est_ouest}
    if type_:
        brut['type'] = type_
    return brut


def toit_mixte():
    """PV62 — un pavage MIXTE : pas PORTRAIT en bas, pas PAYSAGE en haut.

    C'est ce que le calepineur produit sur ``ctx.sel.orient === 'mixed'`` (une
    pose choisie rangée par rangée). ``_safe_zone_geometry`` ne publie PAS la
    pose par panneau : depuis la donnée assainie, ce toit ressemble à un toit
    uniforme — c'est tout le piège.
    """
    pas_portrait, pas_paysage = 1.323, 2.404
    panneaux = []
    for c in range(6):                                   # rangée portrait
        panneaux.append({'cx': round(-(-6.0 + c * pas_portrait), 3),
                         'cy': -2.0})
    for c in range(4):                                   # rangée paysage
        panneaux.append({'cx': round(-(-6.0 + c * pas_paysage), 3),
                         'cy': -0.8})
    layout = toit(rangees=1, colonnes=1)
    layout['zones'][0]['geometry']['panels'] = panneaux
    layout['zones'][0]['geometry']['count'] = len(panneaux)
    return layout


class _DevisFactice:
    """Le strict minimum que le module lit sur un devis : son layout BRUT."""

    def __init__(self, layout=None):
        self.roof_layout = layout
        self.pk = 1


def offres(**comptes):
    """Un bloc ``offres_tailles`` réduit à ce que ce module en lit."""
    return {'offres': [
        {'cle': cle, 'titre': cle.title(),
         'est_le_devis': cle == 'recommande',
         'sans': {'nb_panneaux': nb}}
        for cle, nb in comptes.items()]}


def panneaux_de(dessin):
    """Tous les centres du dessin, toutes zones confondues."""
    return [panneau
            for zone in dessin['layout']['zones']
            for panneau in (zone.get('geometry') or {}).get('panels', [])]


# ═══════════════════════════════════════════════════════════════════════════
# 1. La trame — lire la pose RÉELLE, jamais la deviner
# ═══════════════════════════════════════════════════════════════════════════

class TrameTests(SimpleTestCase):

    def test_les_rangees_sont_lues_dans_l_ordre_canonique(self):
        trame = co.lire_trames(toit(rangees=3, colonnes=6))[0]
        self.assertEqual(len(trame.rangees), 3)
        for _v, cellules in trame.rangees:
            self.assertEqual(len(cellules), 6)
            us = [u for u, _p in cellules]
            self.assertEqual(us, sorted(us))
        vs = [v for v, _c in trame.rangees]
        self.assertEqual(vs, sorted(vs))

    def test_les_pas_sont_MESURES_sur_la_pose(self):
        # Aucune constante de panneau n'est devinée : le pas est celui que le
        # calepinage porte. Une future pose portrait/paysage se dérive donc
        # toute seule, sans toucher à ce module.
        trame = co.lire_trames(toit())[0]
        self.assertAlmostEqual(trame.pas_colonne, _PAS_U, places=3)
        self.assertAlmostEqual(trame.pas_rangee, _PAS_V, places=3)

    def test_un_trou_n_est_pas_un_pas_de_grille(self):
        # Le trou laissé autour d'une cheminée crée un écart DOUBLE dans sa
        # rangée. Le retenir comme pas de grille aurait décalé toute
        # l'extension d'un demi-panneau — on prend donc le MINIMUM.
        trame = co.lire_trames(toit(trou=(1, 2)))[0]
        self.assertAlmostEqual(trame.pas_colonne, _PAS_U, places=3)

    def test_une_zone_sans_pose_est_ignoree(self):
        layout = toit()
        layout['zones'][0]['geometry']['panels'] = []
        self.assertEqual(co.lire_trames(layout), [])

    def test_une_zone_sans_contour_est_ignoree(self):
        layout = toit()
        layout['zones'][0]['vertices'] = [[_OLNG, _OLAT]]
        self.assertEqual(co.lire_trames(layout), [])

    def test_la_projection_enu_est_celle_du_navigateur(self):
        # `viewerFullModel.ringENUFromVertices` : (lng-o)*DEG2M*cos(lat),
        # (lat-o)*DEG2M. Si les deux divergent, « dans le polygone » ne veut
        # plus dire la même chose ici et à l'écran.
        anneau = co.anneau_enu([_lnglat(-12, -8), _lnglat(12, -8),
                                _lnglat(12, 8), _lnglat(-12, 8)],
                               [_OLNG, _OLAT])
        for attendu, obtenu in zip([(-12, -8), (12, -8), (12, 8), (-12, 8)],
                                   anneau):
            self.assertAlmostEqual(obtenu[0], attendu[0], places=2)
            self.assertAlmostEqual(obtenu[1], attendu[1], places=2)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Le RETRAIT — déterministe, et il ne rebouche rien
# ═══════════════════════════════════════════════════════════════════════════

class RetraitTests(SimpleTestCase):

    def test_on_retire_par_la_fin_de_la_derniere_rangee(self):
        layout = toit(rangees=3, colonnes=6)          # 18 posés
        trame = co.lire_trames(layout)[0]
        attendus = trame.panneaux_ordonnes()[:14]
        bloc = co.deriver(_DevisFactice(layout), offres(eco=14), layout)
        obtenus = panneaux_de(bloc['offres']['eco']['sans'])
        # Les 14 PREMIERS de l'ordre canonique, au bit près : ce sont les 4
        # DERNIERS (dernière rangée, u le plus grand) qui sont partis.
        self.assertEqual(obtenus, attendus)
        self.assertEqual(len(obtenus), 14)

    def test_le_retrait_est_rejouable(self):
        layout = toit()
        devis = _DevisFactice(layout)
        premier = co.deriver(devis, offres(eco=11), layout)
        second = co.deriver(devis, offres(eco=11), layout)
        self.assertEqual(json.dumps(premier, sort_keys=True),
                         json.dumps(second, sort_keys=True))

    def test_les_panneaux_gardes_ne_bougent_pas_d_un_millimetre(self):
        # Un panneau CONSERVÉ est recopié tel quel : jamais re-snappé sur une
        # lattice recalculée (ce serait « un autre toit » au sens WJ24).
        layout = toit()
        reels = {(p['cx'], p['cy'])
                 for p in layout['zones'][0]['geometry']['panels']}
        bloc = co.deriver(_DevisFactice(layout), offres(eco=12), layout)
        for panneau in panneaux_de(bloc['offres']['eco']['sans']):
            self.assertIn((panneau['cx'], panneau['cy']), reels)

    def test_un_trou_reste_un_trou(self):
        layout = toit(trou=(1, 2))                    # 17 posés
        bloc = co.deriver(_DevisFactice(layout), offres(eco=15), layout)
        dessines = {(p['cx'], p['cy'])
                    for p in panneaux_de(bloc['offres']['eco']['sans'])}
        # La cellule contournée (rangée 1, colonne 2) n'est JAMAIS rebouchée.
        cellule = (round(-(-6.0 + 2 * _PAS_U), 3), round(-2.0 + 1 * _PAS_V, 3))
        self.assertNotIn(cellule, dessines)


# ═══════════════════════════════════════════════════════════════════════════
# 3. L'EXTENSION — jamais un panneau dehors, jamais un toit fabriqué
# ═══════════════════════════════════════════════════════════════════════════

class ExtensionTests(SimpleTestCase):

    def _tous_dans_le_polygone(self, layout, dessin):
        """L'EMPREINTE ENTIÈRE tient — pas seulement le centre.

        Sonder le centre ne prouve RIEN de ce que l'en-tête de ce fichier
        promet : un panneau dont le centre est à 10 cm du bord a la moitié de
        sa surface dans le vide. On sonde donc les QUATRE COINS de l'empreinte
        conservatrice ET le retrait de rive, exactement comme le calepineur
        (`estimatorBrainV2` : chaque coin dans le toit ET à ≥ `setbackM` du
        bord). Les panneaux CONSERVÉS sont exclus du contrôle de retrait : le
        commercial a pu les poser avec un réglage de rive plus permissif, et
        les republier tels quels est justement la promesse WJ24.
        """
        zone = layout['zones'][0]
        anneau = co.anneau_enu(zone['vertices'], zone['geometry']['origin'])
        self.assertTrue(anneau)
        trame = co.lire_trames(layout)[0]
        reels = {(p['cx'], p['cy'])
                 for p in zone['geometry']['panels']}
        du = (trame.pas_colonne or 0) / 2.0
        dv = (trame.pas_rangee or 0) / 2.0
        self.assertGreater(du, 0)
        self.assertGreater(dv, 0)
        for panneau in panneaux_de(dessin):
            uu, vv = co._vers_uv(panneau['cx'], panneau['cy'],
                                 trame.u, trame.s)
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                coin = co._vers_enu(uu + su * du, vv + sv * dv,
                                    trame.u, trame.s)
                self.assertTrue(
                    co._dans_polygone(coin, anneau),
                    f'coin HORS du polygone réel : {panneau} → {coin}')
                if (panneau['cx'], panneau['cy']) in reels:
                    continue
                self.assertGreaterEqual(
                    co._distance_bord(coin, anneau), co._RETRAIT_RIVE_M,
                    f'coin AJOUTÉ sous le retrait de rive : {panneau}')

    def test_chaque_panneau_ajoute_tombe_dans_le_polygone_reel(self):
        layout = toit(rangees=3, colonnes=6)          # 18 posés
        bloc = co.deriver(_DevisFactice(layout), offres(max=30), layout)
        dessin = bloc['offres']['max']['sans']
        self.assertEqual(dessin['nb_panneaux_dessines'], 30)
        self.assertNotIn('plafonne', dessin)
        self._tous_dans_le_polygone(layout, dessin)

    def test_les_ajouts_restent_sur_la_trame_observee(self):
        layout = toit()
        trame = co.lire_trames(layout)[0]
        reels = {(round(p['cx'], 3), round(p['cy'], 3))
                 for p in layout['zones'][0]['geometry']['panels']}
        bloc = co.deriver(_DevisFactice(layout), offres(max=26), layout)
        ajouts = [p for p in panneaux_de(bloc['offres']['max']['sans'])
                  if (round(p['cx'], 3), round(p['cy'], 3)) not in reels]
        self.assertTrue(ajouts)
        for panneau in ajouts:
            uu, vv = co._vers_uv(panneau['cx'], panneau['cy'],
                                 trame.u, trame.s)
            # Sur la trame : (u - u0) et (v - v0) sont des MULTIPLES du pas.
            self.assertAlmostEqual((uu + 6.0) / _PAS_U,
                                   round((uu + 6.0) / _PAS_U), places=2)
            self.assertAlmostEqual((vv + 2.0) / _PAS_V,
                                   round((vv + 2.0) / _PAS_V), places=2)

    def test_les_panneaux_reels_sont_TOUS_conserves_a_l_extension(self):
        layout = toit()
        reels = [(p['cx'], p['cy'])
                 for p in layout['zones'][0]['geometry']['panels']]
        bloc = co.deriver(_DevisFactice(layout), offres(max=24), layout)
        dessines = {(p['cx'], p['cy'])
                    for p in panneaux_de(bloc['offres']['max']['sans'])}
        for centre in reels:
            self.assertIn(centre, dessines)

    def test_un_toit_trop_petit_PLAFONNE_au_lieu_de_deborder(self):
        etroit = toit(demi_largeur=8.0, demi_hauteur=3.5)
        bloc = co.deriver(_DevisFactice(etroit), offres(max=40), etroit)
        dessin = bloc['offres']['max']['sans']
        self.assertIs(dessin['plafonne'], True)
        self.assertEqual(dessin['nb_panneaux'], 40)
        self.assertLess(dessin['nb_panneaux_dessines'], 40)
        self._tous_dans_le_polygone(etroit, dessin)

    def test_un_obstacle_repousse_les_ajouts(self):
        # La boîte couvre x ∈ [-14, -8] : les prolongements de rangée qui
        # tombaient à x = -8,4 et -10,8 doivent DISPARAÎTRE.
        obs = [obstacle(-11.0, 0.0, nord_sud=10.0, est_ouest=6.0)]
        sans_obstacle = co.lire_trames(toit())[0].candidats(50)
        avec_obstacle = co.lire_trames(toit(obstacles=obs))[0].candidats(50)
        self.assertLess(min(p['cx'] for p in sans_obstacle), -8.0)
        self.assertGreater(min(p['cx'] for p in avec_obstacle), -8.0)
        for panneau in avec_obstacle:
            self.assertFalse(-14.0 < panneau['cx'] < -8.0
                             and -5.0 < panneau['cy'] < 5.0,
                             f'panneau posé SUR l’obstacle : {panneau}')

    def test_les_axes_d_un_obstacle_NON_CARRE_ne_sont_pas_intervertis(self):
        """F1 — ``lengthM`` est NORD-SUD, ``widthM`` EST-OUEST.

        Une boîte CARRÉE est aveugle à cette erreur : c'est pour ça qu'elle a
        survécu au premier jeu de tests. Une cheminée étroite et longue
        (1 m E-O × 6 m N-S) donne, elle, deux réponses opposées selon la
        convention — et si on les intervertit, la zone d'exclusion pivote de
        90° : elle protège une bande de toit VIDE et laisse poser un panneau
        SUR la souche.

        Ancré sur la SOURCE (``obstacles.ts obstacleRing``), pas sur notre
        propre sortie : la boîte doit s'étendre de ±3 m en Y (nord-sud) et de
        seulement ±0,5 m en X (est-ouest), dégagement en sus.
        """
        boites = co.obstacles_enu(
            [obstacle(0.0, 0.0, nord_sud=6.0, est_ouest=1.0, type_='autre')],
            [_OLNG, _OLAT])
        (xmin, ymin, xmax, ymax), = boites
        degagement = 0.3
        self.assertAlmostEqual(xmax - xmin, 1.0 + 2 * degagement, places=2)
        self.assertAlmostEqual(ymax - ymin, 6.0 + 2 * degagement, places=2)
        # …et la conséquence concrète : le panneau qui tombe au nord de la
        # souche est refusé, celui qui tombe à l'est ne l'est pas.
        trame = co.lire_trames(
            toit(obstacles=[obstacle(-8.4, -2.0, nord_sud=6.0,
                                     est_ouest=1.0)]))[0]
        for panneau in trame.candidats(50):
            self.assertFalse(-1.0 < panneau['cx'] + 8.4 < 1.0
                             and -3.5 < panneau['cy'] + 2.0 < 3.5,
                             f'panneau posé SUR la souche : {panneau}')

    def test_le_degagement_PV61_depend_du_TYPE_d_obstacle(self):
        """F2 — le calepineur exige ``distToBoundary > clearance``, par type.

        ``CLEARANCE_BY_TYPE`` (roofPro11/types.ts) : 0,50 m pour une cheminée,
        un chien-assis ou un édicule ; 0,30 m sinon. Ne tester que le
        chevauchement nu de la boîte laissait un panneau se poser à 1 cm d'une
        souche de cheminée — un emplacement que l'outil 3D refuse.
        """
        for type_, attendu in (('cheminee', 0.5), ('chien_assis', 0.5),
                               ('edicule', 0.5), ('ventilation', 0.3),
                               ('antenne', 0.3), ('autre', 0.3), (None, 0.3)):
            (xmin, _ymin, xmax, _ymax), = co.obstacles_enu(
                [obstacle(0.0, 0.0, nord_sud=2.0, est_ouest=2.0,
                          type_=type_)], [_OLNG, _OLAT])
            self.assertAlmostEqual(xmax - xmin, 2.0 + 2 * attendu, places=2,
                                   msg=f'dégagement faux pour {type_}')

    def test_une_cheminee_ecarte_PLUS_qu_une_antenne(self):
        # La preuve par le comportement, pas seulement par la constante : au
        # MÊME endroit, la cheminée (0,5 m) doit refuser au moins autant
        # d'emplacements que l'antenne (0,3 m).
        # L'obstacle est placé pour que la BANDE de dégagement tranche : son
        # bord est à 0,40 m de l'empreinte du prochain emplacement — hors de
        # portée d'une antenne (0,30 m), dans celle d'une cheminée (0,50 m).
        def ajouts(type_):
            obs = [obstacle(-11.0, 0.0, nord_sud=6.0, est_ouest=2.0,
                            type_=type_)]
            return {(p['cx'], p['cy'])
                    for p in co.lire_trames(toit(obstacles=obs))[0].candidats(60)}
        antenne = ajouts('antenne')
        cheminee = ajouts('cheminee')
        self.assertTrue(cheminee.issubset(antenne))
        self.assertLess(len(cheminee), len(antenne))
        # …et c'est bien l'emplacement de la bande qui fait la différence.
        self.assertIn((-8.4, -2.0), antenne)
        self.assertNotIn((-8.4, -2.0), cheminee)

    def test_un_pavage_MIXTE_refuse_de_se_prolonger(self):
        """F3/PV62 — deux pas dans la même zone ⇒ aucune extension.

        Le pas retenu serait le plus PETIT (portrait) et l'empreinte de
        validation deviendrait plus petite que le panneau réellement dessiné
        sur les rangées paysage : la preuve de contenance ne couvrirait plus
        le rendu. On plafonne — le pire honnête.
        """
        mixte = toit_mixte()
        trame = co.lire_trames(mixte)[0]
        self.assertFalse(trame.trame_reguliere())
        self.assertFalse(trame.extensible())
        self.assertEqual(trame.candidats(10), [])
        bloc = co.deriver(_DevisFactice(mixte), offres(max=20), mixte)
        dessin = bloc['offres']['max']['sans']
        self.assertIs(dessin['plafonne'], True)
        self.assertEqual(dessin['nb_panneaux_dessines'], 10)

    def test_une_trame_reguliere_A_TROU_reste_prolongeable(self):
        # La garde PV62 ne doit pas jeter le bébé : un TROU laisse un écart
        # DOUBLE, qui est bien un multiple entier du pas. Ce toit-là reste
        # extensible — sans quoi la garde casserait le cas le plus courant.
        troue = toit(trou=(1, 2))
        trame = co.lire_trames(troue)[0]
        self.assertTrue(trame.trame_reguliere())
        self.assertTrue(trame.extensible())

    def test_une_pose_a_la_main_n_est_jamais_prolongee(self):
        # PV30 — ``mode: 'free'`` : les centres ne sont pas sur une trame. Les
        # rejouer sur une lattice détruirait le gain de place enregistré.
        libre = toit(mode='free')
        devis = _DevisFactice(libre)
        bloc = co.deriver(devis, offres(eco=9, max=30), libre)
        self.assertEqual(bloc['offres']['eco']['sans']['nb_panneaux_dessines'],
                         9)                                    # retrait : OK
        maxi = bloc['offres']['max']['sans']
        self.assertIs(maxi['plafonne'], True)
        self.assertEqual(maxi['nb_panneaux_dessines'], 18)      # aucun ajout

    def test_une_zone_a_une_seule_rangee_n_est_pas_prolongee(self):
        # Sans pas de RANGÉE, la profondeur occupée par un panneau est
        # inconnue : on ne peut pas PROUVER qu'un ajout tient. On plafonne.
        plat = toit(rangees=1, colonnes=6)
        bloc = co.deriver(_DevisFactice(plat), offres(max=12), plat)
        dessin = bloc['offres']['max']['sans']
        self.assertIs(dessin['plafonne'], True)
        self.assertEqual(dessin['nb_panneaux_dessines'], 6)


# ═══════════════════════════════════════════════════════════════════════════
# 4. LA FORME SERVIE — le contrat, et rien du devis qui déteigne
# ═══════════════════════════════════════════════════════════════════════════

class FormeServieTests(SimpleTestCase):

    def test_la_taille_du_calepinage_pointe_sur_le_layout_officiel(self):
        layout = toit()                               # 18 posés
        bloc = co.deriver(_DevisFactice(layout),
                          offres(recommande=18), layout)
        dessin = bloc['offres']['recommande']['sans']
        self.assertEqual(dessin['origine'], 'devis')
        # AUCUN layout transporté : la page réutilise la clé racine
        # ``roof_layout``. Zéro copie, donc zéro dessin capable de diverger de
        # l'artefact contractuel.
        self.assertNotIn('layout', dessin)
        self.assertEqual(bloc['nb_panneaux_calepines'], 18)

    def test_un_layout_derive_ne_porte_aucun_total_du_devis(self):
        layout = toit()
        bloc = co.deriver(_DevisFactice(layout), offres(eco=12), layout)
        derive = bloc['offres']['eco']['sans']['layout']
        self.assertEqual(set(derive), {'version', 'zones'})
        self.assertNotIn('result', derive)
        self.assertNotIn('pans', derive)
        zone = derive['zones'][0]
        self.assertNotIn('neededPanels', zone)
        self.assertNotIn('kwc', zone['geometry'])
        # …mais tout ce que la visionneuse LIT est là.
        self.assertEqual(zone['geometry']['count'], 12)
        for cle in ('azimuthDeg', 'tiltDeg', 'family', 'flush', 'origin'):
            self.assertIn(cle, zone['geometry'])
        for cle in ('vertices', 'obstacles', 'roofType', 'pitchDeg',
                    'facingAzimuthDeg'):
            self.assertIn(cle, zone)

    def test_le_compte_declare_suit_les_panneaux_dessines(self):
        layout = toit()
        bloc = co.deriver(_DevisFactice(layout), offres(eco=13), layout)
        zone = bloc['offres']['eco']['sans']['layout']['zones'][0]
        self.assertEqual(zone['geometry']['count'],
                         len(zone['geometry']['panels']))

    def test_les_deux_variantes_sont_dessinees_separement(self):
        layout = toit()
        bloc = co.deriver(_DevisFactice(layout), {'offres': [{
            'cle': 'eco', 'est_le_devis': False,
            'sans': {'nb_panneaux': 12}, 'avec': {'nb_panneaux': 15}}]},
            layout)
        eco = bloc['offres']['eco']
        self.assertEqual(eco['sans']['nb_panneaux_dessines'], 12)
        self.assertEqual(eco['avec']['nb_panneaux_dessines'], 15)

    def test_sans_calepinage_le_bloc_est_absent(self):
        self.assertIsNone(co.deriver(_DevisFactice(None), offres(eco=10),
                                     None))
        self.assertIsNone(co.deriver(_DevisFactice({}), offres(eco=10), {}))

    def test_sans_taille_le_bloc_est_absent(self):
        layout = toit()
        self.assertIsNone(co.deriver(_DevisFactice(layout), None, layout))
        self.assertIsNone(co.deriver(_DevisFactice(layout), {'offres': []},
                                     layout))

    def test_la_garde_best_effort_ne_leve_jamais(self):
        layout = toit()
        with mock.patch.object(co, 'deriver', side_effect=RuntimeError('boum')):
            self.assertIsNone(co.calepinage_options_publique(
                _DevisFactice(layout), offres(eco=10), layout))

    def test_la_forme_servie_est_celle_du_contrat(self):
        exemple = json.loads(CONTRAT.read_text(encoding='utf-8'))
        attendu = exemple['exemple']['calepinage_options']
        layout = toit()
        bloc = co.deriver(_DevisFactice(layout),
                          offres(eco=12, recommande=18, max=30), layout)
        self.assertEqual(set(bloc) - {'sld'}, set(attendu) - {'sld'})
        self.assertEqual(set(bloc['offres']), set(attendu['offres']))
        derive = bloc['offres']['eco']['sans']
        self.assertEqual(set(derive),
                         set(attendu['offres']['eco']['sans']))
        self.assertEqual(set(bloc['offres']['recommande']['sans']),
                         set(attendu['offres']['recommande']['sans']))

    def test_aucun_prix_ni_marge_ne_franchit_la_frontiere(self):
        """DÉFENSE EN PROFONDEUR — même si l'appelant se trompait de source.

        En production le dessin est bâti sur la sortie DÉJÀ assainie de
        ``_safe_roof_layout`` : ces champs ne peuvent pas s'y trouver. Ce test
        les injecte QUAND MÊME, aux QUATRE profondeurs où des échantillons
        réels en portent (racine, zone, obstacle, panneau), parce que le jour
        où quelqu'un passera le blob BRUT « c'est plus simple », c'est ce test
        qui doit rougir — pas un client qui doit lire un prix d'achat.

        L'obstacle est la profondeur la plus discrète : sa liste est recopiée
        EN BLOC (c'est déjà le comportement de ``_safe_roof_layout``), donc
        c'est la seule où une clé parasite pourrait encore voyager. Le test la
        surveille pour que ce fait reste une décision, pas un oubli.
        """
        layout = toit(obstacles=[obstacle(-11.0, 0.0, nord_sud=2.0,
                                          est_ouest=2.0)])
        layout['prix_achat_total'] = 123456
        layout['zones'][0]['marge'] = 0.31
        layout['zones'][0]['obstacles'][0]['prix_achat'] = 4242
        layout['zones'][0]['geometry']['panels'][0]['prix_achat'] = 9999
        bloc = co.deriver(_DevisFactice(layout), offres(eco=12), layout)
        blob = json.dumps(bloc)
        for fuite in ('prix_achat', 'marge', 'prix_vente', '123456', '9999',
                      '4242', '0.31'):
            self.assertNotIn(fuite, blob)


# ═══════════════════════════════════════════════════════════════════════════
# 4 bis. UNE ZONE ILLISIBLE — la carte et le dessin ne divergent JAMAIS
# ═══════════════════════════════════════════════════════════════════════════

class ZoneIllisibleTests(SimpleTestCase):
    """F4 — le calepinage PUBLIÉ est l'ancre, pas ce qu'on sait relire.

    ``_safe_roof_layout`` publie une zone dès qu'elle est un dict ; la
    dérivation, elle, en écarte certaines (contour de moins de trois sommets
    valides). Compter le toit sur les SECONDES ouvrait deux mensonges
    symétriques — c'est ce que ces deux tests arment.
    """

    def _toit_a_deux_zones(self):
        """Zone 1 lisible (18 panneaux) + zone 2 publiée mais illisible (2)."""
        layout = toit()
        illisible = json.loads(json.dumps(layout['zones'][0]))
        illisible['id'] = 'z2'
        illisible['label'] = 'Pan Est'
        illisible['vertices'] = [_lnglat(20, 20), _lnglat(22, 20)]  # < 3
        illisible['geometry']['panels'] = [{'cx': 20.0, 'cy': 20.0},
                                           {'cx': 22.0, 'cy': 20.0}]
        illisible['geometry']['count'] = 2
        layout['zones'].append(illisible)
        return layout

    def test_le_toit_est_compte_sur_les_zones_PUBLIEES(self):
        layout = self._toit_a_deux_zones()
        self.assertEqual(co.nb_panneaux_publies(layout), 20)   # 18 + 2
        self.assertEqual(len(co.lire_trames(layout)), 1)       # une seule
        bloc = co.deriver(_DevisFactice(layout), offres(recommande=20),
                          layout)
        self.assertEqual(bloc['nb_panneaux_calepines'], 20)

    def test_a_la_taille_du_VRAI_pose_le_dessin_reste_le_calepinage(self):
        # (a) — avant, 20 ≠ nb_reel(18) partait en DÉRIVÉ et le dessin perdait
        # silencieusement les 2 panneaux de la zone illisible : « Recommandé »
        # divergeait du roof_layout racine, exactement ce que origine:"devis"
        # existe pour empêcher.
        layout = self._toit_a_deux_zones()
        bloc = co.deriver(_DevisFactice(layout), offres(recommande=20),
                          layout)
        dessin = bloc['offres']['recommande']['sans']
        self.assertEqual(dessin['origine'], 'devis')
        self.assertNotIn('layout', dessin)
        self.assertEqual(dessin['nb_panneaux_dessines'], 20)

    def test_le_sous_compte_ne_se_fait_plus_passer_pour_le_devis(self):
        # (b) — avant, une taille à 18 (le sous-compte) recevait
        # origine:"devis" alors que le calepinage racine en dessine 20.
        layout = self._toit_a_deux_zones()
        bloc = co.deriver(_DevisFactice(layout), offres(eco=18,
                                                        recommande=20),
                          layout)
        self.assertNotIn('eco', bloc['offres'])       # absence honnête
        self.assertEqual(bloc['offres']['recommande']['sans']['origine'],
                         'devis')

    def test_un_toit_entierement_lisible_derive_normalement(self):
        # La garde ne doit pas éteindre le cas nominal.
        layout = toit()
        bloc = co.deriver(_DevisFactice(layout), offres(eco=12,
                                                        recommande=18),
                          layout)
        self.assertEqual(bloc['offres']['eco']['sans']['origine'], 'derive')


# ═══════════════════════════════════════════════════════════════════════════
# 4 ter. L'ALIGNEMENT DES RANGS — la protection « pose à la main » tient
# ═══════════════════════════════════════════════════════════════════════════

class RangsDeZoneTests(SimpleTestCase):

    def test_une_entree_parasite_ne_decale_plus_le_drapeau_free(self):
        """F6 — le rang BRUT n'est pas le rang PUBLIÉ.

        ``_safe_roof_layout`` saute les entrées qui ne sont pas des dicts. Une
        entrée parasite AVANT la zone libre décalait tous les rangs d'un cran :
        la zone libre héritait du drapeau de sa voisine et se faisait
        prolonger sur une lattice qu'elle n'a jamais eue.
        """
        libre = toit(mode='free')
        brut = json.loads(json.dumps(libre))
        brut['zones'].insert(0, 'entrée parasite')      # sautée par la whitelist
        identifiants, rangs = co._modes_libres(_DevisFactice(brut))
        self.assertEqual(identifiants, {'z1'})
        self.assertEqual(rangs, {0})                    # rang PUBLIÉ, pas brut
        trame = co.lire_trames(libre, (identifiants, rangs))[0]
        self.assertTrue(trame.libre)
        bloc = co.deriver(_DevisFactice(brut), offres(max=24), libre)
        dessin = bloc['offres']['max']['sans']
        self.assertIs(dessin['plafonne'], True)
        self.assertEqual(dessin['nb_panneaux_dessines'], 18)

    def test_le_repli_par_rang_couvre_les_zones_sans_id(self):
        libre = toit(mode='free')
        libre['zones'][0].pop('id')
        brut = json.loads(json.dumps(libre))
        identifiants, rangs = co._modes_libres(_DevisFactice(brut))
        self.assertEqual(identifiants, set())
        self.assertEqual(rangs, {0})
        self.assertTrue(co.lire_trames(libre, (identifiants, rangs))[0].libre)


# ═══════════════════════════════════════════════════════════════════════════
# 5. LE POINTEUR DE SCHÉMA — nommer, jamais fabriquer
# ═══════════════════════════════════════════════════════════════════════════

def design(batterie_presente):
    """L'artefact ``Devis.electrical_design``, reduit a ce qui tranche.

    ``materiel.batterie.presente`` est pose par ``electrical_service`` au
    moment du calcul (``bool(entree.batterie)``) : c'est LE fait qui dit si le
    schema stocke dessine une batterie.
    """
    return {'materiel': {'batterie': {'presente': batterie_presente,
                                      'designation': 'Deye BOS-B 16'}}}


class PointeurSldTests(SimpleTestCase):
    """F7 — le pointeur lit l'ARTEFACT, jamais un signal commercial.

    Deduire « avec batterie » du fait que la carte Recommande sert une
    variante « avec » revenait a legender un dessin TECHNIQUE avec une
    information COMMERCIALE. Les deux divergent pour de vrai, dans les deux
    sens, et la page affirmait alors au client un fait que le schema sous ses
    yeux contredisait.
    """

    def _bloc(self, offres_tailles, sld_servi, design_stocke=None):
        layout = toit()
        with mock.patch.object(co, '_design_stocke',
                               return_value=design_stocke):
            return co.deriver(_DevisFactice(layout), offres_tailles, layout,
                              sld_servi=sld_servi)

    def test_sans_schema_servi_aucun_pointeur(self):
        bloc = self._bloc(offres(eco=12, recommande=18), sld_servi=False,
                          design_stocke=design(False))
        self.assertNotIn('sld', bloc)

    def test_le_pointeur_nomme_la_carte_du_devis(self):
        bloc = self._bloc(offres(eco=12, recommande=18), sld_servi=True,
                          design_stocke=design(False))
        self.assertEqual(bloc['sld'], {'cle': 'recommande',
                                       'variante': 'sans'})

    def test_la_variante_vient_de_l_artefact_pas_de_la_carte(self):
        deux = {'offres': [{
            'cle': 'recommande', 'est_le_devis': True,
            'sans': {'nb_panneaux': 18}, 'avec': {'nb_panneaux': 18}}]}
        avec = self._bloc(deux, sld_servi=True, design_stocke=design(True))
        self.assertEqual(avec['sld']['variante'], 'avec')
        sans = self._bloc(deux, sld_servi=True, design_stocke=design(False))
        self.assertEqual(sans['sld']['variante'], 'sans')

    def test_carte_AVEC_mais_schema_SANS_batterie_ne_ment_plus(self):
        # Chemin vivant : les lignes servent l'option batterie (la carte
        # « avec » existe) mais la conception a ete jouee sur le panier SANS.
        # L'ancien code legendait « avec batterie » un schema raccorde reseau.
        bloc = self._bloc({'offres': [{
            'cle': 'recommande', 'est_le_devis': True,
            'sans': {'nb_panneaux': 18}, 'avec': {'nb_panneaux': 18}}]},
            sld_servi=True, design_stocke=design(False))
        self.assertEqual(bloc['sld']['variante'], 'sans')

    def test_schema_AVEC_batterie_sur_un_devis_devenu_SANS_est_omis(self):
        # Chemin vivant inverse : l'artefact est anterieur a une
        # resynchronisation qui a retire la batterie. La carte ne sert plus
        # que « sans » ; le schema, lui, dessine encore une batterie. Aucun
        # pointeur — plutot rien qu'une legende fausse.
        bloc = self._bloc({'offres': [{
            'cle': 'recommande', 'est_le_devis': True,
            'sans': {'nb_panneaux': 18}}]},
            sld_servi=True, design_stocke=design(True))
        self.assertNotIn('sld', bloc)

    def test_un_artefact_muet_ne_donne_aucun_pointeur(self):
        for muet in (None, {}, {'materiel': {}},
                     {'materiel': {'batterie': {}}}):
            bloc = self._bloc(offres(eco=12, recommande=18), sld_servi=True,
                              design_stocke=muet)
            self.assertNotIn('sld', bloc)

    def test_une_taille_AJUSTEE_ne_porte_plus_le_schema(self):
        # Le vendeur a modifie la taille « Recommande » : elle n'est plus le
        # devis, donc le schema stocke ne la decrit plus. Absence honnete.
        bloc = self._bloc({'offres': [{
            'cle': 'recommande', 'est_le_devis': False,
            'sans': {'nb_panneaux': 18}}]}, sld_servi=True,
            design_stocke=design(False))
        self.assertNotIn('sld', bloc)

    def test_aucune_autre_taille_ne_recoit_de_schema(self):
        bloc = self._bloc(offres(eco=12, recommande=18, max=30),
                          sld_servi=True, design_stocke=design(False))
        self.assertEqual(bloc['sld']['cle'], 'recommande')
        for cle in ('eco', 'max'):
            for dessin in bloc['offres'][cle].values():
                self.assertNotIn('sld', dessin)


# ═══════════════════════════════════════════════════════════════════════════
# 6. L'ANNEXE « PARAMÈTRES DU SITE » (audit #23)
# ═══════════════════════════════════════════════════════════════════════════

class ParametresSiteTests(SimpleTestCase):

    def test_les_angles_viennent_du_pan_le_plus_puissant(self):
        layout = toit()
        annexe = co.parametres_site_publics(_DevisFactice(layout), layout)
        self.assertEqual(annexe['orientation_deg'], 0.0)
        self.assertEqual(annexe['inclinaison_deg'], 15.0)
        self.assertEqual(annexe['orientation'], 'Sud')
        self.assertEqual(annexe['type_toit'], 'flat')

    def test_aucune_coordonnee_machine_ne_sort(self):
        # ANTICOPIE : des angles et des noms, jamais un repère exploitable.
        layout = toit()
        annexe = co.parametres_site_publics(
            _DevisFactice(layout), layout,
            hypotheses={'productible_ville': 'Casablanca'})
        blob = json.dumps(annexe)
        for fuite in ('origin', 'vertices', 'centerLng', str(_OLNG),
                      str(_OLAT), 'cx', 'cy'):
            self.assertNotIn(fuite, blob)

    def test_l_irradiation_NOMME_la_source_sans_republier_le_chiffre(self):
        # PAS DE SECOND ARRONDI : le productible vit dans `hypotheses`.
        annexe = co.parametres_site_publics(
            _DevisFactice(None), None,
            hypotheses={'productible_ville': 'Casablanca',
                        'productible_net_kwh_kwc': 1687})
        self.assertEqual(annexe['irradiation'],
                         {'source': 'PVGIS', 'ville': 'Casablanca'})
        self.assertNotIn('1687', json.dumps(annexe))

    def test_sans_ville_pvgis_l_irradiation_est_omise(self):
        annexe = co.parametres_site_publics(
            _DevisFactice(None), None, hypotheses={'tarif_kwh': 1.4})
        self.assertIsNone(annexe)

    def test_aucun_ombrage_par_defaut(self):
        # RÈGLE FONDATEUR : pas de valeur mesurée ⇒ pas de champ. Un « 0 % de
        # pertes d'ombrage » serait un chiffre que personne n'a mesuré.
        layout = toit()
        annexe = co.parametres_site_publics(_DevisFactice(layout), layout)
        self.assertNotIn('ombrage', annexe)

    def test_l_ombrage_MESURE_est_lu_sous_LA_VRAIE_CLE(self):
        """F8 — la clé est ``shading12x24``, comme le producteur l'écrit.

        Le champ était du CODE MORT : il interrogeait ``shading``, un nom que
        rien n'écrit (``roofPro11/prefill.ts`` sérialise ``shading12x24``, et
        ``apps.ventes.etude`` lit déjà ce nom-là). Le test d'origine injectait
        la clé fantôme, donc il se mentait à lui-même : les deux moitiés
        étaient d'accord sur une clé qui n'existe nulle part en production.
        """
        layout = toit()
        brut = dict(layout)
        brut['shading12x24'] = [[0.9] * 24 for _ in range(12)]
        annexe = co.parametres_site_publics(_DevisFactice(brut), layout)
        self.assertEqual(annexe['ombrage'], {'mesure': True})
        self.assertNotIn('0.9', json.dumps(annexe))

    def test_l_ombrage_est_lu_AUSSI_par_zone(self):
        # MÊMES deux emplacements que ``etude`` : « PV71 choisit encore où la
        # matrice voyage côté web ».
        layout = toit()
        brut = json.loads(json.dumps(layout))
        brut['zones'][0]['shading12x24'] = [[0.8] * 24 for _ in range(12)]
        annexe = co.parametres_site_publics(_DevisFactice(brut), layout)
        self.assertEqual(annexe['ombrage'], {'mesure': True})

    def test_la_CLE_FANTOME_ne_declenche_rien(self):
        # La garde anti-régression du code mort : si quelqu'un réintroduit
        # ``shading``, ce test rougit au lieu de laisser le champ revenir mort.
        layout = toit()
        brut = dict(layout)
        brut['shading'] = [[0.9] * 24 for _ in range(12)]
        annexe = co.parametres_site_publics(_DevisFactice(brut), layout)
        self.assertNotIn('ombrage', annexe or {})

    def test_une_matrice_d_ombrage_mal_formee_est_refusee_en_bloc(self):
        layout = toit()
        for matrice in ([[0.9] * 24 for _ in range(11)],
                        [[0.9] * 23 for _ in range(12)],
                        [[2.0] * 24 for _ in range(12)],
                        'pas une matrice'):
            brut = dict(layout)
            brut['shading12x24'] = matrice
            annexe = co.parametres_site_publics(_DevisFactice(brut), layout)
            self.assertNotIn('ombrage', annexe or {})

    def test_les_chaines_resument_ce_qui_est_deja_public(self):
        annexe = co.parametres_site_publics(
            _DevisFactice(None), None,
            conception_electrique={'chaines': [{'pan': 'Sud', 'mppt': 1,
                                                'nb_modules': 11},
                                               {'pan': 'Sud', 'mppt': 2,
                                                'nb_modules': 11}]})
        self.assertEqual(annexe['chaines'],
                         {'nb': 2, 'modules_par_chaine': [11, 11]})

    def test_rien_de_reel_aucune_cle(self):
        self.assertIsNone(co.parametres_site_publics(_DevisFactice(None), None))
        self.assertIsNone(co.parametres_site_publics(_DevisFactice({}), {},
                                                     hypotheses={},
                                                     conception_electrique={}))


# ═══════════════════════════════════════════════════════════════════════════
# 7. LA CHARGE UTILE PUBLIQUE — gardes, sections, société
# ═══════════════════════════════════════════════════════════════════════════

def _company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug,
                                               defaults={'nom': slug})
    return company


def _devis(company, user, client_obj, reference, layout=None):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client_obj,
        statut='envoye', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user, roof_layout=layout)
    for designation, quantite, pu in [('Onduleur réseau 8kW', '1', '14000'),
                                      ('Panneau mono 550W', '18', '1400')]:
        produit = Produit.objects.create(
            company=company, nom=designation,
            sku=f'{reference[-6:]}-{designation[:8]}',
            prix_vente=Decimal(pu), prix_achat=Decimal('9999'),
            quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=designation,
            quantite=Decimal(quantite), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


class ChargeUtileTests(TestCase):
    """Les gardes de la VUE — celles des blocs voisins, à la lettre."""

    def setUp(self):
        self.company = _company('calep-opt')
        self.user = User.objects.create_user(
            username='calep_opt', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Toit', prenom='Client',
            email='toit@ex.com', telephone='+212600000009')

    def _lien(self, devis, **kwargs):
        token = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.company, devis=devis, token=token,
            niveau=kwargs.pop('niveau', ShareLink.NIVEAU_CONFIANCE), **kwargs)
        return token

    def _payload(self, token):
        reponse = DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(reponse.status_code, 200)
        return reponse.json()

    # ── la garde de la vue, éprouvée sans rejouer tout le moteur ────────────
    def _garde(self, devis, **kwargs):
        from apps.ventes.public_views import _calepinage_options_publique
        from apps.ventes.public_views import _safe_roof_layout
        parametres = {'offres_tailles': offres(eco=12, recommande=18),
                      'layout_public': _safe_roof_layout(devis),
                      'sld_servi': False, 'est_residentiel': True}
        parametres.update(kwargs)
        return _calepinage_options_publique(
            devis, parametres['offres_tailles'], parametres['layout_public'],
            parametres['sld_servi'], parametres['est_residentiel'])

    def test_un_devis_non_residentiel_n_a_pas_de_dessins(self):
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-1', layout=toit())
        self.assertIsNone(self._garde(devis, est_residentiel=False))

    def test_sans_tailles_aucun_dessin(self):
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-2', layout=toit())
        self.assertIsNone(self._garde(devis, offres_tailles=None))

    def test_section_calepinage_decochee_aucun_dessin(self):
        # MÊME case que le calepinage officiel : le layout assaini vaut déjà
        # None, donc les dessins par option partent AVEC lui — jamais un
        # dessin orphelin sur une page qui a masqué le calepinage.
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-3', layout=toit())
        self.assertIsNone(self._garde(devis, layout_public=None))

    def test_un_devis_avec_calepinage_recoit_ses_dessins(self):
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-4', layout=toit())
        bloc = self._garde(devis)
        self.assertEqual(bloc['nb_panneaux_calepines'], 18)
        self.assertEqual(set(bloc['offres']), {'eco', 'recommande'})

    # ── bout en bout, sur le vrai endpoint ─────────────────────────────────
    def test_l_endpoint_sert_les_dessins_quand_les_tailles_existent(self):
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-5', layout=toit())
        token = self._lien(devis)
        with mock.patch('apps.ventes.public_views._offres_tailles_publique',
                        return_value=offres(eco=12, recommande=18, max=30)):
            payload = self._payload(token)
        bloc = payload['calepinage_options']
        self.assertEqual(set(bloc['offres']), {'eco', 'recommande', 'max'})
        self.assertEqual(payload['roof_layout']['result']['panels'], 18)
        # RÈGLE #4 — aucune fuite dans les clés neuves.
        blob = json.dumps(bloc)
        for fuite in ('prix_achat', 'marge', '9999'):
            self.assertNotIn(fuite, blob)

    def test_l_endpoint_sert_les_dessins_AUSSI_au_niveau_standard(self):
        # L-SECT (24/08) : le calepinage est visible aux DEUX niveaux ; les
        # dessins par option suivent la MÊME règle, pas une plus stricte.
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-6', layout=toit())
        token = self._lien(devis, niveau=ShareLink.NIVEAU_STANDARD)
        with mock.patch('apps.ventes.public_views._offres_tailles_publique',
                        return_value=offres(eco=12, recommande=18)):
            payload = self._payload(token)
        self.assertIn('calepinage_options', payload)
        self.assertIsNotNone(payload['roof_layout'])

    def test_l_endpoint_omet_les_dessins_sans_calepinage(self):
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-7', layout=None)
        token = self._lien(devis)
        with mock.patch('apps.ventes.public_views._offres_tailles_publique',
                        return_value=offres(eco=12, recommande=18)):
            payload = self._payload(token)
        self.assertNotIn('calepinage_options', payload)
        self.assertIsNone(payload['roof_layout'])

    def test_la_case_calepinage_3d_retire_les_deux(self):
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-8', layout=toit())
        token = self._lien(devis, sections={'roof3d': False})
        with mock.patch('apps.ventes.public_views._offres_tailles_publique',
                        return_value=offres(eco=12, recommande=18)):
            payload = self._payload(token)
        self.assertIsNone(payload['roof_layout'])
        self.assertNotIn('calepinage_options', payload)

    def test_le_jeton_ne_sert_que_le_devis_de_SA_societe(self):
        autre = _company('calep-opt-2')
        autre_user = User.objects.create_user(
            username='calep_opt_2', password='x', role_legacy='responsable',
            company=autre)
        autre_client = Client.objects.create(
            company=autre, nom='Autre', prenom='Societe',
            email='autre@ex.com', telephone='+212600000010')
        mien = _devis(self.company, self.user, self.client_obj,
                      'DEV-CAL-9', layout=toit(rangees=3, colonnes=6))
        sien = _devis(autre, autre_user, autre_client, 'DEV-CAL-10',
                      layout=toit(rangees=2, colonnes=4))
        with mock.patch('apps.ventes.public_views._offres_tailles_publique',
                        return_value=offres(eco=6, recommande=18)):
            mien_payload = self._payload(self._lien(mien))
        token_autre = str(uuid.uuid4())
        ShareLink.objects.create(company=autre, devis=sien,
                                 token=token_autre,
                                 niveau=ShareLink.NIVEAU_CONFIANCE)
        with mock.patch('apps.ventes.public_views._offres_tailles_publique',
                        return_value=offres(eco=6, recommande=8)):
            sien_payload = self._payload(token_autre)
        self.assertEqual(
            mien_payload['calepinage_options']['nb_panneaux_calepines'], 18)
        self.assertEqual(
            sien_payload['calepinage_options']['nb_panneaux_calepines'], 8)


class ParametresSiteChargeUtileTests(TestCase):
    """L'annexe branchée POUR DE VRAI — pas seulement sa fonction pure.

    Les tests purs prouvent la logique d'omission ; ils ne prouvent PAS que la
    vue passe les bons arguments. Un ``hypotheses`` non câblé, ou des
    ``chaines`` servies malgré la case « Schéma unifilaire » décochée,
    seraient invisibles sans ces quatre-là.
    """

    def setUp(self):
        self.company = _company('calep-annexe')
        self.user = User.objects.create_user(
            username='calep_annexe', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Annexe', prenom='Client',
            email='annexe@ex.com', telephone='+212600000011')

    def _payload(self, devis, **kwargs):
        token = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.company, devis=devis, token=token,
            niveau=kwargs.pop('niveau', ShareLink.NIVEAU_CONFIANCE), **kwargs)
        reponse = DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(reponse.status_code, 200)
        return reponse.json()

    def test_les_angles_du_calepinage_arrivent_jusqu_a_la_page(self):
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-11', layout=toit())
        annexe = self._payload(devis).get('parametres_site')
        self.assertIsNotNone(annexe)
        self.assertEqual(annexe['inclinaison_deg'], 15.0)
        self.assertEqual(annexe['orientation'], 'Sud')
        # ANTICOPIE — des angles et des noms, jamais un repère exploitable.
        blob = json.dumps(annexe)
        for fuite in ('origin', 'vertices', 'centerLng', str(_OLNG)):
            self.assertNotIn(fuite, blob)

    def test_l_irradiation_est_CABLEE_sur_le_bloc_hypotheses(self):
        # Le CÂBLAGE, pas la fonction : la vue doit passer
        # ``payload['hypotheses']`` (déjà soumis à la règle Z2), et l'annexe
        # doit dire la MÊME ville — ou se taire.
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-12', layout=toit())
        payload = self._payload(devis)
        ville = (payload.get('hypotheses') or {}).get('productible_ville')
        annexe = payload.get('parametres_site') or {}
        if ville:
            self.assertEqual(annexe['irradiation'],
                             {'source': 'PVGIS', 'ville': ville})
        else:
            # Pas de ville PVGIS sur ce devis ⇒ champ OMIS, jamais inventé.
            self.assertNotIn('irradiation', annexe)

    def test_la_case_schema_unifilaire_emporte_les_chaines(self):
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-13', layout=toit())
        payload = self._payload(devis, sections={'sld': False})
        self.assertIsNone(payload.get('conception_electrique'))
        self.assertNotIn('chaines', payload.get('parametres_site') or {})

    def test_la_case_calepinage_3d_emporte_les_angles(self):
        devis = _devis(self.company, self.user, self.client_obj,
                       'DEV-CAL-14', layout=toit())
        annexe = self._payload(devis, sections={'roof3d': False}).get(
            'parametres_site') or {}
        for cle in ('orientation_deg', 'inclinaison_deg', 'orientation',
                    'type_toit'):
            self.assertNotIn(cle, annexe)

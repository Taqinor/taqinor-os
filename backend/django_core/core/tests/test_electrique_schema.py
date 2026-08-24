# -*- coding: utf-8 -*-
"""PV39 — schéma unifilaire : ce qui est DESSINÉ est ce qui a été CALCULÉ.

Le test central : le tableau d'équipements du schéma EST la liste des
protections et des câbles du résultat — même repères, mêmes calibres, mêmes
quantités. Un schéma qui montre un organe absent du bordereau (ou l'inverse) est
exactement le défaut qu'un bureau de contrôle relève, et c'est la seule chose
qu'un rendu SVG peut faire semblant de bien faire.

Trois dossiers golden : mono réseau 8 panneaux, triphasé 24 panneaux sur deux
pans, hybride avec batterie.

Aucune base de données : ``unittest`` pur.
"""

import re
import unittest
import xml.etree.ElementTree as ET

from core.electrique import concevoir
from core.electrique.schema import (
    FORMAT_A3_PAYSAGE,
    FORMAT_A4_PAYSAGE,
    Bloc,
    blocs_du_schema,
    lignes_tableau,
    rendre_schema,
)
from core.electrique.types import (
    EntreeElectrique,
    GroupePan,
    SpecModule,
    SpecOnduleur,
)

MODULE_550 = SpecModule(vmp_v=41.5, voc_v=49.5, isc_a=13.9, imp_a=13.26,
                        pmax_wc=550.0, temp_coeff_voc_pct_c=-0.25,
                        temp_coeff_pmax_pct_c=-0.35)


def _mono_reseau(**kwargs):
    return EntreeElectrique(
        module=MODULE_550,
        onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=80.0, mppt_v_max=550.0,
                              v_max_abs=600.0, i_max_mppt_a=16.0, ac_kw=4.0,
                              phases=1, v_demarrage_v=90.0),
        groupes=(GroupePan("Sud", 8, 180.0, 20.0),),
        dc_m=12.0, ac_m=8.0, phases=1, **kwargs)


def _triphase_deux_pans():
    return EntreeElectrique(
        module=MODULE_550,
        onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=200.0, mppt_v_max=850.0,
                              v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=12.0,
                              phases=3, v_demarrage_v=200.0),
        groupes=(GroupePan("Sud", 12, 180.0, 15.0),
                 GroupePan("Ouest", 12, 270.0, 15.0)),
        dc_m=25.0, ac_m=15.0, phases=3)


def _une_seule_chaine():
    """5 modules : UNE chaîne pour DEUX entrées MPPT — la seconde est libre."""
    return EntreeElectrique(
        module=MODULE_550,
        onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=80.0, mppt_v_max=550.0,
                              v_max_abs=600.0, i_max_mppt_a=16.0, ac_kw=3.0,
                              phases=1, v_demarrage_v=90.0),
        groupes=(GroupePan("Sud", 5, 180.0, 20.0),),
        dc_m=12.0, ac_m=8.0, phases=1)


def _hybride_batterie():
    return EntreeElectrique(
        module=MODULE_550,
        onduleur=SpecOnduleur(n_mppt=2, mppt_v_min=80.0, mppt_v_max=550.0,
                              v_max_abs=600.0, i_max_mppt_a=16.0, ac_kw=8.0,
                              phases=1, v_demarrage_v=90.0),
        groupes=(GroupePan("Sud", 16, 180.0, 25.0),),
        dc_m=8.0, ac_m=6.0, phases=1, batterie=True)


def _textes(svg):
    """Tous les textes du SVG — le rendu est parsé, jamais deviné."""
    racine = ET.fromstring(svg)
    espace = "{http://www.w3.org/2000/svg}"
    return [(noeud.text or "") for noeud in racine.iter(espace + "text")]


class LeSvgEstBienForme(unittest.TestCase):
    def test_les_trois_dossiers_rendent_un_svg_parsable(self):
        for entree in (_mono_reseau(), _triphase_deux_pans(),
                       _hybride_batterie()):
            svg = rendre_schema(entree, concevoir(entree))
            self.assertTrue(svg.startswith("<svg "))
            self.assertTrue(svg.endswith("</svg>"))
            racine = ET.fromstring(svg)       # lève si le XML est cassé
            self.assertIn("viewBox", racine.attrib)

    def test_le_viewbox_est_fixe_pour_un_format(self):
        premier = rendre_schema(_mono_reseau(), concevoir(_mono_reseau()))
        second = rendre_schema(_hybride_batterie(),
                               concevoir(_hybride_batterie()))
        motif = re.compile(r'viewBox="([^"]+)"')
        self.assertEqual(motif.search(premier).group(1),
                         motif.search(second).group(1))
        self.assertEqual(
            motif.search(premier).group(1),
            "0 0 %s %s" % (int(FORMAT_A4_PAYSAGE[0]),
                           int(FORMAT_A4_PAYSAGE[1])))

    def test_a3_au_dela_du_seuil_de_largeur(self):
        """Une chaîne assez longue pour déborder deux rangées passe en A3."""
        chaine_courte = blocs_du_schema(_mono_reseau(),
                                        concevoir(_mono_reseau()))
        longue = chaine_courte + tuple(
            Bloc("reseau", "Organe %d" % i) for i in range(6))
        from core.electrique.schema import _format_planche
        self.assertEqual(_format_planche(len(chaine_courte)),
                         FORMAT_A4_PAYSAGE)
        self.assertEqual(_format_planche(len(longue)), FORMAT_A3_PAYSAGE)

    def test_aucun_prix_dans_le_rendu(self):
        svg = rendre_schema(_hybride_batterie(), concevoir(_hybride_batterie()))
        for interdit in ("MAD", "DH", "prix", "€", "Total"):
            self.assertNotIn(interdit, svg)


class LaChaineCanoniqueSuitLesRegles(unittest.TestCase):
    def test_l_ordre_canonique_des_blocs(self):
        entree = _mono_reseau()
        clefs = [b.clef for b in blocs_du_schema(entree, concevoir(entree))]
        self.assertEqual(clefs, [
            "champ", "coffret_dc", "parafoudre_dc", "sectionneur_dc",
            "onduleur", "disjoncteur_ac", "parafoudre_ac", "ddr",
            "compteur_production", "tgbt", "reseau"])

    def test_pas_de_fusible_dessine_quand_il_n_est_pas_exige(self):
        entree = _mono_reseau()
        clefs = [b.clef for b in blocs_du_schema(entree, concevoir(entree))]
        self.assertNotIn("fusibles", clefs)

    def test_fusibles_dessines_des_trois_chaines_en_parallele(self):
        entree = EntreeElectrique(
            module=MODULE_550,
            onduleur=SpecOnduleur(n_mppt=1, mppt_v_min=80.0, mppt_v_max=550.0,
                                  v_max_abs=600.0, i_max_mppt_a=60.0,
                                  ac_kw=6.0, phases=1, v_demarrage_v=90.0),
            groupes=(GroupePan("Sud", 12, 180.0, 20.0),),
            dc_m=12.0, ac_m=8.0, phases=1, longueur_chaine_forcee=4)
        clefs = [b.clef for b in blocs_du_schema(entree, concevoir(entree))]
        self.assertIn("fusibles", clefs)

    def test_pas_de_parafoudre_dc_sur_une_liaison_courte(self):
        entree = _hybride_batterie()          # liaison DC de 8 m
        clefs = [b.clef for b in blocs_du_schema(entree, concevoir(entree))]
        self.assertNotIn("parafoudre_dc", clefs)

    def test_la_branche_batterie_apparait_avec_le_stockage(self):
        avec = [b.clef for b in blocs_du_schema(
            _hybride_batterie(), concevoir(_hybride_batterie()))]
        sans = [b.clef for b in blocs_du_schema(
            _mono_reseau(), concevoir(_mono_reseau()))]
        self.assertIn("batterie", avec)
        self.assertNotIn("batterie", sans)

    def test_huit_panneaux_dessinent_UNE_chaine_et_UN_depart_dc(self):
        """RÈGLE FONDATEUR 24/08/2026 — le schéma suit la chaîne unique.

        Le dessin annonçait « 2 × 4 modules », un coffret à 2 chaînes et DEUX
        amorces MPPT. Avec la chaîne unique : un seul départ DC (une paire
        descendante), donc deux conducteurs au câble W1 — le courant de chaîne,
        lui, ne change pas (les modules sont en SÉRIE), c'est le courant du
        départ commun qui n'additionne plus deux chaînes.
        """
        entree = _mono_reseau()
        resultat = concevoir(entree)
        textes = _textes(rendre_schema(entree, resultat))
        self.assertIn("MPPT 1 · 1 chaîne(s)", textes)
        self.assertNotIn("MPPT 2 · 1 chaîne(s)", textes)
        sous_titres = {b.clef: b.sous_titre
                       for b in blocs_du_schema(entree, resultat)}
        self.assertIn("1 × 8 modules", sous_titres["champ"])
        self.assertIn("1 chaîne(s)", sous_titres["coffret_dc"])
        dc = [c for c in resultat.cables if c.repere == "W1"][0]
        self.assertEqual(dc.nb_conducteurs, 2)

    def test_les_amorces_mppt_annoncent_leurs_chaines(self):
        entree = _triphase_deux_pans()
        textes = _textes(rendre_schema(entree, concevoir(entree)))
        self.assertIn("MPPT 1 · 1 chaîne(s)", textes)
        self.assertIn("MPPT 2 · 1 chaîne(s)", textes)

    def test_variante_mono_et_tri_sur_les_conducteurs(self):
        mono = _textes(rendre_schema(_mono_reseau(),
                                     concevoir(_mono_reseau())))
        tri = _textes(rendre_schema(_triphase_deux_pans(),
                                    concevoir(_triphase_deux_pans())))
        self.assertIn("P + N + T · 230 V", mono)
        self.assertIn("3P + N + T · 400 V", tri)
        self.assertTrue(any("monophasé" in t for t in mono))
        self.assertTrue(any("triphasé" in t for t in tri))

    def test_la_batterie_pend_en_branche_hors_de_la_chaine_serie(self):
        """Dessinée EN SÉRIE, elle laisserait croire que l'énergie la traverse."""
        from core.electrique.schema import (_BLOC_H, _format_planche,
                                            _positions)
        entree = _hybride_batterie()
        blocs = blocs_du_schema(entree, concevoir(entree))
        largeur = _format_planche(len(blocs))[0]
        places = _positions(blocs, largeur)
        batterie = next(p for p in places if p[0].clef == "batterie")
        onduleur = next(p for p in places if p[0].clef == "onduleur")
        self.assertTrue(batterie[4], "la batterie doit être une branche")
        self.assertFalse(onduleur[4])
        self.assertGreater(batterie[2], onduleur[2] + _BLOC_H)
        # Décalée de l'aplomb de l'onduleur : c'est par là que le serpentin
        # redescend vers la rangée suivante.
        self.assertNotEqual(batterie[1], onduleur[1])
        # « ⇄ » : le courant batterie va dans LES DEUX sens (charge et
        # décharge) — la pointe dessinée, elle, ne peut en montrer qu'un.
        self.assertIn("branche DC ⇄",
                      _textes(rendre_schema(entree, concevoir(entree))))

    def test_la_barrette_de_terre_est_unique(self):
        entree = _mono_reseau()
        textes = _textes(rendre_schema(entree, concevoir(entree)))
        barrettes = [t for t in textes if t.startswith("Barrette de terre")]
        self.assertEqual(len(barrettes), 1)
        self.assertIn("liaison équipotentielle", barrettes[0])


class AucunTraitNeTraverseUnOrgane(unittest.TestCase):
    """Sur un schéma, un trait qui coupe une boîte se lit comme une LIAISON.

    Ce test est le garde-fou de toute évolution de mise en page : il rejoue la
    géométrie réelle du rendu et refuse qu'un segment (liaison série, descente
    de terre, raccordement de branche) traverse l'intérieur d'un organe.
    """

    SEGMENT = re.compile(
        r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"')
    #: Tolérance : un trait a le droit d'ARRIVER sur le bord d'une boîte.
    BORD = 3.0

    def _boites(self, entree, resultat):
        from core.electrique.schema import (_BLOC_H, _BLOC_L, _format_planche,
                                            _positions)
        blocs = blocs_du_schema(entree, resultat)
        largeur = _format_planche(len(blocs))[0]
        return [(place[0].clef, place[1], place[2],
                 place[1] + _BLOC_L, place[2] + _BLOC_H)
                for place in _positions(blocs, largeur)]

    def test_les_traits_contournent_les_organes(self):
        cas = (("mono", _mono_reseau()), ("tri", _triphase_deux_pans()),
               ("hybride", _hybride_batterie()))
        for nom, entree in cas:
            resultat = concevoir(entree)
            svg = rendre_schema(entree, resultat)
            boites = self._boites(entree, resultat)
            for x1, y1, x2, y2 in self.SEGMENT.findall(svg):
                x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
                for clef, bx1, by1, bx2, by2 in boites:
                    bx1, by1 = bx1 + self.BORD, by1 + self.BORD
                    bx2, by2 = bx2 - self.BORD, by2 - self.BORD
                    if x1 == x2:
                        traverse = (bx1 < x1 < bx2 and min(y1, y2) < by2
                                    and max(y1, y2) > by1)
                    elif y1 == y2:
                        traverse = (by1 < y1 < by2 and min(x1, x2) < bx2
                                    and max(x1, x2) > bx1)
                    else:
                        traverse = False
                    self.assertFalse(
                        traverse,
                        "%s : un trait traverse l'organe « %s »" % (nom, clef))

    def test_aucun_organe_n_en_recouvre_un_autre(self):
        for entree in (_mono_reseau(), _triphase_deux_pans(),
                       _hybride_batterie()):
            boites = self._boites(entree, concevoir(entree))
            for index, a in enumerate(boites):
                for b in boites[index + 1:]:
                    recouvre = (a[1] < b[3] and b[1] < a[3]
                                and a[2] < b[4] and b[2] < a[4])
                    self.assertFalse(recouvre,
                                     "« %s » recouvre « %s »" % (a[0], b[0]))


class ToutePointeDisposeDeSonDegagement(unittest.TestCase):
    """PVSLD — la flèche onduleur → batterie était ÉCRASÉE par son équerre.

    ``_BRANCHE_DY`` valait 96 en dur : l'équerre tombait 94 px sous le haut de
    l'onduleur, la boîte batterie 96 px — soit 2 px pour loger une pointe de 9.
    La pointe ÉTAIT bien émise ; elle était simplement tracée sous l'équerre,
    donc invisible, pendant que le libellé « branche DC », posé au-dessus de
    cette équerre, flottait au niveau de la gouttière de terre POINTILLÉE, qui
    récupérait la lecture. Aucun test ne pouvait le voir : le texte était
    présent, aucun trait ne traversait d'organe, le SVG restait bien formé.

    Le verrou est donc un INVARIANT, pas une coordonnée : devant CHAQUE pointe
    du rendu, le couloir « hauteur de pointe + marge » doit être libre de tout
    trait qui la barre et de toute boîte. Reposer les anciennes constantes le
    fait échouer.
    """

    POINTE = re.compile(r'<polygon points="([^"]+)"')
    SEGMENT = re.compile(
        r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"')
    #: Marge exigée EN AMONT de la base de la pointe, en plus de sa hauteur.
    MARGE = 6.0
    #: Deux coordonnées SVG écrites au dixième sont égales en deçà de ça.
    EPS = 0.01

    def _cas(self):
        return (("mono", _mono_reseau()), ("tri", _triphase_deux_pans()),
                ("hybride", _hybride_batterie()),
                ("simple", _une_seule_chaine()))

    def _boites(self, entree, resultat):
        from core.electrique.schema import (_BLOC_H, _BLOC_L, _format_planche,
                                            _positions)
        blocs = blocs_du_schema(entree, resultat)
        largeur = _format_planche(len(blocs))[0]
        return [(place[0].clef, place[1], place[2],
                 place[1] + _BLOC_L, place[2] + _BLOC_H)
                for place in _positions(blocs, largeur)]

    def _couloirs(self, svg):
        """Le rectangle à garder LIBRE devant chaque pointe RÉELLEMENT émise."""
        couloirs = []
        for points in self.POINTE.findall(svg):
            sommets = tuple(tuple(float(v) for v in couple.split(","))
                            for couple in points.split())
            self.assertEqual(len(sommets), 3, points)
            couloirs.append(self._couloir(sommets))
        return couloirs

    def _couloir(self, sommets):
        """``(axe, x1, y1, x2, y2)`` — la boîte du triangle ÉTIRÉE vers l'amont.

        La base est la paire de sommets alignés ; le sommet restant est la
        POINTE, et « l'amont » est le côté opposé à elle — celui d'où arrive le
        conducteur, et le seul qui doive rester dégagé (la pointe TOUCHE par
        construction la boîte qu'elle vise).
        """
        xs = [s[0] for s in sommets]
        ys = [s[1] for s in sommets]
        for index, sommet in enumerate(sommets):
            base = sommets[:index] + sommets[index + 1:]
            if abs(base[0][0] - base[1][0]) < self.EPS:       # base verticale
                amont = -self.MARGE if sommet[0] > base[0][0] else self.MARGE
                return ("horizontal", min(xs) + min(0.0, amont), min(ys),
                        max(xs) + max(0.0, amont), max(ys))
            if abs(base[0][1] - base[1][1]) < self.EPS:       # base horizontale
                amont = -self.MARGE if sommet[1] > base[0][1] else self.MARGE
                return ("vertical", min(xs), min(ys) + min(0.0, amont),
                        max(xs), max(ys) + max(0.0, amont))
        self.fail("pointe dégénérée : %r" % (sommets,))

    def test_aucune_pointe_du_schema_n_est_recouverte(self):
        """Le vrai garde-fou : il rejoue la géométrie de TOUS les dossiers."""
        for nom, entree in self._cas():
            resultat = concevoir(entree)
            svg = rendre_schema(entree, resultat)
            couloirs = self._couloirs(svg)
            self.assertTrue(couloirs, "%s : aucune pointe dans le rendu" % nom)
            boites = self._boites(entree, resultat)
            segments = [tuple(float(v) for v in quadruplet)
                        for quadruplet in self.SEGMENT.findall(svg)]
            for axe, cx1, cy1, cx2, cy2 in couloirs:
                for x1, y1, x2, y2 in segments:
                    # Un trait PARALLÈLE au couloir est le fût de la flèche (ou
                    # longe la branche) : il ne la cache pas. C'est le trait en
                    # TRAVERS — l'équerre — qui l'écrase.
                    if axe == "vertical" and abs(x1 - x2) < self.EPS:
                        continue
                    if axe == "horizontal" and abs(y1 - y2) < self.EPS:
                        continue
                    self.assertFalse(
                        (min(x1, x2) < cx2 and cx1 < max(x1, x2)
                         and min(y1, y2) < cy2 and cy1 < max(y1, y2)),
                        "%s : le trait (%s,%s)-(%s,%s) barre une pointe"
                        % (nom, x1, y1, x2, y2))
                for clef, bx1, by1, bx2, by2 in boites:
                    self.assertFalse(
                        (bx1 < cx2 and cx1 < bx2 and by1 < cy2 and cy1 < by2),
                        "%s : l'organe « %s » recouvre une pointe"
                        % (nom, clef))

    def test_la_branche_batterie_garde_le_degagement_de_reference(self):
        """L'ancien réglage (``_BRANCHE_DY`` = 96) ne laissait que 2 px."""
        from core.electrique.schema import (_BLOC_H, _BRANCHE_DY,
                                            _BRANCHE_EQUERRE_DY,
                                            _DEGAGEMENT_POINTE, _POINTE_H,
                                            _format_planche, _positions)
        degagement = _BRANCHE_DY - _BLOC_H - _BRANCHE_EQUERRE_DY
        self.assertGreaterEqual(
            degagement, _POINTE_H + self.MARGE,
            "il reste %s px entre l'équerre et la batterie pour une pointe "
            "de %s px" % (degagement, _POINTE_H))
        self.assertGreaterEqual(degagement, _DEGAGEMENT_POINTE)
        # Et sur la géométrie RÉELLE du dossier hybride, pas sur les seules
        # constantes : une position calculée autrement le dirait aussi.
        entree = _hybride_batterie()
        blocs = blocs_du_schema(entree, concevoir(entree))
        places = _positions(blocs, _format_planche(len(blocs))[0])
        batterie = next(p for p in places if p[0].clef == "batterie")
        onduleur = next(p for p in places if p[0].clef == "onduleur")
        equerre = onduleur[2] + _BLOC_H + _BRANCHE_EQUERRE_DY
        self.assertGreaterEqual(batterie[2] - equerre, _DEGAGEMENT_POINTE)

    def test_la_rangee_a_branche_loge_la_branche_entiere(self):
        """Descendre la branche SANS agrandir la rangée poserait la batterie
        sur l'organe de la rangée suivante."""
        from core.electrique.schema import (_BLOC_H, _BRANCHE_DY,
                                            _RANGEE_H_AVEC_BRANCHE)
        self.assertGreater(_RANGEE_H_AVEC_BRANCHE, _BRANCHE_DY + _BLOC_H)

    def test_le_libelle_de_branche_ne_flotte_plus_sur_la_terre(self):
        """Il doit se rattacher à l'équerre DC, pas à la gouttière pointillée.

        Posé à ``equerre − 5``, il tombait entre la ligne de terre et l'équerre,
        et l'œil le donnait à la ligne de terre. Il est maintenant SOUS
        l'équerre, du côté de la batterie qu'il nomme.
        """
        from core.electrique.schema import (_BLOC_H, _BRANCHE_EQUERRE_DY,
                                            _GOUTTIERE_DY, _format_planche,
                                            _positions)
        entree = _hybride_batterie()
        resultat = concevoir(entree)
        blocs = blocs_du_schema(entree, resultat)
        places = _positions(blocs, _format_planche(len(blocs))[0])
        onduleur = next(p for p in places if p[0].clef == "onduleur")
        batterie = next(p for p in places if p[0].clef == "batterie")
        equerre = onduleur[2] + _BLOC_H + _BRANCHE_EQUERRE_DY
        terre = onduleur[2] + _BLOC_H + _GOUTTIERE_DY
        espace = "{http://www.w3.org/2000/svg}"
        racine = ET.fromstring(rendre_schema(entree, resultat))
        libelles = [noeud for noeud in racine.iter(espace + "text")
                    if (noeud.text or "").startswith("branche DC")]
        self.assertEqual(len(libelles), 1)
        y = float(libelles[0].get("y"))
        self.assertGreater(
            y, equerre,
            "le libellé est repassé au-dessus de l'équerre, donc dans la "
            "bande de la gouttière de terre")
        self.assertLess(y, batterie[2])
        # Et il est franchement plus près de son équerre que de la terre.
        self.assertLess(abs(y - equerre), abs(y - terre))

    def _points_dessines(self, racine, espace):
        """Tous les points RÉELLEMENT posés sur la planche."""
        points = []
        for noeud in racine.iter():
            balise = noeud.tag.replace(espace, "")
            if balise == "rect":
                x, y = float(noeud.get("x")), float(noeud.get("y"))
                points.append((x, y))
                points.append((x + float(noeud.get("width")),
                               y + float(noeud.get("height"))))
            elif balise == "line":
                points.append((float(noeud.get("x1")), float(noeud.get("y1"))))
                points.append((float(noeud.get("x2")), float(noeud.get("y2"))))
            elif balise == "polygon":
                for couple in noeud.get("points").split():
                    x, y = couple.split(",")
                    points.append((float(x), float(y)))
            elif balise == "text":
                points.append((float(noeud.get("x")), float(noeud.get("y"))))
        return points

    def test_le_dessin_tient_dans_la_planche(self):
        """Agrandir la rangée à branche ne doit rien pousser hors du cadre."""
        espace = "{http://www.w3.org/2000/svg}"
        for nom, entree in self._cas():
            racine = ET.fromstring(rendre_schema(entree, concevoir(entree)))
            largeur, hauteur = [float(v)
                                for v in racine.get("viewBox").split()[2:]]
            for x, y in self._points_dessines(racine, espace):
                self.assertTrue(0.0 <= x <= largeur,
                                "%s : x=%s hors planche" % (nom, x))
                self.assertTrue(0.0 <= y <= hauteur,
                                "%s : y=%s hors planche" % (nom, y))


class LesEtiquettesMpptNeMordentAucunOrgane(unittest.TestCase):
    """PV85 — les amorces MPPT s'écrivaient PAR-DESSUS le disjoncteur AC.

    Sur une rangée parcourue de droite à gauche, l'organe qui suit l'onduleur
    est dessiné à sa GAUCHE : c'est exactement la place où les étiquettes
    étaient ancrées. Le test rejoue la géométrie réelle du rendu et refuse
    qu'une étiquette recouvre une boîte — et refuse aussi qu'une entrée sans
    chaîne soit annoncée.
    """

    #: Même estimation de largeur que le halo du rendu (font-size 8).
    LARGEUR_CAR = 8.0 * 0.58

    def _etiquettes(self, svg):
        racine = ET.fromstring(svg)
        espace = "{http://www.w3.org/2000/svg}"
        return [(float(noeud.get("x")), float(noeud.get("y")),
                 noeud.text or "")
                for noeud in racine.iter(espace + "text")
                if (noeud.text or "").startswith("MPPT")]

    def _boites(self, entree, resultat):
        from core.electrique.schema import (_BLOC_H, _BLOC_L, _format_planche,
                                            _positions)
        blocs = blocs_du_schema(entree, resultat)
        largeur = _format_planche(len(blocs))[0]
        return [(place[0].clef, place[1], place[2],
                 place[1] + _BLOC_L, place[2] + _BLOC_H)
                for place in _positions(blocs, largeur)]

    def _cas(self):
        return (("mono", _mono_reseau()), ("tri", _triphase_deux_pans()),
                ("hybride", _hybride_batterie()), ("simple", _une_seule_chaine()))

    def test_aucune_etiquette_ne_recouvre_une_boite(self):
        for nom, entree in self._cas():
            resultat = concevoir(entree)
            etiquettes = self._etiquettes(rendre_schema(entree, resultat))
            self.assertTrue(etiquettes, "%s : aucune étiquette MPPT" % nom)
            for x, y, texte in etiquettes:
                x2 = x + len(texte) * self.LARGEUR_CAR
                haut, bas = y - 8.0, y + 2.0
                for clef, bx1, by1, bx2, by2 in self._boites(entree, resultat):
                    recouvre = (x < bx2 and bx1 < x2
                                and haut < by2 and by1 < bas)
                    self.assertFalse(
                        recouvre,
                        "%s : « %s » recouvre l'organe « %s »"
                        % (nom, texte, clef))

    def test_les_etiquettes_sont_au_dessus_du_bloc_onduleur(self):
        """Au-dessus, jamais à gauche : à gauche il n'y a que 34 px."""
        for nom, entree in self._cas():
            resultat = concevoir(entree)
            boites = dict((b[0], b) for b in self._boites(entree, resultat))
            _clef, ond_x, ond_y, _x2, _y2 = boites["onduleur"]
            for x, y, texte in self._etiquettes(
                    rendre_schema(entree, resultat)):
                self.assertGreaterEqual(x, ond_x, "%s : %s" % (nom, texte))
                self.assertLess(y, ond_y, "%s : %s" % (nom, texte))

    def test_une_entree_sans_chaine_n_est_jamais_annoncee(self):
        """« MPPT 2 · 0 chaîne(s) » décrivait une amorce qui n'existe pas."""
        for nom, entree in self._cas():
            svg = rendre_schema(entree, concevoir(entree))
            self.assertNotIn("0 chaîne(s)", svg, nom)
        # Le cas qui produisait le défaut : 1 chaîne, 2 entrées MPPT.
        entree = _une_seule_chaine()
        resultat = concevoir(entree)
        self.assertEqual(resultat.nb_chaines, 1)
        self.assertEqual(entree.onduleur.n_mppt, 2)
        textes = _textes(rendre_schema(entree, resultat))
        self.assertIn("MPPT 1 · 1 chaîne(s)", textes)
        self.assertFalse([t for t in textes if t.startswith("MPPT 2")])
        # Le nombre d'entrées de l'appareil reste lisible sous son titre.
        self.assertTrue(any("2 entrée(s) MPPT" in t for t in textes))


class LeTableauEstLaListeDesProtections(unittest.TestCase):
    """Le verrou : tableau == protections[] + cables[], pour les 3 dossiers."""

    def _cas(self):
        return (_mono_reseau(), _triphase_deux_pans(), _hybride_batterie())

    def test_le_tableau_reprend_chaque_protection_et_chaque_cable(self):
        for entree in self._cas():
            resultat = concevoir(entree)
            lignes = lignes_tableau(resultat)
            self.assertEqual(len(lignes),
                             len(resultat.protections) + len(resultat.cables))
            for index, protection in enumerate(resultat.protections):
                self.assertEqual(lignes[index][0], protection.repere)
                self.assertEqual(lignes[index][1], protection.designation)
                self.assertEqual(lignes[index][2], protection.calibre)
                self.assertEqual(lignes[index][3],
                                 "%d u" % protection.quantite)
            decalage = len(resultat.protections)
            for index, cable in enumerate(resultat.cables):
                self.assertEqual(lignes[decalage + index][0], cable.repere)

    def test_chaque_repere_du_tableau_est_dessine(self):
        for entree in self._cas():
            resultat = concevoir(entree)
            textes = _textes(rendre_schema(entree, resultat))
            for protection in resultat.protections:
                self.assertIn(protection.repere, textes,
                              "repère absent du schéma : %s"
                              % protection.repere)
            for cable in resultat.cables:
                self.assertIn(cable.repere, textes)

    def test_le_tableau_a_ses_entetes(self):
        entree = _mono_reseau()
        textes = _textes(rendre_schema(entree, concevoir(entree)))
        for entete in ("Repère", "Désignation", "Calibre / section", "Qté"):
            self.assertIn(entete, textes)
        self.assertIn("Nomenclature des équipements", textes)


class LesTextesTiennentDansLeursBoites(unittest.TestCase):
    """Le SVG ne coupe pas un texte trop long : il le laisse déborder.

    Un détail d'organe qui dépasse sa boîte va se poser sur le voisin — défaut
    invisible à tout test qui se contente de chercher une sous-chaîne.
    """

    def test_le_detail_se_repartit_sur_deux_lignes_au_plus(self):
        from core.electrique.schema import (_CARACTERES_SOUS_TITRE,
                                            _LIGNES_SOUS_TITRE,
                                            _lignes_sous_titre)
        lignes = _lignes_sous_titre("8,0 kW · monophasé · 2 entrée(s) MPPT")
        self.assertEqual(lignes, ("8,0 kW · monophasé", "2 entrée(s) MPPT"))
        self.assertLessEqual(len(lignes), _LIGNES_SOUS_TITRE)
        for ligne in lignes:
            self.assertLessEqual(len(ligne), _CARACTERES_SOUS_TITRE)

    def test_un_detail_court_reste_sur_une_ligne(self):
        from core.electrique.schema import _lignes_sous_titre
        self.assertEqual(_lignes_sous_titre("40 A / 230 V"), ("40 A / 230 V",))
        self.assertEqual(_lignes_sous_titre(""), ())

    def test_un_detail_sans_separateur_est_tronque_pas_deborde(self):
        from core.electrique.schema import (_CARACTERES_SOUS_TITRE,
                                            _lignes_sous_titre)
        lignes = _lignes_sous_titre("x" * 80)
        self.assertEqual(len(lignes), 1)
        self.assertLessEqual(len(lignes[0]), _CARACTERES_SOUS_TITRE)

    def test_aucun_libelle_de_bloc_ne_deborde_a_l_ecran(self):
        from core.electrique.schema import (_CARACTERES_SOUS_TITRE,
                                            _CARACTERES_TITRE)
        limite = max(_CARACTERES_TITRE, _CARACTERES_SOUS_TITRE)
        espace = "{http://www.w3.org/2000/svg}"
        for entree in (_mono_reseau(), _triphase_deux_pans(),
                       _hybride_batterie()):
            svg = rendre_schema(entree, concevoir(entree))
            for noeud in ET.fromstring(svg).iter(espace + "text"):
                if noeud.get("text-anchor") != "middle":
                    continue          # textes du tableau / cartouche, alignés
                self.assertLessEqual(len(noeud.text or ""), limite,
                                     "libellé trop long : %r" % noeud.text)


class CartoucheEtSurcharges(unittest.TestCase):
    def test_le_cartouche_porte_les_mentions_attendues(self):
        entree = _mono_reseau()
        svg = rendre_schema(entree, concevoir(entree), cartouche={
            "client": "SARL Exemple", "reference": "DEV-2026-0042",
            "date": "14/08/2026", "indice": "B"})
        textes = _textes(svg)
        for attendu in ("Client", "Référence", "Puissance crête", "Date",
                        "Indice", "Brouillon — dossier technique",
                        "SARL Exemple", "DEV-2026-0042", "14/08/2026", "B",
                        "4,40 kWc"):
            self.assertIn(attendu, textes)

    def test_sans_cartouche_le_rendu_reste_valide(self):
        entree = _mono_reseau()
        textes = _textes(rendre_schema(entree, concevoir(entree)))
        self.assertIn("—", textes)          # champs non renseignés
        self.assertIn("A", textes)          # indice par défaut

    def test_une_position_forcee_est_honoree(self):
        entree = _mono_reseau()
        resultat = concevoir(entree)
        defaut = rendre_schema(entree, resultat)
        force = rendre_schema(entree, resultat,
                              positions={"onduleur": {"x": 500.0, "y": 600.0}})
        self.assertNotEqual(defaut, force)
        self.assertIn('x="500" y="600"', force)

    def test_une_clef_inconnue_dans_les_surcharges_est_ignoree(self):
        entree = _mono_reseau()
        resultat = concevoir(entree)
        self.assertEqual(
            rendre_schema(entree, resultat),
            rendre_schema(entree, resultat,
                          positions={"organe_inexistant": {"x": 1.0}}))

    def test_les_libelles_sont_en_francais(self):
        entree = _mono_reseau()
        textes = " ".join(_textes(rendre_schema(entree, concevoir(entree))))
        for attendu in ("Champ PV", "Coffret DC", "Sectionneur DC",
                        "Onduleur", "Disjoncteur AC", "Différentiel type A",
                        "Compteur de production", "TGBT", "Compteur ONEE",
                        "Schéma unifilaire"):
            self.assertIn(attendu, textes)

# -*- coding: utf-8 -*-
"""QJR165 (30/08/2026) — UN SEUL lecteur de layout → (compte, watt, batterie).

CE QUE CETTE TÂCHE A TROUVÉ. Ce dépôt lisait le MÊME blob ``roof_layout`` de
deux façons, et les deux chaînes de repli avaient réellement divergé :

* ``domain/geometrie._cible_panneaux_du_layout`` + ``_watt_du_layout`` — la
  lecture de la RESYNCHRONISATION (et du plafond de l'échelle de tailles, via
  ``dimensionnement.plafond_toit_du_devis``) ;
* la lecture INLINE recopiée dans ``domain/creation.build_devis_from_layout``
  — celle du CALEPINAGE 3D.

Sur un corpus de 25 layouts dérivés des fixtures réelles du dépôt
(``test_qjr_bascule_3d``, ``test_qjr_sync_layout_fraicheur``,
``test_build_from_layout``/FG248, ``test_calepinage_bascule``,
``test_auto_pipeline``), **11 cas sur 25 donnaient deux réponses
différentes**. Quatre classes de divergence, tranchées une par une :

──────────────────────────────────────────────────────────────────────────────
D1 · LE COMPTE — ``result.count`` au niveau TOP (C12/C13/C14)
    AVANT : resynchro = 12 · création = 0.
    VERDICT : **la resynchro a raison, ``count`` reste accepté.**
    PREUVE DU PRODUCTEUR : aucun producteur de ce dépôt n'écrit ``count`` au
    TOP de ``result`` — ``SerializedResult`` (apps/web roofPro11/prefill.ts)
    y écrit ``{panels, kwc, annualKwh, savings}``, et les 13 fixtures du dépôt
    qui portent ``'result': {'count': …}`` sont TOUTES au niveau d'une ZONE
    (elles portent ``areaM2`` et vivent dans ``areas``/``zones``), où ``count``
    est la clé légitime que ``extract_roof_config`` lit déjà. La règle
    « **ne jamais inventer un compte** » est donc respectée des deux côtés ; ce
    qui départage, c'est le blob LÉGACY ou écrit à la main : là, la création
    lisait 0 (devis refusé « aucun panneau ») pendant que la resynchro du MÊME
    devis lisait 12. Retirer ``count`` aurait fait PERDRE au plafond de toit et
    à la resynchro un compte réellement présent ; l'ajouter à la création ne
    peut, lui, jamais inventer un nombre absent.

D2 · LE WATTAGE — normalisation (C05/C06/C07)
    AVANT : resynchro = ``int(round(float(w)))`` · création = la valeur BRUTE.
    VERDICT : **la resynchro a raison, on normalise.**
    Un blob portant ``545.6`` composait à 545,6 W d'un côté et 546 W de
    l'autre ; un blob portant la CHAÎNE ``"abc"`` la laissait descendre
    jusqu'à ``composition_residentielle`` (``float(panel_watt or 0)``), où elle
    LÈVE. Le producteur, lui, n'écrit qu'un ``number`` (prefill.ts) et aucune
    fixture du dépôt ne porte autre chose qu'un entier : la normalisation est
    donc sans effet sur toute sortie réelle, et ne fait que fermer le cas
    illisible.

D3 · LE WATTAGE — le repli quand rien n'est déductible (C08/C09/C10/C19)
    AVANT : resynchro = 550 (``CIBLE_WATT_DEFAUT``) · création = ``None``.
    VERDICT : **la resynchro a raison, le repli est 550.**
    ``None`` était déjà re-défaut é à 550 DEUX fois en aval
    (``kwc_composition = kwc or nb * float(watt or 550) / 1000`` puis
    ``composition_residentielle`` : ``float(panel_watt or 0) or 550.0``) : le
    rendre explicite ne déplace aucune ligne composée. Il en déplace UNE, et
    c'est un gain : dans ``composition_deux_optimiseurs``, ``kwc_avec`` non
    fourni se dérive de ``nb_avec * float(panel_watt or 0)`` — avec ``None``
    ce terme valait 0 et l'option « avec » RECOPIAIT le kWc de l'option
    « sans », très exactement ce que le commentaire de cette ligne interdit
    (« jamais on ne recopie celui d'en face »).

D4 · LA BATTERIE — le libellé « les deux » (C22)
    AVANT : ``scenario_du_layout`` = ``les_deux`` · création inline = ``sans``.
    VERDICT : **``scenario_du_layout`` a raison.**
    C'est le lecteur que la PRÉ-VÉRIFICATION du même écran utilise déjà
    (``validate_composition_for_layout`` → ``verifier``) : un layout
    ``scenario: 'les_deux'`` était donc vérifié sur DEUX options puis composé
    en UNE seule. Aucun producteur n'écrit ce libellé aujourd'hui
    (``LayoutScenario = 'reseau' | 'avec_batterie' | 'hybride'``), donc aucune
    sortie réelle ne bouge ; ce qui disparaît, c'est la contradiction.
──────────────────────────────────────────────────────────────────────────────

CE MODULE EST LE GOLDEN DE CE CORPUS : il fige, cas par cas, la réponse
tranchée, et il garde la porte fermée (aucune lecture inline ne subsiste).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_qjr165_lecteur_layout"
"""
import ast
import inspect

from django.test import SimpleTestCase

from apps.ventes.domain import geometrie
from apps.ventes.domain.creation import (
    build_devis_auto, build_devis_from_layout)
from apps.ventes.domain.geometrie import (
    _cible_panneaux_du_layout, _watt_du_layout, lire_layout)


def _zone(count, kwc, area=30.0):
    """Une ZONE roofPro11 telle que le dépôt en stocke (cf. FG248)."""
    return {'label': 'Toit', 'roofType': 'flat', 'pitchDeg': 15,
            'facingAzimuthDeg': 180,
            'result': {'count': count, 'kwc': kwc, 'areaM2': area}}


#: LE CORPUS ET SON GOLDEN — ``(id, layout, (compte, watt, watt_declare,
#: kwc, scenario))``. Chaque ligne a été CAPTURÉE sur le lecteur unifié réel,
#: jamais dérivée à la main.
CORPUS = (
    ('C01 result.panels+kwc, reseau',
     {'scenario': 'reseau', 'result': {'panels': 12, 'kwc': 8.64,
                                       'annualKwh': 13000, 'savings': 11000}},
     (12, 720, 720, 8.64, 'sans')),
    ('C02 result.panels+kwc, avec_batterie',
     {'scenario': 'avec_batterie', 'result': {'panels': 10, 'kwc': 5.5}},
     (10, 550, 550, 5.5, 'avec')),
    ('C03 panelWatt explicite 550',
     {'scenario': 'reseau', 'panelWatt': 550,
      'result': {'panels': 20, 'kwc': 11.0}},
     (20, 550, 550, 11.0, 'sans')),
    ('C04 alias historique watt',
     {'watt': 500, 'result': {'panels': 8, 'kwc': 4.0}},
     (8, 500, 500, 4.0, 'sans')),
    # ── D2 — la normalisation du wattage ──────────────────────────────────
    ('C05 panelWatt flottant 545.6',
     {'panelWatt': 545.6, 'result': {'panels': 10, 'kwc': 5.5}},
     (10, 546, 546, 5.5, 'sans')),
    ('C06 panelWatt chaine "550"',
     {'panelWatt': '550', 'result': {'panels': 10, 'kwc': 5.5}},
     (10, 550, 550, 5.5, 'sans')),
    ('C07 panelWatt illisible "abc"',
     {'panelWatt': 'abc', 'result': {'panels': 10, 'kwc': 5.5}},
     (10, 550, 550, 5.5, 'sans')),
    # ── D3 — les replis VIDES ─────────────────────────────────────────────
    ('C08 result vide (golden bascule 3D)',
     {'scenario': 'reseau', 'result': {}}, (0, 550, None, 0.0, 'sans')),
    ('C09 layout entierement vide', {}, (0, 550, None, 0.0, 'sans')),
    ('C10 panels sans kwc', {'result': {'panels': 12}},
     (12, 550, None, 0.0, 'sans')),
    ('C11 kwc sans panels', {'result': {'kwc': 6.6}},
     (0, 550, None, 6.6, 'sans')),
    # ── D1 — result.count au niveau TOP ───────────────────────────────────
    ('C12 result.count seul', {'result': {'count': 12, 'kwc': 6.6}},
     (12, 550, 550, 6.6, 'sans')),
    ('C13 result.count + panels=0',
     {'result': {'panels': 0, 'count': 9, 'kwc': 4.95}},
     (9, 550, 550, 4.95, 'sans')),
    ('C14 result.count + panelWatt',
     {'panelWatt': 550, 'result': {'count': 14, 'kwc': 7.7}},
     (14, 550, 550, 7.7, 'sans')),
    # ── la GÉOMÉTRIE de zones, et les formes mixtes ───────────────────────
    ('C15 zones seules', {'zones': [_zone(12, 8.52)]},
     (12, 710, 710, 8.52, 'sans')),
    ('C16 zones + result top vide',
     {'result': {}, 'zones': [_zone(12, 8.52)]}, (12, 710, 710, 8.52, 'sans')),
    ('C17 zones + result.panels top (le top gagne)',
     {'result': {'panels': 10, 'kwc': 5.5}, 'areas': [_zone(12, 8.52)]},
     (10, 550, 550, 5.5, 'sans')),
    ('C18 multi-pans FG248',
     {'areas': [{'label': 'Pan Sud', 'roofType': 'pitched', 'pitchDeg': 30,
                 'facingAzimuthDeg': 180,
                 'result': {'count': 12, 'kwc': 6.6, 'areaM2': 24.0}},
                {'label': 'Pan Est', 'roofType': 'pitched', 'pitchDeg': 25,
                 'facingAzimuthDeg': 90,
                 'result': {'count': 4, 'kwc': 2.2, 'areaM2': 9.0}}]},
     (16, 550, 550, 8.8, 'sans')),
    ('C19 zones sans kwc (compte seul)',
     {'zones': [{'label': 'T', 'roofType': 'flat', 'pitchDeg': 0,
                 'facingAzimuthDeg': 180,
                 'result': {'count': 11, 'areaM2': 25.0}}]},
     (11, 550, None, 0.0, 'sans')),
    # ── la BATTERIE ───────────────────────────────────────────────────────
    ('C20 scenario hybride',
     {'scenario': 'hybride', 'result': {'panels': 10, 'kwc': 5.5}},
     (10, 550, 550, 5.5, 'avec')),
    ('C21 cle battery seule',
     {'battery': True, 'result': {'panels': 10, 'kwc': 5.5}},
     (10, 550, 550, 5.5, 'avec')),
    ('C22 scenario les_deux',
     {'scenario': 'les_deux', 'result': {'panels': 10, 'kwc': 5.5}},
     (10, 550, 550, 5.5, 'les_deux')),
    ('C23 aucun scenario', {'result': {'panels': 10, 'kwc': 5.5}},
     (10, 550, 550, 5.5, 'sans')),
    # ── l'arrondi à la dizaine ────────────────────────────────────────────
    ('C24 543,75 W arrondi a 540', {'result': {'panels': 16, 'kwc': 8.7}},
     (16, 540, 540, 8.7, 'sans')),
    ('C25 705 W arrondi a 700', {'result': {'panels': 20, 'kwc': 14.1}},
     (20, 700, 700, 14.1, 'sans')),
)


class LeGoldenDuCorpus(SimpleTestCase):
    """Le corpus, cas par cas, sur le lecteur UNIQUE."""

    def test_chaque_cas_rend_le_quintuplet_tranche(self):
        for identifiant, layout, attendu in CORPUS:
            with self.subTest(cas=identifiant):
                lecture = lire_layout(layout)
                obtenu = (lecture.compte, lecture.watt, lecture.watt_declare,
                          round(lecture.kwc, 3), lecture.scenario)
                self.assertEqual(obtenu, attendu)

    def test_le_lecteur_ne_mute_jamais_le_layout_de_l_appelant(self):
        layout = {'scenario': 'reseau', 'result': {'panels': 12, 'kwc': 6.6}}
        avant = repr(layout)
        lire_layout(layout)
        self.assertEqual(repr(layout), avant)


class LesQuatreDivergencesTranchees(SimpleTestCase):
    """Chaque verdict de l'en-tête, exprimé comme une assertion nommée."""

    def test_D1_le_compte_accepte_result_count_au_niveau_top(self):
        """La création lisait 0 là où la resynchro lisait 12 : plus jamais."""
        self.assertEqual(lire_layout({'result': {'count': 12}}).compte, 12)
        # ``panels`` reste PRIORITAIRE — un blob qui porte les deux n'est pas
        # départagé par l'ordre des clés d'un dict.
        self.assertEqual(
            lire_layout({'result': {'panels': 7, 'count': 12}}).compte, 7)

    def test_D2_le_wattage_est_normalise_en_entier(self):
        self.assertEqual(lire_layout(
            {'panelWatt': 545.6, 'result': {'panels': 10}}).watt, 546)
        self.assertEqual(lire_layout(
            {'panelWatt': '550', 'result': {'panels': 10}}).watt, 550)

    def test_D2_un_wattage_illisible_est_ignore_jamais_propage(self):
        """``float('abc')`` LEVAIT dans ``composition_residentielle``."""
        lecture = lire_layout({'panelWatt': 'abc',
                               'result': {'panels': 10, 'kwc': 5.5}})
        self.assertEqual(lecture.watt, 550)
        self.assertIsInstance(lecture.watt, int)

    def test_D3_le_repli_du_wattage_est_550_jamais_None(self):
        for layout in ({}, {'result': {}}, {'result': {'panels': 12}}):
            with self.subTest(layout=layout):
                self.assertEqual(lire_layout(layout).watt,
                                 geometrie.CIBLE_WATT_DEFAUT)

    def test_D3_watt_declare_reste_None_quand_rien_n_est_deductible(self):
        """La nuance dont la SÉLECTION CATALOGUE a besoin : « aucune
        préférence de wattage » n'est pas « préférer 550 »."""
        self.assertIsNone(lire_layout({'result': {'panels': 12}}).watt_declare)
        self.assertEqual(
            lire_layout({'result': {'panels': 12, 'kwc': 6.6}}).watt_declare,
            550)

    def test_D4_le_scenario_comprend_le_libelle_les_deux(self):
        self.assertEqual(
            lire_layout({'scenario': 'les_deux',
                         'result': {'panels': 10}}).scenario, 'les_deux')


class LaRegleNeJamaisInventerUnCompte(SimpleTestCase):
    """Un compte n'est retenu que s'il est PRÉSENT ou MESURÉ — jamais comblé."""

    def test_un_layout_muet_rend_zero_panneau(self):
        for layout in ({}, {'result': {}}, {'scenario': 'reseau'},
                       {'result': {'kwc': 9.9}}, {'zones': []}):
            with self.subTest(layout=layout):
                self.assertEqual(lire_layout(layout).compte, 0)

    def test_le_compte_mesure_sur_la_geometrie_est_la_somme_des_pans(self):
        lecture = lire_layout({'zones': [_zone(12, 6.6), _zone(4, 2.2)]})
        self.assertEqual(lecture.compte, 16)


class LesCinqOriginesLisentLeMemeLecteur(SimpleTestCase):
    """La preuve STRUCTURELLE : plus aucune seconde chaîne de repli."""

    #: Les motifs qui trahissent une lecture de layout écrite à la main.
    MOTIFS = ("result.get('panels')", "result.get('count')",
              "get('panelWatt')", "layout.get('watt')",
              "layout.get('battery')")

    def test_la_lecture_inline_de_la_creation_3D_est_supprimee(self):
        source = inspect.getsource(build_devis_from_layout)
        for motif in self.MOTIFS + ("'batterie' in", "'hybride' in"):
            with self.subTest(motif=motif):
                self.assertNotIn(
                    motif, source,
                    "build_devis_from_layout relit le layout à la main : "
                    "c'est la seconde chaîne de repli que QJR165 supprime.")
        self.assertIn('lire_layout(', source)

    def test_le_devis_automatique_et_le_tunnel_ne_relisent_pas_le_layout(self):
        """Ces deux origines SYNTHÉTISENT leur layout (QJR96) : elles ne le
        relisent pas pour en ressortir le compte qu'elles viennent d'écrire."""
        source = inspect.getsource(build_devis_auto)
        for motif in self.MOTIFS:
            with self.subTest(motif=motif):
                self.assertNotIn(motif, source)

    def test_les_accesseurs_de_la_resynchro_delaguent_au_lecteur_unique(self):
        """``resynchronisation`` et ``dimensionnement.plafond_toit_du_devis``
        importent ces deux noms : c'est par eux que ces origines passent."""
        for fonction in (_cible_panneaux_du_layout, _watt_du_layout):
            with self.subTest(fonction=fonction.__name__):
                source = inspect.getsource(fonction)
                self.assertIn('lire_layout(', source)
                for motif in self.MOTIFS:
                    self.assertNotIn(motif, source)

    def test_les_accesseurs_rendent_exactement_ce_que_le_lecteur_rend(self):
        for identifiant, layout, _attendu in CORPUS:
            with self.subTest(cas=identifiant):
                lecture = lire_layout(layout)
                toiture = lecture.toiture
                self.assertEqual(
                    _cible_panneaux_du_layout(layout, toiture), lecture.compte)
                self.assertEqual(
                    _watt_du_layout(layout, toiture, lecture.compte),
                    lecture.watt)

    def test_geometrie_n_heberge_qu_une_seule_lecture_de_layout(self):
        """Les SEULES fonctions autorisées à toucher ces clés :

        * ``lire_layout`` — LE lecteur ;
        * ``extract_roof_config`` — le lecteur de ZONES, où ``count`` est la
          clé légitime (et ``panels`` une LISTE de poses, pas un nombre) ;
        * ``layout_hash`` — qui n'INTERPRÈTE rien, il empreinte.
        """
        source = inspect.getsource(geometrie)
        arbre = ast.parse(source)
        porteuses = set()
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.FunctionDef):
                continue
            corps = ast.get_source_segment(source, noeud) or ''
            if any(motif in corps for motif in
                   ("get('panelWatt')", "get('panels')", "get('count')")):
                porteuses.add(noeud.name)
        self.assertEqual(
            porteuses,
            {'lire_layout', 'extract_roof_config', 'layout_hash'},
            "une NOUVELLE lecture de layout est apparue dans "
            "domain/geometrie.py — QJR165 n'en autorise qu'une.")

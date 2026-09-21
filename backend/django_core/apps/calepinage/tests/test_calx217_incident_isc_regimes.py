# -*- coding: utf-8 -*-
"""CALX217 — l'incident DEV-202608-0016 rejoué sur les TROIS régimes neufs.

L'incident, cité dans le code (``core/electrique/chaines.py``) : 25 modules
CS7N-710, **Isc 18,59 A par chaîne**, sur un **Deye 5 kW mono dont chaque
entrée admet 17 A** — une chaîne SEULE sort déjà de la borne, et le schéma
se dessinait quand même.

Le seul garde-fou existant (``test_elec_bloquants_onduleur.py``) ne couvre
qu'UN régime : la chaîne de modules sur onduleur de chaîne. CALX206
(polystring), CALX209 (micro-onduleur) et CALX211 (optimiseur à longueur
fermée) ouvrent TROIS nouveaux chemins vers la même faute. Ce fichier vérifie
qu'aucun d'eux ne la contourne :

* trois régimes, trois BLOQUANTS nommés ;
* zéro SVG produit — la condition de sortie du schéma
  (``views/schema.py``) reste fausse dans les trois cas ;
* un quatrième cas, fiche MUETTE sur ``isc_max_mppt_a``, rend une ALERTE et
  non un bloquant : le repli prudent ne fonde aucun refus, ce que le code dit
  déjà.

Parité : Aurora présente sa validation temps réel comme le garde-fou qui
empêche de « violate codes or equipment specifications »
(https://aurorasolar.com/blog/solar-panel-wiring-basics-an-intro-to-how-to-string-solar-panels/).

``SimpleTestCase`` : aucune base. La porte HTTP elle-même
(``GET schema-unifilaire``) exige l'ORM et reste gardée par la CI ; ce
fichier rejoue sa CONDITION de sortie, celle qui décide du dessin.

Run :
    python manage.py test \
        apps.calepinage.tests.test_calx217_incident_isc_regimes -v2
"""
from django.test import SimpleTestCase

from apps.calepinage.services.electrique import (
    CLE_POLYSTRING, PublicationBloquee, bloquants_nommes,
    conception_du_calepinage, evaluation_electrique, garde_publication,
)

# ── Les valeurs de l'incident, telles que le code les cite ───────────────
#: CS7N-710 : Isc 18,59 A — c'est CE chiffre qui a détruit la garantie.
MODULE_CS7N_710 = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.59, 'imp_a': 17.59,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
#: Deye 5 kW monophasé : chaque entrée MPPT admet 17 A en court-circuit.
DEYE_5K_MONO = {
    'n_mppt': 2, 'mppt_v_min': 120.0, 'mppt_v_max': 500.0,
    'v_max_abs': 600.0, 'i_max_mppt_a': 17.0, 'isc_max_mppt_a': 17.0,
    'ac_kw': 5.0, 'phases': 1,
}

#: 25 modules, répartis sur deux versants (le cas que le polystring ouvre).
LAYOUT = {'version': 2, 'zones': [
    {'label': 'PAN-EST', 'geometry': {'count': 12, 'azimuthDeg': 90.0,
                                      'tiltDeg': 20.0}},
    {'label': 'PAN-OUEST', 'geometry': {'count': 13, 'azimuthDeg': 270.0,
                                        'tiltDeg': 20.0}},
]}

#: Régime micro-onduleur (CALX209) : la fiche publie une sortie ALTERNATIVE.
MICRO_ONDULEUR = {
    'pmax_in_w': 800.0, 'v_in_max': 60.0, 'i_in_max_a': 20.0,
    'modules_par_optimiseur': 1, 'ac_kw': 0.365, 'ac_tension_v': 230.0,
    'ac_i_max_a': 1.6, 'ac_unites_max_par_branche': 4,
}

#: Régime optimiseur à longueur FERMÉE (CALX211) : les deux champs de sortie.
OPTIMISEUR_FERME = {
    'pmax_in_w': 800.0, 'v_in_min': 12.0, 'v_in_max': 60.0,
    'i_in_max_a': 20.0, 'modules_par_optimiseur': 1,
    'v_out_nominal_v': 400.0, 'modules_max_par_chaine': 25,
}


class _Calepinage:
    pk = 217
    statut = 'brouillon'

    def __init__(self, entree=None):
        self.roof_layout = LAYOUT
        saisie = {'temperature_min_c': -5.0, 'temperature_max_c': 70.0}
        saisie.update(entree or {})
        self.resultat = {'entree_electrique': saisie}
        self.company = None


def _materiel(optimiseur=None, **onduleur):
    return {
        'module': MODULE_CS7N_710,
        'onduleur': dict(DEYE_5K_MONO, **onduleur),
        'optimiseur': optimiseur,
        'designations': {'module': 'Canadian Solar CS7N-710',
                         'onduleur': 'Deye 5 kW mono',
                         'optimiseur': 'Composant d essai'
                         if optimiseur else ''},
        'absents': (),
    }


def _schema_sortirait(calepinage, materiel):
    """La CONDITION de sortie du schéma, celle de ``views/schema.py``.

    L'``@action`` ne dessine que ``if not manquantes and not bloquants`` —
    cette fonction rejoue exactement ce test sur la conception, sans passer
    par HTTP (impossible sans base ici). Elle rend ``True`` quand un SVG
    SERAIT produit.
    """
    conception, _materiel, _donnees, _document = conception_du_calepinage(
        calepinage, materiel=materiel)
    manquantes = list(getattr(conception, 'manquantes', ()) or ())
    bloquants = list(bloquants_nommes(conception) or ())
    return not manquantes and not bloquants


#: Les TROIS régimes neufs, chacun avec l'entrée et le matériel qui l'active.
REGIMES = (
    ('polystring (CALX206)',
     {CLE_POLYSTRING: [{'mppt': 1, 'pans': ['PAN-EST', 'PAN-OUEST']}]},
     None),
    ('micro-onduleur (CALX209)', {}, MICRO_ONDULEUR),
    ('optimiseur à longueur fermée (CALX211)', {}, OPTIMISEUR_FERME),
)


class TroisRegimesTroisBloquantsTest(SimpleTestCase):
    """Aucun des trois chemins neufs ne contourne la borne d'Isc."""

    def test_chaque_regime_rend_un_bloquant_nomme(self):
        for nom, entree, optimiseur in REGIMES:
            with self.subTest(regime=nom):
                evaluation = evaluation_electrique(
                    _Calepinage(entree), materiel=_materiel(optimiseur))

                self.assertEqual(evaluation['verdict'], 'bloquant', nom)
                self.assertFalse(evaluation['publiable'], nom)
                # …et le refus vient de la BORNE D'ISC, pas d'une fiche
                # incomplète (qui rendrait « indetermine » et ferait passer
                # ce test pour de mauvaises raisons).
                self.assertEqual(evaluation['manquantes'], [], nom)
                self.assertTrue(
                    any('Isc' in message
                        for message in evaluation['bloquants']), nom)

    def test_le_bloquant_nomme_l_entree_et_l_onduleur(self):
        for nom, entree, optimiseur in REGIMES:
            with self.subTest(regime=nom):
                evaluation = evaluation_electrique(
                    _Calepinage(entree), materiel=_materiel(optimiseur))
                message = next(m for m in evaluation['bloquants']
                               if 'Isc' in m)

                self.assertIn('MPPT', message)
                self.assertIn('Deye 5 kW mono', message)

    def test_le_refus_de_publication_cite_les_contraintes_bloquantes(self):
        # ``garde_publication`` ne prend pas de matériel injecté (elle lit le
        # catalogue de la société) : on rejoue ici la phrase EXACTE qu'elle
        # construit depuis l'évaluation, celle que l'écran affiche.
        for nom, entree, optimiseur in REGIMES:
            with self.subTest(regime=nom):
                evaluation = evaluation_electrique(
                    _Calepinage(entree), materiel=_materiel(optimiseur))
                refus = PublicationBloquee(
                    "Publication refusée : %d contrainte(s) onduleur "
                    "bloquante(s). %s" % (len(evaluation['bloquants']),
                                          ' '.join(evaluation['bloquants'])),
                    bloquants=evaluation['bloquants'])

                self.assertIn('Isc', str(refus), nom)
                self.assertTrue(refus.bloquants, nom)

    def test_la_garde_refuse_aussi_quand_les_fiches_manquent(self):
        # Sans matériel résolu (aucune société en test pur), la garde refuse
        # TOUJOURS — mais avec l'autre motif, et c'est ce qu'elle doit dire.
        with self.assertRaises(PublicationBloquee) as capture:
            garde_publication(_Calepinage())

        self.assertIn('fiches techniques', str(capture.exception))


class ZeroSchemaProduitTest(SimpleTestCase):
    """Un champ hors spécification ne se DESSINE pas non plus."""

    def test_aucun_svg_dans_les_trois_regimes(self):
        for nom, entree, optimiseur in REGIMES:
            with self.subTest(regime=nom):
                self.assertFalse(
                    _schema_sortirait(_Calepinage(entree),
                                      _materiel(optimiseur)), nom)

    def test_la_condition_de_sortie_n_est_pas_vide_par_construction(self):
        # Contrôle du contrôle : sur une fiche qui tient la borne, le schéma
        # SORTIRAIT — sans quoi le test précédent ne prouverait rien.
        self.assertTrue(
            _schema_sortirait(_Calepinage(),
                              _materiel(isc_max_mppt_a=45.0,
                                        i_max_mppt_a=45.0)))


class FicheMuetteSurIscTest(SimpleTestCase):
    """Le repli PRUDENT alerte, il ne bloque pas — le code le dit déjà."""

    def test_sans_isc_publie_le_verdict_est_une_alerte(self):
        materiel = _materiel()
        materiel['onduleur'] = {cle: valeur
                                for cle, valeur in materiel['onduleur'].items()
                                if cle != 'isc_max_mppt_a'}

        evaluation = evaluation_electrique(_Calepinage(), materiel=materiel)

        self.assertEqual(evaluation['verdict'], 'alerte')
        self.assertTrue(evaluation['publiable'])
        self.assertEqual(evaluation['bloquants'], [])
        self.assertTrue(evaluation['alertes'])

    def test_sans_isc_publie_le_schema_sort(self):
        materiel = _materiel()
        materiel['onduleur'] = {cle: valeur
                                for cle, valeur in materiel['onduleur'].items()
                                if cle != 'isc_max_mppt_a'}

        self.assertTrue(_schema_sortirait(_Calepinage(), materiel))

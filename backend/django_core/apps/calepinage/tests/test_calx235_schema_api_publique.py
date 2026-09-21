# -*- coding: utf-8 -*-
"""CALX233-238 (crochet de phase 2) — L'API PUBLIQUE DU DESSIN.

LE CONSTAT
----------
``services/sld.py`` et ``services/sld_export.py`` importaient HUIT privés de
``core/electrique/schema.py`` — ``_positions``, ``_format_planche``,
``_EN_BRANCHE``, ``_bloc_svg``, ``_MARGE``, ``_BLOC_L``, ``_BLOC_H``,
``_TABLEAU_L``. Deux services applicatifs vivaient donc sur la géométrie
INTERNE du moteur : le premier ajustement de mise en page les aurait cassés
en silence, et le SVG édité était RECOMPOSÉ après coup (un fragment de dessin
réémis à la main dans une chaîne déjà rendue).

CE QUE CES TESTS ARMENT
-----------------------
* le moteur publie ``GEOMETRIE``, ``places_du_schema``, ``bloc_svg`` et les
  deux paramètres ``blocs=`` / ``bandeau=`` de ``rendre_schema`` ;
* plus AUCUN service du module n'importe un privé du schéma ;
* le dessin ne bouge pas : SVG octet pour octet avec et sans le nouveau
  chemin, bandeau compris ;
* CALX238 — un seul onduleur ⇒ planche IDENTIQUE ; plusieurs exemplaires
  identiques ⇒ « typique de N », sans qu'aucun nombre ne soit inventé.

Tests PURS : le noyau et ``rendu_du_schema`` se calculent sans base.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from apps.calepinage.services.sld import (
    branches_onduleur_de_la_conception, rendu_du_schema,
)
from core.electrique import concevoir
from core.electrique.schema import (
    GEOMETRIE, blocs_du_schema, bloc_svg, places_du_schema, rendre_schema,
)
from core.electrique.types import (
    EntreeElectrique, GroupePan, SpecModule, SpecOnduleur,
)

SERVICES = (pathlib.Path(__file__).resolve().parents[1] / 'services')

MODULE = SpecModule(vmp_v=41.4, voc_v=49.3, isc_a=18.59, imp_a=17.59,
                    pmax_wc=710.0, designation='CS7N-710')
ONDULEUR = SpecOnduleur(n_mppt=2, mppt_v_min=120.0, mppt_v_max=800.0,
                        v_max_abs=1000.0, i_max_mppt_a=26.0, ac_kw=10.0,
                        phases=3, designation='Deye SG10RT')


def _entree(nb_modules=18, plafond=None):
    """Une entrée réelle. ``plafond`` (kWc raccordables par onduleur) est la
    SEULE chose qui fait retenir plusieurs exemplaires (``nombre_onduleurs``)
    — c'est une règle de dossier, pas un nombre supposé ici."""
    return EntreeElectrique(
        module=MODULE, onduleur=ONDULEUR,
        groupes=(GroupePan(label='Sud', nb_modules=nb_modules,
                           azimut_deg=180.0, inclinaison_deg=15.0),),
        dc_m=30.0, ac_m=12.0, phases=3,
        plafond_kwc_par_onduleur=plafond)


def _conception(entree):
    """Un porteur duck-typé : ce que ``evaluer_onduleurs`` lit, rien de plus.

    Sa ``resultat`` est le ``ResultatChaines`` du chaînage — c'est ce que la
    ``Conception`` du calepinage porte, pas le résultat électrique complet.
    """
    import types

    from core.electrique.chaines import concevoir_chaines

    chaines = concevoir_chaines(entree)
    return types.SimpleNamespace(entree=entree, resultat=chaines,
                                 chaines=chaines.chaines,
                                 fiche_incomplete=False, manquantes=())


class ApiPubliqueTest(unittest.TestCase):
    """Le moteur publie ce dont un consommateur a besoin."""

    def test_la_geometrie_publie_les_quatre_cotes(self):
        from core.electrique import schema

        self.assertEqual(GEOMETRIE.marge, schema._MARGE)
        self.assertEqual(GEOMETRIE.bloc_l, schema._BLOC_L)
        self.assertEqual(GEOMETRIE.bloc_h, schema._BLOC_H)
        self.assertEqual(GEOMETRIE.tableau_l, schema._TABLEAU_L)

    def test_places_du_schema_place_comme_le_moteur(self):
        entree = _entree()
        resultat = concevoir(entree)
        blocs = blocs_du_schema(entree, resultat)
        places, largeur, hauteur = places_du_schema(blocs)
        self.assertEqual([place[0].clef for place in places],
                         [bloc.clef for bloc in blocs])
        self.assertGreater(largeur, 0.0)
        self.assertGreater(hauteur, 0.0)
        # Les positions FORCÉES sont consommées comme par ``rendre_schema``.
        forcees = {blocs[0].clef: {'x': 11.0, 'y': 13.0}}
        place = places_du_schema(blocs, forcees)[0][0]
        self.assertEqual((place[1], place[2]), (11.0, 13.0))

    def test_bloc_svg_est_l_emetteur_du_moteur(self):
        from core.electrique import schema

        entree = _entree()
        bloc = blocs_du_schema(entree, concevoir(entree))[0]
        self.assertEqual(bloc_svg(10.0, 20.0, bloc),
                         schema._bloc_svg(10.0, 20.0, bloc))

    def test_aucun_service_n_importe_un_prive_du_schema(self):
        coupables = []
        for chemin in sorted(SERVICES.glob('*.py')):
            texte = chemin.read_text(encoding='utf-8')
            for ligne in texte.splitlines():
                if 'core.electrique.schema import' in ligne \
                        and re.search(r'import\s+_|,\s*_', ligne):
                    coupables.append('%s : %s' % (chemin.name, ligne.strip()))
        self.assertEqual(
            coupables, [],
            "un service importe encore un privé de core/electrique/schema.py "
            '— le moteur publie GEOMETRIE, places_du_schema et bloc_svg.')


class DessinInchangeTest(unittest.TestCase):
    """Le nouveau chemin rend le MÊME dessin, octet pour octet."""

    def test_des_blocs_passes_donnent_le_meme_svg(self):
        entree = _entree()
        resultat = concevoir(entree)
        blocs = blocs_du_schema(entree, resultat)
        self.assertEqual(rendre_schema(entree, resultat, blocs=blocs),
                         rendre_schema(entree, resultat))

    def test_un_bandeau_s_appose_sans_rien_deplacer(self):
        entree = _entree()
        resultat = concevoir(entree)
        nu = rendre_schema(entree, resultat)
        avec = rendre_schema(entree, resultat, bandeau='Calibres OMIS')
        self.assertTrue(avec.endswith('</svg>'))
        self.assertIn('Calibres OMIS', avec)
        # Le dessin est INTACT : seule une ligne s'ajoute avant la fermeture.
        fermeture = nu.rindex('</svg>')
        self.assertEqual(avec[:fermeture], nu[:fermeture])

    def test_un_libelle_edite_ne_deplace_rien(self):
        entree = _entree()
        resultat = concevoir(entree)
        nu = rendu_du_schema(entree, resultat)
        edite = rendu_du_schema(
            entree, resultat,
            edition={'libelles': {'onduleur': 'Onduleur hybride'}})
        self.assertIn('Onduleur hybride', edite['svg'])
        self.assertEqual(len(edite['svg']), len(nu['svg'])
                         + len('Onduleur hybride')
                         - len(ONDULEUR.designation))
        # Places et liaisons sont les mêmes : un texte ne bouge rien.
        self.assertEqual([(bloc['clef'], bloc['x'], bloc['y'])
                          for bloc in edite['blocs']],
                         [(bloc['clef'], bloc['x'], bloc['y'])
                          for bloc in nu['blocs']])
        self.assertEqual(edite['liaisons'], nu['liaisons'])


class BranchesOnduleurTest(unittest.TestCase):
    """CALX238 — « typique de N », sans inventer un seul nombre."""

    def test_un_seul_onduleur_ne_produit_aucune_branche(self):
        self.assertEqual(
            branches_onduleur_de_la_conception(_conception(_entree())), ())

    def test_plusieurs_exemplaires_donnent_autant_de_branches_identiques(self):
        # Plafond de 5 kWc par onduleur pour ~12,8 kWc : le noyau en
        # retient trois.
        conception = _conception(_entree(nb_modules=18, plafond=5.0))
        branches = branches_onduleur_de_la_conception(conception)
        self.assertGreater(len(branches), 1)
        self.assertEqual(len(set(tuple(sorted(b.items())) for b in branches)),
                         1, 'les exemplaires d un même modèle sont identiques')

    def test_une_branche_ne_porte_que_ce_qui_est_connu(self):
        conception = _conception(_entree(nb_modules=18, plafond=5.0))
        branches = branches_onduleur_de_la_conception(conception)
        self.assertEqual(sorted(branches[0]), ['modele'])
        self.assertEqual(branches[0]['modele'], ONDULEUR.designation)

    def test_plusieurs_exemplaires_replient_la_planche(self):
        entree = _entree(nb_modules=18, plafond=5.0)
        branches = branches_onduleur_de_la_conception(_conception(entree))
        svg = rendre_schema(entree, concevoir(entree),
                            branches_onduleur=branches)
        self.assertIn('typique de %d' % len(branches), svg)

    def test_sans_branche_la_planche_est_identique(self):
        entree = _entree()
        resultat = concevoir(entree)
        self.assertEqual(rendre_schema(entree, resultat, branches_onduleur=()),
                         rendre_schema(entree, resultat))


if __name__ == '__main__':      # pragma: no cover
    unittest.main()

"""QJR77 — pin de la surface exportée par ``apps.ventes.dimensionnement``.

POURQUOI CE PIN EXISTE. QJR77 scinde ``dimensionnement.py`` en deux : le
BALAYAGE PUR reste ici, la COUCHE LIÉE AU DEVIS part dans
``apps/ventes/domain/dimensionnement_devis.py``, et ``dimensionnement.py``
RÉ-EXPORTE. Un ré-export oublié ne se voit NULLE PART avant la CI : flake8 ne
signale JAMAIS la disparition d'un nom importé par un AUTRE module. Le texte
de la tâche le dit explicitement — ``offres_tailles`` importe des PRIVÉS de ce
module —, d'où ce pin, jumeau de ``test_services_surface`` (QJR5).

CE QUE LE PIN COUVRE — l'ensemble EXACT des noms exportés :

* ``SURFACE_PUBLIQUE`` — les 49 noms PUBLICS que le module offre (38 avant
  QJR104, + les 11 du type ``Optimum`` et de sa règle de publication) : ceux
  qu'il
  DÉFINIT (le balayage pur) ET ceux qu'il RÉ-EXPORTE depuis
  ``domain/dimensionnement_devis.py``. La liste est vérifiée EXACTE : un nom
  retiré est rouge, un nom ajouté aussi (il faut le déclarer ici, ce qui rend
  tout élargissement de surface visible en revue).
* ``PRIVES_IMPORTES_AILLEURS`` — les 4 noms PRIVÉS (préfixe ``_``) qu'un AUTRE
  module atteint réellement, avec le ou les modules importateurs. Le message
  d'échec nomme le nom manquant ET son importateur.
* ``NOMS_DEPLACES`` — les 16 noms que QJR77 a fait passer dans ``domain/`` :
  le pin vérifie qu'ils y sont DÉFINIS et qu'ils sont ré-exportés ICI, et que
  le bloc de ré-exports ne laisse RIEN derrière lui.

COMMENT LA LISTE A ÉTÉ DÉRIVÉE (jamais de mémoire, jamais à la main). Lecture
statique des fichiers réels : définitions de niveau module par AST, plus les
noms du ``from apps.ventes.domain.dimensionnement_devis import …`` de niveau
module — puis balayage AST de tout ``backend/django_core`` pour les deux
façons d'atteindre un privé : ``from apps.ventes.dimensionnement import _x``
et ``dimensionnement._x`` après une liaison de module PROUVÉE par un import
(un grep textuel donnait un faux positif — ``dimensionnement.get(...)`` dans
``public_views``/``offres_tailles``/``profils_comparatifs``, où
``dimensionnement`` est une VARIABLE LOCALE portant un dict, pas le module).

NOTE DE VÉRIFICATION (29/08/2026). Le texte de QJR77 cite cinq privés —
``_lire_composition``, ``_compter_modules_batterie``,
``_lignes_produit_du_devis``, ``_payback``, ``_arrondi`` — comme importés par
``offres_tailles``, ``services`` et ``taille_detail``. VÉRIFIÉ, et la réalité
est plus étroite : ``services.py`` et ``taille_detail.py`` n'importent AUCUN
privé de ce module (``services`` n'en prend que ``recommander_taille`` ;
``taille_detail`` ne le cite qu'en commentaire), et ``_arrondi`` n'est importé
NULLE PART ailleurs. Il reste par ailleurs défini ici (côté pur) : rien à
ré-exporter pour lui. Les quatre privés réellement atteints sont pinnés
ci-dessous.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_dimensionnement_surface -v 2
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes import dimensionnement
from apps.ventes.domain import dimensionnement_devis

#: Le module vers lequel QJR77 a déplacé la couche liée au devis. Les noms
#: qu'il rend sont ré-exportés par ``dimensionnement.py`` : la surface du
#: module d'origine est donc « ce qu'il définit ∪ ce qu'il ré-exporte d'ici ».
MODULE_DEVIS = "apps.ventes.domain.dimensionnement_devis"

# METTRE À JOUR CETTE LISTE dans le MÊME commit que le changement de surface.
# Elle se re-dérive mécaniquement (ne jamais la retaper de mémoire) : c'est
# exactement ce que calcule ``_surface_niveau_module`` plus bas, filtré sur les
# noms sans préfixe ``_``.
SURFACE_PUBLIQUE = (
    # QJR104 — le TYPE d'optimum et sa règle de publication (11 noms). Ils
    # sont ICI parce que c'est ici que les optima sont PRODUITS ; les
    # consommateurs (charge utile publique QJR14, moteur PDF QJR13) ne font
    # plus que les lire.
    "ConfigInstallation",
    "Optimum",
    "TOLERANCE_CAPACITE_KWH",
    "config_du_bloc",
    "config_vendue_du_devis",
    "decrit",
    "decrit_la_capacite",
    "optima_publiables",
    "optimum_de_ligne",
    "optimum_du_bloc",
    "publier_si_decrit",
    # ── la surface d'avant QJR104 ───────────────────────────────────────────
    "CRITERES",
    "CRITERE_DEFAUT",
    "EGALITE_PAYBACK_ANNEES",
    "FACTEUR_MAX_FALAISE",
    "HORIZON_MARGINAL_BATTERIE",
    "HORIZON_MARGINAL_PV",
    "MAX_PALIERS_ECHELLE",
    "MAX_PALIERS_STOCKAGE",
    "MAX_PANNEAUX_BALAYAGE",
    "MAX_SONDES_ECHELLE",
    "RATIO_ONDULEUR_MIN",
    "balayer_tailles",
    "bornes_candidates",
    "capacite_batterie_des_lignes",
    "capacite_utile_batterie",
    "chercher_falaise",
    "choisir_recommandation",
    "choisir_recommandation_avec",
    "combos_champ_stockage",
    "contenance_toit_du_devis",
    "contour_du_devis_lnglat",
    "depart_dans_horizon",
    "echelle_paliers_batterie",
    "facteur_remise_du_devis",
    "grimper_par_pas_marginaux",
    "horizon_du_pas",
    "logger",
    "module_batterie_du_devis",
    "paliers_stockage_candidats",
    "plafond_physique_du_devis",
    "plafond_toit_du_devis",
    "plus_grande_contenance",
    "point_depart_meilleur_payback",
    "ratio_pas_marginal",
    "recommander_taille",
    "residuel_minimal",
    "tailles_eligibles",
    "verdict_bloquant",
)

PRIVES_IMPORTES_AILLEURS = {
    # DÉPLACÉ EN QJR77 — c'est le cas que la tâche nomme : un ré-export oublié
    # ici casserait ``offres_tailles`` en production sans un mot de flake8.
    "_compter_modules_batterie": (
        "apps/ventes/offres_tailles.py",
        "apps/ventes/tests/test_bathomo_banque_homogene.py",
    ),
    # DÉPLACÉ EN QJR77 — cinq sites d'appel dans ``offres_tailles``.
    "_lignes_produit_du_devis": ("apps/ventes/offres_tailles.py",),
    # RESTE côté pur (lecture d'une composition, aucune base) — pinné parce
    # qu'un déplacement ultérieur lui ferait courir le même risque.
    "_lire_composition": (
        "apps/ventes/offres_tailles.py",
        "apps/ventes/tests/test_bathomo_banque_homogene.py",
    ),
    # RESTE côté pur. Atteint par ``dimensionnement._payback(...)`` après
    # ``from apps.ventes import dimensionnement`` — la seconde façon d'importer
    # un privé, celle qu'un grep de ``import`` ne montre pas.
    "_payback": ("apps/ventes/tests/test_deux_optimiseurs.py",),
}

#: Les 16 noms que QJR77 a fait passer dans ``domain/dimensionnement_devis.py``
#: — la couche qui LIT un ``Devis`` et qui MUTE l'instance qu'on lui passe.
#: Ils doivent être DÉFINIS là-bas et RÉ-EXPORTÉS ici, sans exception.
NOMS_DEPLACES = (
    "MAX_PALIERS_ECHELLE",
    "MAX_SONDES_ECHELLE",
    "_MEMO_PLAFOND_PHYSIQUE",
    "_compter_modules_batterie",
    "_compter_modules_batterie_generique",
    "_echelle_paliers_batterie",
    "_lignes_produit_du_devis",
    "capacite_batterie_des_lignes",
    "contenance_toit_du_devis",
    "contour_du_devis_lnglat",
    "echelle_paliers_batterie",
    "facteur_remise_du_devis",
    "module_batterie_du_devis",
    "plafond_physique_du_devis",
    "plafond_toit_du_devis",
    "plus_grande_contenance",
)

#: ``logger`` est DÉLIBÉRÉMENT défini des deux côtés
#: (``logging.getLogger(__name__)``, comme ``domain/entrees.py``) : ce n'est
#: pas un nom déplacé, c'est le journal propre à chaque module.
_JOURNAL_PROPRE = "logger"


def _definitions_niveau_module(chemin):
    """Noms définis AU NIVEAU MODULE (def / class / affectation) du fichier.

    Volontairement limité à ``tree.body`` : une définition conditionnelle
    (sous ``if``/``try``) n'est pas une garantie d'export.
    """
    arbre = ast.parse(Path(chemin).read_text(encoding="utf-8"))
    noms = set()
    for noeud in arbre.body:
        if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            noms.add(noeud.name)
        elif isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name):
                    noms.add(cible.id)
        elif isinstance(noeud, ast.AnnAssign) and isinstance(noeud.target,
                                                             ast.Name):
            noms.add(noeud.target.id)
    return noms


def _reexports_niveau_module(chemin, module):
    """Noms ré-exportés AU NIVEAU MODULE par ``from <module> import …``.

    Limité au module nommé : les imports d'outillage (``logging``, ``math``,
    ``decimal``) ne font pas partie de la surface que ce pin décrit.
    """
    arbre = ast.parse(Path(chemin).read_text(encoding="utf-8"))
    noms = set()
    for noeud in arbre.body:
        if (isinstance(noeud, ast.ImportFrom) and noeud.level == 0
                and noeud.module == module):
            for alias in noeud.names:
                noms.add(alias.asname or alias.name)
    return noms


def _surface_niveau_module(chemin):
    """Ce que le fichier offre : ce qu'il définit ∪ ce qu'il ré-exporte."""
    return (_definitions_niveau_module(chemin)
            | _reexports_niveau_module(chemin, MODULE_DEVIS))


class SurfaceDimensionnementTests(SimpleTestCase):
    """La surface de ``apps.ventes.dimensionnement`` ne bouge pas en silence."""

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.surface = _surface_niveau_module(dimensionnement.__file__)
        cls.reexports = _reexports_niveau_module(dimensionnement.__file__,
                                                 MODULE_DEVIS)
        cls.definitions_devis = _definitions_niveau_module(
            dimensionnement_devis.__file__)

    # ── les noms doivent EXISTER (le cas « ré-export oublié en QJR77 ») ─────

    def test_chaque_nom_public_est_toujours_exporte(self):
        manquants = [nom for nom in SURFACE_PUBLIQUE
                     if not hasattr(dimensionnement, nom)]
        self.assertEqual(
            manquants, [],
            "apps.ventes.dimensionnement n'exporte plus ce(s) nom(s) "
            "PUBLIC(S) : " + ", ".join(manquants)
            + ". Le déplacement QJR77 doit laisser un ré-export dans "
              "apps/ventes/dimensionnement.py (ou retirer le nom de "
              "SURFACE_PUBLIQUE dans le MÊME commit, ce qui rend le retrait "
              "visible en revue).")

    def test_chaque_prive_importe_ailleurs_est_toujours_exporte(self):
        for nom, importateurs in sorted(PRIVES_IMPORTES_AILLEURS.items()):
            with self.subTest(nom=nom):
                self.assertTrue(
                    hasattr(dimensionnement, nom),
                    "apps.ventes.dimensionnement n'exporte plus le nom PRIVÉ "
                    "%s, importé par : %s. flake8 ne signale PAS cette "
                    "disparition — d'où ce pin. Laisser un ré-export dans "
                    "apps/ventes/dimensionnement.py, ou mettre l'importateur à "
                    "jour dans le même commit." % (nom, ", ".join(importateurs)))

    # ── la liste dorée doit rester EXACTE (le cas « surface élargie ») ──────

    def test_la_surface_publique_est_exacte(self):
        attendus = set(SURFACE_PUBLIQUE)
        reels = {nom for nom in self.surface if not nom.startswith("_")}
        disparus = sorted(attendus - reels)
        non_declares = sorted(reels - attendus)
        self.assertEqual(
            (disparus, non_declares), ([], []),
            "SURFACE_PUBLIQUE ne décrit plus la surface publique de "
            "apps/ventes/dimensionnement.py (définitions + ré-exports de "
            "domain/dimensionnement_devis.py).\n"
            "  disparus du module : %s\n"
            "  ajoutés mais non déclarés ici : %s\n"
            "Mettre la liste dorée à jour dans le MÊME commit que le "
            "changement de surface." % (disparus or "aucun",
                                        non_declares or "aucun"))

    def test_les_prives_pinnes_sont_definis_ou_reexportes(self):
        absents = sorted(nom for nom in PRIVES_IMPORTES_AILLEURS
                         if nom not in self.surface)
        self.assertEqual(
            absents, [],
            "PRIVES_IMPORTES_AILLEURS épingle un nom qui n'est plus ni défini "
            "ni ré-exporté au niveau module de apps/ventes/dimensionnement.py "
            ": %s. Soit il a été déplacé (laisser un ré-export), soit il n'a "
            "jamais appartenu à ce module (le retirer de la liste)."
            % ", ".join(absents))

    def test_aucun_nom_prive_dans_la_surface_publique(self):
        intrus = sorted(nom for nom in SURFACE_PUBLIQUE
                        if nom.startswith("_"))
        self.assertEqual(intrus, [],
                         "SURFACE_PUBLIQUE ne contient que des noms publics ; "
                         "les privés vont dans PRIVES_IMPORTES_AILLEURS.")

    def test_la_liste_doree_est_triee_et_sans_doublon(self):
        """Une liste triée se relit en diff ; un doublon masque un retrait."""
        self.assertEqual(list(SURFACE_PUBLIQUE), sorted(SURFACE_PUBLIQUE),
                         "SURFACE_PUBLIQUE doit rester triée.")
        self.assertEqual(len(set(SURFACE_PUBLIQUE)), len(SURFACE_PUBLIQUE),
                         "SURFACE_PUBLIQUE contient un doublon.")
        self.assertEqual(list(NOMS_DEPLACES), sorted(NOMS_DEPLACES),
                         "NOMS_DEPLACES doit rester triée.")
        self.assertEqual(len(set(NOMS_DEPLACES)), len(NOMS_DEPLACES),
                         "NOMS_DEPLACES contient un doublon.")
        chevauchement = sorted(set(SURFACE_PUBLIQUE)
                               & set(PRIVES_IMPORTES_AILLEURS))
        self.assertEqual(chevauchement, [],
                         "Un nom ne peut pas être dans les deux listes.")
        for nom, importateurs in PRIVES_IMPORTES_AILLEURS.items():
            with self.subTest(nom=nom):
                self.assertTrue(importateurs,
                                "%s doit nommer au moins un importateur." % nom)

    # ── la SCISSION elle-même est pinnée (QJR77) ────────────────────────────

    def test_chaque_nom_deplace_vit_bien_dans_domain(self):
        absents = sorted(nom for nom in NOMS_DEPLACES
                         if nom not in self.definitions_devis)
        self.assertEqual(
            absents, [],
            "QJR77 a déplacé ce(s) nom(s) vers "
            "apps/ventes/domain/dimensionnement_devis.py, mais ils n'y sont "
            "plus définis au niveau module : %s. Un retour en arrière doit se "
            "voir en revue — mettre NOMS_DEPLACES à jour dans le MÊME commit."
            % ", ".join(absents))

    def test_chaque_nom_deplace_est_reexporte_par_dimensionnement(self):
        oublies = sorted(nom for nom in NOMS_DEPLACES
                         if nom not in self.reexports)
        self.assertEqual(
            oublies, [],
            "apps/ventes/dimensionnement.py ne ré-exporte plus : %s. Ces noms "
            "sont importés depuis apps.ventes.dimensionnement par "
            "offres_tailles, public_views et six suites de tests — flake8 ne "
            "dirait RIEN. Rétablir le ré-export."
            % ", ".join(oublies))

    def test_le_bloc_de_reexports_ne_laisse_rien_derriere(self):
        """Un nom ajouté dans ``domain/`` sans ré-export ne passe pas.

        C'est le piège symétrique du ré-export oublié : la moitié déplacée
        grandit, ``dimensionnement.py`` ne suit pas, et le nouveau nom n'est
        joignable que par son chemin ``domain.…`` — deux surfaces au lieu
        d'une, exactement ce que QJR77 ferme.
        """
        attendus = set(self.definitions_devis) - {_JOURNAL_PROPRE}
        non_reexportes = sorted(attendus - self.reexports)
        en_trop = sorted(self.reexports - attendus)
        self.assertEqual(
            (non_reexportes, en_trop), ([], []),
            "Le bloc de ré-exports de apps/ventes/dimensionnement.py ne "
            "correspond plus aux définitions de "
            "apps/ventes/domain/dimensionnement_devis.py.\n"
            "  définis là-bas, PAS ré-exportés ici : %s\n"
            "  ré-exportés ici, plus définis là-bas : %s"
            % (non_reexportes or "aucun", en_trop or "aucun"))

"""Tests PACT7 — scripts/check_openapi_shapes.py.

Stdlib pur (unittest), aucune base de donnees, aucun Django, aucune generation
de schema. Lancer :
    python -m unittest scripts.tests.test_check_openapi_shapes -v

Chaque test correspond a un fait MESURE de l'incident du 03/08/2026 :
``/ao/tableau-marches/`` documente « type: object » sans propriete,
``/flotte/vehicules/tableau-bord/`` documente avec le mauvais serializer, et
406 vues sur lesquelles le generateur declare forfait.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_openapi_shapes as cos  # noqa: E402


def ecrire(base: Path, chemin: str, texte: str) -> Path:
    cible = base / chemin
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(texte, encoding="utf-8")
    return cible


class VocabulaireAgregeTests(unittest.TestCase):
    def test_les_formes_de_tableau_de_bord_sont_reconnues(self):
        for chemin in ("tableau-bord", "tableau_bord", "tableau-de-bord",
                       "tableau-marches", "dashboard", "cockpit-cloture",
                       "kpi", "kpis", "kpi-mere", "statistiques", "stats",
                       "synthese-mensuelle", "indicateurs", "pilotage",
                       "analyse-concurrents", "fiche-360", "fournisseur-360"):
            self.assertTrue(cos.est_agrege(chemin), chemin)

    def test_une_action_metier_ordinaire_n_est_pas_agregee(self):
        # Aucun de ces chemins ne doit tomber dans le vocabulaire : une garde
        # qui crie au loup finit desactivee.
        for chemin in ("valider", "soumettre", "annuler", "generer-pdf",
                       "export-csv", "prendre-en-charge", "resoudre",
                       "calendrier-equipe", "historique", "noter",
                       "grand_livre", "balance-referentiel"):
            self.assertFalse(cos.est_agrege(chemin), chemin)

    def test_accents_et_soulignes_sont_normalises(self):
        self.assertEqual(cos.normaliser_chemin("Synthèse_Mensuelle"),
                         "synthese-mensuelle")


class FormesVidesTests(unittest.TestCase):
    """R1 — une forme vide valide TOUT, donc elle ne protege RIEN."""

    def _vides(self, source: str):
        import ast
        return cos.formes_vides(ast.parse(source), "apps.x.views")

    def test_response_dict_est_refuse(self):
        # LA declaration exacte de /ao/tableau-marches/ le 03/08/2026.
        source = ("@extend_schema(responses={200: OpenApiResponse("
                  "response=dict, description='x')})\n"
                  "def tableau_marches_view(request):\n    pass\n")
        self.assertEqual(self._vides(source),
                         [("apps.x.views:tableau_marches_view", "dict")])

    def test_openapitypes_object_est_refuse(self):
        source = ("@extend_schema(responses=OpenApiTypes.OBJECT)\n"
                  "def comparer(self, request):\n    pass\n")
        self.assertEqual(self._vides(source),
                         [("apps.x.views:comparer", "OpenApiTypes.OBJECT")])

    def test_chaque_occurrence_est_nommee_separement(self):
        # Regression : dedupliquer par module transformait trois defauts d'un
        # meme fichier en UNE ligne, donc en une correction sur trois.
        source = ("class V:\n"
                  "    @extend_schema(responses=OpenApiTypes.OBJECT)\n"
                  "    def comparer(self): pass\n"
                  "    @extend_schema(responses=OpenApiTypes.OBJECT)\n"
                  "    def marches(self): pass\n")
        porteurs = {porteur for porteur, _ in self._vides(source)}
        self.assertEqual(porteurs,
                         {"apps.x.views:V.comparer", "apps.x.views:V.marches"})

    def test_un_serialiseur_reel_passe(self):
        source = ("@extend_schema(responses=inline_serializer('X', {"
                  "'total': serializers.IntegerField()}))\n"
                  "def tableau_bord(self, request): pass\n")
        self.assertEqual(self._vides(source), [])

    def test_le_depot_ne_declare_plus_aucune_forme_vide(self):
        # R1 n'a AUCUNE base de reference : zero aujourd'hui, zero demain.
        vides, _ = cos.analyser()
        self.assertEqual(vides, [], f"formes vides reapparues : {vides}")


class EndpointsAgregesTests(unittest.TestCase):
    """R3 — un agregat sans forme declaree est publie avec un MENSONGE."""

    def _agreges(self, source: str):
        import ast
        return cos.endpoints_agreges_sans_forme(ast.parse(source), "apps.x.views")

    def test_action_tableau_bord_sans_extend_schema(self):
        # Le cas mesure : /flotte/vehicules/tableau-bord/ etait publie avec le
        # VehiculeSerializer alors qu'il renvoie {vehicules, engins, ...}.
        source = ("class VehiculeViewSet:\n"
                  "    @action(detail=False, methods=['get'], url_path='tableau-bord')\n"
                  "    def tableau_bord(self, request): pass\n")
        self.assertEqual(self._agreges(source),
                         ["apps.x.views:VehiculeViewSet.tableau_bord"])

    def test_action_tableau_bord_avec_forme_declaree(self):
        source = ("class VehiculeViewSet:\n"
                  "    @extend_schema(responses=inline_serializer('FlotteTableauBord', {}))\n"
                  "    @action(detail=False, methods=['get'], url_path='tableau-bord')\n"
                  "    def tableau_bord(self, request): pass\n")
        self.assertEqual(self._agreges(source), [])

    def test_url_path_par_defaut_est_le_nom_de_methode(self):
        # DRF : sans url_path, le chemin est le NOM DE LA METHODE tel quel.
        source = ("class V:\n"
                  "    @action(detail=False)\n"
                  "    def statistiques(self, request): pass\n")
        self.assertEqual(self._agreges(source), ["apps.x.views:V.statistiques"])

    def test_vue_fonction_api_view(self):
        source = ("@api_view(['GET'])\n"
                  "def tableau_bord(request): pass\n")
        self.assertEqual(self._agreges(source), ["apps.x.views:tableau_bord"])

    def test_une_action_ordinaire_est_ignoree(self):
        source = ("class V:\n"
                  "    @action(detail=True, methods=['post'], url_path='valider')\n"
                  "    def valider(self, request, pk=None): pass\n")
        self.assertEqual(self._agreges(source), [])


class CliquetsTests(unittest.TestCase):
    def test_le_plafond_non_devinables_correspond_au_depot(self):
        # R2 — le plafond gele DOIT etre celui reellement atteint, sinon le
        # cliquet a du jeu et la dette peut remonter en silence.
        self.assertEqual(cos.compter_non_devinables(),
                         cos.PLAFOND_NON_DEVINABLES)

    def test_la_base_r3_couvre_exactement_la_dette_actuelle(self):
        _, agreges = cos.analyser()
        base = cos.charger_base()
        self.assertEqual(sorted(set(agreges) - base), [],
                         "un endpoint agrege NOUVEAU n'est pas dans la base")

    def test_la_base_ne_peut_que_retrecir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "allow.txt"
            cos.ecrire_base({"apps.x.views:V.tableau_bord"}, path)
            self.assertEqual(cos.charger_base(path),
                             {"apps.x.views:V.tableau_bord"})
            entete = path.read_text(encoding="utf-8")
            self.assertIn("NE PEUT QUE RETRECIR", entete)

    def test_la_signature_ne_porte_ni_fichier_ni_ligne(self):
        # Lecon du depot : une allowlist `fichier:ligne` derive au moindre
        # decalage de lignes.
        for entree in cos.charger_base():
            self.assertNotIn(".py", entree, entree)
            self.assertRegex(entree, r"^[\w.]+:[\w.]+$", entree)


class DepotReelTests(unittest.TestCase):
    def test_un_nouvel_agrege_sans_forme_rend_la_garde_ROUGE(self):
        # LE critere de PACT7 : « aucune nouvelle vue ne peut declarer
        # response=dict » et aucun nouveau tableau de bord ne peut naitre muet.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            ecrire(base, "apps/neuf/views.py",
                   "class NeufViewSet:\n"
                   "    @action(detail=False, url_path='tableau-bord')\n"
                   "    def tableau_bord(self, request): pass\n")
            _, agreges = cos.analyser(base)
            self.assertEqual(agreges, ["apps.neuf.views:NeufViewSet.tableau_bord"])
            self.assertEqual(sorted(set(agreges) - cos.charger_base()), agreges)

    def test_l_entete_explique_pourquoi_le_schema_n_aurait_rien_vu(self):
        entete = Path(cos.__file__).read_text(encoding="utf-8")[:4000]
        self.assertIn("03/08/2026", entete)
        self.assertIn("tableau-marches", entete)
        self.assertIn("VehiculeSerializer", entete)


if __name__ == "__main__":
    unittest.main()

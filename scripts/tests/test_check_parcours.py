"""AMET98 — garde des tables de parcours (`scripts/check_parcours.py`) et outil de rejeu
(`scripts/rejouer_parcours.py`), sans Django, sans base, sans docker.

Verrouille : une étape sans règle aval ou sans checkpoint fait échouer la table (mutant
« accepter une étape sans checkpoint ») ; un symbole résolu passe ; une étape « manquante »
déclarée passe la garde et n'est JAMAIS jouée par le rejeu ; la dette `portes[]` est un cliquet ;
l'enregistrement d'acceptation écrit par le rejeu est conforme à `check_acceptation.py` (AMET88).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_acceptation  # noqa: E402
import check_parcours  # noqa: E402
import rejouer_parcours  # noqa: E402

SYM = "backend/django_core/core/parcours.py::resoudre_symbole"
CLASSE = "backend/django_core/core/parcours.py::charger_table"


def _etape(**surcharges):
    etape = {"id": "PX.01", "nom": "n", "proprietaire": "p", "declencheur": {"type": "clic", "source": SYM},
             "fonction_entree": SYM, "checkpoint": {"modifiable": False, "champs": [], "persistance": CLASSE},
             "regle_aval": ["reference"], "taches": ["AMET98"]}
    etape.update(surcharges)
    return etape


def _compacte(**surcharges):
    etape = {"id": "c1", "libelle": "l", "declencheur": {"type": "http", "source": SYM}, "fonction_entree": SYM,
             "checkpoint": {"persistance": CLASSE}, "regles_aval": [{"regle": "r", "source": SYM}]}
    etape.update(surcharges)
    return etape


class ParcoursTests(unittest.TestCase):
    def test_etape_sans_regle_aval_echoue_et_symbole_resolu_passe(self):
        self.assertEqual(check_parcours.problemes({"portes": ["x"], "etapes": [_etape()]}), [])
        sans = check_parcours.problemes({"portes": ["x"], "etapes": [_etape(regle_aval=[])]})
        self.assertTrue(any("regle_aval" in e for e in sans), sans)
        faux = check_parcours.problemes({"portes": ["x"], "etapes": [_etape(fonction_entree=SYM + "_absent")]})
        self.assertTrue(any("introuvable" in e for e in faux), faux)

    def test_etape_sans_checkpoint_echoue_dans_les_deux_dialectes(self):
        canon = _etape()
        del canon["checkpoint"]
        compacte = _compacte()
        del compacte["checkpoint"]
        for table in ({"portes": ["x"], "etapes": [canon]}, {"portes": ["x"], "etapes": [compacte]}):
            self.assertTrue(any("checkpoint" in e for e in check_parcours.problemes(table)))

    def test_dialecte_compact_regle_aval_et_portes(self):
        self.assertEqual(check_parcours.problemes({"portes": ["x"], "etapes": [_compacte()]}), [])
        erreurs = check_parcours.problemes({"etapes": [_compacte(regles_aval=[{"regle": "", "source": SYM}])]})
        self.assertTrue(any("règle aval" in e for e in erreurs) and any("portes" in e for e in erreurs), erreurs)

    def test_etape_manquante_declaree_passe_la_garde(self):
        manq = _compacte(manquante=True, raison="r", attendu="a", declencheur={"manquant": True},
                         fonction_entree={"manquant": True})
        self.assertEqual(check_parcours.problemes({"portes": ["x"], "etapes": [manq]}), [])
        manq["raison"] = ""
        self.assertTrue(check_parcours.problemes({"portes": ["x"], "etapes": [manq]}))

    def test_dette_portes_est_un_cliquet(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "PA5.json"
            chemin.write_text(json.dumps({"parcours": "PA5", "portes": ["x"], "etapes": [_compacte()]}), "utf-8")
            lignes, echecs = check_parcours.verifier([chemin])
        self.assertEqual(echecs, 1)
        self.assertIn("cliquet", "\n".join(lignes))

    def test_les_sept_tables_sont_trouvees(self):
        # Le verdict sur les tables réelles est la garde elle-même (`python scripts/check_parcours.py`,
        # branchée dans ci_guards) : ici on vérifie seulement qu'elle les voit toutes.
        noms = {c.stem for c in check_parcours.tables()}
        self.assertLessEqual({f"PA{i}" for i in range(1, 8)}, noms)


class RejeuTests(unittest.TestCase):
    TABLE = {"parcours": "PX", "portes": ["x"], "etapes": [
        _etape(), _compacte(id="m1", manquante=True, raison="r", attendu="a", declencheur={"manquant": True},
                            fonction_entree={"manquant": True})]}

    def _faux_shell(self, verdict="PASS"):
        oracles = "PPNNPPPNPP" if verdict == "PASS" else "PFNNPPPNPP"
        resultats = {"etapes": [{"id": "PX.01", "verdict": verdict, "trace": "POST /x/ -> 201",
                                 "o": oracles, "par": "NNP"}]}
        observe = "bruit\n" + rejouer_parcours.MARQUE + json.dumps(resultats)
        res = {"observe": observe, "verdict": "REPRO", "base_inchangee": True}

        def faux(cmd, prog, timeout):
            self.programme = prog
            return 0, "@@RESULT " + json.dumps(res) + "\n", ""
        return faux

    def test_etape_manquante_rapportee_jamais_jouee(self):
        jouables, manquantes = rejouer_parcours.partager(self.TABLE)
        self.assertEqual([e["id"] for e in jouables], ["PX.01"])
        self.assertEqual([e["id"] for e in manquantes], ["m1"])
        source = rejouer_parcours.source_sonde(self.TABLE, jouables, "42", None, {})
        compile(source, "sonde", "exec")
        self.assertNotIn('"m1"', source.split("TABLE_ETAPES = ")[1].split("\n")[0])

    def test_enregistrement_ecrit_conforme_a_check_acceptation(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(check_acceptation, "ROOT", Path(d)):
            with contextlib.redirect_stdout(io.StringIO()) as sortie:
                code = rejouer_parcours.rejouer(self.TABLE, "PX", "42", executer=self._faux_shell(),
                                                racine=Path(d), sha="0123456789abcdef", date="2026-10-12")
            md = Path(d) / "docs/audits/acceptation/AMET/2026-10-12-012345678.md"
            self.assertEqual(code, 0, sortie.getvalue())
            self.assertTrue(md.is_file(), sortie.getvalue())
            erreurs: list = []
            self.assertEqual(check_acceptation.lire_enregistrement(md, erreurs), {"AMET98"}, erreurs)
            self.assertIn("m1 : MANQUANTE", sortie.getvalue())
        self.assertIn("set_rollback(True)", self.programme)  # le rejeu passe par sonde.py

    def test_etape_en_echec_rend_un_enregistrement_fail_qui_ne_couvre_rien(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(check_acceptation, "ROOT", Path(d)):
            with contextlib.redirect_stdout(io.StringIO()):
                code = rejouer_parcours.rejouer(self.TABLE, "PX", "42", executer=self._faux_shell("FAIL"),
                                                racine=Path(d), sha="0123456789abcdef", date="2026-10-12")
            md = Path(d) / "docs/audits/acceptation/AMET/2026-10-12-012345678.md"
            self.assertEqual(code, 1)
            self.assertEqual(check_acceptation.lire_enregistrement(md, []), set())

    def test_route_retrouvee_par_le_mro_et_url_concrete(self):
        class Mixin:
            pass

        class VueDevis(Mixin):
            pass
        rappel = mock.Mock(actions={"post": "convertir_en_bc"})
        moteur = object.__new__(rejouer_parcours._Moteur)
        moteur.routes = [("api/django/ventes/^devis/(?P<pk>[^/.]+)/convertir_en_bc/$", rappel, VueDevis)]
        motif, verbe, cls = moteur.route_de("backend/django_core/apps/v.py::Mixin.convertir_en_bc")
        self.assertEqual((verbe, cls), ("post", VueDevis))
        self.assertEqual(moteur.concret(motif, 42), "/api/django/ventes/devis/42/convertir_en_bc/")
        self.assertIsNone(moteur.route_de("frontend/src/pages/DevisList.jsx::convertirDevisEnBC"))

    def test_jamais_contre_la_prod(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            rejouer_parcours.main(["PA4", "--enregistrement", "1", "--conteneur", "taqinor-prod-django"])
        self.assertTrue(os.path.isfile(rejouer_parcours.sonde.__file__))


if __name__ == "__main__":
    unittest.main()

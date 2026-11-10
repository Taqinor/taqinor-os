"""Rejoue le calcul « périmé » de SauvegardesPage.jsx (node) sur un exercice ÉCHOUÉ d'hier, et lit dans resume_sauvegardes le tri '-termine_le' qui place en tête les exercices échoués (termine_le nul, NULLS FIRST sous Postgres)."""
SONDE = {"constat": "C-ADCG-019", "sha": "ce4e5fc4f",
         "attendu": "A : drill echec d'hier → drillPerime=false (badge masqué) ; B : dernier_drill sans filtre de statut, tri -termine_le sans nulls_last, échecs sans termine_le"}
import ast, json, pathlib, re, shutil, subprocess, tempfile
RACINE = pathlib.Path(__file__).resolve().parents[4]


def partie_a():
    jsx = (RACINE / "frontend/src/pages/parametres/SauvegardesPage.jsx").read_text(encoding="utf-8")
    seuil = re.search(r"const DRILL_STALE_DAYS = \d+", jsx).group(0)
    jours = re.search(r"function joursDepuis\(iso\) \{.*?\n\}", jsx, re.S).group(0)
    calc = re.search(r"const joursDrill = .*?\n\s*const drillPerime = .*?\n", jsx, re.S).group(0)
    js = (f"{seuil}\n{jours}\nconst drill = {{statut: 'echec', date: new Date(Date.now() - 86400000).toISOString()}}\n"
          f"{calc}\nconsole.log(JSON.stringify({{joursDrill, drillPerime, drillEchec}}))\n")
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "calc.mjs"; p.write_text(js, encoding="utf-8")
        out = subprocess.run([shutil.which("node"), str(p)], capture_output=True, text=True, timeout=60)
    return json.loads(out.stdout.strip().splitlines()[-1])


def partie_b():
    src = (RACINE / "backend/django_core/core/backup.py").read_text(encoding="utf-8")
    arbre = ast.parse(src)
    resume = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "resume_sauvegardes")
    seg = ast.get_source_segment(src, resume)
    bloc = seg[seg.index("dernier_drill = ("):seg.index("rto_annonce_heures = None")]
    filtre_statut = "statut" in bloc
    tri_nul_en_tete = "'-termine_le'" in bloc and "nulls_last" not in bloc
    drill = ast.get_source_segment(src, next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "restore_drill"))
    nb_echecs = drill.count("STATUT_ECHEC")
    nb_termine_le = drill.count("run.termine_le")
    return {"filtre_statut": filtre_statut, "tri_nul_en_tete": tri_nul_en_tete,
            "branches_echec": nb_echecs, "affectations_termine_le": nb_termine_le}


def sonde(ctx=None):
    a, b = partie_a(), partie_b()
    # ADCG42 : le correctif laisse drillPerime faux sur un échec mais affiche le badge drillEchec ; masqué = ni l'un ni l'autre.
    masque = a["drillPerime"] is False and a.get("drillEchec") is not True
    nul_en_tete = (not b["filtre_statut"]) and b["tri_nul_en_tete"] and b["affectations_termine_le"] == 1
    return {"repro": masque or nul_en_tete, "observe": (
        f"A (page) : drill echec d'hier → joursDrill={a['joursDrill']}, drillPerime={a['drillPerime']}, drillEchec={a.get('drillEchec')} ; "
        f"B (resume_sauvegardes) : filtre de statut sur dernier_drill={b['filtre_statut']}, tri -termine_le sans nulls_last="
        f"{b['tri_nul_en_tete']}, restore_drill : {b['branches_echec']} branches echec et {b['affectations_termine_le']} "
        f"seule affectation de termine_le (succès) → un échec a termine_le nul et passe en tête sous Postgres")}


if __name__ == "__main__":
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))

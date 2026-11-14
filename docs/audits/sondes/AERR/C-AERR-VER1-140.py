"""Contre-visite AERR (VER1, écart sur AERR87) : frontend/src/pages/stock/ProduitForm.jsx::validate applique
validationEntiers.js::erreursEntiersProduit à TOUS les champs entiers, y compris `quantite_stock`, aussi en ÉDITION, alors
que ce champ y est désactivé (`disabled={isEdit}`) et n'est pas envoyé. Une fiche dont le stock est NÉGATIF (données
historiques — XSTK8 les déclare « restent lisibles » — ou `AchatsParametres.stock_negatif_autorise`) reçoit
« Saisissez un nombre entier. » sous un champ grisé : `validate()` renvoie faux, AUCUN enregistrement possible.
Le détecteur évalue la VRAIE fonction JS (node) sur les champs qu'une édition construit pour quantite_stock = -3,
puis lit ProduitForm (validate sans exemption d'édition + champ désactivé en édition)."""
SONDE = {"constat": "C-AERR-VER1-140", "sha": "47f925be1",
         "attendu": "erreursEntiersProduit({quantite_stock: '-3', ...}) non vide ET validate() l'applique en édition "
                    "ET l'input pf-qte est disabled={isEdit}"}
import json, pathlib, re, shutil, subprocess
RACINE = pathlib.Path(__file__).resolve().parents[4]
SRC = RACINE / "frontend/src"


def lire(rel):
    p = SRC / rel
    return p.read_text(encoding="utf-8") if p.is_file() else None


def evaluer_js(source_module):
    """Exécute le module réel (sans import) sous node et renvoie erreursEntiersProduit pour une édition à stock -3."""
    node = shutil.which("node")
    if not node:
        return None
    corps = re.sub(r"^export\s+", "", source_module, flags=re.M)
    champs = {"quantite_stock": "-3", "seuil_alerte": "0", "garantie_mois": "", "garantie_production_mois": "",
              "tension_v": ""}  # = ProduitForm::initialFields pour produit.quantite_stock = -3 (String(-3))
    code = corps + "\nprocess.stdout.write(JSON.stringify(erreursEntiersProduit(" + json.dumps(champs) + ")))\n"
    r = subprocess.run([node, "--input-type=module", "-"], input=code, capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    if r.returncode != 0:
        return {"erreur_node": r.stderr.strip()[:300]}
    return json.loads(r.stdout or "{}")


def sonde(ctx=None):
    v = lire("pages/stock/validationEntiers.js")
    f = lire("pages/stock/ProduitForm.jsx")
    introuvable = [x for x, t in (("pages/stock/validationEntiers.js", v), ("pages/stock/ProduitForm.jsx", f)) if t is None]
    if introuvable:
        return {"repro": False, "observe": {"introuvable": introuvable}, "methode": "lecture + node"}
    erreurs = evaluer_js(v)
    m = re.search(r"const validate = \(\) => \{(.*?)\n  \}\n", f, re.S)
    val = m.group(1) if m else ""
    applique = bool(re.search(r"erreursEntiersProduit\(\s*fields\s*\)", val))
    exempte_edition = bool(re.search(r"isEdit[^\n]*erreursEntiersProduit|erreursEntiersProduit[^\n]*isEdit", val))
    champ = re.search(r'<Input id="pf-qte"(.*?)/>', f, re.S)
    desactive_en_edition = bool(champ and re.search(r"disabled=\{isEdit\}", champ.group(1)))
    bloque = isinstance(erreurs, dict) and "quantite_stock" in erreurs
    repro = bloque and applique and not exempte_edition and desactive_en_edition
    return {"repro": repro, "observe": {"introuvable": [], "erreurs_js_stock_moins_3": erreurs,
                                         "validate_applique_erreursEntiersProduit": applique,
                                         "exemption_en_edition": exempte_edition,
                                         "champ_pf_qte_desactive_en_edition": desactive_en_edition},
            "methode": "lecture + exécution node de validationEntiers.js"}


if __name__ == "__main__":
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))

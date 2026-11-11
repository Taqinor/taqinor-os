# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans réseau)
"""C-AMSG-010 — (1) le jeu de démonstration `authentication/management/commands/seed_demo.py` sème des adresses e-mail
de domaines NON réservés (hors RFC 2606/6761 : `.invalid`, `.test`, `.local`, `.localhost`, `.example`, `example.com|net|org`) :
la sonde lit les littéraux du fichier (ast) et les COMPTE sans en recopier aucun ; (2) aucune garde de destinataires hors
production : aucun backend e-mail « enveloppe » (classe hors tests définissant `send_messages`) n'existe dans
`backend/django_core`, et aucun réglage `EMAIL_BACKEND` de `erp_agentique/settings/` n'en désigne un. Latent tant que la
production est en console ; S1 le jour où l'e-mail s'allume (relances, lot « Envoyer par email »)."""
SONDE = {"constat": "C-AMSG-010", "sha": "3acfee471",
         "attendu": "adresses du seed à domaine non réservé > 0 ; aucun backend enveloppe défini ni branché"}
import ast, pathlib, re
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
SEED = "authentication/management/commands/seed_demo.py"
ADRESSE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
TLD_RESERVES = {"invalid", "test", "local", "localhost", "example"}
DOMAINES_RESERVES = {"example.com", "example.net", "example.org"}


def reserve(domaine):
    d = domaine.lower().rstrip(".")
    return d.rsplit(".", 1)[-1] in TLD_RESERVES or d in DOMAINES_RESERVES or any(d.endswith("." + r) for r in DOMAINES_RESERVES)


def adresses_du_seed():  # domaines des adresses écrites en littéral (chaînes et morceaux de f-strings)
    arbre = ast.parse((DJ / SEED).read_text(encoding="utf-8"))
    return [m.group(1) for n in ast.walk(arbre) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            for m in ADRESSE.finditer(n.value)]


def _hors_tests(p):
    r = p.relative_to(DJ).as_posix()
    return "/tests" not in "/" + r and not p.name.startswith("test") and "/migrations/" not in "/" + r


def backends_enveloppes():  # classes (hors tests) qui définissent send_messages = backend e-mail Django
    out = []
    for p in DJ.rglob("*.py"):
        if not _hors_tests(p): continue
        texte = p.read_text(encoding="utf-8", errors="replace")
        if "send_messages" not in texte: continue
        for c in (n for n in ast.walk(ast.parse(texte)) if isinstance(n, ast.ClassDef)):
            if any(isinstance(f, ast.FunctionDef) and f.name == "send_messages" for f in c.body):
                out.append(p.relative_to(DJ).with_suffix("").as_posix().replace("/", ".") + "." + c.name)
    return out


def backends_regles():  # chemins de backend écrits dans les réglages (valeurs par défaut comprises)
    vus = set()
    for p in (DJ / "erp_agentique/settings").glob("*.py"):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.fullmatch(r"[\w.]+\.\w*Backend", n.value):
                vus.add(n.value)
    return sorted(vus)


def sonde(ctx=None):
    domaines = adresses_du_seed()
    non_reserves = [d for d in domaines if not reserve(d)]
    enveloppes, regles = backends_enveloppes(), backends_regles()
    branchees = [e for e in enveloppes if e in regles]
    return {"repro": bool(non_reserves) or not branchees, "observe": {
        "methode": "ast (littéraux du seed ; classes send_messages ; réglages EMAIL_BACKEND)",
        "fichier_seed": SEED, "adresses_litterales_du_seed": len(domaines),
        "adresses_a_domaine_non_reserve": len(non_reserves), "domaines_non_reserves_distincts": len(set(d.lower() for d in non_reserves)),
        "adresses_a_domaine_reserve": len(domaines) - len(non_reserves),
        "backends_enveloppes_definis_hors_tests": enveloppes, "backends_ecrits_dans_les_reglages": regles,
        "garde_de_destinataires_branchee": branchees}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))

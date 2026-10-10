"""Regle REGLAGE — un NOUVEAU nom de reglage lu est declare (delegue a check_settings_declares).

Lectures et exclusions = `_Lecteur`/`_est_exclu` de check_settings_declares ; seuls les noms absents
du fichier a la base sont juges : X affecte dans `erp_agentique/settings/*.py` a la tete, et la
variable d'environnement de meme nom qui l'alimente (`os.environ.get('X')`, `X_JSON`) dans `.env.example`.
"""
from __future__ import annotations

import ast
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath

from .socle import DJANGO, Constat, lire_blobs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_settings_declares as csd  # noqa: E402


def _lues(fichier) -> set:
    if fichier is None or fichier.arbre is None or "settings" not in fichier.texte:
        return set()
    lecteur = csd._Lecteur(csd._alias_settings(fichier.arbre))
    lecteur.visit(fichier.arbre)
    return {cle for cle, environ in lecteur.lectures if not environ}


def _variables_env(noeud) -> set:
    vues = set()
    for n in ast.walk(noeud):
        appel = isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant) and (
            getattr(n.func, "attr", None) == "getenv" or getattr(n.func, "id", None) == "getenv"
            or (getattr(n.func, "attr", None) == "get" and getattr(n.func.value, "attr", "") == "environ"))
        indice = isinstance(n, ast.Subscript) and getattr(n.value, "attr", "") == "environ" \
            and isinstance(n.slice, ast.Constant)
        if appel or indice:
            vues.add(str((n.args[0] if appel else n.slice).value))
    return vues


def _declarations(ctx) -> tuple:
    """(cles declarees, {cle: variables d'env}, texte .env.example) a la tete — memo."""
    if "reglages" not in ctx.memo:
        dossier = csd.SETTINGS_DIR.as_posix() + "/"
        noms = [n for n in ctx.arbre_tete() if n.startswith(dossier) and "/" not in n[len(dossier):]
                and n.endswith(".py")]
        textes = lire_blobs(ctx.racine, [f"{ctx.tete}:{n}" for n in noms])
        env = {}
        with tempfile.TemporaryDirectory() as tmp:
            for spec, texte in textes.items():
                cible = Path(tmp) / spec.split(":", 1)[1]
                cible.parent.mkdir(parents=True, exist_ok=True)
                cible.write_text(texte or "", encoding="utf-8")
                for n in ast.walk(ast.parse(texte or "")):
                    for t in (n.targets if isinstance(n, ast.Assign) else []):
                        if isinstance(t, ast.Name):
                            env.setdefault(t.id, set()).update(_variables_env(n.value))
            declarees = csd.cles_declarees(Path(tmp)) | csd.defauts_django()
        ctx.memo["reglages"] = (declarees, env, ctx.texte("tete", ".env.example", lire=True) or "")
    return ctx.memo["reglages"]


def _probleme(ctx, cle: str) -> str | None:
    declarees, env, exemple = _declarations(ctx)
    if cle not in declarees:
        return "n'est déclaré dans aucun erp_agentique/settings/*.py"
    # Variable d'exploitation = du nom du reglage (`X`, `X_JSON`) ; une sonde (`PYTEST_CURRENT_TEST`) n'en est pas une.
    propres = (v for v in env.get(cle, ()) if v == cle or v.startswith(cle + "_"))
    manquantes = sorted(v for v in propres if not re.search(rf"^\s*#?\s*{re.escape(v)}\s*=", exemple, re.M))
    return f"lu depuis l'environnement ({', '.join(manquantes)}) mais absent de .env.example" if manquantes else None


def verifier(ctx) -> list:
    constats = []
    for c, base, tete in ctx.paires_py():
        if not c.apres.startswith(DJANGO) or csd._est_exclu(PurePosixPath(c.apres[len(DJANGO):])):
            continue
        neuves = _lues(tete) - _lues(base)
        for cle in sorted(neuves):
            probleme = _probleme(ctx, cle)
            if probleme:
                constats.append(Constat("REGLAGE", c.apres, cle, f"réglage {cle} lu par ce fichier {probleme}"))
    return constats

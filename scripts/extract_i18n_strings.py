#!/usr/bin/env python3
"""NTI18N1 — Rapport de couverture i18n de l'UI (Groupe NTI18N).

Mesure combien de COMPOSANTS DE PAGE réels (le registre effectif des écrans —
`frontend/src/features/*/module.config.jsx` `routes[].component` + les
quelques routes « noyau » déclarées directement dans `frontend/src/router/
index.jsx`) consomment le cadre i18n léger (`useI18n()`/`useT()`, N93) plutôt
que du texte français en dur, et repère les chaînes en dur restantes pour
prioriser le rollout (NTI18N32 automatisera la migration fichier par fichier ;
ce script mesure et priorise, il ne modifie AUCUN fichier).

Dénominateur = le VRAI registre de pages, pas un `find *.jsx` brut :
- un module « coquille » dépose ses écrans (composants `lazy(() => import(...))`)
  dans son `module.config.jsx`, référencés par `routes: [{ path, component }]`
  (voir `router/moduleRoutes.jsx`) ;
- les 6 verticaux PARQUÉS pour l'édition solaire (agriculture, education,
  hospitality, immobilier, mrp, sante — même liste littérale que le glob négatif
  de `router/moduleRoutes.jsx`) sont EXCLUS : ce sont les « modules gated » de
  l'énoncé NTI18N1, ils ne sont jamais servis dans le build vendu ;
- quelques écrans authentifiés du cœur (Dashboard, HomeMenu…) sont déclarés
  directement dans `router/index.jsx` plutôt que dans un `module.config.jsx` —
  comptés à part sous le domaine synthétique ``core``.

« Migré » (heuristique simple, zéro faux-positif d'import non utilisé — l'ESLint
`no-unused-vars` du repo l'interdirait déjà) : le fichier appelle `useI18n()`
ou `useT()`. « Chaîne en dur » (heuristique) : nœud de texte JSX ou attribut
usuel (label/title/placeholder/aria-label/alt/…) contenant un indice français
(accent, ou mot-outil FR fréquent) — approximatif par construction, pensé pour
PRIORISER, pas pour un compte exact caractère-près.

Usage :
    python scripts/extract_i18n_strings.py                # résumé sur stdout
    python scripts/extract_i18n_strings.py --write         # + écrit le JSON
    python scripts/extract_i18n_strings.py --write --json PATH
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
FEATURES_DIR = FRONTEND_SRC / "features"
ROUTER_INDEX = FRONTEND_SRC / "router" / "index.jsx"
DEFAULT_REPORT_PATH = FRONTEND_SRC / "i18n" / "coverage-report.json"

# Verticaux parqués pour l'édition solaire (SOL6) — LITTÉRALEMENT la même
# liste que le glob négatif de `router/moduleRoutes.jsx` (gardée alignée par
# lecture directe de ce fichier ci-dessous ; ce tuple est un repli si jamais le
# fichier venait à changer de forme).
FALLBACK_GATED_MODULES = (
    "agriculture", "education", "hospitality", "immobilier", "mrp", "sante",
)

# Quelques écrans authentifiés du cœur, déclarés directement dans
# `router/index.jsx` (pas de module.config.jsx) — comptés sous le domaine
# synthétique ``core``. Routes PUBLIQUES/portails/kiosque exclues à dessein
# (pas des « composants de page » de l'UI interne visée par NTI18N1).
CORE_ROUTE_IMPORTS = (
    "../pages/Dashboard",
    "../pages/home/HomeMenu",
    "../pages/onboarding/DemarrageWizard",
    "../pages/messaging/ChatPage",
    "../pages/aide/LexiquePage",
    "../pages/ia/AgentChat",
    "../pages/ia/AgentActions",
    "../pages/ia/OcrUpload",
    "../pages/ged/DocumentsPage",
)

LAZY_IMPORT_RE = re.compile(
    r"lazy\(\s*\(\)\s*=>\s*import\(\s*['\"]([^'\"]+)['\"]\s*\)"
)
I18N_HOOK_RE = re.compile(r"\buse(?:I18n|T)\s*\(")

TEXT_NODE_RE = re.compile(r">([^<>{}\n]{2,120})<")
ATTR_RE = re.compile(
    r'\b(?:label|title|placeholder|aria-label|alt|helperText|description|'
    r'subtitle|emptyMessage|message)\s*=\s*"([^"]{2,160})"'
)

# Mots-outils FR fréquents (heuristique volontairement simple — pas un
# lexique exhaustif, juste de quoi distinguer un texte FR d'un libellé
# technique/anglais avec un bon niveau de confiance).
FRENCH_HINT_WORDS = {
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "pour",
    "dans", "sur", "avec", "sans", "par", "ce", "cette", "ces", "votre",
    "vos", "nous", "vous", "est", "sont", "être", "avoir", "nouveau",
    "nouvelle", "ajouter", "modifier", "supprimer", "enregistrer", "annuler",
    "fermer", "rechercher", "chargement", "aucun", "aucune", "toutes",
    "tous", "société", "client", "fournisseur", "devis", "facture", "voir",
    "aujourd'hui", "aujourd", "retour", "suivant", "précédent", "en", "au",
    "aux", "chaque", "tout", "toute", "à", "déjà", "encore", "plus",
}
ACCENT_RE = re.compile(r"[àâäéèêëïîôöùûüçœÀÂÄÉÈÊËÏÎÔÖÙÛÜÇŒ]")
WORD_RE = re.compile(r"[a-zà-ÿ']+", re.IGNORECASE)


def has_french_hint(text: str) -> bool:
    if ACCENT_RE.search(text):
        return True
    words = {w.lower() for w in WORD_RE.findall(text)}
    return bool(words & FRENCH_HINT_WORDS)


def count_hardcoded_strings(src: str) -> int:
    # On retire d'abord toute expression `{...}` pour ne jamais compter le
    # contenu d'un `{t('...')}` (ou de tout autre expr JS) comme texte en dur.
    stripped = re.sub(r"\{[^{}]*\}", "{}", src)
    count = 0
    for m in TEXT_NODE_RE.finditer(stripped):
        txt = m.group(1).strip()
        if txt and has_french_hint(txt):
            count += 1
    for m in ATTR_RE.finditer(stripped):
        txt = m.group(1).strip()
        if txt and has_french_hint(txt):
            count += 1
    return count


def is_migrated(src: str) -> bool:
    return bool(I18N_HOOK_RE.search(src))


def resolve_import(base_dir: Path, spec: str) -> Path | None:
    """Résout un import relatif JS (sans extension) vers un fichier réel."""
    candidate = (base_dir / spec).resolve()
    for suffix in ("", ".jsx", ".js", ".tsx", ".ts"):
        p = Path(str(candidate) + suffix) if suffix else candidate
        if p.is_file():
            return p
    if candidate.is_dir():
        for name in ("index.jsx", "index.js"):
            p = candidate / name
            if p.is_file():
                return p
    return None


def gated_modules() -> set[str]:
    """Lit la liste des verticaux parqués depuis `router/moduleRoutes.jsx`
    (glob négatif SOL6) pour rester aligné sans dupliquer la vérité — repli sur
    la liste littérale ci-dessus si le fichier est absent/reformaté."""
    routes_file = FRONTEND_SRC / "router" / "moduleRoutes.jsx"
    try:
        src = routes_file.read_text(encoding="utf-8")
    except OSError:
        return set(FALLBACK_GATED_MODULES)
    found = set(re.findall(r"!\.\./features/([a-z_]+)/module\.config\.jsx", src))
    return found or set(FALLBACK_GATED_MODULES)


def collect_module_components(gated: set[str]) -> list[dict]:
    components = []
    if not FEATURES_DIR.is_dir():
        return components
    for config_path in sorted(FEATURES_DIR.glob("*/module.config.jsx")):
        module_key = config_path.parent.name
        if module_key in gated:
            continue
        try:
            src = config_path.read_text(encoding="utf-8")
        except OSError:
            continue
        # `const Name = lazy(() => import('spec'))` — capture nom + spec.
        const_map: dict[str, str] = {}
        for m in re.finditer(
            r"const\s+(\w+)\s*=\s*" + LAZY_IMPORT_RE.pattern, src
        ):
            const_map[m.group(1)] = m.group(2)
        # Composants réellement référencés par une route (ignore les lazy
        # déclarés mais jamais routés, s'il y en a).
        used_names = set(re.findall(r"component:\s*(\w+)", src))
        for name in used_names & const_map.keys():
            resolved = resolve_import(config_path.parent, const_map[name])
            if resolved is None:
                continue
            components.append({"path": resolved, "domain": module_key})
    return components


def collect_core_components() -> list[dict]:
    components = []
    try:
        src = ROUTER_INDEX.read_text(encoding="utf-8")
    except OSError:
        return components
    const_map: dict[str, str] = {}
    for m in re.finditer(r"const\s+(\w+)\s*=\s*" + LAZY_IMPORT_RE.pattern, src):
        const_map[m.group(1)] = m.group(2)
    for name, spec in const_map.items():
        if spec not in CORE_ROUTE_IMPORTS:
            continue
        resolved = resolve_import(ROUTER_INDEX.parent, spec)
        if resolved is None:
            continue
        components.append({"path": resolved, "domain": "core"})
    return components


def build_report() -> dict:
    gated = gated_modules()
    entries = collect_module_components(gated) + collect_core_components()
    # Dédoublonne (un même écran peut en théorie être référencé deux fois).
    seen: dict[Path, dict] = {}
    for e in entries:
        seen.setdefault(e["path"], e)
    rows = []
    for path, meta in sorted(seen.items()):
        try:
            src = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        rows.append({
            "path": rel,
            "domain": meta["domain"],
            "migrated": is_migrated(src),
            "hardcoded_strings": count_hardcoded_strings(src),
        })

    total = len(rows)
    migrated = sum(1 for r in rows if r["migrated"])
    domains: dict[str, dict] = {}
    for r in rows:
        d = domains.setdefault(
            r["domain"], {"total": 0, "migrated": 0, "hardcoded_strings": 0})
        d["total"] += 1
        d["migrated"] += int(r["migrated"])
        d["hardcoded_strings"] += r["hardcoded_strings"]
    for d in domains.values():
        d["pct"] = round(100.0 * d["migrated"] / d["total"], 1) if d["total"] else 0.0

    # Priorisation : composants NON migrés avec le plus de chaînes en dur
    # d'abord (les meilleures candidates pour NTI18N32 / le rollout manuel).
    priority = sorted(
        (r for r in rows if not r["migrated"]),
        key=lambda r: r["hardcoded_strings"], reverse=True,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gated_modules_excluded": sorted(gated),
        "total_components": total,
        "migrated_components": migrated,
        "coverage_pct": round(100.0 * migrated / total, 1) if total else 0.0,
        "domains": dict(sorted(domains.items())),
        "priority_targets": [
            {"path": r["path"], "domain": r["domain"],
             "hardcoded_strings": r["hardcoded_strings"]}
            for r in priority[:50]
        ],
        "components": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true",
        help="Écrit le rapport JSON (sinon dry-run stdout).")
    parser.add_argument(
        "--json", default=str(DEFAULT_REPORT_PATH),
        help="Chemin du rapport JSON (avec --write).")
    args = parser.parse_args(argv)

    report = build_report()

    print(f"Composants de page (hors modules gated) : {report['total_components']}")
    print(f"Migrés (useI18n/useT)                    : {report['migrated_components']}")
    print(f"Couverture                               : {report['coverage_pct']}%")
    print("Par domaine :")
    for key, d in report["domains"].items():
        print(f"  - {key:16s} {d['migrated']:3d}/{d['total']:3d} "
              f"({d['pct']:5.1f}%) — {d['hardcoded_strings']} chaîne(s) en dur restante(s)")

    if args.write:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nRapport écrit : {out_path.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

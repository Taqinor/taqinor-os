"""YAPIC6 — CI guard: the OpenAPI schema stays generatable, VALID, and free of
any NEW drf-spectacular warning; plus a versioned, diffable contract snapshot.

What it does (one pass, DB-free):

  1. runs ``manage.py spectacular --file <tmp> --validate`` (drf-spectacular's
     own OpenAPI-3 document validation — an invalid document fails hard);
  2. parses the generator's warnings/errors into STABLE signatures and fails on
     any signature absent from ``scripts/openapi_schema_allow.txt``. That is a
     scoped ``--fail-on-warn``: the repo carries ~1 000 pre-existing findings
     (386 views without a resolvable serializer, un-hinted ``SerializerMethod``
     fields, enum/operationId collisions) that no single task can clear, but a
     NEW unresolved serializer or a NEW ``operationId`` collision turns the job
     red — which is exactly the regression YAPIC6 is about;
  3. FAILS when the freshly generated operation inventory differs from the
     committed snapshot ``docs/openapi-schema.yml`` (PACT6).

PACT6 — POURQUOI LA DERIVE DE L'INSTANTANE EST BLOQUANTE (03/08/2026)
--------------------------------------------------------------------
Cette comparaison etait « advisory, never fails », au motif qu'exiger une
regeneration de ~3 min a chaque PR bloquerait la file de construction. Le prix
mesure de ce confort : l'instantane a ete regenere pour la derniere fois le
31/07, AVANT la fusion du module Appels d'offres du 02/08. **Un module entier
est entre en production sans que le fichier de contrat bouge d'une ligne** —
29 ressources presentes dans le code en etaient absentes, dont 21 dans
``apps/ao``. Tant que l'instantane est en retard, AUCUNE garde front<->back ne
peut s'appuyer dessus : c'est un document qui a l'air d'etre le contrat sans
l'etre.

La regeneration est donc desormais une obligation de la PR qui ajoute la route,
et le message d'echec porte la commande exacte :

    python scripts/check_openapi_schema.py --write

Ne repassez pas ce controle en « advisory ». Si la regeneration est trop lente,
accelerez-la ; ne rendez pas le contrat facultatif.

WOW-CI3 — ACCELERATION (18/08/2026), la reponse a ce « accelerez-la »
---------------------------------------------------------------------
Le job `backend-openapi` durait 5 min 53 s et fixait SEUL le plancher du gate.
Mesure par phase dans l'image de prod (~2,2x plus lente qu'un runner CI) :

    django.setup()            53,7 s
    get_schema()             284,4 s   <- 16 918 operations... dont la moitie
                                          est le MIROIR `api/v1/` de l'autre
    rendu YAML (22,8 Mo)      98,9 s   <- vs 4,7 s en JSON (40,4 Mo)
    --validate               102,2 s
    yaml.safe_load           230,8 s   <- vs 4,1 s en json.loads (!)

Trois causes, trois corrections, AUCUNE perte de garantie :

 1. `erp_agentique/urls.py` monte la meme liste `_APP_URLS` sous `api/django/`
    ET sous `api/v1/` : drf-spectacular re-introspecte donc chaque vue, chaque
    serializer et chaque type-hint DEUX fois. Le controle passe desormais
    `--generator-class erp_agentique.openapi_check.SchemaGeneratorAliasV1`,
    qui introspecte l'arbre une fois puis RECONSTITUE le miroir `api/v1/`
    (copie profonde + `operationId` `django_X` -> `v1_X`) AVANT les
    postprocessing hooks. Le document produit est identique ; les garde-fous
    structurels sont dans ce module (voir son en-tete) et font ECHOUER la
    generation — jamais passer en silence — si le miroir cesse d'etre derivable.
 2. le fichier intermediaire passe de YAML a JSON (`--format openapi-json`) :
    meme document, serialisation 21x plus rapide a ecrire...
 3. ...et 56x plus rapide a relire (`json.loads` au lieu de `yaml.safe_load`
    sur 22,8 Mo). L'inventaire ne lit que `paths`/`components`/`info` : il en
    ressort au bit pres identique.

Tout ce qui GELE un fichier de reference — `--write` (l'instantane versionne) et
`--write-baseline` (le cliquet d'avertissements) — utilise le generateur de
REFERENCE : l'instantane reste la verite generee par les deux montages reels, et
le raccourci du controle est compare A ELLE. Un raccourci qui derivait ne
pourrait donc produire qu'un FAUX ROUGE, jamais un faux vert. `--reference`
force ce meme generateur pour le controle lui-meme.

Why the snapshot is an INVENTORY and not the raw document: the full schema is
9 407 paths / 16 918 operations (22,8 MB en YAML, 40,4 MB en JSON) — git-hostile
and un-renderable in a PR. Sur ces 16 918 operations, 8 467 sont sous
``/api/django/`` et 8 423 en sont le MIROIR EXACT sous ``/api/v1/`` (les 44
restantes sont les routes publiques tokenisees et les 3 endpoints JWT, montees
hors de ``_APP_URLS`` donc sans jumeau v1) : c'est ce doublon integral que
WOW-CI3 cesse de payer deux fois. The inventory
(one sorted ``method path -> operationId`` line per operation + the component
names) is the part that actually surfaces a breaking change, and it diffs
line-by-line in review.

The signature deliberately carries NO file path and NO line number: a checker
keyed on ``file:line`` goes red on every unrelated line shift.

Usage:
    python scripts/check_openapi_schema.py                 # CI gate (rapide)
    python scripts/check_openapi_schema.py --reference     # CI gate, sans le raccourci
    python scripts/check_openapi_schema.py --write         # refresh docs/openapi-schema.yml
    python scripts/check_openapi_schema.py --write-baseline
    python scripts/check_openapi_schema.py --from-log FILE # parse an existing log (offline)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DJANGO_CORE = ROOT / "backend" / "django_core"
BASELINE_PATH = ROOT / "scripts" / "openapi_schema_allow.txt"
SNAPSHOT_PATH = ROOT / "docs" / "openapi-schema.yml"

# `<file>: Warning [Ident]: msg` / `<file>:12: Error [Ident]: msg`
_TAGGED = re.compile(r"^.*?: (Warning|Error) \[([^\]]+)\]: (.*)$")
# `Warning: msg` (generator-global: enum / operationId collisions)
_GLOBAL = re.compile(r"^(Warning|Error): (.*)$")

# drf-spectacular disambiguates a colliding enum with a content hash suffix
# (`ModePaiement8f6Enum`). Normalised away so an unrelated choice-set edit
# elsewhere cannot invalidate an existing baseline entry.
_ENUM_HASH = re.compile(r"[0-9a-f]{3,}Enum\b")
# "Encountered 2 components with identical names" -> digits are noise.
_DIGITS = re.compile(r"\d+")

# Signatures keep only the informative head of the message: every
# drf-spectacular finding ends with the same boilerplate advice tail.
_MSG_KEEP = 120


def normalise_message(msg: str) -> str:
    msg = _ENUM_HASH.sub("<hash>Enum", msg)
    msg = _DIGITS.sub("#", msg)
    # rstrip AFTER truncating: the baseline file is read back with .strip(), so a
    # signature ending on a space would never match itself.
    return " ".join(msg.split())[:_MSG_KEEP].rstrip()


def parse_log(text: str) -> set[str]:
    """Extract ``SEVERITY|IDENTITY|normalised-message`` signatures from a log."""
    signatures: set[str] = set()
    for raw in text.splitlines():
        raw = raw.rstrip()
        m = _TAGGED.match(raw)
        if m:
            severity, identity, msg = m.groups()
        else:
            m = _GLOBAL.match(raw)
            if not m:
                continue
            severity, msg = m.groups()
            identity = "<global>"
        signatures.add(f"{severity}|{identity}|{normalise_message(msg)}")
    return signatures


def load_baseline(path: Path = BASELINE_PATH) -> set[str]:
    if not path.is_file():
        return set()
    entries = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            entries.add(line)
    return entries


def _schema_env() -> dict:
    env = dict(os.environ)
    env.setdefault("DJANGO_SETTINGS_MODULE", "erp_agentique.settings.dev")
    env.setdefault("DJANGO_SECRET_KEY", "openapi-schema-check-not-a-real-secret")
    env.setdefault("DJANGO_DEBUG", "True")
    # No database is contacted while generating the schema (drf-spectacular only
    # introspects viewsets/serializers), but Django still needs the settings to
    # resolve — so placeholders, never a live connection.
    env.setdefault("DB_NAME", "erp_db")
    env.setdefault("DB_USER", "erp_user")
    env.setdefault("DB_PASSWORD", "unused")
    env.setdefault("DB_HOST", "localhost")
    env.setdefault("DB_PORT", "5432")
    return env


# WOW-CI3 — generateur qui n'introspecte qu'une fois l'arbre monte deux fois
# (voir backend/django_core/erp_agentique/openapi_check.py). Le document
# produit est identique a celui du generateur par defaut.
ALIAS_GENERATOR = "erp_agentique.openapi_check.SchemaGeneratorAliasV1"


def spectacular_command(target: Path, *, reference: bool = False) -> list[str]:
    """Commande `manage.py spectacular` du controle (testee en isolation)."""
    cmd = [sys.executable, "manage.py", "spectacular",
           "--file", str(target), "--validate", "--format", "openapi-json"]
    if not reference:
        cmd += ["--generator-class", ALIAS_GENERATOR]
    return cmd


def use_reference_generator(args) -> bool:
    """PACT6/WOW-CI3 — tout ce qui GELE un fichier de reference est produit par
    le generateur de REFERENCE :

    * ``--write`` (l'instantane de contrat) reste la verite generee par les
      DEUX montages reels ; c'est a elle que le raccourci du controle est
      compare, donc un raccourci qui derivait ne pourrait produire qu'un FAUX
      ROUGE, jamais un faux vert ;
    * ``--write-baseline`` doit voir les constats des deux arbres (le miroir
      `api/v#/` a ses propres avertissements globaux de collision
      d'operationId) — sinon le cliquet perdrait silencieusement ces entrees.
    """
    return bool(args.reference or args.write
                or getattr(args, "write_baseline", False))


def generate(target: Path, *, reference: bool = False) -> str:
    """Run the generator (with ``--validate``); return its warning log.

    ``reference=True`` -> generateur par defaut, les deux montages reellement
    introspectes (c'est ce que `--write` utilise pour produire l'instantane).
    Sinon le raccourci WOW-CI3, qui rend le meme document ~2x plus vite.
    """
    cmd = spectacular_command(target, reference=reference)
    proc = subprocess.run(
        cmd, cwd=str(DJANGO_CORE), env=_schema_env(),
        capture_output=True, text=True, errors="replace", timeout=1800,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        print("\nECHEC : la generation/validation du schema OpenAPI a echoue "
              "(document invalide ou generateur en erreur).")
        if not reference:
            print("Si l'echec vient du raccourci WOW-CI3 (garde-fou du miroir "
                  "api/v1/), rejouer avec --reference pour l'isoler.")
        raise SystemExit(1)
    return proc.stderr


def build_inventory(schema_path: Path) -> str:
    """Compact, deterministic contract snapshot (see module docstring).

    Lit le document JSON produit par ``--format openapi-json`` (WOW-CI3) :
    seuls ``paths``/``components``/``info`` sont exploites, donc l'inventaire
    est identique a celui bati depuis l'ancien rendu YAML — pour 4 s au lieu
    de 231 s de ``yaml.safe_load`` sur 22,8 Mo.
    """
    with schema_path.open(encoding="utf-8") as fh:
        doc = json.load(fh)

    paths = doc.get("paths") or {}
    schemas = (doc.get("components") or {}).get("schemas") or {}
    security = sorted((doc.get("components") or {}).get("securitySchemes") or {})

    operations = []
    for path in sorted(paths):
        item = paths[path] or {}
        for method in sorted(item):
            if method == "parameters":
                continue
            op = item[method] or {}
            operations.append(f"- {method} {path} -> {op.get('operationId')}")

    info = doc.get("info") or {}
    header = [
        "# YAPIC6 — instantane de contrat de l'API (GENERE, ne pas editer a la main).",
        "# Regenerer : python scripts/check_openapi_schema.py --write",
        "#",
        "# Inventaire des operations + noms de composants du schema OpenAPI 3",
        "# produit par drf-spectacular (YAPIC5). Le document complet fait ~20 Mo :",
        "# illisible en revue, donc c'est cet inventaire, trie et stable, qui est",
        "# versionne — une ligne ajoutee/supprimee/renommee = un changement de",
        "# contrat visible dans le diff de la PR.",
        f"openapi: {doc.get('openapi')!r}",
        f"title: {info.get('title')!r}",
        f"version: {info.get('version')!r}",
        f"counts: {{paths: {len(paths)}, operations: {len(operations)}, "
        f"components: {len(schemas)}}}",
        "securitySchemes:",
    ]
    header += [f"- {name}" for name in security]
    header.append("operations:")
    body = operations
    tail = ["components:"] + [f"- {name}" for name in sorted(schemas)]
    return "\n".join(header + body + tail) + "\n"


def _operation_lines(text: str) -> set[str]:
    return {ln for ln in text.splitlines() if ln.startswith("- ") and " -> " in ln}


def _component_lines(text: str) -> set[str]:
    """Noms de composants : la queue `components:` de l'instantane."""
    _, _, tail = text.partition("\ncomponents:\n")
    return {ln for ln in tail.splitlines() if ln.startswith("- ")}


REGEN_COMMAND = "python scripts/check_openapi_schema.py --write"


def derive_instantane(previous: str, inventory: str) -> dict | None:
    """PACT6 — decrit la derive entre l'instantane versionne et le code.

    Retourne None si l'instantane est a jour, sinon un dictionnaire nomme :
    les operations et composants ABSENTS de l'instantane (routes livrees sans
    regeneration — le cas du module AO du 02/08) et ceux qui y sont EN TROP
    (routes retirees du code). `identique` distingue une derive de contenu
    d'une simple derive d'en-tete (compteurs, titre, version).
    """
    if previous == inventory:
        return None
    anciennes, nouvelles = _operation_lines(previous), _operation_lines(inventory)
    anciens, nouveaux = _component_lines(previous), _component_lines(inventory)
    return {
        "operations_manquantes": sorted(nouvelles - anciennes),
        "operations_en_trop": sorted(anciennes - nouvelles),
        "composants_manquants": sorted(nouveaux - anciens),
        "composants_en_trop": sorted(anciens - nouveaux),
    }


def rapporter_derive(derive: dict, snapshot_rel: str) -> None:
    """Message d'echec : les routes NOMMEES + la commande de regeneration."""
    manquantes = derive["operations_manquantes"]
    en_trop = derive["operations_en_trop"]
    comp_manquants = derive["composants_manquants"]
    comp_en_trop = derive["composants_en_trop"]
    print(f"\nECHEC : l'instantane de contrat {snapshot_rel} est EN RETARD "
          f"sur le code (PACT6).\n")
    print(f"  +{len(manquantes)} operation(s) presente(s) dans le code et ABSENTE(s) "
          f"de l'instantane")
    print(f"  -{len(en_trop)} operation(s) presente(s) dans l'instantane et "
          f"DISPARUE(s) du code")
    if comp_manquants or comp_en_trop:
        print(f"  composants : +{len(comp_manquants)} / -{len(comp_en_trop)}")
    for titre, lignes in (("ABSENTES de l'instantane", manquantes),
                          ("DISPARUES du code", en_trop),
                          ("composants absents", comp_manquants),
                          ("composants disparus", comp_en_trop)):
        if not lignes:
            continue
        print(f"\n  {titre} :")
        for ligne in lignes[:40]:
            print(f"    {ligne}")
        if len(lignes) > 40:
            print(f"    ... et {len(lignes) - 40} autre(s).")
    if not (manquantes or en_trop or comp_manquants or comp_en_trop):
        print("\n  (aucune operation ni composant ne differe : seul l'en-tete de "
              "l'instantane — compteurs, titre, version — a bouge.)")
    # WOW-CI3 — diagnostic : une derive PUREMENT `api/v1/` ne vient pas d'une
    # route oubliee mais du raccourci qui reconstitue ce miroir.
    lignes_ops = manquantes + en_trop
    if lignes_ops and all(" /api/v1/" in ligne for ligne in lignes_ops):
        print("\n  NB : la derive ne porte QUE sur des chemins /api/v#/. Ce miroir "
              "est reconstitue\n  par le raccourci WOW-CI3 "
              "(erp_agentique/openapi_check.py). Rejouer le controle avec\n"
              "  --reference : si la derive disparait, c'est le raccourci qu'il "
              "faut corriger,\n  pas l'instantane.")
    print(f"\nREGENERER L'INSTANTANE, PUIS LE COMMITTER :\n    {REGEN_COMMAND}\n")
    print("POURQUOI C'EST BLOQUANT : le 02/08/2026 le module Appels d'offres est "
          "entre en production\nsans que l'instantane bouge d'une ligne "
          "(29 ressources absentes, dont 21 dans apps/ao).\nUn contrat en retard "
          "est un contrat qui ment : aucune garde front<->back ne peut s'appuyer\n"
          "dessus. Ne repassez pas ce controle en « advisory » — voir l'en-tete "
          "de ce script.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="refresh docs/openapi-schema.yml from the generated schema")
    parser.add_argument("--write-baseline", action="store_true",
                        help="refresh scripts/openapi_schema_allow.txt")
    parser.add_argument("--from-log", metavar="FILE",
                        help="parse an existing spectacular log instead of regenerating")
    parser.add_argument("--reference", action="store_true",
                        help="generer avec le generateur par defaut (les deux "
                             "montages reellement introspectes) au lieu du "
                             "raccourci WOW-CI3 ; implicite avec --write")
    args = parser.parse_args()

    inventory = None
    if args.from_log:
        log = Path(args.from_log).read_text(encoding="utf-8", errors="replace")
    else:
        reference = use_reference_generator(args)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "openapi-schema-full.json"
            log = generate(target, reference=reference)
            inventory = build_inventory(target)

    found = parse_log(log)
    print(f"drf-spectacular : {len(found)} signature(s) unique(s) d'avertissement/erreur.")

    if args.write_baseline:
        BASELINE_PATH.write_text(
            "# YAPIC6 — base de reference des avertissements drf-spectacular (GENEREE).\n"
            "# Regenerer : python scripts/check_openapi_schema.py --write-baseline\n"
            "# check_openapi_schema.py echoue sur toute signature ABSENTE de cette\n"
            "# liste (nouveau serializer non resolu, nouvelle collision d'operationId,\n"
            "# nouveau type non resolu...). Une entree qui disparait est un progres :\n"
            "# elle peut etre retiree d'ici lors de la prochaine regeneration.\n"
            + "\n".join(sorted(found)) + "\n",
            encoding="utf-8", newline="\n",  # LF partout (Windows <-> CI Linux)
        )
        print(f"Base de reference reecrite : {BASELINE_PATH.relative_to(ROOT)}")

    derive = None
    if inventory is not None:
        snapshot_rel = SNAPSHOT_PATH.relative_to(ROOT).as_posix()
        previous = SNAPSHOT_PATH.read_text(encoding="utf-8") if SNAPSHOT_PATH.is_file() else ""
        if args.write:
            SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
            SNAPSHOT_PATH.write_text(inventory, encoding="utf-8", newline="\n")
            print(f"Instantane ecrit : {snapshot_rel}")
        elif not previous:
            print(f"\nECHEC : l'instantane de contrat {snapshot_rel} est absent "
                  f"(PACT6).\n    {REGEN_COMMAND}")
            derive = {"operations_manquantes": [], "operations_en_trop": [],
                      "composants_manquants": [], "composants_en_trop": []}
        else:
            # PACT6 — BLOQUANT (etait « advisory, never fails » : voir l'en-tete).
            derive = derive_instantane(previous, inventory)
            if derive is not None:
                rapporter_derive(derive, snapshot_rel)
            else:
                print(f"OK : instantane {snapshot_rel} a jour du code "
                      f"({len(_operation_lines(inventory))} operations).")

    baseline = load_baseline()
    new_findings = sorted(found - baseline)
    if new_findings:
        print(f"\nECHEC : {len(new_findings)} avertissement(s) de schema NOUVEAU(x) "
              f"(absent(s) de {BASELINE_PATH.relative_to(ROOT)}) :\n")
        for sig in new_findings[:40]:
            print(f"  {sig}")
        if len(new_findings) > 40:
            print(f"  ... et {len(new_findings) - 40} autre(s).")
        print("\nCorriger la vue/le serializer signale (serializer_class, "
              "@extend_schema, @extend_schema_field, operationId unique).\n"
              "Si le constat est deliberement accepte, l'ajouter a la base de\n"
              "reference : python scripts/check_openapi_schema.py --write-baseline")
        return 1

    stale = len(baseline - found)
    print(f"OK : aucun avertissement de schema nouveau "
          f"({len(baseline)} en base de reference, dont {stale} desormais corrige(s)).")
    return 1 if derive is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())

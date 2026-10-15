"""ENF11 — préparation du schéma fuzzé et verdict du job `api-fuzz`.

Trois sous-commandes, un seul module (le harnais du fuzz, comme ses voisins
de ``scripts/fuzz/``) :

``proprietaires``
    Fichiers modifiés d'une PR -> paquets Django « propriétaires » touchés
    (``apps.ventes``, ``core``, ``authentication``…). Stdlib pur : le job
    `api-fuzz-pr` (ci.yml) l'appelle AVANT toute mise en place lourde et saute
    le fuzz si la liste est vide (PR sans code d'API).

``schema``
    Lit le schéma OpenAPI généré par drf-spectacular et écrit le schéma
    RÉELLEMENT fuzzé :
      * sans le miroir ``/api/v1/`` (mêmes vues que ``/api/django/``, YAPIC7 —
        déjà retiré par ``schemathesis.toml``, retiré ici aussi pour ne pas
        payer son chargement) ;
      * avec ``--proprietaires`` : réduit aux opérations dont la VUE, ou un
        urlconf traversé, vit dans un des paquets donnés (résolution Django
        réelle du chemin ; jamais un préfixe d'URL deviné : `authentication`
        monte ses routes à la racine de ``/api/django/``, `facturation` monte
        des vues de `ventes`) ;
      * avec des LIENS OpenAPI déclarés (phase stateful) : chaque
        ``POST /x/`` qui répond 201 avec un ``id`` est relié à toutes les
        opérations de ``/x/{pk}/`` et de ses actions ``/x/{pk}/…`` —
        ``{pk}: $response.body#/id``. Le run du 11/10 (38129616897) n'avait
        que des liens INFÉRÉS : « API Links: 3 covered / 36872 selected »,
        48 scénarios en 632 s — la phase stateful ne testait presque rien.
    Avec ``--proprietaires``, ce sous-mode importe Django (à lancer depuis
    ``backend/django_core``).

``verdict``
    Lit le rapport JSON de Schemathesis et rend le verdict du job PR :
    ÉCHEC sur tout constat (check, opération) absent de la dette gelée
    ``scripts/fuzz/api_fuzz_dette.txt``, sur toute ERREUR du moteur (opération
    non testée — jamais gelable) et sur un run inexploitable (incomplet,
    authentification perdue). Le NOCTURNE, lui, n'a pas de dette :
    ``schemathesis run`` y échoue sur le moindre constat (release-verify.yml) ;
    il rejoue ``verdict --resume`` pour ALERTER dès la première nuit sur une
    RÉGRESSION (constat hors dette), noyée sinon dans le rouge de la dette.

``soldes``
    Résumé du nocturne : lignes de la dette qu'un run COMPLET ne revoit plus
    (à retirer du fichier). Un rapport, pas un contrôle : sort toujours 0.

Usage :
    git diff --name-only BASE HEAD | python scripts/fuzz/api_fuzz_scope.py proprietaires
    python ../../scripts/fuzz/api_fuzz_scope.py schema --in brut.json --out fuzz.json \\
        [--proprietaires apps.ventes core]
    python scripts/fuzz/api_fuzz_scope.py verdict --rapport schemathesis-report/json-X.json \\
        [--resume alerte.md]
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DETTE_PATH = ROOT / "scripts" / "fuzz" / "api_fuzz_dette.txt"

_BACKEND = "backend/django_core/"
_METHODES = ("get", "put", "post", "delete", "patch", "head", "options", "trace")

# Fichiers du HARNAIS et de la plateforme qui sert TOUTES les vues : leur
# modification relance le fuzz des seules surfaces plateforme `core` +
# `authentication`. Le reste de l'API est couvert par le nocturne : le
# sous-ensemble PR tient dans ~5 min, pas dans les 30 du run complet.
_PLATEFORME = (
    "backend/django_core/erp_agentique/",
    "backend/django_core/requirements",
    "scripts/fuzz/",
    "schemathesis.toml",
)
PROPRIETAIRES_PLATEFORME = ("authentication", "core")


def _hors_api(chemin: str) -> bool:
    """Fichier d'un paquet backend qui ne change pas le comportement HTTP."""
    nom = chemin.rsplit("/", 1)[-1]
    return (
        "/tests/" in chemin
        or nom.startswith("test_")
        or nom.startswith("tests_")
        or nom == "tests.py"
        or nom.endswith(".md")
        # Échantillons de contrat (PACT10) : des JSON lus par les tests et les
        # gardes, jamais par une vue — un contrat posé AVANT sa vue ne change
        # aucun comportement HTTP.
        or "/contract_samples/" in chemin
    )


def proprietaires_modifies(fichiers) -> list[str]:
    """Paquets Django dont le code d'API a changé, triés."""
    trouves: set[str] = set()
    for brut in fichiers:
        chemin = brut.strip().replace("\\", "/")
        if not chemin:
            continue
        # La dette gelée (scripts/fuzz/api_fuzz_dette.txt) n'est pas du harnais :
        # la geler ne doit JAMAIS élargir le périmètre à la plateforme (VNT M0,
        # 12/10/2026 : chaque gel relançait core + authentication → nouveaux
        # constats à chaque tour, treadmill).
        if chemin.endswith("api_fuzz_dette.txt"):
            continue
        if any(chemin.startswith(p) for p in _PLATEFORME):
            trouves.update(PROPRIETAIRES_PLATEFORME)
            continue
        if not chemin.startswith(_BACKEND) or _hors_api(chemin):
            continue
        parties = chemin[len(_BACKEND):].split("/")
        if parties[0] == "apps" and len(parties) > 2:
            trouves.add(f"apps.{parties[1]}")
        elif parties[0] in PROPRIETAIRES_PLATEFORME and len(parties) > 1:
            trouves.add(parties[0])
    return sorted(trouves)


def proprietaire_du_module(module: str | None) -> str | None:
    """``apps.stock.views.produit`` -> ``apps.stock`` ; ``core.views`` -> ``core``."""
    if not module:
        return None
    parties = module.split(".")
    if parties[0] == "apps" and len(parties) > 1:
        return ".".join(parties[:2])
    if parties[0] in PROPRIETAIRES_PLATEFORME + ("erp_agentique",):
        return parties[0]
    return None


_PARAM = re.compile(r"\{[^}]+\}")
# Valeurs d'essai pour résoudre un gabarit `{x}` contre l'urlconf : entier,
# UUID, puis jeton libre — le premier que le convertisseur Django accepte.
_VALEURS_ESSAI = ("1", "00000000-0000-0000-0000-000000000000", "a")


def gabarit_vers_chemins(gabarit: str) -> list[str]:
    return [_PARAM.sub(v, gabarit) for v in _VALEURS_ESSAI]


def modules_de_vue(gabarit: str, resoudre) -> tuple:
    """Modules qui servent ``gabarit`` : celui de la VUE et ceux des urlconf
    traversés. ``resoudre(chemin)`` rend un module ou une suite de modules, ou
    lève (``Resolver404``…) — la valeur d'essai suivante est alors tentée.

    Les deux comptent : ``apps.facturation.urls`` monte des vues définies dans
    ``apps.ventes`` (re-export) — une PR qui touche facturation doit fuzzer ces
    routes même si le module de la vue est ventes."""
    for chemin in gabarit_vers_chemins(gabarit):
        try:
            modules = resoudre(chemin)
        except Exception:  # Resolver404 & co : valeur d'essai refusée
            continue
        if isinstance(modules, str):
            modules = (modules,)
        if modules:
            return tuple(modules)
    return ()


def _urlconfs_traverses(resolveur, chemin: str) -> list:
    """Noms des urlconf (``include('apps.x.urls')``) de la chaîne qui résout
    ``chemin`` sous ``resolveur``."""
    from django.urls import URLResolver

    for motif in resolveur.url_patterns:
        if not isinstance(motif, URLResolver):
            continue
        correspondance = motif.pattern.match(chemin)
        if not correspondance:
            continue
        try:
            motif.resolve(chemin)
        except Exception:  # cette branche ne mène pas à la vue
            continue
        # `include('apps.x.urls')` a déjà importé le module : on lit son nom.
        conf = motif.urlconf_name
        nom = conf if isinstance(conf, str) else getattr(conf, "__name__", None)
        return ([nom] if nom else []) + _urlconfs_traverses(motif, correspondance[0])
    return []


def resolveur_django():
    """Résolveur réel : chemin -> (module de la vue, urlconf traversés)."""
    sys.path.insert(0, os.getcwd())
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "erp_agentique.settings.dev")
    import django

    django.setup()
    from django.urls import get_resolver, resolve

    racine = get_resolver()

    def resoudre(chemin):
        vue = resolve(chemin).func
        classe = getattr(vue, "cls", None) or getattr(vue, "view_class", None)
        return ((classe or vue).__module__, *_urlconfs_traverses(racine, chemin.lstrip("/")))

    return resoudre


def filtrer_schema(doc: dict, garder) -> dict:
    """Copie du document sans le miroir ``/api/v1/`` et sans les chemins que
    ``garder(gabarit)`` refuse. ``components`` est conservé tel quel (les
    ``$ref`` des opérations gardées doivent rester résolubles)."""
    sortie = dict(doc)
    sortie["paths"] = {
        gabarit: item
        for gabarit, item in (doc.get("paths") or {}).items()
        if not gabarit.startswith("/api/v1/") and garder(gabarit)
    }
    return sortie


def _resoudre_ref(doc: dict, schema, profondeur: int = 0) -> dict:
    if not isinstance(schema, dict) or profondeur > 8:
        return {}
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        schemas = (doc.get("components") or {}).get("schemas") or {}
        return _resoudre_ref(doc, schemas.get(ref.rsplit("/", 1)[-1]), profondeur + 1)
    return schema


def _reponse_porte_id(doc: dict, reponse: dict) -> bool:
    for media in ((reponse or {}).get("content") or {}).values():
        schema = _resoudre_ref(doc, (media or {}).get("schema"))
        if "id" in (schema.get("properties") or {}):
            return True
    return False


_PREMIER_PARAM = re.compile(r"^\{([^}/]+)\}/")


def declarer_liens(doc: dict) -> int:
    """Ajoute les liens CRUD (POST collection 201 -> opérations de l'élément).

    Pour ``POST /x/`` (201 dont le corps a un ``id``) et chaque chemin
    ``/x/{pk}/…`` dont le PREMIER segment après ``/x/`` est un paramètre,
    déclare ``{pk}: $response.body#/id``. Un lien existant n'est jamais
    écrasé. Retourne le nombre de liens ajoutés."""
    chemins = doc.get("paths") or {}
    ajoutes = 0
    for collection, item in chemins.items():
        post = (item or {}).get("post")
        if not post or not collection.endswith("/") or collection.endswith("}/"):
            continue
        reponse = (post.get("responses") or {}).get("201")
        if not reponse or not _reponse_porte_id(doc, reponse):
            continue
        for cible, item_cible in chemins.items():
            if cible == collection or not cible.startswith(collection):
                continue
            m = _PREMIER_PARAM.match(cible[len(collection):])
            if not m:
                continue
            for methode in _METHODES:
                operation = (item_cible or {}).get(methode)
                if not operation or not operation.get("operationId"):
                    continue
                liens = reponse.setdefault("links", {})
                nom = f"{methode.upper()} {cible}"
                if nom in liens:
                    continue
                liens[nom] = {
                    "operationId": operation["operationId"],
                    "parameters": {m.group(1): "$response.body#/id"},
                }
                ajoutes += 1
    return ajoutes


def partager_chemins(chemins, shard: str | None):
    """Partition DÉTERMINISTE des chemins en N tranches (« i/N ») : le chemin de
    rang k (ordre trié) va à la tranche k % N. Chaque tranche fuzze TOUT son
    lot ; l'union des N tranches = toute la surface, à chaque run — plus
    d'échantillon aléatoire tronqué par `--max-time` (CI #997, 14/10/2026)."""
    if not shard:
        return set(chemins)
    i, n = (int(x) for x in shard.split("/", 1))
    if n < 1 or not 0 <= i < n:
        raise ValueError(f"tranche invalide : {shard!r} (attendu i/N avec 0 <= i < N)")
    return {chemin for k, chemin in enumerate(sorted(chemins)) if k % n == i}


def preparer_schema(doc: dict, proprietaires=None, resoudre=None,
                    shard: str | None = None) -> tuple[dict, dict]:
    """Schéma fuzzé + statistiques. ``proprietaires`` vide/None = tout garder ;
    ``shard`` (« i/N ») ne garde que la tranche i des chemins retenus."""
    voulus = set(proprietaires or ())
    caches: dict = {}

    def garder(gabarit):
        if not voulus:
            return True
        if gabarit not in caches:
            caches[gabarit] = {proprietaire_du_module(m) for m in modules_de_vue(gabarit, resoudre)}
        return bool(caches[gabarit] & voulus)

    sortie = copy.deepcopy(filtrer_schema(doc, garder))
    if shard:
        retenus = partager_chemins(sortie["paths"].keys(), shard)
        sortie["paths"] = {c: v for c, v in sortie["paths"].items() if c in retenus}
    liens = declarer_liens(sortie)
    operations = sum(
        1 for item in sortie["paths"].values() for m in _METHODES if m in (item or {})
    )
    return sortie, {"chemins": len(sortie["paths"]), "operations": operations, "liens": liens}


# ── Verdict du job PR ──────────────────────────────────────────────────────
def constats_du_rapport(rapport: dict) -> set:
    """``Titre du check|MÉTHODE /chemin`` pour chaque constat du rapport JSON."""
    return {
        f"{echec.get('title')}|{operation}"
        for echec in rapport.get("failures") or []
        for operation in echec.get("operations") or []
    }


def charger_dette(chemin: Path = DETTE_PATH) -> set:
    if not chemin.is_file():
        return set()
    return {
        ligne.strip()
        for ligne in chemin.read_text(encoding="utf-8").splitlines()
        if ligne.strip() and not ligne.lstrip().startswith("#")
    }


def erreurs_du_rapport(rapport: dict) -> list:
    """Erreurs du MOTEUR (crash de génération, schéma inutilisable) : une
    opération en erreur n'a PAS été testée. Le rapport JSON ne les rattache à
    aucune opération (``errors: [{title, count}]``) : elles ne sont donc jamais
    gelables — « tous les checks » (ENF11) exclut un trou de couverture muet."""
    lignes = sorted(f"Erreur du moteur|{e.get('title')}"
                    for e in rapport.get("errors") or [])
    en_erreur = (rapport.get("operations") or {}).get("errored") or 0
    if en_erreur and not lignes:
        lignes.append(f"Erreur du moteur|{en_erreur} opération(s) en erreur")
    return lignes


def anomalies_du_rapport(rapport: dict) -> list:
    """Run INEXPLOITABLE : un verdict vert n'y prouverait rien.

    * ``complete`` faux : le moteur ne s'est pas terminé (Schemathesis émet
      ``EngineFinished`` sur fin normale ET sur ``--max-time``) ;
    * ``stop_reason`` ``interrupted`` ;
    * ``auth.reauth_broke`` : la session du fuzzeur a sauté, la suite du run
      n'a vu que des 401."""
    anomalies = []
    if rapport.get("complete") is False or rapport.get("stop_reason") == "interrupted":
        anomalies.append(f"Run incomplet|stop_reason={rapport.get('stop_reason')}")
    if (rapport.get("auth") or {}).get("reauth_broke"):
        anomalies.append("Authentification perdue|reauth_broke")
    return anomalies


def verdict(rapport: dict, dette: set) -> tuple[list, list]:
    """(constats NOUVEAUX — rouges, constats de la dette re-vus).

    Les NOUVEAUX comprennent les erreurs du moteur et les anomalies du run,
    jamais couvertes par la dette."""
    constats = constats_du_rapport(rapport)
    rouges = sorted(constats - dette) + erreurs_du_rapport(rapport) + anomalies_du_rapport(rapport)
    return rouges, sorted(constats & dette)


_RESUME_MAX = 60


def resume_markdown(nouveaux: list, revus: list) -> str:
    """Corps d'alerte (issue du nocturne) : les régressions NOMMÉES."""
    if not nouveaux:
        return (f"Aucune régression api-fuzz hors dette gelée "
                f"({len(revus)} constat(s) de la dette re-vu(s)).\n")
    lignes = [f"{len(nouveaux)} constat(s) api-fuzz HORS de la dette gelée "
              f"`scripts/fuzz/api_fuzz_dette.txt` ({len(revus)} constat(s) de la "
              f"dette re-vu(s)) :", ""]
    lignes += [f"- `{ligne}`" for ligne in nouveaux[:_RESUME_MAX]]
    if len(nouveaux) > _RESUME_MAX:
        lignes.append(f"- … et {len(nouveaux) - _RESUME_MAX} autre(s) (rapport du job).")
    return "\n".join(lignes) + "\n"


def soldes(rapport: dict, dette: set) -> list:
    """Lignes de la dette absentes d'un rapport — PROBANT seulement sur un run
    COMPLET (le nocturne) : le job PR, plafonné et partiel, ne prouve rien."""
    vus = constats_du_rapport(rapport)
    return sorted(ligne for ligne in dette if ligne not in vus)


def _cmd_soldes(args) -> int:
    rapport = json.loads(Path(args.rapport).read_text(encoding="utf-8"))
    lignes = soldes(rapport, charger_dette(Path(args.dette)))
    print(f"\n### Dette gelée api-fuzz : {len(lignes)} ligne(s) soldée(s) par ce run\n")
    for ligne in lignes:
        print(f"- `{ligne}`")
    return 0


def _cmd_proprietaires(_args) -> int:
    for nom in proprietaires_modifies(sys.stdin.read().splitlines()):
        print(nom)
    return 0


def _cmd_schema(args) -> int:
    doc = json.loads(Path(args.entree).read_text(encoding="utf-8"))
    resoudre = resolveur_django() if args.proprietaires else None
    sortie, stats = preparer_schema(doc, args.proprietaires, resoudre, shard=args.shard)
    Path(args.sortie).write_text(json.dumps(sortie), encoding="utf-8")
    portee = f" — propriétaires : {' '.join(args.proprietaires)}" if args.proprietaires else ""
    portee += f" — tranche {args.shard}" if args.shard else ""
    print(f"Schéma fuzzé : {stats['operations']} opération(s) sur {stats['chemins']} "
          f"chemin(s), {stats['liens']} lien(s) stateful déclaré(s){portee}")
    return 0


def _cmd_verdict(args) -> int:
    rapport = json.loads(Path(args.rapport).read_text(encoding="utf-8"))
    nouveaux, revus = verdict(rapport, charger_dette(Path(args.dette)))
    if args.resume:
        Path(args.resume).write_text(resume_markdown(nouveaux, revus), encoding="utf-8")
    print(f"api-fuzz PR : {len(nouveaux)} constat(s) NOUVEAU(x), "
          f"{len(revus)} constat(s) de la dette gelée re-vu(s).")
    for ligne in nouveaux:
        print(f"  NOUVEAU  {ligne}")
    if nouveaux:
        print("\nCorriger la cause (schéma exact @extend_schema ou validation de la vue) ;\n"
              "rejouer : `st replay <id>` depuis le journal du job. La dette gelée\n"
              f"({Path(args.dette).name}) ne fait que rétrécir — jamais d'ajout.")
        return 1
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = parser.add_subparsers(dest="commande", required=True)
    sous.add_parser("proprietaires").set_defaults(func=_cmd_proprietaires)
    p_schema = sous.add_parser("schema")
    p_schema.add_argument("--in", dest="entree", required=True)
    p_schema.add_argument("--out", dest="sortie", required=True)
    p_schema.add_argument("--proprietaires", nargs="*", default=[])
    p_schema.add_argument("--shard", default=None, help="tranche i/N des chemins (CI matricielle)")
    p_schema.set_defaults(func=_cmd_schema)
    p_verdict = sous.add_parser("verdict")
    p_verdict.add_argument("--rapport", required=True)
    p_verdict.add_argument("--dette", default=str(DETTE_PATH))
    p_verdict.add_argument("--resume", default="",
                           help="écrit le corps d'alerte markdown (régressions nommées)")
    p_verdict.set_defaults(func=_cmd_verdict)
    p_soldes = sous.add_parser("soldes")
    p_soldes.add_argument("--rapport", required=True)
    p_soldes.add_argument("--dette", default=str(DETTE_PATH))
    p_soldes.set_defaults(func=_cmd_soldes)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

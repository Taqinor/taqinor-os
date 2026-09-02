#!/usr/bin/env python3
"""CRX11 — REGLE #1 DE CLAUDE.md, MACHINE-VERIFIEE : aucune ecriture Odoo
non declaree ne peut entrer dans ce depot.

CE QUE CETTE GARDE FERME
------------------------
La regle #1 dit « toute ecriture Odoo passe par l'API JSON-2, jamais de SQL ».
Elle etait tenue par la DISCIPLINE seule. Or le depot porte TROIS transports
Odoo independants, dont deux sont capables d'ecrire :

  * `apps/crm/odoo_sync.py` — JSON-2 (`/json/2/<model>/<method>`) ENTIEREMENT
    generique : `model` et `method` sont des parametres. Rien n'empechait un
    appelant futur d'ecrire n'importe quoi dans la base Odoo du fondateur ;
  * `core/odoo_accounting.py` — JSON-2 comptable, `account.move/create` et
    `account.payment/create`, aujourd'hui DORMANT (aucun appelant hors tests,
    verifie ci-dessous) ;
  * `apps/adsengine/odoo_client.py` — JSON-RPC, deja lecture-seule par
    construction (`_READ_METHODS`).

Une seule ecriture est voulue dans tout le depot : le deplacement d'etape de
`push_odoo_stages` (`crm.lead.write` sur `stage_id`, a blanc par defaut,
`--apply` explicite). Tout le reste est un rouge, sauf exception ECRITE ici
avec sa raison.

CE QUE LA GARDE LIT
-------------------
1. AUCUN TRANSPORT NON DECLARE. Tout fichier `.py` de `backend/django_core`
   qui porte une marque de transport Odoo (`/json/2/`, `/jsonrpc`,
   `execute_kw`, `xmlrpc`) doit figurer dans `TRANSPORTS_DECLARES` ou
   `HOOKS_DECLARES`. Un quatrieme transport ne peut donc pas apparaitre en
   silence — c'est ce qui rend le point 2 exhaustif.
2. TOUT APPEL EST UNE LECTURE, OU UNE EXCEPTION DECLAREE. Lecture AST de
   chaque site d'appel des transports declares ; la methode doit etre dans
   `METHODES_LECTURE`, sinon le couple (modele, methode) doit figurer dans
   `EXCEPTIONS`. Un modele ou une methode qui n'est pas un litteral est aussi
   un rouge : un appel invérifiable ne peut pas etre autorise.
3. L'ALLOWLIST D'EXECUTION EXISTE ET RESTE MINIMALE. `apps/crm/odoo_sync.py`
   doit declarer `_WRITE_ALLOWED` et `odoo_call` doit s'en servir ; son
   contenu doit correspondre exactement aux exceptions declarees ici pour ce
   transport. La garde statique et la garde d'execution ne peuvent pas diverger.
4. `core/odoo_accounting` N'A AUCUN APPELANT HORS TESTS. Ses deux `create`
   ne sont tolerees que parce que le module est DORMANT ; le jour ou on le
   branche, ce rouge force la decision au lieu de la laisser passer.
5. LE HOOK `CONNECTEUR_ODOO_MODULE` RESTE DECLARE. `apps/migration/services.py`
   nomme un module connecteur (`apps.publicapi.connectors.odoo`) qui n'existe
   pas encore ; s'il apparait un jour, son fichier devra etre declare en
   transport — la garde le dit au lieu de le decouvrir en production.

Chaque regle pointe dans LES DEUX SENS : un fichier declare qui disparait, ou
une exception qui ne correspond plus a rien, est aussi un rouge. Une liste
epinglee qui ne verifie plus rien est la classe de panne que ce depot a deja
payee plusieurs fois.

Usage : `python scripts/check_odoo_writes.py`
Stdlib pure : ni base de donnees, ni docker, ni Django, ni node.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend" / "django_core"

# ── Methodes de LECTURE de l'API Odoo (jamais un rouge) ────────────────────
METHODES_LECTURE = frozenset({
    'search_read', 'search', 'search_count', 'read', 'read_group',
    'fields_get', 'name_search', 'name_get', 'default_get',
    'authenticate', 'version', 'check_access_rights',
    # `core/odoo_accounting.fetch_payment_status` — consultation de l'etat de
    # paiement d'une facture, aucune ecriture.
    'payment_state',
})

# ── Transports Odoo DECLARES (chemins relatifs a backend/django_core) ──────
TRANSPORTS_DECLARES = {
    'apps/crm/odoo_sync.py':
        "JSON-2 generique (odoo_call) — sync leads + push d'etape ; garde "
        "d'execution `_WRITE_ALLOWED`.",
    'core/odoo_accounting.py':
        "JSON-2 comptable — DORMANT (aucun appelant hors tests, verifie par "
        "cette garde).",
    'apps/adsengine/odoo_client.py':
        "JSON-RPC lecture-seule par construction (`_READ_METHODS` dans le "
        "module lui-meme).",
}

# ── Hooks qui NOMMENT un connecteur Odoo sans en etre un ───────────────────
HOOKS_DECLARES = {
    'apps/migration/services.py':
        "CONNECTEUR_ODOO_MODULE — chemin pointille vers un connecteur "
        "d'EXPORT (`client_pour_societe` -> `exporter_entite`) qui n'existe "
        "pas encore ; import paresseux, ImportError avalee, endpoint en 400.",
}

# Constante du hook + module qu'elle nomme (verifies au point 5).
HOOK_CONSTANTE = 'CONNECTEUR_ODOO_MODULE'
HOOK_FICHIER = 'apps/migration/services.py'

# ── Exceptions d'ECRITURE, chacune avec sa raison ──────────────────────────
# (fichier QUI LANCE L'APPEL, modele, methode) -> raison. La cle porte le
# fichier appelant, pas le transport : la meme ecriture lancee d'un autre
# module reste un rouge (un transport Odoo a un proprietaire, pas des
# passagers). Ajouter une entree ici est une DECISION, jamais un contournement.
EXCEPTIONS = {
    ('apps/crm/odoo_sync.py', 'crm.lead', 'write'):
        "push_odoo_stages — deplacement d'etape SEUL (`stage_id`), a blanc "
        "par defaut, `--apply` explicite ; c'est la seule ecriture Odoo "
        "voulue du depot.",
    ('core/odoo_accounting.py', 'account.move', 'create'):
        "Module DORMANT : aucun appelant hors tests (verifie par cette "
        "garde). Le brancher exige de re-decider ici.",
    ('core/odoo_accounting.py', 'account.payment', 'create'):
        "Module DORMANT : meme raison que account.move/create.",
}

# Le contenu attendu de la garde d'EXECUTION `_WRITE_ALLOWED` d'odoo_sync est
# derive des exceptions ci-dessus — jamais recopie a la main (point 3).
FICHIER_ALLOWLIST_EXECUTION = 'apps/crm/odoo_sync.py'

# ── Detection d'un transport Odoo (point 1) ───────────────────────────────
MARQUES_TRANSPORT = (
    re.compile(r'/json/2/'),
    re.compile(r'/jsonrpc\b'),
    re.compile(r'\bexecute_kw\b'),
    re.compile(r'\bxmlrpc\b'),
)

DOSSIERS_IGNORES = {'migrations', '__pycache__', 'node_modules'}


def _est_test(rel: str) -> bool:
    parts = rel.split('/')
    return any(p == 'tests' for p in parts) or parts[-1].startswith('test')


def _fichiers_python():
    for path in sorted(BACKEND.rglob('*.py')):
        rel = path.relative_to(BACKEND).as_posix()
        if any(part in DOSSIERS_IGNORES for part in path.parts):
            continue
        yield rel, path


def _litteral(node):
    """Valeur d'un noeud AST si c'est une chaine litterale, sinon None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


# ── Extraction des couples (modele, methode) par transport ────────────────

def _appels_odoo_call(tree):
    """`odoo_call(config, '<modele>', '<methode>', ...)` — n'importe ou."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        nom = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else None)
        if nom != 'odoo_call' or len(node.args) < 3:
            continue
        yield node.lineno, _litteral(node.args[1]), _litteral(node.args[2])


def _appels_json2_chemin(tree):
    """`self._call('<modele>/<methode>', ...)` — client JSON-2 comptable."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != '_call':
            continue
        if not node.args:
            continue
        chemin = _litteral(node.args[0])
        if chemin is None:
            yield node.lineno, None, None
            continue
        modele, _, methode = chemin.partition('/')
        yield node.lineno, modele or None, methode or None


def _appels_execute_kw(tree):
    """`self._execute_kw(model, '<methode>', ...)` — client JSON-RPC.

    Le MODELE y est un parametre (les litteraux `crm.lead` / `sale.order` /
    `res.partner` vivent chez les appelants) : seule la methode est verifiee,
    ce qui suffit — c'est elle qui distingue lecture et ecriture.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in ('_execute_kw', '_rpc'):
            continue
        if len(node.args) < 2:
            continue
        methode = _litteral(node.args[1])
        if methode == 'execute_kw':
            # `_rpc('object', 'execute_kw', ...)` : c'est le transport lui-meme,
            # la vraie methode est verifiee sur `_execute_kw`.
            continue
        yield node.lineno, '<parametre>', methode


EXTRACTEURS = {
    'apps/crm/odoo_sync.py': _appels_odoo_call,
    'core/odoo_accounting.py': _appels_json2_chemin,
    'apps/adsengine/odoo_client.py': _appels_execute_kw,
}


def _verifier_transports_declares(textes, echecs):
    """Point 1 — aucun transport Odoo non declare, et aucun declare disparu."""
    connus = set(TRANSPORTS_DECLARES) | set(HOOKS_DECLARES)
    for rel, texte in textes.items():
        if rel in connus or _est_test(rel):
            continue
        if any(marque.search(texte) for marque in MARQUES_TRANSPORT):
            echecs.append(
                f"{rel} : nouveau transport Odoo NON DECLARE. Ajoutez-le a "
                f"TRANSPORTS_DECLARES de scripts/check_odoo_writes.py (avec "
                f"sa raison) et faites verifier ses appels, ou passez par "
                f"apps/crm/odoo_sync.odoo_call.")
    for rel in sorted(connus):
        if rel not in textes:
            echecs.append(
                f"{rel} : transport/hook declare mais INTROUVABLE. Retirez-le "
                f"de scripts/check_odoo_writes.py dans le meme commit — une "
                f"declaration qui ne verifie plus rien est un faux vert.")


def _verifier_appels(textes, echecs):
    """Point 2 — chaque appel est une lecture, ou une exception declaree."""
    exceptions_vues = set()
    # `odoo_call` peut etre appele depuis N'IMPORTE OU : on balaie tout le
    # backend pour ce transport-la, pas seulement son module de definition.
    for rel, texte in textes.items():
        if _est_test(rel):
            continue
        extracteurs = []
        if 'odoo_call' in texte:
            extracteurs.append(_appels_odoo_call)
        if rel in EXTRACTEURS and EXTRACTEURS[rel] is not _appels_odoo_call:
            extracteurs.append(EXTRACTEURS[rel])
        if not extracteurs:
            continue
        try:
            tree = ast.parse(texte)
        except SyntaxError as exc:  # pragma: no cover - fichier casse
            echecs.append(f"{rel} : illisible ({exc}).")
            continue
        for extracteur in extracteurs:
            for ligne, modele, methode in extracteur(tree):
                if methode is None or modele is None:
                    echecs.append(
                        f"{rel}:{ligne} : appel Odoo dont le modele ou la "
                        f"methode n'est pas un litteral — invérifiable, donc "
                        f"refuse. Nommez-les en clair au site d'appel.")
                    continue
                if methode in METHODES_LECTURE:
                    continue
                # L'exception est portee par le FICHIER qui lance l'appel :
                # la meme ecriture depuis un autre module reste un rouge (un
                # transport Odoo a un proprietaire, pas des passagers).
                cle = (rel, modele, methode)
                if cle in EXCEPTIONS:
                    exceptions_vues.add(cle)
                    continue
                echecs.append(
                    f"{rel}:{ligne} : ECRITURE Odoo non declaree "
                    f"{modele}.{methode}. Une ecriture Odoo se declare dans "
                    f"EXCEPTIONS de scripts/check_odoo_writes.py AVEC SA "
                    f"RAISON, et dans `_WRITE_ALLOWED` "
                    f"(apps/crm/odoo_sync.py) pour le transport JSON-2.")
    for cle in sorted(set(EXCEPTIONS) - exceptions_vues):
        echecs.append(
            f"{cle[0]} : exception declaree {cle[1]}.{cle[2]} mais AUCUN "
            f"appel correspondant. Retirez-la — une exception qui ne couvre "
            f"plus rien elargit la surface autorisee pour rien.")


def _verifier_allowlist_execution(textes, echecs):
    """Point 3 — `_WRITE_ALLOWED` existe, est utilisee, et colle aux
    exceptions declarees ici pour le transport JSON-2."""
    rel = FICHIER_ALLOWLIST_EXECUTION
    texte = textes.get(rel)
    if texte is None:
        return  # deja signale par le point 1
    attendu = {(m, meth) for (f, m, meth) in EXCEPTIONS if f == rel}
    tree = ast.parse(texte)
    trouve = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == '_WRITE_ALLOWED'
                for t in node.targets):
            try:
                valeur = ast.literal_eval(
                    node.value.args[0] if isinstance(node.value, ast.Call)
                    else node.value)
            except (ValueError, SyntaxError, AttributeError, IndexError):
                valeur = None
            if valeur is not None:
                trouve = {tuple(v) for v in valeur}
    if trouve is None:
        echecs.append(
            f"{rel} : `_WRITE_ALLOWED` absente ou illisible. La garde "
            f"d'EXECUTION doit exister a cote de la garde statique — sans "
            f"elle, `odoo_call` reste un transport generique ouvert.")
        return
    if trouve != attendu:
        echecs.append(
            f"{rel} : `_WRITE_ALLOWED` = {sorted(trouve)} alors que les "
            f"exceptions declarees pour ce transport sont {sorted(attendu)}. "
            f"Les deux gardes doivent dire la MEME chose.")
    if '_WRITE_ALLOWED' not in texte.split('def odoo_call', 1)[-1]:
        echecs.append(
            f"{rel} : `odoo_call` n'utilise pas `_WRITE_ALLOWED` — une "
            f"allowlist qui n'est jamais consultee ne garde rien.")


def _verifier_module_dormant(textes, echecs):
    """Point 4 — `core/odoo_accounting` n'a aucun appelant hors tests."""
    cible = 'core/odoo_accounting.py'
    if cible not in textes:
        return  # deja signale par le point 1
    importeurs = []
    for rel, texte in textes.items():
        if rel == cible or _est_test(rel):
            continue
        if re.search(r'\bodoo_accounting\b', texte):
            importeurs.append(rel)
    if importeurs:
        echecs.append(
            "core/odoo_accounting n'est plus dormant — appelant(s) hors "
            "tests : " + ', '.join(sorted(importeurs)) + ". Ses deux "
            "`create` (account.move / account.payment) n'etaient tolerees "
            "QUE parce que rien ne les appelait : re-decidez ici avant de "
            "brancher une ecriture comptable dans Odoo.")


def _verifier_hook_connecteur(textes, echecs):
    """Point 5 — le hook CONNECTEUR_ODOO_MODULE reste declare et dormant."""
    texte = textes.get(HOOK_FICHIER)
    if texte is None:
        return  # deja signale par le point 1
    motif = re.search(
        HOOK_CONSTANTE + r"\s*=\s*['\"]([^'\"]+)['\"]", texte)
    if not motif:
        echecs.append(
            f"{HOOK_FICHIER} : `{HOOK_CONSTANTE}` a disparu. Si le hook "
            f"connecteur Odoo n'existe plus, retirez-le de HOOKS_DECLARES "
            f"dans le meme commit.")
        return
    module = motif.group(1)
    chemin = BACKEND / (module.replace('.', '/') + '.py')
    paquet = BACKEND / module.replace('.', '/') / '__init__.py'
    if chemin.exists() or paquet.exists():
        rel = (chemin if chemin.exists() else paquet).relative_to(
            BACKEND).as_posix()
        if rel not in TRANSPORTS_DECLARES:
            echecs.append(
                f"{rel} : le connecteur nomme par `{HOOK_CONSTANTE}` "
                f"({module}) EXISTE desormais. Declarez-le dans "
                f"TRANSPORTS_DECLARES et faites verifier ses appels — le "
                f"hook n'est plus dormant.")


def main() -> int:
    if not BACKEND.is_dir():
        print(f"check_odoo_writes: {BACKEND} introuvable.")
        return 2
    textes = {}
    for rel, path in _fichiers_python():
        try:
            textes[rel] = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue

    echecs: list[str] = []
    _verifier_transports_declares(textes, echecs)
    _verifier_appels(textes, echecs)
    _verifier_allowlist_execution(textes, echecs)
    _verifier_module_dormant(textes, echecs)
    _verifier_hook_connecteur(textes, echecs)

    if echecs:
        print("check_odoo_writes : ecriture Odoo non declaree ou garde "
              "perimee (CLAUDE.md regle #1) :")
        for echec in echecs:
            print(f"  - {echec}")
        return 1

    autorisees = ', '.join(
        f"{m}.{meth}" for (_f, m, meth) in sorted(EXCEPTIONS))
    print("check_odoo_writes : OK — tout appel Odoo est une lecture, sauf "
          f"les ecritures declarees ({autorisees}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

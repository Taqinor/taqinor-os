"""Baux partagés entre sessions de plan concurrentes (plusieurs postes).

Deux sessions « loop work on all plans » (ou une + « work on the plan ») sur
deux ordinateurs ne se voient pas : ce script leur donne un registre commun,
porté par des refs git sur origin (`refs/plan-claims/<clé>`), sans commit sur
main ni CI. Une clé = un fichier de plan (`file:docs/plans/PLAN_AUDIT_LEAD.md`)
ou une app (`app:crm`). La prise est ATOMIQUE : créer une ref déjà existante
est refusé par le serveur (non fast-forward), donc un seul poste gagne.

Usage :
  python scripts/plan_claims.py list
  python scripts/plan_claims.py claim  <clé>... --owner <id> [--branch dev-all]
  python scripts/plan_claims.py renew  <clé>... --owner <id>
  python scripts/plan_claims.py release <clé>... --owner <id>

Un bail non renouvelé depuis TTL heures (6 par défaut) est périmé : un autre
propriétaire peut le reprendre. `claim` sort 0 si TOUTES les clés sont prises,
1 sinon (et n'en garde aucune : tout ou rien).
"""
import argparse
import json
import re
import subprocess
import sys
import time

NS = "refs/plan-claims/"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
TTL_HOURS = 6


def git(*args, check=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} : {r.stderr.strip()}")
    return r


def slug(key):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", key).strip("_")


def remote_claims():
    """{slug: (sha, données)} lus sur origin."""
    out = git("ls-remote", "origin", NS + "*").stdout.split()
    refs = dict(zip(out[1::2], out[0::2]))
    if not refs:
        return {}
    git("fetch", "-q", "origin", f"+{NS}*:{NS}*")
    claims = {}
    for ref, sha in refs.items():
        msg = git("log", "-1", "--format=%B", sha).stdout.strip()
        try:
            data = json.loads(msg)
        except ValueError:
            data = {"owner": "?", "ts": 0, "key": ref[len(NS):]}
        claims[ref[len(NS):]] = (sha, data)
    return claims


def is_stale(data):
    return time.time() - float(data.get("ts", 0)) > TTL_HOURS * 3600


def make_commit(key, owner, branch, parent=None):
    msg = json.dumps({"key": key, "owner": owner, "branch": branch, "ts": int(time.time())})
    args = ["commit-tree", EMPTY_TREE, "-m", msg]
    if parent:
        args += ["-p", parent]
    return git(*args).stdout.strip()


def push(ref, sha, lease=None):
    args = ["push", "-q", "origin"]
    if lease is not None:
        args.append(f"--force-with-lease={ref}:{lease}")
    return git(*args, f"{sha}:{ref}", check=False).returncode == 0


def cmd_list(_):
    claims = remote_claims()
    if not claims:
        print("Aucun bail actif.")
    for s, (_, d) in sorted(claims.items()):
        age = (time.time() - float(d.get("ts", 0))) / 3600
        flag = " (PÉRIMÉ)" if is_stale(d) else ""
        print(f"{d.get('key', s):55} {d.get('owner', '?'):28} {d.get('branch', ''):14} {age:4.1f} h{flag}")


def cmd_claim(a):
    claims = remote_claims()
    won = []
    for key in a.keys:
        ref = NS + slug(key)
        cur = claims.get(slug(key))
        if cur and cur[1].get("owner") == a.owner:
            ok = push(ref, make_commit(key, a.owner, a.branch, cur[0]))
        elif cur and not is_stale(cur[1]):
            print(f"REFUSÉ {key} : tenu par {cur[1].get('owner')} ({cur[1].get('branch', '')})")
            ok = False
        elif cur:
            ok = push(ref, make_commit(key, a.owner, a.branch), lease=cur[0])
        else:
            ok = push(ref, make_commit(key, a.owner, a.branch))
        if not ok:
            for k in won:  # tout ou rien
                git("push", "-q", "origin", f":{NS}{slug(k)}", check=False)
            print(f"ÉCHEC — aucune clé gardée ({key} non obtenu).")
            return 1
        won.append(key)
    print("PRIS : " + ", ".join(won))
    return 0


def cmd_renew(a):
    claims = remote_claims()
    rc = 0
    for key in a.keys:
        cur = claims.get(slug(key))
        if not cur or cur[1].get("owner") != a.owner:
            print(f"PERDU {key} : plus à {a.owner}")
            rc = 1
            continue
        push(NS + slug(key), make_commit(key, a.owner, cur[1].get("branch", ""), cur[0]))
    return rc


def cmd_release(a):
    claims = remote_claims()
    for key in a.keys:
        cur = claims.get(slug(key))
        if cur and cur[1].get("owner") == a.owner:
            git("push", "-q", "origin", f":{NS}{slug(key)}", check=False)
            print(f"LIBÉRÉ {key}")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("claim", "renew", "release"):
        s = sub.add_parser(name)
        s.add_argument("keys", nargs="+")
        s.add_argument("--owner", required=True, help="poste+session, ex. DESKTOP-APTAHF6/dev-all-8")
        s.add_argument("--branch", default="")
    a = p.parse_args()
    return {"list": cmd_list, "claim": cmd_claim, "renew": cmd_renew, "release": cmd_release}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

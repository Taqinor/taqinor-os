#!/usr/bin/env python3
"""Sonde autonome du premier contact avec l'API officielle Meta Ad Library (VEIL40).

Python standard uniquement. Lancee par Reda en local, JAMAIS depuis le serveur ni
depuis l'ERP. Lecture seule : seul le point d'acces ``ads_archive`` (et
``debug_token``) est appele. Le jeton est lu dans un fichier hors depot
(``~/.yanbow/adlib.env``) et n'est JAMAIS ecrit dans le journal.

    python tools/adlib_probe/probe.py --mots "sandals" --journal sonde.jsonl
    python tools/adlib_probe/probe.py --rejouer reponses.jsonl --journal rejeu.jsonl

Voir LISEZ-MOI.md. Ne rien lancer sans l'approbation de ``tos_risk/meta_ad_library_api.md``.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH_VERSION = "v25.0"
BASE_URL = "https://graph.facebook.com/%s" % GRAPH_VERSION
DEFAULT_ENV = os.path.join("~", ".yanbow", "adlib.env")
HARD_MAX_CALLS = 150
USAGE_PAUSE_PCT = 75
USAGE_PAUSE_S = 300
# code Meta -> attente (s) puis ARRET (jamais de nouvel essai immediat)
WAIT_THEN_STOP = {4: 300, 17: 600, 32: 1200, 613: 1800}
STOP_NOW = {10, 190}

EU_COUNTRIES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
]
UK = "GB"
ALL_COUNTRIES = EU_COUNTRIES + [UK]

BASE_FIELDS = "id,page_id,page_name,ad_creative_bodies,ad_delivery_start_time,ad_snapshot_url"
UK_FIELDS = BASE_FIELDS + ",age_country_gender_reach_breakdown,eu_total_reach"

_SECRET_RES = [
    re.compile(r"access_token=[^&\s\"']*", re.I),
    re.compile(r"EAA[A-Za-z0-9_\-]{6,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-|.]{8,}", re.I),
]


# Seuls chemins couverts par tos_risk/meta_ad_library_api.md ; tout ajout exige d'abord
# la mise a jour du fichier de risque et l'accord du fondateur (CLAUDE.md regle #5).
CHEMINS_AUTORISES = frozenset({"ads_archive", "debug_token"})


class ProbeStop(Exception):
    """Arret propre de la sonde (budget, code Meta, rejeu epuise)."""

    def __init__(self, raison, diagnostic=None):
        super().__init__(raison)
        self.raison = raison
        self.diagnostic = diagnostic


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = {str(k).lower(): v for k, v in (headers or {}).items()}
        self.body = body if isinstance(body, dict) else {}


# ---------------------------------------------------------------- secrets

def scrub(value):
    """Retire tout jeton d'une valeur arbitraire (recursif)."""
    if isinstance(value, str):
        for rx in _SECRET_RES:
            value = rx.sub("[RETIRE]", value)
        return value
    if isinstance(value, dict):
        return {str(k): scrub(v) for k, v in value.items() if str(k).lower() != "access_token"}
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    return value


def contains_secret(text):
    return any(rx.search(text) for rx in _SECRET_RES) or "access_token" in text.lower()


# ------------------------------------------------------------ transports

def _json(raw):
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def http_transport(url, params, headers, timeout=60):
    """Transport reel (urllib). GET uniquement."""
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return Response(resp.status, dict(resp.headers), _json(raw))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        return Response(exc.code, dict(exc.headers or {}), _json(raw))


class ReplayTransport:
    """Rejoue des reponses enregistrees (une ligne JSON par reponse), dans l'ordre.
    Aucun acces reseau."""

    def __init__(self, lines):
        self._items = [json.loads(ln) for ln in lines if ln.strip()]
        self._i = 0

    @classmethod
    def from_file(cls, path):
        with open(path, encoding="utf-8") as fh:
            return cls(fh.readlines())

    def __call__(self, url, params, headers):
        if self._i >= len(self._items):
            raise ProbeStop("rejeu epuise")
        item = self._items[self._i]
        self._i += 1
        return Response(item.get("status", 200), item.get("headers"), item.get("body"))


# ------------------------------------------------------------------ sonde

class Probe:
    def __init__(self, token, transport, journal_path, max_calls=HARD_MAX_CALLS,
                 sleep=time.sleep, pause_s=2.0, clock=time.time):
        if max_calls > HARD_MAX_CALLS:
            raise ValueError("--max-calls plafonne a %d" % HARD_MAX_CALLS)
        self.token = token
        self.transport = transport
        self.journal_path = journal_path
        self.max_calls = max_calls
        self.sleep = sleep
        self.pause_s = pause_s
        self.clock = clock
        self.calls = 0
        self.pending_pause = 0
        self.stopped = None

    # -- journal (sans secret)
    def log(self, entry):
        entry = scrub(dict(entry, ts=int(self.clock())))
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        if contains_secret(line):  # ceinture et bretelles
            line = json.dumps({"exp": entry.get("exp"), "erreur_journal": "secret detecte, ligne retiree"})
        with open(self.journal_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # -- un appel
    def call(self, exp, path, params, use_header=False, extra_log=None):
        if path not in CHEMINS_AUTORISES:  # perimetre de tos_risk/meta_ad_library_api.md (regle #5)
            raise ProbeStop("chemin hors perimetre tos_risk : %s" % path)
        if self.calls >= self.max_calls:
            raise ProbeStop("budget --max-calls atteint (%d)" % self.max_calls)
        if self.pending_pause:
            wait, self.pending_pause = self.pending_pause, 0
            self.log({"exp": exp, "evenement": "pause_usage", "attente_s": wait})
            self.sleep(wait)
        elif self.calls and self.pause_s:
            self.sleep(self.pause_s)
        params = dict(params)
        headers = {}
        if use_header:
            headers["Authorization"] = "Bearer " + self.token
        else:
            params["access_token"] = self.token
        self.calls += 1
        resp = self.transport("%s/%s" % (BASE_URL, path), params, headers)
        usage = self._usage(resp)
        err = resp.body.get("error") if isinstance(resp.body.get("error"), dict) else None
        data = resp.body.get("data")
        paging = resp.body.get("paging") or {}
        entry = {
            "exp": exp, "appel": self.calls, "chemin": path,
            "params": self._safe_params(params),
            "entete_auth": bool(use_header),
            "statut": resp.status, "x_app_usage": usage,
            "n": len(data) if isinstance(data, list) else None,
            "a_suivant": bool(paging.get("next")),
        }
        if err:
            entry["erreur"] = {"code": err.get("code"), "sous_code": err.get("error_subcode"),
                               "type": err.get("type"), "message": err.get("message")}
        if extra_log:
            entry.update(extra_log)
        self.log(entry)
        self._guard(exp, err, usage)
        return resp

    @staticmethod
    def _safe_params(params):
        # ni jeton ni curseur de pagination dans le journal (« ne stockez pas de curseurs »)
        out = {k: v for k, v in params.items() if k not in ("access_token", "after")}
        if "after" in params:
            out["apres_curseur"] = True
        return out

    @staticmethod
    def _usage(resp):
        raw = resp.headers.get("x-app-usage")
        if not raw:
            return None
        try:
            val = json.loads(raw) if isinstance(raw, str) else raw
            return val if isinstance(val, dict) else None
        except ValueError:
            return None

    def _guard(self, exp, err, usage):
        code = err.get("code") if err else None
        if code in WAIT_THEN_STOP:
            wait = WAIT_THEN_STOP[code]
            self.log({"exp": exp, "evenement": "limite_debit", "code": code, "attente_s": wait})
            self.sleep(wait)
            raise ProbeStop("code Meta %s : attente %ds puis arret" % (code, wait))
        if code in STOP_NOW:
            diag = {"code": code, "sous_code": err.get("error_subcode"), "message": err.get("message")}
            self.log({"exp": exp, "evenement": "arret_diagnostic", "diagnostic": diag})
            raise ProbeStop("code Meta %s : arret" % code, diag)
        if usage:
            nums = [v for v in usage.values() if isinstance(v, (int, float))]
            if nums and max(nums) >= USAGE_PAUSE_PCT:
                self.pending_pause = USAGE_PAUSE_S

    # -- aides
    def search(self, exp, country, terms, limit=None, search_type="KEYWORD_UNORDERED",
               fields=BASE_FIELDS, after=None, use_header=False, extra_log=None):
        countries = country if isinstance(country, list) else [country]
        params = {
            "search_terms": terms, "search_type": search_type, "fields": fields,
            "ad_reached_countries": json.dumps(countries),
            "ad_active_status": "ACTIVE", "ad_type": "ALL",
        }
        if limit:
            params["limit"] = limit
        if after:
            params["after"] = after
        return self.call(exp, "ads_archive", params, use_header=use_header, extra_log=extra_log)


def _ids(resp):
    return {str(a.get("id")) for a in (resp.body.get("data") or []) if isinstance(a, dict)}


def _n(resp):
    d = resp.body.get("data")
    return len(d) if isinstance(d, list) else None


# ------------------------------------------------------------ experiences

def e0(p, **_):
    r = p.call("E0", "debug_token", {"input_token": p.token})
    d = r.body.get("data")
    d = d if isinstance(d, dict) else {}
    p.log({"exp": "E0", "evenement": "resultat", "valide": d.get("is_valid"),
           "expire_a": d.get("expires_at"), "donnees_acces_expire_a": d.get("data_access_expires_at"),
           "type": d.get("type")})


def e1(p, mots, **_):
    res = {}
    for s in [None, 100, 250, 500, 1000, 2000]:
        r = p.search("E1", "FR", mots, limit=s, extra_log={"limit_demande": s})
        res[str(s)] = _n(r)
    p.log({"exp": "E1", "evenement": "resultat", "taille_page_par_limit": res})


def e2(p, mots, **_):
    res = {}
    for c in ALL_COUNTRIES:
        r = p.search("E2", c, mots, limit=25)
        res[c] = _n(r)
    p.log({"exp": "E2", "evenement": "resultat", "n_par_pays": res})


def e2_uk(p, mots, **_):
    r = p.search("E2-UK", UK, mots, limit=100, fields=UK_FIELDS)
    ads = [a for a in (r.body.get("data") or []) if isinstance(a, dict)]
    sans_ue = avec_rep = 0
    for a in ads:
        rows = a.get("age_country_gender_reach_breakdown") or []
        countries = {row.get("country") for row in rows if isinstance(row, dict)}
        if rows:
            avec_rep += 1
        if not (countries & set(EU_COUNTRIES)):
            sans_ue += 1
    p.log({"exp": "E2-UK", "evenement": "resultat", "n_gb": len(ads),
           "avec_repartition": avec_rep, "sans_pays_ue_dans_repartition": sans_ue})


def e3(p, mots, **_):
    a = p.search("E3", "FR", mots, limit=100, search_type="KEYWORD_UNORDERED")
    b = p.search("E3", "FR", mots, limit=100, search_type="KEYWORD_EXACT_PHRASE")
    p.log({"exp": "E3", "evenement": "resultat", "n_unordered": _n(a), "n_exact_phrase": _n(b),
           "ids_communs": len(_ids(a) & _ids(b))})


def e4(p, mots, **_):
    multi = p.search("E4", ["FR", "DE"], mots, limit=100)
    fr = p.search("E4", "FR", mots, limit=100)
    de = p.search("E4", "DE", mots, limit=100)
    ids_m, ids_fr, ids_de = _ids(multi), _ids(fr), _ids(de)
    p.log({"exp": "E4", "evenement": "resultat", "n_multi": _n(multi), "n_fr": _n(fr), "n_de": _n(de),
           "multi_dans_fr_ou_de": len(ids_m & (ids_fr | ids_de)),
           "multi_dans_fr_et_de": len(ids_m & ids_fr & ids_de)})


def e5(p, mots, max_pages=10, **_):
    per_page, after = [], None
    for _i in range(max_pages):
        r = p.search("E5", "FR", mots, limit=100, after=after)
        per_page.append(_n(r))
        paging = r.body.get("paging") or {}
        after = (paging.get("cursors") or {}).get("after")
        if not paging.get("next") or not after:
            break
    # le curseur n'est jamais journalise ni conserve
    p.log({"exp": "E5", "evenement": "resultat", "pages": len(per_page), "n_par_page": per_page,
           "fin_par_next_absent": len(per_page) < max_pages})


def e7(p, mots, **_):
    r = p.search("E7", "FR", mots, limit=25)
    urls = [a.get("ad_snapshot_url") for a in (r.body.get("data") or []) if isinstance(a, dict)]
    flag = any(isinstance(u, str) and "access_token" in u.lower() for u in urls)
    # booleen seulement : l'URL n'est jamais gardee
    p.log({"exp": "E7", "evenement": "resultat", "jeton_dans_snapshot": flag, "n_urls": len(urls)})


def e8(p, mots, **_):
    r = p.search("E8", "FR", mots, limit=5, use_header=True)
    ok = r.status == 200 and "error" not in r.body
    p.log({"exp": "E8", "evenement": "resultat", "entete_authorization_accepte": ok, "statut": r.status})


EXPERIMENTS = [("E0", e0), ("E1", e1), ("E2", e2), ("E2-UK", e2_uk), ("E3", e3), ("E4", e4),
               ("E5", e5), ("E7", e7), ("E8", e8)]


def run(probe, mots, only=None):
    """Execute les experiences ; retourne la raison d'arret ('termine' sinon)."""
    try:
        for name, fn in EXPERIMENTS:
            if only and name not in only:
                continue
            fn(probe, mots=mots)
    except ProbeStop as stop:
        probe.stopped = stop.raison
        probe.log({"exp": "FIN", "evenement": "arret", "raison": stop.raison, "appels": probe.calls})
        return stop.raison
    probe.log({"exp": "FIN", "evenement": "termine", "appels": probe.calls})
    return "termine"


# ------------------------------------------------------------------- main

def read_token(path):
    path = os.path.expanduser(path)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("META_AD_LIBRARY_ACCESS_TOKEN="):
                return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("META_AD_LIBRARY_ACCESS_TOKEN absent de %s" % path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mots", default="sandals", help="mot-cle (<= 100 caracteres)")
    ap.add_argument("--env", default=DEFAULT_ENV, help="fichier .env hors depot")
    ap.add_argument("--journal", default="adlib_probe.jsonl")
    ap.add_argument("--max-calls", type=int, default=HARD_MAX_CALLS)
    ap.add_argument("--only", help="experiences separees par des virgules (ex. E0,E1)")
    ap.add_argument("--rejouer", help="rejoue ces reponses enregistrees : AUCUN appel reseau, aucun jeton lu")
    args = ap.parse_args(argv)
    if not 1 <= args.max_calls <= HARD_MAX_CALLS:
        ap.error("--max-calls doit etre entre 1 et %d" % HARD_MAX_CALLS)
    if len(args.mots) > 100:
        ap.error("--mots depasse 100 caracteres")
    only = set(args.only.split(",")) if args.only else None
    if args.rejouer:
        probe = Probe("REJEU", ReplayTransport.from_file(args.rejouer), args.journal,
                      max_calls=args.max_calls, sleep=lambda s: None, pause_s=0)
    else:
        probe = Probe(read_token(args.env), http_transport, args.journal, max_calls=args.max_calls)
    result = run(probe, args.mots, only)
    print("sonde : %s, %d appel(s), journal %s" % (result, probe.calls, args.journal))
    return 0


if __name__ == "__main__":
    sys.exit(main())

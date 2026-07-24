#!/usr/bin/env python3
"""READ-ONLY Meta Ads audit runner — TAQINOR (audit 2026-07).

Companion to docs/engine/audit-2026-07.md. Fills the data sections of that
audit: inventory (ad accounts, pages, pixels, campaigns), 30-day deep-dive on
active campaigns, Instant Forms + FULL lead export to CSV (Meta deletes leads
after 90 days), and pixel/dataset firing checks.

STRICTLY READ-ONLY: every request is an HTTP GET. There is no POST/DELETE
anywhere in this file; nothing on Meta is created, modified, or paused.

Zero dependencies (stdlib only, Python >= 3.8) so it runs on the Hetzner host,
inside the django_core container, or on any PC — no pip install needed.

Usage (on a machine with open egress to graph.facebook.com):
    python3 audit_meta_readonly.py --env-file /opt/taqinor-os/.env
    # or: META_SYSTEM_USER_TOKEN=... python3 audit_meta_readonly.py
Token resolution order: --token, META_SYSTEM_USER_TOKEN, ACCESS_TOKEN
(env vars first, then the --env-file file).

Outputs (default ./meta_audit_output/):
    audit_data.json     full raw data (keep local)
    audit_summary.md    PII-free digest ready to paste into the audit doc
    leads_<page>_<form>.csv   one per Instant Form — CONTAINS PII, NEVER
                              commit these to the repo.
The token is sent via the Authorization header (never in URLs), so it cannot
leak into logs or error messages.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

API_VERSION = "v25.0"  # matches meta-ads CLI 1.1.0 (facebook-business 25.0.3)
BASE = "https://graph.facebook.com/" + API_VERSION
URGENT_LEAD_AGE_DAYS = 60   # Meta deletes leads at 90 days; >60 is urgent
RETRYABLE_CODES = {1, 2, 4, 17, 32, 613}  # transient / rate-limit error codes

TOKEN = None


def log(msg):
    print(msg, flush=True)


def redact(text):
    """Never let a token-looking string reach stdout/files."""
    return re.sub(r"EAA[0-9A-Za-z]+", "EAA<redacted>", str(text))


def get(path, params=None, ok_missing_fields=None):
    """GET one Graph API resource. Returns (data, error_dict_or_None).

    ok_missing_fields: optional list of field names to drop and retry once
    with, when the API rejects a field the account/version doesn't support —
    the drop is recorded so the audit shows what was unavailable.
    """
    params = dict(params or {})
    dropped = []
    attempt = 0
    while True:
        qs = urllib.parse.urlencode(params)
        url = BASE + path + ("?" + qs if qs else "")
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + TOKEN,
            "User-Agent": "taqinor-readonly-audit/1.0",
        })  # GET only — no data= ever passed, so urllib cannot POST
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if dropped:
                    data.setdefault("_audit_dropped_fields", dropped)
                return data, None
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode("utf-8")).get("error", {})
            except Exception:
                err = {"message": "HTTP %s" % e.code, "code": e.code}
            code = err.get("code")
            # transient / rate-limit -> backoff and retry a few times
            if code in RETRYABLE_CODES and attempt < 4:
                wait = 2 ** attempt * 15
                log("  rate-limited/transient (code %s) — waiting %ss" % (code, wait))
                time.sleep(wait)
                attempt += 1
                continue
            # unknown-field error -> drop optional fields once and retry
            if code == 100 and ok_missing_fields and "fields" in params:
                fields = params["fields"].split(",")
                keep = [f for f in fields if f.split("{")[0] not in ok_missing_fields]
                if len(keep) < len(fields):
                    dropped += [f for f in fields if f not in keep]
                    params["fields"] = ",".join(keep)
                    ok_missing_fields = None  # only one fallback round
                    continue
            return None, {"path": path, "error": redact(err)}
        except Exception as e:  # DNS, TLS, timeout...
            if attempt < 3:
                time.sleep(2 ** attempt * 5)
                attempt += 1
                continue
            return None, {"path": path, "error": redact(repr(e))}


def get_all(path, params=None, limit_pages=200, **kw):
    """GET with cursor pagination. Returns (rows, errors)."""
    params = dict(params or {})
    params.setdefault("limit", 100)
    rows, errors = [], []
    pages = 0
    while pages < limit_pages:
        data, err = get(path, params, **kw)
        if err:
            errors.append(err)
            break
        rows.extend(data.get("data", []))
        after = (data.get("paging", {}).get("cursors", {}) or {}).get("after")
        if not after or not data.get("data"):
            break
        params["after"] = after
        pages += 1
        time.sleep(0.2)  # stay far from rate limits
    return rows, errors


def parse_env_file(path):
    vals = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    vals[k.strip()] = v.strip().strip('"').strip("'")
    except OSError as e:
        log("WARN: cannot read env file %s: %s" % (path, e))
    return vals


def lead_age_days(created_time, now):
    try:
        dt = datetime.strptime(created_time[:19], "%Y-%m-%dT%H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        return (now - dt).days
    except Exception:
        return None


def slug(s):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s or "")[:40] or "unnamed"


def main():
    global TOKEN
    ap = argparse.ArgumentParser(description="READ-ONLY Meta Ads audit")
    ap.add_argument("--token", help="access token (else META_SYSTEM_USER_TOKEN/ACCESS_TOKEN)")
    ap.add_argument("--env-file", help=".env file to read the token from (e.g. /opt/taqinor-os/.env)")
    ap.add_argument("--out", default="meta_audit_output", help="output directory")
    args = ap.parse_args()

    envf = parse_env_file(args.env_file) if args.env_file else {}
    TOKEN = (args.token or os.environ.get("META_SYSTEM_USER_TOKEN")
             or os.environ.get("ACCESS_TOKEN")
             or envf.get("META_SYSTEM_USER_TOKEN") or envf.get("ACCESS_TOKEN"))
    if not TOKEN:
        sys.exit("No token. Pass --token, set META_SYSTEM_USER_TOKEN, or --env-file /opt/taqinor-os/.env")

    os.makedirs(args.out, exist_ok=True)
    now = datetime.now(timezone.utc)
    audit = {"generated_at": now.isoformat(), "api_version": API_VERSION,
             "read_only": True, "errors": [], "capability_notes": []}

    # ---- 0. whoami ---------------------------------------------------------
    me, err = get("/me", {"fields": "id,name"})
    if err:
        audit["errors"].append(err)
        log("FATAL: token rejected: %s" % err)
        # still write the file so the failure is documented
        with open(os.path.join(args.out, "audit_data.json"), "w") as fh:
            json.dump(audit, fh, indent=1)
        sys.exit(1)
    audit["token_identity"] = me
    log("Authenticated as: %s (id %s)" % (me.get("name"), me.get("id")))

    # ---- 1. inventory: ad accounts ----------------------------------------
    log("\n[1/6] Ad accounts...")
    accounts, errs = get_all("/me/adaccounts", {
        "fields": "id,account_id,name,account_status,currency,timezone_name,"
                  "amount_spent,spend_cap,created_time"})
    audit["errors"] += errs
    audit["ad_accounts"] = accounts
    log("  %d ad account(s)" % len(accounts))

    # ---- 2. inventory: pages (with page tokens for lead reads) ------------
    log("[2/6] Pages...")
    pages, errs = get_all("/me/accounts", {
        "fields": "id,name,category,link,access_token,tasks"},
        ok_missing_fields=["access_token", "tasks"])
    audit["errors"] += errs
    audit["pages"] = [{k: v for k, v in p.items() if k != "access_token"}
                      for p in pages]  # tokens never persisted to disk
    log("  %d page(s)" % len(pages))

    # ---- 3. inventory: pixels/datasets per account -------------------------
    log("[3/6] Pixels / datasets...")
    audit["pixels"] = []
    for acct in accounts:
        pixels, errs = get_all("/%s/adspixels" % acct["id"], {
            "fields": "id,name,last_fired_time,creation_time,is_unavailable"},
            ok_missing_fields=["is_unavailable"])
        audit["errors"] += errs
        for px in pixels:
            px["_ad_account"] = acct["id"]
            # firing volume, last 30 days (try known aggregations, read-only)
            since = int((now - timedelta(days=30)).timestamp())
            for agg in ("event", "pixel_fire"):
                stats, serr = get("/%s/stats" % px["id"],
                                  {"aggregation": agg, "start_time": since})
                if not serr:
                    px["stats_last_30d_aggregation"] = agg
                    px["stats_last_30d"] = stats.get("data", [])
                    break
            else:
                audit["capability_notes"].append(
                    "pixel %s: /stats not readable with this token" % px["id"])
            # EMQ is not documented as API-readable; probe politely, expect no
            emq, eerr = get("/%s" % px["id"], {"fields": "event_match_quality"})
            if eerr:
                px["event_match_quality"] = None
                audit["capability_notes"].append(
                    "pixel %s: Event Match Quality not exposed via API — read "
                    "it in Events Manager UI (capability gap)" % px["id"])
            else:
                px["event_match_quality"] = emq.get("event_match_quality")
        audit["pixels"] += pixels
    log("  %d pixel(s)/dataset(s)" % len(audit["pixels"]))

    # ---- 4. campaigns (ALL, active + paused) -------------------------------
    log("[4/6] Campaigns...")
    audit["campaigns"] = []
    for acct in accounts:
        camps, errs = get_all("/%s/campaigns" % acct["id"], {
            "fields": "id,name,status,effective_status,objective,daily_budget,"
                      "lifetime_budget,budget_remaining,start_time,stop_time,"
                      "created_time,buying_type,special_ad_categories"})
        audit["errors"] += errs
        for c in camps:
            c["_ad_account"] = acct["id"]
            c["_account_currency"] = acct.get("currency")
        audit["campaigns"] += camps
    active = [c for c in audit["campaigns"] if c.get("effective_status") == "ACTIVE"]
    log("  %d campaign(s), %d ACTIVE" % (len(audit["campaigns"]), len(active)))

    # ---- 5. deep-dive on ACTIVE campaigns ----------------------------------
    log("[5/6] 30-day deep-dive on active campaign(s)...")
    audit["active_campaign_details"] = []
    ins_fields = ("spend,impressions,reach,frequency,clicks,ctr,cpc,cpm,"
                  "actions,cost_per_action_type,inline_link_clicks,"
                  "results,cost_per_result")
    for c in active:
        detail = {"campaign_id": c["id"], "campaign_name": c.get("name")}
        ins, errs = get_all("/%s/insights" % c["id"], {
            "date_preset": "last_30d", "fields": ins_fields},
            ok_missing_fields=["results", "cost_per_result"])
        detail["insights_last_30d"] = ins
        audit["errors"] += errs
        adsets, errs = get_all("/%s/adsets" % c["id"], {
            "fields": "id,name,status,effective_status,daily_budget,"
                      "lifetime_budget,optimization_goal,billing_event,"
                      "bid_strategy,destination_type,promoted_object,"
                      "targeting,start_time,attribution_spec",
        }, ok_missing_fields=["destination_type", "attribution_spec"])
        detail["adsets"] = adsets
        audit["errors"] += errs
        ads, errs = get_all("/%s/ads" % c["id"], {
            "fields": "id,name,status,effective_status,"
                      "creative{id,name,title,body,object_story_spec,"
                      "asset_feed_spec,image_url,thumbnail_url,video_id,"
                      "call_to_action_type,instagram_permalink_url}"})
        if errs:  # nested creative fetch can fail -> flat fallback
            audit["errors"] += errs
            ads, errs2 = get_all("/%s/ads" % c["id"],
                                 {"fields": "id,name,status,effective_status,creative"})
            audit["errors"] += errs2
            for ad in ads:
                cid = (ad.get("creative") or {}).get("id")
                if cid:
                    cr, cerr = get("/%s" % cid, {
                        "fields": "id,name,title,body,object_story_spec,"
                                  "image_url,thumbnail_url,call_to_action_type"})
                    if cr:
                        ad["creative"] = cr
                    if cerr:
                        audit["errors"].append(cerr)
        detail["ads"] = ads
        audit["active_campaign_details"].append(detail)
        log("  campaign %s: %d adset(s), %d ad(s)" %
            (c.get("name"), len(adsets), len(ads)))

    # ---- 6. Instant Forms + FULL lead export -------------------------------
    log("[6/6] Instant Forms + lead export (90-day retention — exporting all)...")
    audit["leadgen"] = []
    csv_files = []
    total_leads = urgent_leads = 0
    for page in pages:
        # lead reads work best with the page's own token when available
        page_token = page.get("access_token")
        token_note = "page token" if page_token else "system-user token"
        prev_token = TOKEN
        if page_token:
            TOKEN = page_token
        forms, errs = get_all("/%s/leadgen_forms" % page["id"], {
            "fields": "id,name,status,created_time,locale,questions,"
                      "leads_count,expired_leads_count,follow_up_action_url"},
            ok_missing_fields=["leads_count", "expired_leads_count",
                               "follow_up_action_url"])
        audit["errors"] += errs
        page_entry = {"page_id": page["id"], "page_name": page.get("name"),
                      "token_used": token_note, "forms": []}
        for form in forms:
            leads, errs = get_all("/%s/leads" % form["id"], {
                "fields": "id,created_time,ad_id,ad_name,adset_name,"
                          "campaign_name,is_organic,platform,field_data"},
                ok_missing_fields=["ad_name", "adset_name", "campaign_name",
                                  "platform"])
            audit["errors"] += errs
            # CSV: flatten field_data into columns
            qcols = []
            for ld in leads:
                for fd in ld.get("field_data", []):
                    if fd.get("name") not in qcols:
                        qcols.append(fd.get("name"))
            fname = "leads_%s_%s_%s.csv" % (page["id"], form["id"], slug(form.get("name")))
            fpath = os.path.join(args.out, fname)
            n_urgent = 0
            with open(fpath, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["lead_id", "created_time", "age_days",
                            "urgent_over_%dd" % URGENT_LEAD_AGE_DAYS,
                            "days_until_meta_deletes", "campaign_name",
                            "ad_name", "is_organic", "platform"] + qcols)
                for ld in leads:
                    age = lead_age_days(ld.get("created_time", ""), now)
                    urgent = age is not None and age > URGENT_LEAD_AGE_DAYS
                    n_urgent += 1 if urgent else 0
                    answers = {fd.get("name"): "; ".join(fd.get("values", []))
                               for fd in ld.get("field_data", [])}
                    w.writerow([ld.get("id"), ld.get("created_time"), age,
                                "URGENT" if urgent else "",
                                (90 - age) if age is not None else "",
                                ld.get("campaign_name", ""), ld.get("ad_name", ""),
                                ld.get("is_organic", ""), ld.get("platform", "")]
                               + [answers.get(q, "") for q in qcols])
            total_leads += len(leads)
            urgent_leads += n_urgent
            csv_files.append((fpath, len(leads), n_urgent))
            page_entry["forms"].append({
                "form_id": form["id"], "name": form.get("name"),
                "status": form.get("status"), "created_time": form.get("created_time"),
                "questions": form.get("questions"),
                "leads_count_reported_by_meta": form.get("leads_count"),
                "expired_leads_count": form.get("expired_leads_count"),
                "leads_exported": len(leads), "leads_urgent_over_60d": n_urgent,
                "csv_file": fname})
            log("  form '%s': %d leads exported (%d URGENT >60d) -> %s"
                % (form.get("name"), len(leads), n_urgent, fname))
        TOKEN = prev_token
        audit["leadgen"].append(page_entry)

    # ---- write outputs -----------------------------------------------------
    data_path = os.path.join(args.out, "audit_data.json")
    with open(data_path, "w", encoding="utf-8") as fh:
        json.dump(audit, fh, indent=1, ensure_ascii=False)

    lines = ["# Meta audit data digest — generated %s (UTC)" % now.strftime("%Y-%m-%d %H:%M"),
             "", "PII-free digest. Paste this file into docs/engine/audit-2026-07.md "
             "data sections. Lead CSVs stay LOCAL (never commit).", ""]
    lines.append("## Ad accounts (%d)" % len(accounts))
    for a in accounts:
        lines.append("- %s (%s) — status %s, currency %s, lifetime spend %s" % (
            a.get("name"), a.get("id"), a.get("account_status"),
            a.get("currency"), a.get("amount_spent")))
    lines.append("\n## Pages (%d)" % len(pages))
    for p in audit["pages"]:
        lines.append("- %s (%s) — %s" % (p.get("name"), p.get("id"), p.get("category")))
    lines.append("\n## Pixels/datasets (%d)" % len(audit["pixels"]))
    for px in audit["pixels"]:
        fired = px.get("last_fired_time") or "NEVER"
        vol = sum(int(d.get("count", 0)) for d in px.get("stats_last_30d", []) or [])
        lines.append("- %s (%s) — last fired %s, ~%s events in 30d, EMQ: %s" % (
            px.get("name"), px.get("id"), fired, vol or "0/unknown",
            px.get("event_match_quality") or "not API-readable (see Events Manager)"))
    lines.append("\n## Campaigns (%d total, %d active)" % (len(audit["campaigns"]), len(active)))
    for c in audit["campaigns"]:
        budget = c.get("daily_budget") or c.get("lifetime_budget") or "?"
        lines.append("- [%s] %s — objective %s, daily budget (minor units) %s, start %s" % (
            c.get("effective_status"), c.get("name"), c.get("objective"),
            budget, c.get("start_time", "")[:10]))
    for d in audit["active_campaign_details"]:
        lines.append("\n## Active campaign deep-dive: %s" % d["campaign_name"])
        for row in d["insights_last_30d"]:
            for k in ("spend", "impressions", "reach", "frequency", "ctr",
                      "cpc", "cpm", "results", "cost_per_result"):
                if k in row:
                    lines.append("- %s: %s" % (k, json.dumps(row[k], ensure_ascii=False)))
            for act in row.get("actions", []) or []:
                lines.append("- action %s: %s" % (act.get("action_type"), act.get("value")))
            for act in row.get("cost_per_action_type", []) or []:
                lines.append("- cost per %s: %s" % (act.get("action_type"), act.get("value")))
        for s in d["adsets"]:
            lines.append("- adset '%s': goal %s, destination %s, daily budget %s" % (
                s.get("name"), s.get("optimization_goal"),
                s.get("destination_type", "?"), s.get("daily_budget")))
            tgt = s.get("targeting") or {}
            geo = tgt.get("geo_locations", {})
            lines.append("  targeting: geo %s, age %s-%s, advantage_audience=%s" % (
                json.dumps(geo, ensure_ascii=False)[:200], tgt.get("age_min"),
                tgt.get("age_max"),
                (tgt.get("targeting_automation") or {}).get("advantage_audience")))
        for ad in d["ads"]:
            cr = ad.get("creative") or {}
            lines.append("- ad '%s' [%s] creative: title=%r body=%r cta=%s" % (
                ad.get("name"), ad.get("effective_status"),
                (cr.get("title") or "")[:80], (cr.get("body") or "")[:120],
                cr.get("call_to_action_type")))
    lines.append("\n## Instant Forms + lead export")
    lines.append("- TOTAL leads exported: %d (URGENT >60 days old: %d)" % (total_leads, urgent_leads))
    for pg in audit["leadgen"]:
        for f in pg["forms"]:
            lines.append("- page '%s' form '%s' [%s]: %d exported / %s reported, "
                         "%d urgent, questions: %s -> %s" % (
                pg["page_name"], f["name"], f["status"], f["leads_exported"],
                f.get("leads_count_reported_by_meta"), f["leads_urgent_over_60d"],
                ", ".join((q.get("label") or q.get("key") or "?")
                          for q in (f.get("questions") or [])), f["csv_file"]))
    if audit["capability_notes"]:
        lines.append("\n## Capability notes")
        lines += ["- " + n for n in audit["capability_notes"]]
    if audit["errors"]:
        lines.append("\n## Errors encountered (read-only probes that failed)")
        lines += ["- " + json.dumps(e, ensure_ascii=False)[:300] for e in audit["errors"]]

    summary_path = os.path.join(args.out, "audit_summary.md")
    with open(summary_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    log("\n" + "=" * 60)
    log("DONE (read-only — nothing on Meta was modified).")
    log("Full data : %s" % data_path)
    log("Digest    : %s  <- paste this back for the audit doc" % summary_path)
    for fpath, n, nu in csv_files:
        log("Leads CSV : %s (%d leads, %d URGENT)" % (fpath, n, nu))
    log("TOTAL leads exported: %d — URGENT (>60d, deleted at 90d): %d"
        % (total_leads, urgent_leads))
    if urgent_leads:
        log("!! %d lead(s) older than 60 days — Meta deletes at 90 days. "
            "The CSVs above are now the only durable copy." % urgent_leads)


if __name__ == "__main__":
    main()

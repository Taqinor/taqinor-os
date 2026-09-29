# -*- coding: utf-8 -*-
"""READ-ONLY document-consistency auditor (prototype) — run via
``python manage.py shell < doc_consistency_audit.py``.

For every Devis it rebuilds what the client documents would print
(builder.build_quote_data -> residential.renderer.synthese_economies/_augment)
and checks cross-figure invariants. Everything runs inside ONE
transaction.atomic() that is ALWAYS rolled back (set_rollback(True)); each
devis is further isolated in a savepoint. Nothing is saved/updated/deleted;
no network image fetches (roof photo patched to '' in this process only).

Output: human-readable report + one line ``AUDIT_JSON <json>``.
"""
import json
import math
import time
import traceback
from collections import Counter, defaultdict

from django.db import transaction

T0 = time.time()

from apps.ventes.models import Devis  # noqa: E402
from apps.ventes.quote_engine import builder as B  # noqa: E402
from apps.ventes.quote_engine.residential import renderer as R  # noqa: E402

# Audit never needs the roof photo (MinIO GET per devis) — patched in THIS
# shell process only; nothing on disk changes.
B._roof_photo_data_uri = lambda devis: ""

# ── Explicit tolerances ─────────────────────────────────────────────────────
TOL = {
    "I1_coverage_vs_hourly_pts": 2,        # |donut - hourly couverture| (pts)
    "I2_linear_upper_pts": 1,              # pct_cut <= coverage + 1 in top tranche
    "I2_linear_lower_slack_pts": 2,        # pct_cut >= cov*(1-fixed share) - 2
    "I3_conso_vs_hourly_ratio": 0.10,      # stored conso_annuelle / hourly conso
    "I4_fallback_kwh": 12,                 # conso == bills/1.20 (+-12 kWh)
    "I4_flat_price": 1.20,
    "I5_bill_ratio": 0.10,                 # printed current bill / real bills
    "I6_payback_ratio": 0.30,              # printed payback vs price/savings
    "I7_kwc_ratio": 0.02,                  # hourly block kWc vs quote kWc
    "I9_conso_js_vs_py_ratio": 0.03,       # stored (JS) conso vs Python bareme
    "I10_savings_pct": 0.03,               # two annual-savings figures
    "I11_pct_cut_pts": 2,                  # -N % vs method-block example
    "I12_parity_pts": 0,                   # PDF vs public synthese (exact)
}
MAX_EX = 5
STATUT_RANK = {"envoye": 0, "accepte": 1, "expire": 2, "refuse": 3,
               "brouillon": 4}


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def frac(v):
    f = num(v)
    return f if (f is not None and 0 < f <= 1) else None


def clamp_pct(x):
    return min(100, max(1, round(x)))


def pctl(values, q):
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 3)


def dist(values):
    if not values:
        return {"n": 0}
    return {"n": len(values), "min": round(min(values), 3),
            "p05": pctl(values, .05), "p25": pctl(values, .25),
            "p50": pctl(values, .5), "p75": pctl(values, .75),
            "p95": pctl(values, .95), "max": round(max(values), 3)}


def walk_bad_numbers(obj, path="", out=None, depth=0):
    """NaN/inf anywhere in the data dict (fields that reach a client doc)."""
    if out is None:
        out = []
    if depth > 6 or len(out) > 5:
        return out
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            out.append(path)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("etude", "roof_layout", "electrical_design"):
                continue
            walk_bad_numbers(v, f"{path}.{k}", out, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj[:60]):
            walk_bad_numbers(v, f"{path}[{i}]", out, depth + 1)
    return out


# ── Tariff context (top-tranche start + fixed charges), per company ─────────
_TARIF_CACHE = {}


def tariff_ctx(company):
    key = getattr(company, "pk", None)
    if key in _TARIF_CACHE:
        return _TARIF_CACHE[key]
    ctx = {"tranches": None, "charges_fixes": None, "top_start": 510.0,
           "fixed_mois": 40.0, "src": "fallback"}
    try:
        from apps.ventes.etude_horaire import (_reglages_tarifaires,
                                               part_non_solarisable)
        tr, cf = _reglages_tarifaires(company)
        ctx["tranches"], ctx["charges_fixes"] = tr, cf
        table = tr
        if table is None:
            from apps.ventes.quote_engine import pricing as P
            table = getattr(P, "ONEE_TRANCHES", None)
        ceils = []
        for e in (table or []):
            try:
                c = float(e[0])
                if c < 1e6:
                    ceils.append(c)
            except Exception:  # noqa: BLE001
                continue
        if ceils:
            ctx["top_start"] = max(ceils)
            ctx["src"] = "tranches"
        try:
            ctx["fixed_mois"] = float(
                part_non_solarisable(cf)["montant_mad_mois"])
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001
        pass
    _TARIF_CACHE[key] = ctx
    return ctx


def real_bills(devis, ep):
    """(12 MAD/month bills actually given by the client, source) or (None, None)."""
    fm = ep.get("factures_mensuelles_reelles")
    if isinstance(fm, (list, tuple)) and len(fm) == 12:
        vals = [num(v) for v in fm]
        if all(v is not None and v > 0 for v in vals):
            return vals, "factures_mensuelles_reelles"
    try:
        from apps.crm.selectors import lead_bills_for_devis
        from apps.ventes.etude_horaire import serie_mad_mensuelle
        b = lead_bills_for_devis(devis) or {}
        serie = serie_mad_mensuelle(b.get("facture_hiver"),
                                    b.get("facture_ete"),
                                    b.get("ete_differente"))
        if serie:
            return [float(v) for v in serie], "lead_hiver_ete"
    except Exception:  # noqa: BLE001
        pass
    return None, None


def py_conso_from_bills(bills, ctx):
    try:
        from apps.ventes.etude_horaire import serie_kwh_depuis_mad
        kwh, _detail = serie_kwh_depuis_mad(
            bills, tranches=ctx["tranches"],
            charges_fixes_mad=ctx["charges_fixes"])
        if kwh:
            return float(sum(kwh))
    except Exception:  # noqa: BLE001
        return None
    return None


def printed_layer(data):
    """What the residential PDF page 1 would print, or None if legacy/omitted."""
    try:
        d = R._augment(data)
    except R.Unsupported:
        return None, "legacy_renderer"
    except Exception as e:  # noqa: BLE001
        return None, f"augment_error:{type(e).__name__}"
    if d.get("masquer_synthese") or d.get("masquer_economies"):
        return None, "economic_layer_omitted"
    if d.get("coverage_pct") is None:
        return None, "no_synthese"
    return d, "printed"


# ── Accumulators ────────────────────────────────────────────────────────────
INV = {
    "I1": "donut coverage_pct vs hourly engine couverture (horaire model, printed)",
    "I2": "pct_cut vs coverage in linear top-tranche regime (printed)",
    "I3": "stored conso_annuelle vs hourly engine consommation_kwh (+-10%)",
    "I4": "fallback signature: conso_annuelle == sum(real bills)/1.20 (+-12 kWh)",
    "I5": "printed 'facture actuelle' vs sum of client's real bills (+-10%)",
    "I6a": "annual savings > printed current bill (or <=0)",
    "I6b": "printed payback vs price_ttc/annual savings outside +-30%",
    "I6c": "NaN/inf or negative in client-facing numbers",
    "I7": "stale hourly block: block kWc vs quote kWc > 2% (silent fallback)",
    "I7b": "hourly block present but a column is NOT priced 'horaire' (any reason)",
    "I8": "PDF (last-render options) synthese vs public proposal synthese",
    "I9": "JS mirror: stored conso_annuelle vs Python bareme inversion of same bills (+-3%)",
    "I10": "page-1 monthly-chart savings total vs option-card annual savings (+-3%)",
    "I11": "page-1 '-N %' vs method-block example (facture actuelle -> avec solaire) (+-2 pts)",
}
flags = defaultdict(list)       # inv -> list of example dicts
flag_ids = defaultdict(set)     # inv -> devis ids
checked = Counter()             # inv -> devis evaluated
dists = defaultdict(list)
exceptions = Counter()
exc_examples = defaultdict(list)
stats = Counter()


def flag(inv, devis, **vals):
    flag_ids[inv].add(devis.pk)
    flags[inv].append({"ref": devis.reference, "statut": devis.statut,
                       "mode": devis.mode_installation or "", **vals})


def safe_build(devis, opts=None, tag="build"):
    try:
        with transaction.atomic():
            return B.build_quote_data(devis, opts)
    except Exception as e:  # noqa: BLE001
        exceptions[f"{tag}:{type(e).__name__}"] += 1
        if len(exc_examples[tag]) < 3:
            exc_examples[tag].append(
                f"{devis.reference}: {type(e).__name__}: {str(e)[:160]}")
        return None


def audit_one(devis):
    ep = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    mode = (devis.mode_installation or "").strip().lower()
    resid = R.is_residential(devis, {"pdf_mode": "full"})
    ctx = tariff_ctx(getattr(devis, "company", None))

    data = safe_build(devis, None, "build_default")
    if data is None:
        return
    stats["built"] += 1

    # ── hourly engine block (stored) ─────────────────────────────────────
    eh = ep.get("etude_horaire") if isinstance(ep.get("etude_horaire"), dict) else None
    an = (eh or {}).get("annuel") if isinstance((eh or {}).get("annuel"), dict) else {}
    conso_h = num(an.get("consommation_kwh"))
    couv_s, couv_a = frac(an.get("couverture_sans")), frac(an.get("couverture_avec"))
    kwc_bloc = num((eh or {}).get("kwc"))

    avec = bool(data.get("deux_options", True)) or bool(data.get("avec_ok", True))
    opt = "avec" if avec else "sans"
    model_opt = data.get(f"savings_model_{opt}")
    conso_st = num(ep.get("conso_annuelle"))
    bills, bills_src = real_bills(devis, ep)
    bills_sum = sum(bills) if bills else None

    printed, why = (None, "not_residential")
    synth = None
    if resid:
        try:
            synth = R.synthese_economies(data)
        except Exception as e:  # noqa: BLE001
            exceptions[f"synthese:{type(e).__name__}"] += 1
        printed, why = printed_layer(data)
    stats[f"page1:{why}"] += 1

    # ── I1 donut vs hourly engine ────────────────────────────────────────
    if printed and model_opt == "horaire":
        if opt == "avec":
            c = couv_s if data.get("avec_batterie_differee") else (
                max(couv_a, couv_s) if (couv_a and couv_s) else couv_a)
        else:
            c = couv_s
        if c is not None:
            checked["I1"] += 1
            exp = clamp_pct(c * 100)
            got = printed.get("coverage_pct")
            dists["I1_diff_pts"].append(got - exp)
            if abs(got - exp) > TOL["I1_coverage_vs_hourly_pts"]:
                flag("I1", devis, donut=got, hourly=exp,
                     pct_cut=printed.get("pct_cut"),
                     conso_annuelle=conso_st, conso_hourly=conso_h)

    # ── I2 coverage vs pct_cut in the linear (top-tranche) regime ────────
    if printed and conso_h and isinstance((eh or {}).get("mois"), list):
        auto_key = f"autoconsomme_{opt}_kwh"
        if opt == "avec" and data.get("avec_batterie_differee"):
            auto_key = "autoconsomme_sans_kwh"
        mins = []
        for m in eh["mois"]:
            cm, am = num((m or {}).get("consommation_kwh")), num((m or {}).get(auto_key))
            if cm is None or am is None:
                mins = []
                break
            mins.append(cm - am)
        if len(mins) == 12:
            cov, cut = printed["coverage_pct"], printed["pct_cut"]
            ab = num(printed.get("annual_before")) or 0
            fs = min(0.5, 12 * ctx["fixed_mois"] / ab) if ab > 0 else 0
            if min(mins) > ctx["top_start"]:
                checked["I2"] += 1
                dists["I2_cut_minus_cov_linear"].append(cut - cov)
                lo = cov * (1 - fs) - TOL["I2_linear_lower_slack_pts"]
                hi = cov + TOL["I2_linear_upper_pts"]
                if not (lo <= cut <= hi):
                    flag("I2", devis, coverage=cov, pct_cut=cut,
                         allowed=[round(lo, 1), hi],
                         min_month_after_kwh=round(min(mins)),
                         fixed_share=round(fs, 3))
            else:
                dists["I2_cut_minus_cov_nonlinear"].append(cut - cov)

    # ── I3 stored conso vs hourly conso ──────────────────────────────────
    if conso_st and conso_h:
        checked["I3"] += 1
        r = conso_st / conso_h
        dists["I3_ratio"].append(r)
        if abs(r - 1) > TOL["I3_conso_vs_hourly_ratio"]:
            flag("I3", devis, conso_annuelle=round(conso_st),
                 conso_hourly=round(conso_h), ratio=round(r, 3),
                 hourly_used=(model_opt == "horaire"))

    # ── I4 fallback signature (bills / 1.20) ─────────────────────────────
    if conso_st and bills_sum and bills_src == "factures_mensuelles_reelles":
        checked["I4"] += 1
        fb = bills_sum / TOL["I4_flat_price"]
        if abs(conso_st - fb) <= TOL["I4_fallback_kwh"]:
            flag("I4", devis, conso_annuelle=round(conso_st),
                 bills_sum=round(bills_sum), bills_div_1_20=round(fb),
                 distributeur=ep.get("distributeur"),
                 conso_hourly=(round(conso_h) if conso_h else None))

    # ── I9 JS-derived stored conso vs Python bareme inversion ────────────
    if conso_st and bills and bills_src == "factures_mensuelles_reelles":
        py = py_conso_from_bills(bills, ctx)
        if py:
            checked["I9"] += 1
            r = conso_st / py
            dists["I9_ratio"].append(r)
            if abs(r - 1) > TOL["I9_conso_js_vs_py_ratio"]:
                flag("I9", devis, conso_stored_js=round(conso_st),
                     conso_python=round(py), ratio=round(r, 3),
                     fallback_1_20=abs(conso_st - bills_sum / 1.2) <= 12)

    # ── I5 printed current bill vs real bills ────────────────────────────
    if bills_sum:
        sm = data.get("savings_method") or {}
        cands = {
            "page1_annual_before": (printed or {}).get("annual_before"),
            "method_facture_actuelle": sm.get("facture_actuelle"),
            "facture_sans_solaire": data.get("facture_sans_solaire"),
        }
        any_checked = False
        for k, v in cands.items():
            v = num(v)
            if not v:
                continue
            any_checked = True
            r = v / bills_sum
            dists[f"I5_ratio_{k}"].append(r)
            if abs(r - 1) > TOL["I5_bill_ratio"]:
                flag("I5", devis, figure=k, printed=round(v),
                     real_bills=round(bills_sum), bills_src=bills_src,
                     ratio=round(r, 3), model=data.get("savings_model"))
        if any_checked:
            checked["I5"] += 1

    # ── I6 sanity: savings <= bill, payback, negatives, NaN ─────────────
    if not data.get("masquer_economies") and not (resid and why == "economic_layer_omitted"):
        checked["I6"] += 1
        fa = num((data.get("savings_method") or {}).get("facture_actuelle")) \
            or num(data.get("facture_sans_solaire"))
        for o, eco_k, roi_k, tot_k, ok_k in (
                ("sans", "eco_s_ann", "roi_s", "total_sans", "sans_ok"),
                ("avec", "eco_a_ann", "roi_a", "total_avec", "avec_ok")):
            if not data.get(ok_k):
                continue
            eco, roi, tot = num(data.get(eco_k)), num(data.get(roi_k)), num(data.get(tot_k))
            if eco is None or eco <= 0:
                if data.get(eco_k) is not None:
                    flag("I6a", devis, option=o, eco=data.get(eco_k), why="eco<=0")
                continue
            if fa and eco > fa * 1.001:
                flag("I6a", devis, option=o, eco=round(eco),
                     facture_actuelle=round(fa), why="eco>bill")
            if roi and tot:
                simple = tot / eco
                r = roi / simple
                dists[f"I6b_roi_over_simple"].append(r)
                if abs(r - 1) > TOL["I6_payback_ratio"]:
                    flag("I6b", devis, option=o, payback=roi,
                         price_over_savings=round(simple, 2),
                         ratio=round(r, 2), model=data.get(f"savings_model_{o}"))
        bad = walk_bad_numbers(data)
        negs = [k for k in ("prod_kwh", "eco_s_ann", "eco_a_ann", "roi_s",
                            "roi_a", "total_sans", "total_avec")
                if (num(data.get(k)) or 0) < 0]
        if printed:
            if printed.get("annual_after", 0) < 0 or not (0 <= printed.get("pct_cut", 0) <= 100):
                negs.append("page1_after_or_pct_cut")
        if bad or negs:
            flag("I6c", devis, nan_paths=bad[:3], negative=negs)

    # ── I7 stale hourly block / silent downgrade ─────────────────────────
    if eh:
        checked["I7"] += 1
        kwcs = {"doc": num(data.get("puissance_kwc"))}
        if data.get("panneaux_divergents"):
            kwcs["sans"] = num(data.get("puissance_kwc_sans"))
            kwcs["avec"] = num(data.get("puissance_kwc_avec"))
        worst = None
        for k, v in kwcs.items():
            if v and kwc_bloc:
                d = abs(kwc_bloc - v) / v
                if worst is None or d > worst[1]:
                    worst = (k, d, v)
        if worst and worst[1] > TOL["I7_kwc_ratio"]:
            flag("I7", devis, block_kwc=kwc_bloc, quote_kwc=worst[2],
                 which=worst[0], delta=round(worst[1], 3),
                 model_sans=data.get("savings_model_sans"),
                 model_avec=data.get("savings_model_avec"))
        ms, ma = data.get("savings_model_sans"), data.get("savings_model_avec")
        if (data.get("sans_ok") and ms != "horaire") or (data.get("avec_ok") and ma != "horaire"):
            flag("I7b", devis, model_sans=ms, model_avec=ma,
                 block_kwc=kwc_bloc, quote_kwc=kwcs["doc"])

    # ── I10 / I11 same-page cross figures (page 1 vs option card / method) ─
    if printed:
        eco_card = num(data.get("eco_a_ann" if opt == "avec" else "eco_s_ann"))
        tot_chart = num(printed.get("eco_mensuelles_total"))
        if eco_card and tot_chart:
            checked["I10"] += 1
            r = tot_chart / eco_card
            dists["I10_ratio"].append(r)
            if abs(r - 1) > TOL["I10_savings_pct"]:
                flag("I10", devis, chart_total=round(tot_chart),
                     option_card=round(eco_card), option=opt, ratio=round(r, 3),
                     bills_source=data.get("factures_source"))
        sm = data.get("savings_method") or {}
        fa, fs_ = num(sm.get("facture_actuelle")), num(sm.get("facture_avec_solaire"))
        if fa and fs_ is not None:
            checked["I11"] += 1
            cut_m = round((1 - fs_ / fa) * 100)
            dists["I11_diff_pts"].append(printed["pct_cut"] - cut_m)
            if abs(printed["pct_cut"] - cut_m) > TOL["I11_pct_cut_pts"]:
                flag("I11", devis, page1_pct_cut=printed["pct_cut"],
                     method_block_pct=cut_m, facture_actuelle=round(fa),
                     avec_solaire=round(fs_), scenario=data.get("scenario"))

    # ── I8 PDF (last-render options) vs public proposal (pdf_mode full) ─
    if resid:
        meta = devis.pdf_render_meta if isinstance(devis.pdf_render_meta, dict) else {}
        opts = meta.get("options") if isinstance(meta.get("options"), dict) else None
        if opts is None:
            stats["I8:no_pdf_render_meta"] += 1
        elif not R.is_residential(devis, opts):
            stats["I8:last_pdf_not_residential_layout"] += 1
        else:
            d_pdf = safe_build(devis, opts, "build_pdf_opts")
            d_pub = safe_build(devis, {"pdf_mode": "full"}, "build_public")
            if d_pdf is not None and d_pub is not None:
                checked["I8"] += 1
                s_pdf = R.synthese_economies(d_pdf)
                s_pub = R.synthese_economies(d_pub)
                p_pdf, _ = printed_layer(d_pdf)
                keys = ("pct_cut", "coverage_pct", "annual_before",
                        "annual_after", "eco_option")
                diffs = {}
                if (s_pdf is None) != (s_pub is None):
                    diffs["presence"] = [s_pdf is not None, s_pub is not None]
                elif s_pdf and s_pub:
                    for k in keys:
                        if s_pdf.get(k) != s_pub.get(k):
                            diffs[k] = [s_pdf.get(k), s_pub.get(k)]
                for k in ("eco_s_ann", "eco_a_ann", "roi_s", "roi_a",
                          "total_sans", "total_avec"):
                    if d_pdf.get(k) != d_pub.get(k):
                        diffs[k] = [d_pdf.get(k), d_pub.get(k)]
                if diffs:
                    flag("I8", devis, pdf_opts={k: opts.get(k) for k in
                                                ("scenario", "pdf_mode", "variante_option")
                                                if opts.get(k) is not None},
                         diffs=diffs, pdf_page1_printed=p_pdf is not None)


# ── Run ─────────────────────────────────────────────────────────────────────
n_total = 0
with transaction.atomic():
    try:
        qs = (Devis.objects.all()
              .select_related("client", "lead", "company")
              .order_by("pk"))
        for devis in qs.iterator(chunk_size=50):
            n_total += 1
            try:
                with transaction.atomic():
                    audit_one(devis)
            except Exception as e:  # noqa: BLE001
                exceptions[f"audit:{type(e).__name__}"] += 1
                if len(exc_examples["audit"]) < 5:
                    exc_examples["audit"].append(
                        f"{devis.reference}: {type(e).__name__}: {str(e)[:160]} | "
                        + traceback.format_exc().strip().splitlines()[-2][:160])
    finally:
        transaction.set_rollback(True)   # READ-ONLY: never commit anything

runtime = round(time.time() - T0, 1)


def top_examples(lst):
    return sorted(lst, key=lambda x: STATUT_RANK.get(x["statut"], 9))[:MAX_EX]


report = {
    "runtime_s": runtime, "devis_total": n_total, "stats": dict(stats),
    "exceptions": dict(exceptions), "exception_examples": dict(exc_examples),
    "tolerances": TOL,
    "tariff_ctx": {str(k): {"top_start": v["top_start"],
                            "fixed_mois": v["fixed_mois"], "src": v["src"]}
                   for k, v in _TARIF_CACHE.items()},
    "invariants": {},
    "distributions": {k: dist(v) for k, v in dists.items()},
}
for inv, label in INV.items():
    ids = flag_ids.get(inv, set())
    exs = flags.get(inv, [])
    by_statut = Counter(e["statut"] for e in
                        {e["ref"]: e for e in exs}.values())
    report["invariants"][inv] = {
        "rule": label,
        "checked": checked.get(inv[:2] if inv in ("I6a", "I6b", "I6c", "I7b")
                               else inv, 0),
        "flagged_devis": len(ids), "flagged_by_statut": dict(by_statut),
        "examples": top_examples(exs),
    }

print("=" * 78)
print(f"DOCUMENT CONSISTENCY AUDIT — {n_total} devis, {runtime}s, READ-ONLY (rolled back)")
print("stats:", dict(stats))
print("exceptions:", dict(exceptions))
for inv, r in report["invariants"].items():
    print(f"{inv:4s} flagged={r['flagged_devis']:4d} checked={r['checked']:4d} "
          f"{r['flagged_by_statut']}  — {r['rule']}")
_blob = json.dumps(report, default=str, ensure_ascii=False)
try:
    with open("/tmp/doc_consistency_audit.json", "w", encoding="utf-8") as _f:
        _f.write(_blob)
except OSError:
    pass
print("AUDIT_JSON " + _blob)

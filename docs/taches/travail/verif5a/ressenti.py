"""Sollicitations simulees + journal de messages (gabarits de spec §3.10)."""
import random
import statistics
import sys
from datetime import date, timedelta
from sim import *


def fmt1(x):
    return ("%.1f" % x).replace(".", ",")


def t_matin(d, nb_att, N, mode, R):
    v = variante(date.fromordinal(START.toordinal() + d).toordinal())
    if N is None:
        return None  # LIBRE : aucun gabarit dans la spec
    return [f"Ta journée : {nb_att} tâches prévues ou en retard. Objectif {N}.",
            f"Bonjour. {nb_att} tâches t'attendent ; objectif du jour : {N}.",
            f"Plan du jour : choisis ton essentiel (objectif {N})."][v]


def t_relance(kind, d, N, mode, R, c15):
    v = variante(START.toordinal() + d)
    if kind == "echeance":
        return ["1 tâche a son échéance aujourd'hui.", "Échéance aujourd'hui : 1 tâche encore ouverte.",
                "Avant ce soir : 1 tâche à échéance."][v]
    if kind == "derive":
        if mode == "pousser":
            return f"{c15} faites sur {N} ; ton essentiel est encore ouvert."
        lo, hi = bande_tenir(R)
        return f"{c15} faites, ta zone est {int(round(lo))} à {int(round(hi))} : le reste peut attendre demain."
    return "Ton projet prioritaire n'a pas avancé depuis 14 jours."  # phrase C8 (aucun gabarit de relance dans la spec)


def t_soir(d, count, prevues):
    v = variante(START.toordinal() + d)
    return [f"Bilan : {count} faites sur {prevues} prévues.", f"Journée close ? {count} tâches faites.",
            f"{count} faites, {max(0, prevues-count)} à placer."][v]


def t_semaine(days_week, N):
    tot = sum(x["count"] for x in days_week)
    nb = sum(1 for x in days_week if x["statut"] == "evalue")
    return f"Revue : {tot} tâches en {nb} jours évalués."


def notif_sim(out, p_notif, seed, pause_after=14, react=False):
    rng = random.Random(seed + 77)
    days = out["days"]
    ign = dict(matin=0, relance=0, soir=0)
    pause = set()
    neg_until = -1
    rows = []
    for x in days:
        d = x["d"]
        sent = []
        if not x["ouvre"] or x["conge"]:
            rows.append((d, sent))
            continue
        N, mode, R = x["N"], x["mode"], x["R"]
        if neg_until < d and rng.random() < 0.03:
            neg_until = d + rng.randint(14, 28)
        # matin
        plan_avant = (x["statut"] == "evalue") and rng.random() < 0.25
        nb_att = max(1, (N or 5) + rng.randint(0, 3))
        if not plan_avant and "matin" not in pause:
            tx = t_matin(d, nb_att, N, mode, R) or f"Ta journée : {nb_att} tâches prévues ou en retard."
            sent.append(("matin", "08:30", tx))
        # relance
        c = {}
        if rng.random() < 0.125:
            c["echeance"] = 1
        c15 = int(x["count"] * rng.uniform(0.3, 0.7))
        if mode == "pousser" and N is not None and derive_pousser_journee(c15, N, bool(x["ee"])) and x["statut"] == "evalue":
            c["derive"] = 1
        if mode == "tenir" and R is not None and c15 >= bande_tenir(R)[1]:
            c["derive"] = 1
        if mode != "libre" and neg_until >= d:
            c["negligé"] = 1
        if mode == "libre":
            c.pop("derive", None); c.pop("negligé", None)
        kind = choisir_relance(set(c))
        if kind and "relance" not in pause:
            sent.append(("relance", "15:00", t_relance(kind, d, N, mode, R, c15)))
        # soir
        if x["statut"] == "evalue" and (x["count"] >= 1 or rng.random() < 0.85) and "soir" not in pause:
            last_day = (d % 7 == 4) or (d % 7 < 4 and not any(days[j]["ouvre"] and not days[j]["conge"] for j in range(d + 1, min(len(days), d + (5 - d % 7)))) if False else d % 7 == 4)
            if last_day:
                sent.append(("soir", "18:00", "Du %s au %s : %d tâches en %d jours. Journées réussies %d sur %d." % (
                    (START + timedelta(d - 4)).strftime("%d/%m"), (START + timedelta(d)).strftime("%d/%m"),
                    sum(y["count"] for y in days[max(0, d - 4):d + 1]),
                    sum(1 for y in days[max(0, d - 4):d + 1] if y["statut"] == "evalue"),
                    sum(1 for y in days[max(0, d - 4):d + 1] if y["statut"] == "evalue" and y["N"] is not None and y["count"] >= y["N"] and (y["k"] == 0 or y["ee"] >= 1)),
                    sum(1 for y in days[max(0, d - 4):d + 1] if y["statut"] == "evalue"))))
            else:
                sent.append(("soir", "18:00", t_soir(d, x["count"], max(x["count"], N or 5))))
        out_sent = []
        for (typ, h, tx) in sent:
            opened = rng.random() < p_notif
            if opened:
                ign[typ] = 0
            else:
                ign[typ] += 1
                if ign[typ] >= pause_after:
                    pause.add(typ)
            out_sent.append((typ, h, tx, opened, typ in pause))
        rows.append((d, out_sent))
    return rows


def stats(rows, label):
    weeks = {}
    maxday = 0
    for d, s in rows:
        weeks.setdefault(d // 7, 0)
        weeks[d // 7] += len(s)
        maxday = max(maxday, len(s))
    ws = [weeks[k] for k in sorted(weeks)][:17]
    return label, ws, maxday


if __name__ == "__main__":
    profs = {"A regulier (ouvre 60 %)": (lambda: P("A"), 0.6),
             "B progresse (ouvre 90 %)": (lambda: P("B", grow=0.1, cap=12), 0.9),
             "C fondateur presse (ouvre 1 sur 3)": (lambda: P("C", sd=1.8, sat=0.2), 0.33),
             "D n'ouvre jamais (5 %)": (lambda: P("D"), 0.05)}
    for lab, (fac, pn) in profs.items():
        tot = []; mx = []; paus = []; ipw = []
        for s in range(30):
            o = run(fac, s, days=120)
            rows = notif_sim(o, pn, s)
            wk = {}
            for d, sn in rows:
                wk[d // 7] = wk.get(d // 7, 0) + len(sn)
            tot.append(statistics.mean(wk.values()))
            mx.append(max(len(sn) for d, sn in rows))
            first_pause = [d for d, sn in rows for (t, h, tx, op, ps) in sn if ps]
            paus.append(first_pause[0] if first_pause else None)
            dernieres = sum(len(sn) for d, sn in rows[-28:])
            ipw.append(dernieres / 4)
        pp = [x for x in paus if x is not None]
        print(f"{lab}: notifications/semaine moyenne {statistics.mean(tot):.1f} ; max/jour {max(mx)} ; "
              f"derniere moitie (4 dernieres semaines) {statistics.mean(ipw):.1f}/sem ; pause d'au moins un type pour {len(pp)}/30 (1re au j{statistics.mean(pp) if pp else '-':.0f})"
              if pp else
              f"{lab}: notifications/semaine moyenne {statistics.mean(tot):.1f} ; max/jour {max(mx)} ; 4 dernieres semaines {statistics.mean(ipw):.1f}/sem ; aucune pause")
    # repartition par type et nature des relances (A, 30 graines)
    from collections import Counter
    for lab, (fac, pn) in list(profs.items())[:3]:
        ct = Counter(); jours = 0; fausses = 0; relances = 0
        for sd_ in range(30):
            o = run(fac, sd_, days=120)
            rows = notif_sim(o, pn, sd_)
            for (d, sn), x in zip(rows, o["days"]):
                if x["ouvre"] and not x["conge"]: jours += 1
                for (t, h, tx, op, ps) in sn:
                    ct[t] += 1
                    if t == "relance":
                        relances += 1
                        if "faites sur" in tx and x["N"] is not None and x["count"] >= x["N"]:
                            fausses += 1
        print(lab, {k: round(v / jours, 2) for k, v in ct.items()}, "par jour ouvre ; relances de derive suivies d'un objectif atteint le soir :", fausses, "/", relances)
    # journaux
    for lab, (fac, pn), seed in ((list(profs.items())[0] + (3,)), (list(profs.items())[1] + (4,)), (list(profs.items())[2] + (5,))):
        o = run(fac, seed, days=56)
        rows = notif_sim(o, pn, seed)
        cards = {c["d"]: c for c in o["cards"]}
        ans = {a[0]: a for a in o["answers"]}
        fn = f"journal_{lab.split()[0]}.txt"
        with open(fn, "w", encoding="utf-8") as f:
            f.write(f"# {lab} — graine {seed} — 8 semaines (dates fictives, lundi 16/11/2026)\n")
            for d, sn in rows:
                dt = START + timedelta(d)
                if d in cards:
                    c = cards[d]
                    f.write(f"[{dt:%a %d/%m}] (carte fin de jour) proposition {c['type']}: {c}\n")
                if d in ans:
                    f.write(f"[{dt:%a %d/%m}] reponse {ans[d][1]} -> {ans[d][2]}\n")
                if not sn:
                    f.write(f"[{dt:%a %d/%m}] —\n")
                for (typ, h, tx, op, ps) in sn:
                    f.write(f"[{dt:%a %d/%m} {h}] {tx}{'' if op else '  (ignorée)'}{'  [PAUSE ' + typ + ']' if ps else ''}\n")
        print("journal ecrit", fn)

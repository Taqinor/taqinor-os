import statistics
import sys
from sim import *

PROFILS = {
    "1 regulier 5+-1,2": lambda: P("reg"),
    "2 progresse (+1/10j si pousse)": lambda: P("prog", grow=0.1, cap=12),
    "3 rafales 9-10 / 1-2": lambda: P("raf", burst=True),
    "4a tricheur (estimes)": lambda: P("tri", cheat=True),
    "4b tricheur (sans estimation)": lambda: P("tri0", cheat=True, est=False),
    "5 interrompu (conge 10j, sam, feries)": lambda: P("int", conge=(40, 49), sat=0.3),
    "6 effondrement j40-69 puis reprise": lambda: P("eff", collapse=(40, 70)),
    "7 froid niveau vrai 3": lambda: P("f3", C=3.0, sd=1.0),
    "8 plafond 6, dit oui": lambda: P("plaf", ceiling=6),
    "10 refuse tout (progresse)": lambda: P("ref", grow=0.1, cap=12, p_yes_up=0.0, p_yes_down=0.0),
    "11 oui a tout (regulier)": lambda: P("oui"),
    "11b oui a tout (progresse)": lambda: P("oui+", grow=0.1, cap=12),
}
ALTERNE = {30: "tenir", 60: "libre", 90: "pousser"}


def agg(runs, key):
    return statistics.mean(key(r) for r in runs)


def at(r, j):
    v = r["N_hist"][j]
    return v


def resume(nom, runs):
    objs = []
    for j in (29, 59, 119):
        vals = [at(r, j) for r in runs if at(r, j) is not None]
        objs.append(round(statistics.mean(vals), 1) if vals else None)
    jumps = [x for r in runs for x in r["jumps"]]
    pire = min(jumps) if jumps else 0
    pire_up = max(jumps) if jumps else 0
    nup = agg(runs, lambda r: r["props"]["monter"])
    ndn = agg(runs, lambda r: r["props"]["baisser"])
    aup = agg(runs, lambda r: r["acc"]["monter"])
    adn = agg(runs, lambda r: r["acc"]["baisser"])
    fb = agg(runs, lambda r: r["fausses_baisses"])
    d20 = agg(runs, lambda r: statistics.mean([c for (_, c) in r["counts"][-20:]]) if r["counts"] else 0)
    rr = []
    for r in runs:
        l = [x for x in r["reussie"] if x is not None]
        rr.append(sum(l) / len(l) if l else 0)
    chg = agg(runs, lambda r: len(r["jumps"]))
    mx = statistics.mean(max([x for x in r["N_hist"] if x is not None] or [0]) for r in runs)
    return (f"| {nom} | {objs[0]}/{objs[1]}/{objs[2]} (max {mx:.1f}) | {pire:+d}/{pire_up:+d} · {chg:.1f} | "
            f"{nup:.1f}/{ndn:.1f} ({aup:.1f}/{adn:.1f}) | {fb:.2f} | {d20:.1f} | {100*statistics.mean(rr):.0f} % |")


if __name__ == "__main__":
    print("| Profil | objectif j30/60/119 | pire saut -/+ · changements | propositions ↑/↓ (acceptees) | fausses baisses | fait 20 derniers j | journees reussies |")
    print("|---|---|---|---|---|---|---|")
    for nom, fac in PROFILS.items():
        runs = [run(fac, s) for s in range(30)]
        print(resume(nom, runs))
    runs = [run(lambda: P("alt", grow=0.1, cap=12), s, modes=ALTERNE) for s in range(30)]
    print(resume("9 alterne P->T->L->P (progresse)", runs))
    # froid avec objectif dit
    runs = [run(lambda: P("dit"), s, dit=4) for s in range(30)]
    print(resume("(extra) regulier 5 qui dit 4", runs))

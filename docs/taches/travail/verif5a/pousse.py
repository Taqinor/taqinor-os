"""Question 6 : la regle POUSSER pousse-t-elle vraiment ? Temps pour gagner 2 taches/jour."""
import statistics
from sim import *

def jour_moy_ge(r, seuil, fen=10):
    c = [x for _, x in r["counts"]]; ds = [d for d, _ in r["counts"]]
    for i in range(fen, len(c) + 1):
        if statistics.mean(c[i - fen:i]) >= seuil:
            return ds[i - 1]
    return None

def jour_palier_ge(r, n):
    for d, x in enumerate(r["N_hist"]):
        if x is not None and x >= n:
            return d
    return None

PERS = {
 "progresse (+1/10 j quand pousse)": lambda: P("g", grow=0.1, cap=12),
 "capable (suit l'objectif, potentiel 9)": lambda: P("c", follow=True, potential=9),
 "tres rapide (+1/5 j)": lambda: P("v", grow=0.2, cap=12),
}
def mk(**cfg):
    def rule(e):
        e.cfg.update(cfg)
    return rule
VARS = {
 "spec (bloc 10, 6/10, +1)": {},
 "V1 spec + arrondi au plus proche du type initial": dict(arrondi_type="round"),
 "V2 +2 si >= 9/10 (sinon +1)": dict(double=9),
 "V3 bloc 5 jours, 4/5 monte, <=1/5 baisse": dict(B=5, haut=4, bas=1),
 "V4 V1+V2": dict(arrondi_type="round", double=9),
}
if __name__ == "__main__":
    S = range(30)
    for pn, fac in PERS.items():
        print("##", pn)
        for vn, cfg in VARS.items():
            runs = [run(fac, s, days=150, rule=mk(**cfg)) for s in S]
            j7 = [jour_moy_ge(r, 7.0) for r in runs]; p7 = [jour_palier_ge(r, 7) for r in runs]
            ok = [x for x in j7 if x is not None]
            print(f" {vn:48s} obj>=7 au jour {statistics.mean(x for x in p7 if x) if all(p7) else 'NA':>5} ; moyenne 10 j >= 7 au jour {statistics.mean(ok):.0f} ({len(ok)}/30) ;"
                  f" objectif j60 {statistics.mean(r['N_hist'][60] for r in runs):.1f} j119 {statistics.mean(r['N_hist'][119] for r in runs):.1f} ; reussies {100*statistics.mean(statistics.mean([1 if x else 0 for x in r['reussie'] if x is not None]) for r in runs):.0f} %")
    print("## effets de bord sur d'autres profils (30 graines)")
    for vn, cfg in VARS.items():
        out = []
        for nom, fac in (("regulier", lambda: P("r")), ("tricheur estime", lambda: P("t", cheat=True)), ("rafales", lambda: P("b", burst=True)), ("plafond 6", lambda: P("pl", ceiling=6))):
            runs = [run(fac, s, days=120, rule=mk(**cfg)) for s in S]
            rep = 100 * statistics.mean(statistics.mean([1 if x else 0 for x in r['reussie'] if x is not None]) for r in runs)
            out.append(f"{nom}: obj {statistics.mean(r['N_hist'][119] for r in runs):.1f}, up {statistics.mean(r['props']['monter'] for r in runs):.1f}/down {statistics.mean(r['props']['baisser'] for r in runs):.1f}, faux-bas {statistics.mean(r['fausses_baisses'] for r in runs):.2f}, reussies {rep:.0f} %")
        print(f" {vn}\n    " + "\n    ".join(out))

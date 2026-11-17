import statistics
from sim import *

CAS = {
 "regulier 5+-1,2": lambda: P("a"),
 "regulier 5+-2,0": lambda: P("b", sd=2.0),
 "rafales": lambda: P("c", burst=True),
 "froid enthousiaste (8 x14 j puis 3)": lambda: P("d", mean_fn=lambda d: 8 if d < 20 else 3, step=(20, 3), sd=1.0),
 "baisse 5->3 au j50": lambda: P("e", mean_fn=lambda d: 5 if d < 50 else 3, step=(50, 3)),
 "surchauffe 5->7 au j50": lambda: P("f", mean_fn=lambda d: 5 if d < 50 else 7, step=(50, 7)),
}
for nom, fac in CAS.items():
    for pas in (False,):
        al = fa = 0; delays = []
        for s in range(30):
            def f():
                p = fac(); p.derive_pass = pas; return p
            r = run(f, s, modes={0: "tenir"})
            al += len(r["alerts"]); fa += r["fausses_alertes"]
            after = [d for d, _ in r["alerts"] if d >= 50]
            if "j50" in nom and after:
                delays.append(after[0] - 50)
        print(f"{nom:40s} alertes {al/30:.1f} fausses {fa/30:.1f} delai {statistics.mean(delays) if delays else '-'}")

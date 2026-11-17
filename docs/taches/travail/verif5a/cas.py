import statistics
from sim import *

S = range(30)


def moy(l):
    l = list(l)
    return statistics.mean(l) if l else float("nan")


def props(runs, typ):
    return moy(r["props"][typ] for r in runs)


print("== A. « je veux faire plus » avec 4 jours d'historique : objectif dit 7 / 10 / 15, niveau vrai 5")
for dit in (7, 10, 15):
    runs = [run(lambda: P("a"), s, dit=dit) for s in S]
    objs = [moy(r["N_hist"][j] for r in runs) for j in (9, 29, 59, 119)]
    rep = [moy(1 if x else 0 for x in r["reussie"] if x is not None) for r in runs]
    jours_a_5 = []
    for r in runs:
        j = next((i for i, n in enumerate(r["N_hist"]) if i > 12 and n is not None and n <= 5), None)
        jours_a_5.append(j if j is not None else 120)
    print(f" dit {dit}: objectif j9/j29/j59/j119 = {[round(o,1) for o in objs]} ; jours reussies {100*moy(rep):.0f} % ;"
          f" baisses proposees {props(runs,'baisser'):.1f} ; 1er jour <=5 : {moy(jours_a_5):.0f} ; type proposé {props(runs,'type'):.1f}")

print("   A' : il refuse la journee type proposee (garde son objectif dit)")
def fac_refuse_type2(): 
    p = P("a'"); old = p.answer
    p.answer = lambda typ, rng: "non" if typ == "type" else old(typ, rng)
    return p
for dit in (7, 15):
    runs = [run(fac_refuse_type2, s, dit=dit) for s in S]
    objs = [moy(r["N_hist"][j] for r in runs) for j in (9, 29, 59, 119)]
    rep = [moy(1 if x else 0 for x in r["reussie"] if x is not None) for r in runs]
    print(f" dit {dit}, refuse le type: objectif j9/29/59/119 = {[round(o,1) for o in objs]} ; reussies {100*moy(rep):.0f} % ; baisses proposees {props(runs,'baisser'):.1f}")
print("== B. objectif dit 1, niveau vrai 5 (accepte la journee type) / refuse")
runs = [run(lambda: P("b"), s, dit=1) for s in S]
print(" accepte: objectif j29/59/119", [round(moy(r["N_hist"][j] for r in runs), 1) for j in (29, 59, 119)])
runs = [run(lambda: P("b", p_yes_up=1.0), s, dit=1) for s in S]
# refus de la proposition 'type' : on simule en neutralisant la reponse
def fac_refuse_type():
    p = P("b2")
    old = p.answer
    p.answer = lambda typ, rng: "non" if typ == "type" else old(typ, rng)
    return p
runs = [run(fac_refuse_type, s, dit=1) for s in S]
print(" refuse le type: objectif j29/59/119", [round(moy(r["N_hist"][j] for r in runs), 1) for j in (29, 59, 119)],
      "reussie", round(100 * moy(moy(1 if x else 0 for x in r["reussie"]) for r in runs)), "%")
# N=1 : jour court
print(" N=1 jour court : objectif_du_jour =", Etat(dit=1).objectif_du_jour(True) if False else "max(1,N-1)=1 dans mon code ; N-1 litteral = 0 (compte>=0 toujours vrai)")

print("== C. 30 taches cochees en un jour (liste collee puis cochee), sans estimation")
for jour in (3, 11, 39):
    fa_t = []; objs = []
    for outl_label, outl in (("sans", {}), ("avec", {jour: 30})):
        runs = [run(lambda: P("c", outliers=outl), s, modes={0: "tenir"}) for s in S]
        fa_t.append(moy(len(r["alerts"]) for r in runs))
    print(f" TENIR, 30 taches au j{jour}: alertes sans {fa_t[0]:.2f} / avec {fa_t[1]:.2f}")
    runs0 = [run(lambda: P("c"), s) for s in S]
    runs1 = [run(lambda: P("c", outliers={jour: 30}), s) for s in S]
    print(f"   POUSSER objectif j119 sans {moy(r['N_hist'][119] for r in runs0):.2f} avec {moy(r['N_hist'][119] for r in runs1):.2f}"
          f" ; propositions monter sans {props(runs0,'monter'):.1f} avec {props(runs1,'monter'):.1f}")
# type initial perturbe
dif = 0
import random as _r
rr = _r.Random(3)
t0 = []; t1 = []
for _ in range(5000):
    cs = [max(0, arrondi(rr.gauss(5, 1.2))) for _ in range(10)]
    t0.append(journee_type(cs)); cs2 = cs[:]; cs2[2] = 30
    t1.append(journee_type(cs2))
print(f" journee type initiale : sans {statistics.mean(t0):.2f}  avec un 30 : {statistics.mean(t1):.2f} (mediane robuste)")

print("== D. semaines ou il ne travaille que 2 jours (mer-ven off) toutes les 4 semaines")
sem = tuple(range(1, 17, 4))
for lab, kw in (("appli fermee les 3 jours", {}), ("appli OUVERTE (plan valide) mais 0 fait", dict(open_on_idle=True))):
    runs = [run(lambda: P("d", week_short=sem, **kw), s) for s in S]
    base = [run(lambda: P("d"), s) for s in S]
    print(f" {lab}: baisses proposees {props(runs,'baisser'):.2f} (ref {props(base,'baisser'):.2f}) ; objectif j119 {moy(r['N_hist'][119] for r in runs):.2f} (ref {moy(r['N_hist'][119] for r in base):.2f});"
          f" statuts {dict((k, round(moy(r['statuts'].get(k,0) for r in runs),1)) for k in ('evalue','sans_donnees'))}")
runs = [run(lambda: P("d", week_short=tuple(range(0, 17)), open_on_idle=False), s) for s in S]
print(f" TOUTES les semaines a 2 jours, appli fermee : evalue {moy(r['statuts'].get('evalue',0) for r in runs):.1f} jours/120 ;"
      f" 1re proposition vers j{moy(next((d for d,x in r['ev'] if x[0] in ('monter','baisser')),120) for r in runs):.0f}")

print("== E. POUSSER -> TENIR au milieu d'un bloc, puis retour")
r = run(lambda: P("e", C=7.0, grow=0), 1, modes={40: "tenir", 55: "pousser"})
e = r["etat"]
print(" palier 7 pour un niveau vrai 5 ; bascule T j40, retour P j55 -> palier", e.palier, " R =", round(e.R, 2) if e.R else None)
sauts = []
for s in S:
    rr_ = run(lambda: P("e"), s, modes={44: "tenir", 58: "pousser"})
    pal_av = rr_["N_hist"][43]; pal_ap = rr_["N_hist"][58]
    sauts.append((pal_av, pal_ap))
print(" régulier 5, T j44 / P j58 : (palier avant, palier apres) moyenne", round(moy(a for a, b in sauts), 2), round(moy(b for a, b in sauts), 2),
      "; sauts <= -2 :", sum(1 for a, b in sauts if b - a <= -2), "/ 30 ; >= +2 :", sum(1 for a, b in sauts if b - a >= 2), "/30")
# biais floor(R) pour un regulier
import random as _r2
r2 = _r2.Random(5)
fl = []; ro = []
for _ in range(20000):
    R = statistics.mean(max(0, arrondi(r2.gauss(5, 1.2))) for _ in range(14))
    fl.append(math.floor(R)); ro.append(arrondi(R))
print(f" TENIR->POUSSER d'un regulier a 5,0 : palier floor(R) {statistics.mean(fl):.2f} ; round(R) {statistics.mean(ro):.2f}; P(floor<=4) = {sum(1 for x in fl if x<=4)/len(fl):.2f}")
# etat d'une proposition en attente au moment de la bascule
e2 = Etat(); e2.froid = False; e2.palier = 6
e2.pending = Proposition("monter", 10, N=6, n_tenus=7)
e2.basculer("tenir", 11)
print(" proposition 'monter' en attente a la bascule -> pending =", e2.pending, "(spec muette : ici abandonnee)")

print("== F. TOUTES les taches sans estimation : garde anti-triche")
for lab, est, pr in (("estimees, n'appuie jamais sur 'changees'", True, 0.0), ("estimees, appuie toujours", True, 1.0), ("sans estimation", False, 0.0)):
    runs = [run(lambda: P("f", cheat=True, est=est, press_changed=pr), s) for s in S]
    print(f" tricheur {lab}: objectif j119 {moy(r['N_hist'][119] for r in runs):.1f} ; gardes taille {props(runs,'taille'):.1f} ; fait 20 derniers j {moy(moy(c for _,c in r['counts'][-20:]) for r in runs):.1f}"
          f" ; fait reel 5")
runs = [run(lambda: P("f", est=False), s) for s in S]
print(f" HONNETE sans estimation: objectif j119 {moy(r['N_hist'][119] for r in runs):.1f} (sain)")
# garde fait-elle fausse alerte sur un honnete qui raccourcit ses taches
for lab, press in (("n'appuie jamais sur 'Mes taches ont change'", 0.0), ("appuie 1 fois sur 2", 0.5), ("appuie toujours", 1.0)):
    runs = [run(lambda: P("g", grow=0.1, cap=12, size_drift=lambda d: 1.0 if d < 40 else 0.55, press_changed=press), s) for s in S]
    print(f" honnete qui progresse et dont les taches raccourcissent de 45 % au j40, {lab}: objectif j119 {moy(r['N_hist'][119] for r in runs):.1f}"
          f" ; gardes {props(runs,'taille'):.1f} ; fait {moy(moy(c for _,c in r['counts'][-20:]) for r in runs):.1f}")
runs = [run(lambda: P("g", grow=0.1, cap=12), s) for s in S]
print(f" meme honnete SANS raccourcissement : gardes (fausses) {props(runs,'taille'):.2f} ; objectif j119 {moy(r['N_hist'][119] for r in runs):.1f}")

print("== G. essentiel jamais choisi : effet sur la relance de derive et la journee reussie")
for lab, ep in (("essentiel choisi 70 %", 0.7), ("jamais choisi", 0.0), ("toujours choisi", 1.0)):
    runs = [run(lambda: P("g", ess_prob=ep), s) for s in S]
    rr_ = moy(moy(1 if x else 0 for x in r["reussie"] if x is not None) for r in runs)
    print(f" {lab}: journees reussies {100*rr_:.0f} %")

print("== H. accepte une montee puis 3 semaines de conge (21 j calendaires)")
for lab, kw in (("retour normal", {}), ("retour a 60 % pendant 5 jours", dict(reentry=0.6))):
    runs = [run(lambda: P("h", grow=0.1, cap=12, conge_after_accept=21, **kw), s, days=150) for s in S]
    rows = []
    for r in runs:
        da = r.get("accept_day")
        if da is None:
            continue
        ret = da + 22
        pal_veille = r["N_hist"][da + 1]
        pal_ret30 = r["N_hist"][min(149, ret + 30)]
        bs = [d for d, x in r["ev"] if x[0] == "baisser" and ret <= d <= ret + 30]
        rows.append((pal_veille, pal_ret30, len(bs)))
    print(f" {lab}: n={len(rows)} palier avant conge {moy(a for a,b,c in rows):.2f} ; 30 j apres retour {moy(b for a,b,c in rows):.2f} ; baisses proposees dans les 30 j {moy(c for a,b,c in rows):.2f}")

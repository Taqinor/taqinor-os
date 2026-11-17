import datetime as dt, random
from dataclasses import dataclass
from typing import Optional

TODAY = dt.date(2026, 11, 17)             # Tuesday
HOLIDAYS = {dt.date(2026, 11, 18)}        # Fete de l'Independance (company calendar)


def ouvre(d):
    return d.weekday() < 5 and d not in HOLIDAYS


def wd_between(a, b):
    """working days in (a, b]  (interpretation: 'within the next 3 working days' = this count <= 3)"""
    n, d = 0, a
    while d < b:
        d += dt.timedelta(days=1)
        if ouvre(d):
            n += 1
    return n


@dataclass
class T:
    id: int
    titre: str
    proj: str
    pp: int                  # project priority 1..3
    prio: int                # task priority 1 haute, 2 normale, 3 basse
    imp: bool = False
    due: Optional[dt.date] = None
    rep: int = 0
    created: dt.datetime = dt.datetime(2026, 11, 1, 9, 0)
    erp: bool = False
    attente: bool = False


D = lambda d, m=11: dt.date(2026, m, d)
TS = dt.datetime(2026, 11, 16, 18, 30, 0)   # one bulk paste (D-TCH-4): identical created_at
tasks = [
    T(1, "Relancer client devis 452 (ERP)", "Ventes", 1, 2, due=D(17), erp=True, created=dt.datetime(2026, 11, 10)),
    T(2, "Payer fournisseur panneaux", "Admin", 2, 1, due=D(16), created=dt.datetime(2026, 11, 2)),
    T(3, "Preparer formation equipe", "Equipe", 1, 2, imp=True, created=dt.datetime(2026, 11, 3)),
    T(4, "Dossier subvention", "Admin", 2, 2, imp=True, due=D(20), rep=3, created=dt.datetime(2026, 10, 20)),
    T(5, "Mettre a jour le site", "Site", 3, 2, created=dt.datetime(2026, 10, 27)),
    T(6, "Renouveler abonnement logiciel (en retard 10 j)", "Perso", 3, 3, due=D(7), created=dt.datetime(2026, 10, 1)),
    T(7, "Envoyer devis client Benali", "Ventes", 1, 1, imp=True, due=D(18), created=dt.datetime(2026, 11, 12)),
    T(8, "Remise chantier Settat (deadline client)", "Chantiers", 1, 2, imp=True, due=D(19), created=dt.datetime(2026, 11, 5)),
    T(9, "Acheter timbres et papier", "Admin", 2, 3, due=D(17), created=dt.datetime(2026, 11, 16)),
    T(10, "Appeler le comptable", "Admin", 2, 2, due=D(17), created=dt.datetime(2026, 11, 14)),
    T(11, "Ranger le bureau", "Perso", 3, 3, created=dt.datetime(2026, 6, 1)),
    T(12, "Reserver vol Casablanca", "Perso", 3, 2, imp=True, due=D(2, 12), created=dt.datetime(2026, 11, 9)),
    T(13, "Renouveler assurance flotte (avril 2027)", "Admin", 2, 2, imp=True, due=dt.date(2027, 4, 15), created=dt.datetime(2026, 11, 9)),
    T(14, "Rediger fiche de poste technicien", "Equipe", 1, 2, imp=True, created=dt.datetime(2026, 11, 8)),
    T(15, "Photos realisations pour le site", "Site", 3, 2, due=D(27), created=dt.datetime(2026, 11, 11)),
    T(16, "Relancer 3 leads froids", "Ventes", 1, 2, rep=1, created=dt.datetime(2026, 11, 6)),
    T(17, "Commander cables 6mm2 chantier Settat", "Chantiers", 1, 1, due=D(18), created=dt.datetime(2026, 11, 13)),
    T(18, "Valider planning techniciens", "Equipe", 1, 1, due=D(20), created=dt.datetime(2026, 11, 13)),
    T(19, "Declaration TVA", "Admin", 2, 1, imp=True, due=D(20), created=dt.datetime(2026, 11, 4)),
    T(20, "Idee : partenariat banque", "Inbox", 2, 2, created=TS),
    T(21, "Idee : parrainage clients", "Inbox", 2, 2, created=TS),
    T(22, "Idee : video chantier", "Inbox", 2, 2, created=TS),
    T(23, "Idee : devis type hotel", "Inbox", 2, 2, created=TS),
    T(24, "Idee : assurance panneaux", "Inbox", 2, 2, created=TS),
    T(25, "Rendez-vous dentiste", "Perso", 3, 2, due=D(17), created=dt.datetime(2026, 11, 1)),
    T(26, "Attendre reponse ONEE (en attente)", "Chantiers", 1, 2, attente=True, created=dt.datetime(2026, 11, 1)),
]


def band(t, fix2=False, fix1=False):
    if t.due is not None and t.due <= TODAY:
        if fix1 and not t.erp and not (t.imp or t.prio == 1 or t.pp == 1) and t.due < TODAY:
            return 2          # an unimportant, non-urgent overdue chore is not an 'engagement'
        return 1
    near = t.due is not None and wd_between(TODAY, t.due) <= 3
    if t.imp:
        if fix2 and t.due is not None and wd_between(TODAY, t.due) > 10:
            return 3
        return 2
    return 2 if near else 3


def key(t, fix1=False, fix2=False, with_id=False, focus=None):
    pp = 1 if (focus and t.proj == focus) else t.pp
    k = (band(t, fix2, fix1), pp, t.prio, t.due or dt.date.max, -t.rep, t.created)
    return k + ((t.id,) if with_id else ())


def show(order, title, **kw):
    print(f"--- {title}")
    for r, t in enumerate(order, 1):
        d = t.due.strftime('%d/%m') if t.due else '  - '
        print(f"{r:2d}. b{band(t, kw.get('fix2', False), kw.get('fix1', False))} P{t.pp} p{t.prio} {'IMP' if t.imp else '   '} due {d} rep{t.rep} {t.proj:9s} {t.titre}")


cand = [t for t in tasks if not t.attente]
print("candidates", len(cand), "(1 blocked task excluded from ranking: 'Attendre reponse ONEE')")
base = sorted(cand, key=key)
show(base, "AS WRITTEN (ties unresolved, stable on input order)")

# strict total order check: shuffle input, count distinct outputs
rng = random.Random(1)
outs = set()
for _ in range(300):
    s = cand[:]
    rng.shuffle(s)
    outs.add(tuple(t.id for t in sorted(s, key=key)))
print("\nDistinct output orders over 300 input shuffles, as written:", len(outs))
keys = [key(t) for t in cand]
dups = len(keys) - len(set(keys))
print("tasks sharing an identical sort key (ties):", dups, "-> the 5 'Idee' tasks imported in one paste (same created_at)")
outs2 = set()
for _ in range(300):
    s = cand[:]
    rng.shuffle(s)
    outs2.add(tuple(t.id for t in sorted(s, key=lambda t: key(t, with_id=True))))
print("with id appended as last key:", len(outs2), "distinct order")


def pos(order):
    return {t.id: i for i, t in enumerate(order, 1)}


p = pos(base)
print("\nFLAGS (as written):")
print(f"F1 unimportant low-priority P3 chore OVERDUE 10 days (#6, rank {p[6]}) above 'Remise chantier Settat' deadline client in 2 working days (#8, rank {p[8]}):", p[6] < p[8])
print(f"F1b same #6 above 'Envoyer devis client Benali' due tomorrow, important P1 (#7, rank {p[7]}):", p[6] < p[7])
print(f"F1c trivial 'Acheter timbres' due today, basse, P2 (#9, rank {p[9]}) above 'Declaration TVA' important haute due Fri (#19, rank {p[19]}):", p[9] < p[19])
print(f"F1d dentist (#25 rank {p[25]}), due today P3, above #8 client deadline:", p[25] < p[8])
print(f"F2 'Renouveler assurance flotte' important but due Apr 2027 (#13, rank {p[13]}) above 'Photos realisations' (#15 rank {p[15]}) / 'Mettre a jour le site' (#5 rank {p[5]}) and above 'Valider planning' due Fri P1 haute (#18 rank {p[18]}):", p[13] < p[18])
print(f"F2b 'Reserver vol' important due 02/12 P3 (#12 rank {p[12]}) above 'Valider planning techniciens' due Fri haute P1 (#18 rank {p[18]}):", p[12] < p[18])
print(f"F3 'Ranger le bureau' (age 5.5 months, low) rank {p[11]} ; 'Relancer 3 leads froids' P1 no due (#16) rank {p[16]}")
print(f"F4 #7 (due tomorrow = bank holiday 18/11) wd_between={wd_between(TODAY, D(18))}; due Sat 21/11 -> {wd_between(TODAY, D(21))}; due Mon 23/11 -> {wd_between(TODAY, D(23))}; due Tue 24/11 -> {wd_between(TODAY, D(24))}")

fixed = sorted(cand, key=lambda t: key(t, fix1=True, fix2=True, with_id=True))
show(fixed, "WITH FIXES: fix1 (unimportant non-urgent overdue chores leave band 1), fix2 (important + due > 10 working days -> band 3), id tie-break", fix1=True, fix2=True)
pf = pos(fixed)
print("\nAFTER:  #6 vs #8:", pf[6], pf[8], "| #6 vs #7:", pf[6], pf[7], "| #13 vs #18:", pf[13], pf[18], "| #12 vs #18:", pf[12], pf[18], "| #9 vs #19:", pf[9], pf[19])

# side effects of fixes: who moved most
mv = sorted(cand, key=lambda t: -abs(pf[t.id] - p[t.id]))[:6]
print("largest rank moves (before -> after):", [(t.id, p[t.id], pf[t.id]) for t in mv])
print("\nNOTE: an overdue task in band 1 stays above EVERYTHING in band 2 for ever (rank is independent of how overdue it is).")
print("Plan filler: band-1 tasks (due <= today) fill slots before any band-2 task; with target 5 and the 5 band-1 tasks here (#1,#2,#9,#10,#25,#6) the important P1 deadline tasks (#7,#8,#17) only enter through the single 'important slot' or not at all.")
b1 = [t for t in base if band(t) == 1]
print("band-1 count:", len(b1), [t.id for t in b1])
print("first 5 by rank (as written):", [t.id for t in base[:5]], "-> includes trivial/overdue chores; #7,#8,#17 ranks", p[7], p[8], p[17])
print("first 5 by rank (fixed):     ", [t.id for t in fixed[:5]])

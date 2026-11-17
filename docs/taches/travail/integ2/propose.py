"""Script JETABLE (révision 3) : nouvelle règle de Proposé (A18-M1/M2), carte « Aide-moi à prioriser »,
temps disponible moins rendez-vous (inv. 35), plus_tard, repère P60. Bibliothèque standard seule.
Repère : mardi 17/11/2026, lun-ven travaillés, 18/11 férié."""
import sys
from dataclasses import dataclass
from datetime import date, time, timedelta

sys.stdout.reconfigure(encoding="utf-8")
J = date(2026, 11, 17)
FERIES = {date(2026, 11, 18)}


def travaille(d):
    return d.weekday() < 5 and d not in FERIES


def n_travailles(apres, jusqu_a):
    d, n = apres + timedelta(1), 0
    while d <= jusqu_a:
        n += travaille(d)
        d += timedelta(1)
    return n


@dataclass(frozen=True)
class P:  # projet
    id: int
    nom: str
    priorite: int
    rang: int
    statut: str = "actif"


@dataclass(frozen=True)
class T:  # ItemPur réduit
    id: int
    titre: str
    projet: int = None
    rang_projet: int = 0
    jour_prevu: date = None
    echeance: date = None
    quelque_jour: bool = False
    bloquee: bool = False
    reports: int = 0
    reports_tranches: int = 0
    priorite: int = 0


SANS = P(0, "Sans projet", -1, 10**9)
PROJETS = {p.id: p for p in [P(1, "Ventes", 3, 1024), P(2, "Polydesign", 2, 2048), P(3, "Maison", 2, 1024),
                             P(4, "Admin", 1, 1024), P(5, "Salon", 3, 512, "en_pause"), SANS]}
TACHES = [T(100 + i, f"V{i}", 1, 1024 * i) for i in range(1, 13)]
TACHES += [T(201, "D1 (en réserve)", 2, 1024, quelque_jour=True), T(202, "D2 (bloquée)", 2, 2048, bloquee=True),
           T(203, "D3", 2, 3072), T(204, "D4", 2, 4096),
           T(205, "R2 échéance dépassée le 12/11", 2, 512, echeance=date(2026, 11, 12))]
TACHES += [T(301, "M1 (prévue ven. 20)", 3, 1024, jour_prevu=date(2026, 11, 20)), T(302, "M2", 3, 2048),
           T(303, "M3", 3, 3072), T(304, "R1 prévue hier", 3, 512, jour_prevu=date(2026, 11, 16))]
TACHES += [T(401, "A1 échéance jeu. 19", 4, 1024, echeance=date(2026, 11, 19)), T(402, "A2", 4, 2048),
           T(403, "A3", 4, 3072), T(404, "R3 prévue le 05/11", 4, 512, jour_prevu=date(2026, 11, 5))]
TACHES += [T(501, "Salon 1", 5, 1024), T(502, "Salon 2", 5, 2048)]
TACHES += [T(601, "S1 (sans projet, triée)", 0, 1024), T(602, "S2 (sans projet, triée)", 0, 2048)]
TACHES += [T(150, "R4 reportée 3 fois", 1, 512, jour_prevu=date(2026, 11, 13), reports=3)]


def motif_revoir(t):
    if t.reports >= t.reports_tranches + 3 and t.jour_prevu and t.jour_prevu <= J:
        return "reportee_3_fois"
    for d in (t.jour_prevu, t.echeance):
        if d and d < J - timedelta(7):
            return "retard_ancien"
    return None


def raison_presse(t):
    if t.jour_prevu and J - timedelta(7) <= t.jour_prevu < J:
        return "retard"
    if t.echeance and J - timedelta(7) <= t.echeance < J:
        return "echeance_passee"
    if t.echeance and t.echeance > J and n_travailles(J, t.echeance) <= 2 and (not t.jour_prevu or t.jour_prevu > t.echeance):
        return "echeance_proche"
    return None


ORDRE_PRESSE = {"retard": 0, "echeance_passee": 1, "echeance_proche": 2}


def candidats(taches):
    out = []
    for t in taches:
        p = PROJETS[t.projet]
        if p.statut != "actif" or t.quelque_jour or t.bloquee or motif_revoir(t):
            continue
        out.append(t)
    return out


def proposer_plan(taches, N):
    cands = candidats(taches)
    presse = sorted([t for t in cands if raison_presse(t)], key=lambda t: (ORDRE_PRESSE[raison_presse(t)], t.echeance or date.max, t.id))
    file = {}
    for t in cands:
        if raison_presse(t) or t.jour_prevu:   # planifiées plus tard : pas candidates au tour
            continue
        file.setdefault(t.projet, []).append(t)
    for k in file:
        file[k].sort(key=lambda t: (t.rang_projet, t.id))
    ordre = sorted(file, key=lambda k: (-PROJETS[k].priorite, PROJETS[k].rang, k))
    tour, rang = [], 0
    while any(len(file[k]) > rang for k in ordre):
        for k in ordre:
            if len(file[k]) > rang:
                tour.append((file[k][rang], "prochaine_action" if rang == 0 else "action_suivante"))
        rang += 1
    places = max(0, N - len(presse))
    pris = [(t, raison_presse(t)) for t in presse] + tour[:places]
    reste = tour[places:]
    return pris, reste


def montre(pris):
    return [t.titre.split(" ")[0] + "/" + r for t, r in pris]


print("projets par ordre de tour : Ventes(3), Maison(2, rang 1024), Polydesign(2, rang 2048), Admin(1), Sans projet")
print("À revoir :", [t.titre.split(" ")[0] + "/" + motif_revoir(t) for t in TACHES if motif_revoir(t)])
for N in (2, 3, 5, 8, 13):
    pris, reste = proposer_plan(TACHES, N)
    print(f"N={N:>2} :", montre(pris), "| reste", len(reste))

# Monopole : ancien cle_tri (bande 2 pour pmax = 3) sur le même tour, 5 places, sans presse
ventes_d_abord = sorted(candidats(TACHES), key=lambda t: (0 if PROJETS[t.projet].priorite == 3 else 1, t.id))
print("ancien classement, 5 places :", [t.titre.split(" ")[0] for t in ventes_d_abord if not raison_presse(t) and not t.jour_prevu][:5])
pris, _ = proposer_plan(TACHES, 5 + 3)
print("nouveau, 5 places de tour :", [t.titre.split(" ")[0] for t, r in pris if r in ("prochaine_action", "action_suivante")])


def classer_priorites(taches, N):
    pris, reste = proposer_plan(taches, 10**6)
    revoir = [(t, motif_revoir(t)) for t in taches if motif_revoir(t) and PROJETS[t.projet].statut == "actif"]
    return [(t, r) for t, r in pris] + revoir, N


lignes, garder_n = classer_priorites(TACHES, 5)
print("priorités (toutes, garder_n=5) :", montre(lignes))


def plus_tard(j):
    d = j + timedelta(1)
    while d.isocalendar()[1] == j.isocalendar()[1]:
        if travaille(d):
            return d
        d += timedelta(1)
    while not travaille(d):
        d += timedelta(1)
    return d


for j in (date(2026, 11, 17), date(2026, 11, 20), date(2026, 11, 19)):
    print("plus_tard", j, "->", plus_tard(j))


def minutes_rdv(evts, fenetre=(time(8, 30), time(19, 0))):
    def m(t):
        return t.hour * 60 + t.minute
    a, b = m(fenetre[0]), m(fenetre[1])
    iv = sorted((max(a, m(d)), min(b, m(f))) for d, f, je in evts if not je)
    total, cour = 0, None
    for d, f in iv:
        if f <= d:
            continue
        if cour and d <= cour[1]:
            cour = (cour[0], max(cour[1], f))
        else:
            if cour:
                total += cour[1] - cour[0]
            cour = (d, f)
    if cour:
        total += cour[1] - cour[0]
    return total


CAS = {"11:00-12:00": [(time(11), time(12), False)],
       "10:00-11:30 + 11:00-12:00": [(time(10), time(11, 30), False), (time(11), time(12), False)],
       "07:00-09:00": [(time(7), time(9), False)],
       "journée entière": [(time(0), time(23, 59), True)],
       "09:00-12:00 + 14:00-16:00": [(time(9), time(12), False), (time(14), time(16), False)],
       "18:30-20:00": [(time(18, 30), time(20), False)]}
for nom, ev in CAS.items():
    r = minutes_rdv(ev)
    print(f"capacité 240, {nom} -> rendez-vous {r}, disponible {max(0, 240 - r)}")


def p60(comptes):
    s = sorted(comptes)
    pos = 0.6 * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return round(s[lo] + (pos - lo) * (s[hi] - s[lo]), 1)


print("p60 [3,4,5,5,5,6,6,7,8] ->", p60([3, 4, 5, 5, 5, 6, 6, 7, 8]), "; [5]*9 ->", p60([5] * 9),
      "; [2,3,4,5,6,7,8,9,10] ->", p60([2, 3, 4, 5, 6, 7, 8, 9, 10]))

"""Flux de calendrier et tuile (regles.md §10) — code PUR.

Aucune base, aucune horloge : J, le plan et les jours travaillés sont des
paramètres ; les titres passent TOUS par `nom_pour(item, usage, reglages)`
fourni par l'appelant (jamais de notes, jamais un titre d'activité ERP).
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from apps.taches.choix import StatutTache
from apps.taches.moteur.classement import (
    ACTIVITE, SECTIONS_GARDEES, TACHE, cle_section, cle_tri_pour, dans_prefiltre, motif_revoir, placer)

FENETRE_JOURS = 14
JOURNEES_MAX = 8
EVENEMENTS_MAX = 200
DUREE_DEFAUT_MIN = 30
TOP_MAX = 6
PASTILLE_MAX = 99
USAGE_FLUX = 'flux'
USAGE_TUILE = 'tuile'


@dataclass(frozen=True)
class EvenementFlux:
    """Un VEVENT : `debut`/`fin` = dates (journée entière, fin exclue) ou heures murales locales."""
    uid: str
    titre: str
    debut: date | datetime
    fin: date | datetime
    journee_entiere: bool


# --- Flux ------------------------------------------------------------------

def emise_au_flux(t, J):
    """Tâche `a_faire` du préfiltre, prévue dans [J, J+14], hors À revoir (inv. 12)."""
    if t.type != TACHE or t.statut != StatutTache.A_FAIRE or t.quelque_jour or not dans_prefiltre(t):
        return False
    if t.jour_prevu is None or not J <= t.jour_prevu <= J + timedelta(days=FENETRE_JOURS):
        return False
    return motif_revoir(t, J) is None


def _accord_autres(n):
    return f'+ {n} autre tâche' if n <= 1 else f'+ {n} autres tâches'


def _evenement_horaire(t, titre):
    debut = datetime.combine(t.jour_prevu, t.heure_debut)
    duree = t.estimation_minutes or DUREE_DEFAUT_MIN
    return EvenementFlux(f'tache-{t.id}', titre, debut, debut + timedelta(minutes=duree), False)


def _evenement_journee(uid, titre, jour):
    return EvenementFlux(uid, titre, jour, jour + timedelta(days=1), True)


def _evenements_du_jour(taches, jour, J, travailles, titre_de):
    """Horodatées par heure, puis ≤ 8 journées entières (priorité, `rang_jour`, `cle_tri`), puis « + N autres »."""
    cle = cle_tri_pour(J, travailles)
    horaires = sorted((t for t in taches if t.heure_debut is not None), key=lambda t: (t.heure_debut, cle(t)))
    entieres = sorted((t for t in taches if t.heure_debut is None),
                      key=lambda t: (-t.priorite, t.rang_jour is None, t.rang_jour, cle(t)))
    sortie = [_evenement_horaire(t, titre_de(t)) for t in horaires]
    sortie += [_evenement_journee(f'tache-{t.id}', titre_de(t), jour) for t in entieres[:JOURNEES_MAX]]
    if len(entieres) > JOURNEES_MAX:
        uid = f'taches-autres-{jour:%Y%m%d}'
        sortie.append(_evenement_journee(uid, _accord_autres(len(entieres) - JOURNEES_MAX), jour))
    return sortie


def evenements_flux(taches, jour, reglages, nom_pour, travailles=frozenset()):
    """Événements du flux `.ics` à partir de J = `jour` : 200 au plus, le dernier jour tronqué."""
    par_jour = {}
    for t in taches:
        if emise_au_flux(t, jour):
            par_jour.setdefault(t.jour_prevu, []).append(t)
    sortie = []
    for d in sorted(par_jour):
        sortie += _evenements_du_jour(par_jour[d], d, jour, travailles,
                                      lambda t: nom_pour(t, USAGE_FLUX, reglages))
        if len(sortie) >= EVENEMENTS_MAX:
            break
    return tuple(sortie[:EVENEMENTS_MAX])


# --- Tuile -----------------------------------------------------------------

def _hh_mm(heure):
    return None if heure is None else f'{heure:%H:%M}'


def gardes_ouverts(items, J, plan, travailles):
    """((item, section), …) : éléments OUVERTS et GARDÉS d'Essentiel, Prévu, Ce soir (inv. 11)."""
    sortie = []
    for item in items:
        p = placer(item, J, plan, travailles)
        ouvert = item.type == ACTIVITE or item.statut == StatutTache.A_FAIRE
        if p is not None and p.section in SECTIONS_GARDEES and ouvert:
            sortie.append((item, p.section))
    return sortie


def _top(gardes, J, travailles):
    """Tâches gardées dans l'ordre de l'écran ; jamais une activité ERP (IR15)."""
    rang = {section: n for n, section in enumerate(SECTIONS_GARDEES)}
    taches = [(i, s) for i, s in gardes if i.type == TACHE]
    taches.sort(key=lambda ligne: (rang[ligne[1]], cle_section(ligne[0], J, travailles)))
    return [i for i, _ in taches[:TOP_MAX]]


def prochaine_echeance(items, J, travailles):
    """Tâche ouverte du préfiltre à plus petite (`echeance`, `echeance_heure`) ≥ J, ou None."""
    cle = cle_tri_pour(J, travailles)
    ouvertes = [t for t in items if t.type == TACHE and t.statut == StatutTache.A_FAIRE
                and not t.quelque_jour and dans_prefiltre(t) and t.echeance is not None and t.echeance >= J]
    if not ouvertes:
        return None
    return min(ouvertes, key=lambda t: (t.echeance, t.echeance_heure is None, t.echeance_heure, cle(t)))


def tuile_pure(items, J, plan, objectif, progression, reglages, nom_pour, travailles=frozenset()):
    """Corps de la tuile hors `jour`, `maj`, `lien` (posés par la vue) — mêmes règles que l'écran."""
    gardes = gardes_ouverts(items, J, plan, travailles)
    pastille = min(PASTILLE_MAX, len(gardes))
    top = _top(gardes, J, travailles)
    echeance = prochaine_echeance(items, J, travailles)
    return {
        'faites': progression['faites'],
        'prevues': progression['prevues'],
        'objectif': objectif,
        'essentiel': {'faites': progression['essentiel_faites'], 'prevues': progression['essentiel_prevues']},
        'top': [{'id': t.id, 'titre': nom_pour(t, USAGE_TUILE, reglages), 'heure': _hh_mm(t.heure_debut),
                 'priorite': t.priorite} for t in top],
        'reste': max(0, pastille - len(top)),
        'prochaine_echeance': None if echeance is None else {
            'titre': nom_pour(echeance, USAGE_TUILE, reglages),
            'jour': echeance.echeance.isoformat(),
            'heure': _hh_mm(echeance.echeance_heure),
        },
    }

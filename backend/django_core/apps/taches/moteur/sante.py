"""TCH31 — la santé d'un projet (reference/regles.md §5), module PUR : ni Django, ni base, ni horloge.

Le jour J et l'ensemble des jours travaillés sont des paramètres. Les tâches sont des objets portant les
champs d'`ItemPur` (regles.md §0.1) ; `annule_le` (burn-up) est lu s'il existe. Les phrases sont celles de
textes.md (« Santé »).
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from apps.taches.moteur.gabarits import format_jour

A_FAIRE = 'a_faire'
EN_ATTENTE = 'en_attente'
FAIT = 'fait'
ANNULE = 'annule'

ARRET_JOURS_DEFAUT = 10  # `projet_arret_jours`, 5 à 30 (regles.md §5)
NEGLIGE_JOURS = 14
CONSTAT_JOURS = 7
RYTHME_JOURS = 28
RYTHME_FAITES_MIN = 5

_PRIORITES = {3: 'haute', 2: 'moyenne', 1: 'basse', 0: 'sans priorité'}


@dataclass(frozen=True)
class Signal:
    code: str
    phrase: str
    donnees: dict


@dataclass(frozen=True)
class ProjetSante:
    """Ce que la santé lit d'un projet. `etapes` : (nom, date_fin) ; `actionnables` : voir `nb_actionnables`."""
    id: int
    nom: str
    priorite: int
    rang: int
    statut_depuis: date
    statut: str = 'actif'
    echeance: date = None
    etapes: tuple = ()
    planification_le: date = None
    actionnables: int = 0


@dataclass(frozen=True)
class Avancement:
    faites: int
    total: int
    derniere_faite: date
    barre: bool
    texte: str


@dataclass(frozen=True)
class PointBurnup:
    fin: date
    total: int
    faites: int


@dataclass(frozen=True)
class Burnup:
    points: tuple
    legende: str


def _jour(v):
    if v is None:
        return None
    return v.date() if isinstance(v, datetime) else v


def _jj_mm(d):
    return f'{d.day:02d}/{d.month:02d}'


def _comptees(taches):
    return [t for t in taches if t.parent_id is None and t.statut != ANNULE]


def _ouvertes(taches):
    return [t for t in _comptees(taches) if t.statut in (A_FAIRE, EN_ATTENTE)]


def _actionnable(t):
    return t.statut == A_FAIRE and not t.quelque_jour and t.bloquee_par is None


def nb_actionnables(taches):
    """Nombre de tâches actionnables (ouvertes, à faire, hors réserve, non bloquées) du projet."""
    return sum(1 for t in _ouvertes(taches) if _actionnable(t))


def _faits_tous_niveaux(taches):
    return [_jour(t.fait_le) for t in taches if t.statut == FAIT and t.fait_le is not None]


def _jours_travailles(travailles, apres, jusqua):
    """Jours travaillés dans ]apres, jusqua]."""
    return sum(1 for d in travailles if apres < d <= jusqua)


def avancement(taches):
    """« F sur F+O » et dernière faite ; 0 comptée → pas de barre."""
    comptees = _comptees(taches)
    faites = [t for t in comptees if t.statut == FAIT]
    total = len(comptees)
    dates = [_jour(t.fait_le) for t in faites if t.fait_le is not None]
    return Avancement(
        faites=len(faites), total=total, derniere_faite=max(dates) if dates else None,
        barre=total > 0, texte=f'{len(faites)} sur {total}')


def _dimanche(d):
    return d + timedelta(days=6 - d.weekday())


def _compte_a(taches, fin):
    """(total, faites) des comptées à la fin de semaine `fin` (reconstruit sur les dates actuelles)."""
    total = faites = 0
    for t in taches:
        if t.parent_id is not None or _jour(t.created_at) > fin:
            continue
        annule_le = _jour(getattr(t, 'annule_le', None))
        if t.statut == ANNULE and (annule_le is None or annule_le <= fin):
            continue
        total += 1
        if t.statut == FAIT and t.fait_le is not None and _jour(t.fait_le) <= fin:
            faites += 1
    return total, faites


def burnup(taches, J):
    """Un point par semaine close (fin dimanche, avant J) ; légende dès 2 semaines."""
    debuts = [_jour(t.created_at) for t in taches if t.parent_id is None]
    if not debuts:
        return Burnup(points=(), legende='')
    fin, points = _dimanche(min(debuts)), []
    while fin < J:
        total, faites = _compte_a(taches, fin)
        points.append(PointBurnup(fin=fin, total=total, faites=faites))
        fin += timedelta(days=7)
    legende = 'reconstruit depuis les dates actuelles' if len(points) >= 2 else ''
    return Burnup(points=tuple(points), legende=legende)


_PHRASES_SANS_ACTION = {
    'reserve': 'Rien à faire maintenant : tout est en réserve.',
    'attend': 'Tout attend quelqu\'un ou une autre tâche.',
    'mixte': 'Rien à faire maintenant : ajoute la prochaine tâche.',
}


def sans_prochaine_action(taches):
    """≥ 1 ouverte et 0 actionnable ; la cause : tout en réserve, tout attend, ou un mélange."""
    ouvertes = _ouvertes(taches)
    if not ouvertes or any(_actionnable(t) for t in ouvertes):
        return None
    if all(t.quelque_jour for t in ouvertes):
        cause = 'reserve'
    elif all(t.statut == EN_ATTENTE or t.bloquee_par is not None for t in ouvertes):
        cause = 'attend'
    else:
        cause = 'mixte'
    return Signal('sans_prochaine_action', _PHRASES_SANS_ACTION[cause], {'cause': cause})


def tout_fait(taches):
    """0 ouverte et ≥ 1 faite → « Tout est fait : terminer le projet ? »."""
    comptees = _comptees(taches)
    if _ouvertes(taches) or not any(t.statut == FAIT for t in comptees):
        return None
    return Signal('tout_fait', 'Tout est fait : terminer le projet ?', {})


def a_l_arret(taches, projet, J, travailles, n=ARRET_JOURS_DEFAUT):
    """≥ 1 ouverte et au moins `n` jours travaillés depuis la référence (dernière faite, tous niveaux, ou statut)."""
    if not _ouvertes(taches):
        return None
    reperes = _faits_tous_niveaux(taches) + [_jour(projet.statut_depuis)]
    ref = max(reperes)
    jours = _jours_travailles(travailles, ref, J)
    if jours < n:
        return None
    return Signal('a_l_arret', f'Rien de fait depuis {jours} jours travaillés.',
                  {'jours': jours, 'depuis': ref.isoformat()})


def _date_prevue(t):
    return t.jour_prevu if t.jour_prevu is not None else t.echeance


def _signal_menace(code_cas, phrase, donnees):
    return Signal('echeance_menacee', phrase, dict(donnees, signal=code_cas))


def _besoin_rythme(taches, projet, J, travailles, ouvertes):
    """Signal (d) : (besoin, reste, f28, j28) si le rythme des 28 jours ne tient pas, sinon None."""
    debut = J - timedelta(days=RYTHME_JOURS)
    f28 = sum(1 for t in _comptees(taches) if t.statut == FAIT and t.fait_le is not None
              and debut < _jour(t.fait_le) <= J)
    if f28 < RYTHME_FAITES_MIN:
        return None
    j28 = _jours_travailles(travailles, debut, J)
    besoin = -(-len(ouvertes) * j28 // f28)
    reste = _jours_travailles(travailles, J, projet.echeance)
    return (besoin, reste, f28, j28) if besoin > reste else None


def echeance_menacee(taches, projet, J, travailles, rythme=False):
    """Premier signal vrai parmi (a) dépassée, (b) tâches après, (c) étape après, (d) rythme (si `rythme`)."""
    ouvertes = _ouvertes(taches)
    ech = projet.echeance
    if ech is None or not ouvertes:
        return None
    if ech < J:
        return _signal_menace('a', f'Échéance dépassée le {_jj_mm(ech)}.', {'echeance': ech.isoformat()})
    apres = [t for t in ouvertes if _date_prevue(t) is not None and _date_prevue(t) > ech]
    if apres:
        k = len(apres)
        mot = 'tâche est prévue' if k == 1 else 'tâches sont prévues'
        return _signal_menace('b', f'{k} {mot} après l\'échéance.', {'k': k})
    for nom, fin in projet.etapes:
        if fin is not None and fin > ech:
            return _signal_menace('c', f'L\'étape « {nom} » finit après l\'échéance.', {'etape': nom})
    calcul = _besoin_rythme(taches, projet, J, travailles, ouvertes) if rythme else None
    if calcul is None:
        return None
    besoin, reste, f28, j28 = calcul
    # R2-034 — la conséquence d'abord ; R3-011 — UN chiffre à lire, déjà soustrait (« il manque environ 2 jours »),
    # jamais un calcul à refaire de tête ; le détail (besoin, reste, F28, J28) reste dans `donnees`
    jour = format_jour(ech, J)
    quand = jour if jour in ("aujourd'hui", 'demain') else f'le {jour}'
    manque = besoin - reste
    phrase = f"À ce rythme, pas prêt pour {quand} : il manque environ {manque} jour{'s' if manque > 1 else ''}."
    return _signal_menace('d', phrase, {'besoin': besoin, 'reste': reste, 'f28': f28, 'j28': j28,
                                        'echeance': ech.isoformat()})


def _autre_de_reference(projet, faites_14j, projets):
    """Q : le plus avancé des projets actifs de priorité strictement inférieure avec d ≥ 1."""
    candidats = [q for q in projets if q.statut == 'actif' and q.priorite < projet.priorite
                 and faites_14j.get(q.id, 0) >= 1]
    if not candidats:
        return None
    return min(candidats, key=lambda q: (-faites_14j[q.id], -q.priorite, q.rang))


def _faite(d):
    return f'{d} faite' if d <= 1 else f'{d} faites'


def neglige(projets, faites_14j, J):
    """{id du projet négligé: Signal}. `faites_14j` : id → tâches faites (tous niveaux) sur 14 jours."""
    limite = J - timedelta(days=NEGLIGE_JOURS)
    rendu = {}
    for p in projets:
        if p.statut != 'actif' or p.actionnables < 1 or _jour(p.statut_depuis) > limite:
            continue
        if faites_14j.get(p.id, 0) != 0:
            continue
        q = _autre_de_reference(p, faites_14j, projets)
        if q is None:
            continue
        d = faites_14j[q.id]
        phrase = (f'« {p.nom} » ({_PRIORITES.get(p.priorite, "")}) n\'a rien vu avancer en '
                  f'{NEGLIGE_JOURS} jours ; « {q.nom} » ({_PRIORITES.get(q.priorite, "")}) : {_faite(d)}.')
        rendu[p.id] = Signal('neglige', phrase, {'projet': p.nom, 'autre': q.nom, 'autre_id': q.id, 'd': d})
    return rendu


def a_planifier(projet, nb_ouvertes):
    """« À planifier » ⇔ actif, jamais planifié, 0 ouverte."""
    return projet.statut == 'actif' and projet.planification_le is None and nb_ouvertes == 0


def constat_projets(actifs, faites_7j):
    """« {actifs} projets actifs, {k} ont avancé ces 7 jours ». `actifs` : ids ; `faites_7j` : id → faites."""
    n = len(actifs)
    k = sum(1 for i in actifs if faites_7j.get(i, 0) >= 1)
    sujet = 'projet actif' if n <= 1 else 'projets actifs'
    verbe = 'a avancé' if k <= 1 else 'ont avancé'
    return {'actifs': n, 'k': k, 'phrase': f'{n} {sujet}, {k} {verbe} ces {CONSTAT_JOURS} jours'}

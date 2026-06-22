"""Jours fériés & jours ouvrés (socle minimal — dépendance FG5).

FG5 (modèle ``Holiday`` / ``WorkingHoursConfig`` global) n'existe pas encore
dans le dépôt. En attendant, ce module fournit le strict nécessaire au décompte
des congés (FG163) : la liste des jours fériés FIXES marocains et un calcul de
jours ouvrés (hors week-end samedi/dimanche et hors fériés) entre deux dates.

Quand FG5 atterrira, ``working_days`` pourra consommer ce modèle à la place de la
table fixe ci-dessous sans changer sa signature. Les fêtes religieuses (Aïd,
Mouloud, 1er Moharram) suivent le calendrier hégirien et glissent chaque année :
elles ne sont PAS codées en dur ici (ce serait faux) ; une société peut les
ajouter via ``extra_holidays`` à l'appel.
"""
from datetime import date, timedelta

# Jours fériés marocains à DATE FIXE (grégorienne). Les fêtes mobiles (Aïd
# el-Fitr, Aïd el-Adha, 1er Moharram, Aïd el-Mawlid) ne sont pas listées ici.
JOURS_FERIES_FIXES_MA = {
    (1, 1): "Nouvel an",
    (1, 11): "Manifeste de l'indépendance",
    (5, 1): "Fête du Travail",
    (7, 30): "Fête du Trône",
    (8, 14): "Allégeance Oued Eddahab",
    (8, 20): "Révolution du Roi et du Peuple",
    (8, 21): "Fête de la Jeunesse",
    (11, 6): "Marche Verte",
    (11, 18): "Fête de l'Indépendance",
}

# Week-end ouvré au Maroc : samedi (5) et dimanche (6) chômés.
WEEKEND = {5, 6}


def is_ferie_fixe(d):
    """Vrai si ``d`` est un jour férié marocain à date fixe."""
    return (d.month, d.day) in JOURS_FERIES_FIXES_MA


def is_jour_ouvre(d, extra_holidays=None):
    """Vrai si ``d`` est un jour ouvré : ni week-end, ni férié.

    ``extra_holidays`` — itérable optionnel de ``date`` supplémentaires (fêtes
    mobiles configurées par la société) traitées comme fériées.
    """
    if d.weekday() in WEEKEND:
        return False
    if is_ferie_fixe(d):
        return False
    if extra_holidays and d in set(extra_holidays):
        return False
    return True


def working_days(date_debut, date_fin, extra_holidays=None):
    """Nombre de jours OUVRÉS entre ``date_debut`` et ``date_fin`` inclus.

    Exclut samedis, dimanches et jours fériés marocains à date fixe (plus tout
    ``extra_holidays`` fourni). Renvoie 0 si ``date_fin`` précède ``date_debut``.
    Borne supérieure (un an + marge) pour éviter une boucle non bornée sur des
    entrées aberrantes.
    """
    if date_debut is None or date_fin is None or date_fin < date_debut:
        return 0
    extra = set(extra_holidays) if extra_holidays else None
    count = 0
    d = date_debut
    # Garde-fou : on ne décompte jamais plus de ~2 ans de plage.
    limite = date_debut + timedelta(days=800)
    while d <= date_fin and d <= limite:
        if is_jour_ouvre(d, extra):
            count += 1
        d += timedelta(days=1)
    return count


def calendar_days(date_debut, date_fin):
    """Nombre de jours CALENDAIRES entre les deux dates incluses (>= 0)."""
    if date_debut is None or date_fin is None or date_fin < date_debut:
        return 0
    return (date_fin - date_debut).days + 1


def annee_courante(d=None):
    """Année de ``d`` (ou d'aujourd'hui)."""
    return (d or date.today()).year

"""Jours fériés & jours ouvrés (socle minimal — dépendance FG5).

FG5 (modèle ``Holiday`` / ``WorkingHoursConfig`` par société) a depuis atterri
dans ``apps.notifications`` (jamais importé ici — cross-app-safe : ``rh``
consomme les fériés RÉELS d'une société via
``apps.rh.services.feries_periode`` → ``apps.notifications.calendar_utils.
feries_entre``, cf. ZRH1). Ce module reste le socle PUR PYTHON, sans base de
données : la table de fériés FIXES par pays qui sert (a) de comportement par
défaut quand aucune ``Holiday`` n'est configurée pour la société et (b) de
brique de base pour ``working_days``/``is_jour_ouvre`` hors contexte société
(tests, calculs isolés).

NTI18N13 — généralisé d'une table mono-pays (Maroc) à une table PAR PAYS
(``JOURS_FERIES_FIXES_PAR_PAYS``), sélectionnée via le paramètre optionnel
``pays`` (code ISO 3166-1 alpha-2, défaut ``'MA'`` — comportement identique
pour tout appelant existant qui ne le précise pas). Seuls les jours fériés à
DATE FIXE (grégorienne) sont listés ; les fêtes religieuses mobiles (Aïd,
Mouloud, 1er Moharram, Pâques/Ascension/Pentecôte…) suivent un calendrier
lunaire ou lunisolaire et glissent chaque année : elles ne sont JAMAIS codées
en dur ici (ce serait faux) — une société les ajoute via ``extra_holidays`` à
l'appel (saisie manuelle dans ``notifications.Holiday``, cf. ZRH1/NTI18N14).

Câblage multi-pays complet HORS PÉRIMÈTRE de ce module (moitiés étrangères à
construire ailleurs, jamais touchées ici) : ``Holiday.pays`` et un seeder par
pays (``apps.notifications``), ``CompanyProfile.pays`` (``apps.parametres``)
pour que ``working_days()`` sache quel ``pays`` passer pour une société donnée.
"""
from datetime import date, timedelta

# Jours fériés à DATE FIXE (grégorienne), PAR PAYS (ISO 3166-1 alpha-2). Les
# fêtes mobiles (hégiriennes, ou basées sur Pâques) ne sont JAMAIS listées ici.
JOURS_FERIES_FIXES_PAR_PAYS = {
    # Maroc — comportement historique, INCHANGÉ (défaut de ce module).
    'MA': {
        (1, 1): "Nouvel an",
        (1, 11): "Manifeste de l'indépendance",
        (5, 1): "Fête du Travail",
        (7, 30): "Fête du Trône",
        (8, 14): "Allégeance Oued Eddahab",
        (8, 20): "Révolution du Roi et du Peuple",
        (8, 21): "Fête de la Jeunesse",
        (11, 6): "Marche Verte",
        (11, 18): "Fête de l'Indépendance",
    },
    # France — jours fériés légaux à date FIXE uniquement (les fériés basés
    # sur Pâques — Lundi de Pâques, Ascension, Lundi de Pentecôte — sont
    # mobiles et donc exclus, comme au Maroc).
    'FR': {
        (1, 1): "Jour de l'An",
        (5, 1): "Fête du Travail",
        (5, 8): "Victoire 1945",
        (7, 14): "Fête nationale",
        (8, 15): "Assomption",
        (11, 1): "Toussaint",
        (11, 11): "Armistice 1918",
        (12, 25): "Noël",
    },
    # Sénégal — jours fériés civils/chrétiens à date FIXE (les fêtes
    # musulmanes — Korité, Tabaski, Maouloud — sont mobiles, exclues).
    'SN': {
        (1, 1): "Jour de l'An",
        (4, 4): "Fête de l'Indépendance",
        (5, 1): "Fête du Travail",
        (8, 15): "Assomption",
        (11, 1): "Toussaint",
        (12, 25): "Noël",
    },
    # Côte d'Ivoire — jours fériés civils/chrétiens à date FIXE (les fêtes
    # musulmanes sont mobiles, exclues).
    'CI': {
        (1, 1): "Jour de l'An",
        (5, 1): "Fête du Travail",
        (8, 7): "Fête de l'Indépendance",
        (8, 15): "Assomption",
        (11, 1): "Toussaint",
        (12, 25): "Noël",
    },
}

# Rétro-compatibilité : tout code existant important ``JOURS_FERIES_FIXES_MA``
# directement continue de fonctionner à l'identique (alias, jamais dupliqué).
JOURS_FERIES_FIXES_MA = JOURS_FERIES_FIXES_PAR_PAYS['MA']

# Pays de repli si ``pays`` est absent de la table (jamais une exception).
PAYS_DEFAUT = 'MA'

# Week-end ouvré au Maroc : samedi (5) et dimanche (6) chômés. Utilisé comme
# défaut pour tous les pays de la table (aucun des pays ci-dessus n'a un
# week-end différent de samedi/dimanche parmi ceux modélisés).
WEEKEND = {5, 6}


def _table_fixe(pays):
    """Table de fériés fixes du ``pays`` demandé, repli sur ``PAYS_DEFAUT``."""
    return JOURS_FERIES_FIXES_PAR_PAYS.get(
        pays or PAYS_DEFAUT, JOURS_FERIES_FIXES_PAR_PAYS[PAYS_DEFAUT])


def is_ferie_fixe(d, pays=PAYS_DEFAUT):
    """Vrai si ``d`` est un jour férié à date fixe pour ``pays`` (défaut MA)."""
    return (d.month, d.day) in _table_fixe(pays)


def is_jour_ouvre(d, extra_holidays=None, pays=PAYS_DEFAUT):
    """Vrai si ``d`` est un jour ouvré : ni week-end, ni férié.

    ``extra_holidays`` — itérable optionnel de ``date`` supplémentaires (fêtes
    mobiles ou fériés société configurés, cf. ``notifications.Holiday``)
    traitées comme fériées. ``pays`` — code ISO 3166-1 alpha-2 sélectionnant
    la table de fériés fixes (défaut ``'MA'`` : comportement inchangé pour
    tout appelant existant).
    """
    if d.weekday() in WEEKEND:
        return False
    if is_ferie_fixe(d, pays=pays):
        return False
    if extra_holidays and d in set(extra_holidays):
        return False
    return True


def working_days(date_debut, date_fin, extra_holidays=None, pays=PAYS_DEFAUT):
    """Nombre de jours OUVRÉS entre ``date_debut`` et ``date_fin`` inclus.

    Exclut samedis, dimanches et jours fériés fixes du ``pays`` demandé
    (défaut ``'MA'``, comportement inchangé pour tout appelant existant), plus
    tout ``extra_holidays`` fourni. Renvoie 0 si ``date_fin`` précède
    ``date_debut``. Borne supérieure (un an + marge) pour éviter une boucle
    non bornée sur des entrées aberrantes.
    """
    if date_debut is None or date_fin is None or date_fin < date_debut:
        return 0
    extra = set(extra_holidays) if extra_holidays else None
    count = 0
    d = date_debut
    # Garde-fou : on ne décompte jamais plus de ~2 ans de plage.
    limite = date_debut + timedelta(days=800)
    while d <= date_fin and d <= limite:
        if is_jour_ouvre(d, extra, pays=pays):
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

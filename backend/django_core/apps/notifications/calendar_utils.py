"""FG5 — Utilitaires de calendrier ouvré, par société.

Quatre helpers publics :
  - is_jour_ouvre(date, company)         → bool
  - prochain_jour_ouvre(date, company)   → date (premier jour ouvré ≥ date)
  - ajouter_jours_ouvres(date, n, company) → date après n jours ouvrés
  - feries_entre(company, debut, fin)    → liste de `date` fériées (ZRH1) —
    surface de LECTURE cross-app-safe (jamais d'import de
    ``notifications.models`` en dehors de ce module) pour alimenter un
    décompte de jours avec les fêtes MOBILES (Aïd, Mawlid…) saisies dans
    `Holiday`.

Un « jour ouvré » = un jour de la semaine marqué comme ouvré dans la
`WorkingHoursConfig` de la société ET non présent dans sa table `Holiday`
(qu'il soit récurrent annuel ou une date exacte pour l'année courante).

ADDITIF : sans `WorkingHoursConfig` pour la société, on tombe sur le défaut
Lundi–Vendredi (bits 0–4, valeur 31). Sans aucune `Holiday`, aucun jour n'est
bloqué par les fériés.

PERFORMANCE : les deux ensembles (config + fériés de l'année) sont chargés
une seule fois par appel de haut niveau et propagés. Un appel isolé à
`is_jour_ouvre` charge toujours les données fraîches (usage direct simple).
"""
from __future__ import annotations

import datetime
import logging

logger = logging.getLogger(__name__)

# Bitmask défaut : Lundi–Vendredi (bits 0–4).
_DEFAULT_WORKING_DAYS = 0b00011111  # 31

# Garde-fou contre une boucle infinie (ex. société avec 0 jours ouvrés).
_MAX_ITERATIONS = 1000


# ---------------------------------------------------------------------------
# Chargement des données (lazy, par appel)
# ---------------------------------------------------------------------------

def _load_working_days(company) -> int:
    """Charge le bitmask de jours ouvrés de la société. Défaut : Lun–Ven."""
    try:
        from .models import WorkingHoursConfig
        cfg = WorkingHoursConfig.objects.filter(company=company).first()
        if cfg is not None:
            return cfg.working_days
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('calendar_utils: chargement WorkingHoursConfig échoué : %s', exc)
    return _DEFAULT_WORKING_DAYS


class _Feries:
    """CAD42 — les fériés d'une société, avec DEUX clés distinctes.

    Un férié RÉCURRENT (1ᵉʳ Mai, Fête du Trône…) se compare sur (mois, jour) :
    c'est la même date chaque année. Un férié NON récurrent (un Aïd, saisi
    pour une année précise) se compare sur la DATE COMPLÈTE.

    Avant CAD42, les deux partageaient la clé (mois, jour) alors que
    ``prochain_jour_ouvre`` et ``ajouter_jours_ouvres`` chargent PLUSIEURS
    années d'un coup : trois Aïd saisis = trois dates bloquées CHAQUE année.
    ``feries_entre`` faisait déjà la distinction correctement — les deux
    lectures parlent enfin du même calendrier.
    """

    __slots__ = ('recurrents', 'dates')

    def __init__(self, recurrents=None, dates=None):
        self.recurrents: set[tuple[int, int]] = set(recurrents or ())
        self.dates: set[datetime.date] = set(dates or ())

    def __ior__(self, autre: '_Feries') -> '_Feries':
        self.recurrents |= autre.recurrents
        self.dates |= autre.dates
        return self

    def contient(self, d: datetime.date) -> bool:
        return (d.month, d.day) in self.recurrents or d in self.dates

    def __bool__(self) -> bool:
        return bool(self.recurrents or self.dates)


def _load_holidays_for_year(company, year: int) -> _Feries:
    """Les fériés de la société applicables à `year`.

    Les jours récurrents annuels sont retenus par (mois, jour) ; les jours
    NON récurrents par leur date complète, et seulement s'ils tombent dans
    `year` — une fête lunaire saisie pour 2027 ne bloque rien en 2026.
    """
    try:
        from .models import Holiday
        qs = Holiday.objects.filter(company=company)
        feries = _Feries()
        for h in qs:
            if h.recurrent_annuel:
                feries.recurrents.add((h.date.month, h.date.day))
            elif h.date.year == year:
                feries.dates.add(h.date)
        return feries
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('calendar_utils: chargement Holiday échoué : %s', exc)
        return _Feries()


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _is_holiday(d: datetime.date, holidays: '_Feries') -> bool:
    return holidays.contient(d)


def _is_working_day_raw(
        d: datetime.date,
        working_days: int,
        holidays: '_Feries') -> bool:
    """Vrai si `d` est ouvré selon le bitmask ET non férié."""
    weekday = d.weekday()  # 0=Lun … 6=Dim
    if not (working_days & (1 << weekday)):
        return False
    return not _is_holiday(d, holidays)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def is_jour_ouvre(d: datetime.date, company) -> bool:
    """Renvoie True si `d` est un jour ouvré pour `company`.

    Tient compte du bitmask de jours de travail ET des jours fériés (fixes +
    annuels) de la société. Sans configuration : Lun–Ven, aucun férié.
    """
    working_days = _load_working_days(company)
    holidays = _load_holidays_for_year(company, d.year)
    return _is_working_day_raw(d, working_days, holidays)


def prochain_jour_ouvre(d: datetime.date, company) -> datetime.date:
    """Renvoie le premier jour ouvré >= `d` pour `company`.

    Si `d` est déjà ouvré, le renvoie tel quel. Sinon avance d'un jour à la
    fois. Sécurisé contre une configuration sans aucun jour ouvré (retourne
    `d` + _MAX_ITERATIONS au pire).
    """
    working_days = _load_working_days(company)
    # Charge les fériés pour l'année de départ + l'année suivante (si on
    # franchit le 31/12).
    holidays = _Feries()
    holidays |= _load_holidays_for_year(company, d.year)
    holidays |= _load_holidays_for_year(company, d.year + 1)

    current = d
    for _ in range(_MAX_ITERATIONS):
        if _is_working_day_raw(current, working_days, holidays):
            return current
        current += datetime.timedelta(days=1)
    # Garde-fou : ne devrait jamais se produire avec une config valide.
    logger.warning(
        'prochain_jour_ouvre: aucun jour ouvré trouvé pour %s après %d itérations.',
        company, _MAX_ITERATIONS)
    return current


def ajouter_jours_ouvres(d: datetime.date, n: int, company) -> datetime.date:
    """Renvoie la date après avoir avancé de `n` jours ouvrés depuis `d`.

    `d` lui-même N'est PAS compté (on part du lendemain si n > 0). Si n = 0,
    renvoie `d` (comportement identique à prochain_jour_ouvre).
    Si n < 0, renvoie `d` sans modifier (cas non supporté, comportement sûr).
    Sécurisé contre l'absence de jours ouvrés (_MAX_ITERATIONS).
    """
    if n < 0:
        logger.warning('ajouter_jours_ouvres: n < 0 (%d) ignoré.', n)
        return d
    if n == 0:
        return prochain_jour_ouvre(d, company)

    working_days = _load_working_days(company)
    # Pré-charge les fériés pour une plage raisonnable (année de `d` + 2 ans).
    holidays = _Feries()
    for yr in range(d.year, d.year + 3):
        holidays |= _load_holidays_for_year(company, yr)

    current = d
    remaining = n
    iterations = 0
    while remaining > 0 and iterations < _MAX_ITERATIONS:
        current += datetime.timedelta(days=1)
        iterations += 1
        if _is_working_day_raw(current, working_days, holidays):
            remaining -= 1

    if remaining > 0:
        logger.warning(
            'ajouter_jours_ouvres: %d jours restants après %d itérations.',
            remaining, _MAX_ITERATIONS)

    return current


# ---------------------------------------------------------------------------
# NTWFL4 — échéance SLA en heures OUVRÉES (core.workflow branché via registre)
# ---------------------------------------------------------------------------

def ajouter_heures_ouvrees(
        started: datetime.datetime, sla_heures: int, company,
) -> datetime.datetime:
    """Échéance ``started + sla_heures`` (datetime) où les jours NON OUVRÉS
    traversés sont SAUTÉS plutôt que comptés (calendrier de la société,
    fériés inclus). Les heures INTRA-journée restent linéaires — pas de
    découpage horaire fin (hors scope) : un jour est soit entièrement compté,
    soit entièrement sauté.

    Point fixe : après avoir décalé l'échéance brute du nombre de jours non
    ouvrés déjà traversés, on recompte les jours NOUVELLEMENT couverts par ce
    décalage et on répète jusqu'à stabilité (aucun jour supplémentaire
    sauté) — c'est ainsi qu'une échéance de 48h démarrée un vendredi finit
    par sauter tout le week-end plutôt qu'un seul jour. Bornée par
    ``_MAX_ITERATIONS`` (garde-fou société sans aucun jour ouvré, comme les
    autres helpers de ce module).

    C'est le résolveur branché par ``apps.notifications.apps.ready()`` sur
    ``core.workflow.register_business_day_advance`` (NTWFL4) — ``core`` reste
    fondation et n'importe jamais ce module directement.
    """
    if not sla_heures:
        return started
    candidate = started + datetime.timedelta(hours=sla_heures)
    dernier_jour_compte = started.date()
    for _ in range(_MAX_ITERATIONS):
        jours_sautes = 0
        jour = dernier_jour_compte + datetime.timedelta(days=1)
        while jour <= candidate.date():
            if not is_jour_ouvre(jour, company):
                jours_sautes += 1
            jour += datetime.timedelta(days=1)
        if jours_sautes == 0:
            return candidate
        dernier_jour_compte = candidate.date()
        candidate = candidate + datetime.timedelta(days=jours_sautes)
    logger.warning(
        'ajouter_heures_ouvrees: pas de stabilisation après %d itérations.',
        _MAX_ITERATIONS)
    return candidate


def feries_entre(
        company, date_debut: datetime.date,
        date_fin: datetime.date, pays: str | None = None) -> list[datetime.date]:
    """ZRH1 — liste les dates FÉRIÉES de la société dans ``[date_debut,
    date_fin]`` (inclusif), fixes ET mobiles (Aïd, Mawlid, 1er Moharram…)
    saisies dans `Holiday`.

    Résout les jours récurrents annuels (mois/jour) sur CHAQUE année couverte
    par la fenêtre, et les jours non récurrents uniquement pour leur année
    exacte. Renvoie une liste de ``date`` triée, sans doublon. Sans
    `Holiday` configuré pour la société : liste vide (comportement sûr,
    n'affecte aucun décompte existant).

    HOLIDAY-PAYS (complément NTI18N13) : ``pays`` (ISO 3166-1 alpha-2,
    ex. ``'FR'``) filtre sur ``Holiday.pays`` QUAND il est fourni — l'appel
    historique (``pays=None``, défaut) ignore ce champ et renvoie TOUS les
    jours fériés de la société quel que soit leur pays, exactement comme
    avant l'ajout du champ (zéro régression pour les appelants existants qui
    ne passent pas ce paramètre).
    """
    if date_debut is None or date_fin is None or date_debut > date_fin:
        return []
    try:
        from .models import Holiday
        qs = Holiday.objects.filter(company=company)
        if pays:
            qs = qs.filter(pays=pays)
        resultats: set[datetime.date] = set()
        for h in qs:
            if h.recurrent_annuel:
                for year in range(date_debut.year, date_fin.year + 1):
                    try:
                        candidate = datetime.date(year, h.date.month, h.date.day)
                    except ValueError:
                        continue  # 29 février sur année non bissextile.
                    if date_debut <= candidate <= date_fin:
                        resultats.add(candidate)
            elif date_debut <= h.date <= date_fin:
                resultats.add(h.date)
        return sorted(resultats)
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('calendar_utils: feries_entre échoué : %s', exc)
        return []


# ── CAD40 ── rappel « les fêtes mobiles de l'année ne sont pas saisies » ────

def rappel_fetes_mobiles(company, annee=None):
    """``None`` si tout va bien, sinon une PHRASE française à afficher.

    Les fêtes mobiles (Aïd al-Fitr, Aïd al-Adha, Nouvel An hégirien, Aïd
    al-Mawlid) suivent le calendrier lunaire : leur date n'est JAMAIS
    calculée ici, elle est saisie (Paramètres → Localisation → Fêtes
    mobiles) ou posée à la création de la société quand ``core.calendar`` la
    connaît déjà. Tant qu'aucune n'existe pour l'année demandée,
    ``is_jour_ouvre`` laisse passer le jour de l'Aïd — et une touche de
    cadence peut y tomber. Ce rappel est ce qui rend ce trou VISIBLE.

    Ne compte que les lignes NON récurrentes : cocher « Récurrent chaque
    année » sur un Aïd est justement l'erreur que CAD42 traite, et une telle
    ligne ne prouve pas que l'année en cours est saisie.
    """
    if annee is None:
        from core.dates import aujourd_hui_local
        annee = aujourd_hui_local().year
    try:
        annee = int(annee)
    except (TypeError, ValueError):
        return None
    try:
        from .models import Holiday
        existe = Holiday.objects.filter(
            company=company, recurrent_annuel=False,
            date__year=annee).exists()
    except Exception as exc:  # pragma: no cover - défensif
        logger.warning('calendar_utils: rappel_fetes_mobiles échoué : %s', exc)
        return None
    if existe:
        return None
    return (
        f'Les fêtes mobiles de {annee} (Aïd al-Fitr, Aïd al-Adha, Nouvel An '
        f'hégirien, Aïd al-Mawlid) ne sont pas saisies : une relance peut '
        f'tomber le jour de la fête. Saisissez-les dans Paramètres → '
        f'Localisation → Fêtes mobiles.'
    )

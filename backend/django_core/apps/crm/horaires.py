"""MRY8 — Fenêtres d'appel : QUAND une touche de cadence peut tomber.

Module PUR (aucune vue, aucun sérialiseur, aucun effet de bord) et unique
autorité sur trois questions :

  * `fenetre_du_jour(d, company)` — la plage d'appel d'un jour donné, ou None
    si ce n'est pas un jour ouvré ;
  * `prochain_creneau_appel(dt, company)` — le prochain instant appelable ;
  * `minutes_ouvrees_entre(a, b, company)` — le temps réellement disponible
    entre deux instants (base du KPI « premier contact » de MRY19).

Pourquoi ce module existe. Une touche planifiée « J+1 » tombait mécaniquement
à l'heure de création du lead : un prospect arrivé à 23 h se voyait rappelé à
23 h le lendemain. Et un délai mesuré en minutes CALENDAIRES comptait la nuit
et le week-end — un lead arrivé vendredi 21 h et rappelé lundi 08:32 affichait
60 heures de retard alors que Meryem avait répondu en 2 minutes ouvrées.

Ce qui n'est PAS ici : les jours ouvrés et les jours fériés, qui restent
portés par `notifications.calendar_utils` (`is_jour_ouvre`,
`prochain_jour_ouvre`, `WorkingHoursConfig`, `Holiday`) — source unique, pas
un second calendrier concurrent.

Convention de temps : les entrées et sorties sont des datetimes AWARE (UTC en
pratique) ; tout le raisonnement se fait en heure locale Africa/Casablanca.
"""
from __future__ import annotations

import datetime
import logging
from zoneinfo import ZoneInfo

from django.utils import timezone

logger = logging.getLogger(__name__)

CASABLANCA = ZoneInfo('Africa/Casablanca')

#: Garde-fou de boucle : au pire ~2 mois de jours non ouvrés d'affilée.
_MAX_JOURS = 60

#: Fenêtre du dimanche du Protocole de rappel v3 — le SEUL rendez-vous
#: dominical autorisé (touche « appel_dimanche »), 16 h-19 h.
DIMANCHE_DEBUT = datetime.time(16, 0)
DIMANCHE_FIN = datetime.time(19, 0)


def _profil(company):
    if company is None:
        return None
    try:
        from apps.parametres.models import CompanyProfile
        return CompanyProfile.objects.filter(company=company).first()
    except Exception:  # noqa: BLE001 — jamais bloquant, défauts assumés
        logger.warning('crm.horaires: profil illisible', exc_info=True)
        return None


def _heure(profil, champ, defaut):
    valeur = getattr(profil, champ, None) if profil is not None else None
    return valeur if isinstance(valeur, datetime.time) else defaut


def est_en_ramadan(d, company, profil=None):
    """`d` tombe-t-il dans la période de Ramadan SAISIE par la société ?

    Faux tant que les deux dates ne sont pas renseignées : la période n'est
    JAMAIS devinée (le calendrier hégirien glisse chaque année)."""
    profil = profil if profil is not None else _profil(company)
    debut = getattr(profil, 'ramadan_debut', None)
    fin = getattr(profil, 'ramadan_fin', None)
    if not debut or not fin:
        return False
    return debut <= d <= fin


def fenetre_du_jour(d, company, *, dimanche=False):
    """`(debut, fin, pause)` du jour `d`, ou ``None`` si non appelable.

    `pause` est ``(debut, fin)`` le vendredi (prière), sinon ``None``.
    `dimanche=True` renvoie la fenêtre dominicale 16 h-19 h du Protocole v3 —
    réservée à la touche marquée `dimanche_ok`, jamais au reste.
    """
    profil = _profil(company)
    if dimanche and d.weekday() == 6:
        return (DIMANCHE_DEBUT, DIMANCHE_FIN, None)
    from apps.notifications.calendar_utils import is_jour_ouvre
    if not is_jour_ouvre(d, company):
        return None
    if est_en_ramadan(d, company, profil=profil):
        # Pendant le Ramadan, la fenêtre entière se resserre — et la pause du
        # vendredi n'a plus lieu d'être (elle tombe hors de 10 h-14 h).
        return (_heure(profil, 'ramadan_appel_debut', datetime.time(10, 0)),
                _heure(profil, 'ramadan_appel_fin', datetime.time(14, 0)),
                None)
    debut = _heure(profil, 'appel_heure_debut', datetime.time(8, 30))
    fin = _heure(profil, 'appel_heure_fin', datetime.time(20, 0))
    pause = None
    if d.weekday() == 4:  # vendredi
        pause = (_heure(profil, 'vendredi_pause_debut', datetime.time(11, 30)),
                 _heure(profil, 'vendredi_pause_fin', datetime.time(15, 0)))
    return (debut, fin, pause)


def _local(dt):
    """Datetime aware → heure locale Casablanca (aware)."""
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, datetime.timezone.utc)
    return dt.astimezone(CASABLANCA)


def _combiner(d, t):
    """Date locale + heure locale → datetime aware Casablanca."""
    return datetime.datetime.combine(d, t, tzinfo=CASABLANCA)


def est_dans_fenetre(dt, company, *, dimanche=False):
    """L'instant `dt` est-il dans la fenêtre d'appel de son jour ?"""
    local = _local(dt)
    fenetre = fenetre_du_jour(local.date(), company, dimanche=dimanche)
    if fenetre is None:
        return False
    debut, fin, pause = fenetre
    heure = local.time()
    if not (debut <= heure < fin):
        return False
    if pause is not None and pause[0] <= heure < pause[1]:
        return False
    return True


def prochain_creneau_appel(dt, company, *, dimanche=False):
    """Le prochain instant APPELABLE à partir de `dt` (inclus).

    Renvoie `dt` inchangé s'il est déjà dans la fenêtre. Sinon, dans l'ordre :
    la pause du vendredi pousse à sa fin ; avant l'ouverture on attend
    l'ouverture ; après la fermeture (ou un jour non ouvré) on passe au
    prochain jour ouvré à son heure d'ouverture. Sortie AWARE, dans le même
    fuseau que l'entrée."""
    tz_entree = dt.tzinfo or datetime.timezone.utc
    local = _local(dt)
    jour = local.date()
    for _ in range(_MAX_JOURS):
        fenetre = fenetre_du_jour(jour, company, dimanche=dimanche)
        if fenetre is not None:
            debut, fin, pause = fenetre
            candidat = local if jour == local.date() else _combiner(jour, debut)
            heure = candidat.time()
            if jour == local.date() and heure < debut:
                candidat = _combiner(jour, debut)
                heure = debut
            if heure < fin:
                if pause is not None and pause[0] <= heure < pause[1]:
                    candidat = _combiner(jour, pause[1])
                    if pause[1] < fin:
                        return candidat.astimezone(tz_entree)
                else:
                    return candidat.astimezone(tz_entree)
        jour += datetime.timedelta(days=1)
        # Les jours suivants démarrent à leur ouverture, plus à l'heure de dt.
        local = _combiner(jour, datetime.time(0, 0))
    logger.warning(
        'crm.horaires: aucun créneau trouvé en %s jours (société %s)',
        _MAX_JOURS, getattr(company, 'pk', '?'))
    return dt


def minutes_ouvrees_entre(a, b, company):
    """Minutes d'ouverture écoulées entre `a` et `b` (0 si `b <= a`).

    C'est LA mesure du KPI « premier contact » : une nuit ou un week-end
    complet vaut 0 minute. La pause du vendredi est retranchée."""
    if a is None or b is None:
        return 0
    debut_local = _local(a)
    fin_local = _local(b)
    if fin_local <= debut_local:
        return 0
    total = 0
    jour = debut_local.date()
    for _ in range(_MAX_JOURS):
        if jour > fin_local.date():
            break
        fenetre = fenetre_du_jour(jour, company)
        if fenetre is not None:
            ouverture, fermeture, pause = fenetre
            plages = [(ouverture, fermeture)]
            if pause is not None:
                plages = [(ouverture, min(fermeture, pause[0])),
                          (max(ouverture, pause[1]), fermeture)]
            for plage_debut, plage_fin in plages:
                if plage_fin <= plage_debut:
                    continue
                borne_bas = max(_combiner(jour, plage_debut), debut_local)
                borne_haut = min(_combiner(jour, plage_fin), fin_local)
                if borne_haut > borne_bas:
                    total += int(
                        (borne_haut - borne_bas).total_seconds() // 60)
        jour += datetime.timedelta(days=1)
    return total

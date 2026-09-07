"""MRY8 — Fenêtres d'appel : QUAND une touche de cadence peut tomber.

Module PUR (aucune vue, aucun sérialiseur, aucun effet de bord) et unique
autorité sur trois questions :

  * `fenetre_du_jour(d, company)` — la plage d'appel d'un jour donné, ou None
    si ce n'est pas un jour ouvré ;
  * `prochain_creneau_appel(dt, company)` — le prochain instant appelable ;
  * `minutes_ouvrees_entre(a, b, company)` — le temps réellement disponible
    entre deux instants (base du KPI « premier contact » de MRY19).

DEUX OUVERTURES, PAS UNE (décision fondateur du 07/09/2026, recherche à
l'appui). Toutes ces fonctions prennent un `canal` : un message WhatsApp ou
e-mail peut partir dès `CompanyProfile.message_heure_debut` (08:30), un APPEL
jamais avant `appel_heure_debut` (09:00). Avec une fenêtre unique, un lead de
nuit recevait son message d'identité à 08:30 puis un coup de téléphone à
08:33 — avant l'heure à laquelle un appel d'affaires se fait au Maroc. Ce qui
reste COMMUN aux deux canaux : la fermeture du soir, la fenêtre de Ramadan et
la fenêtre dominicale du Protocole v3. Ce qui ne l'est pas : la pause de la
prière du vendredi, qui ne vaut que pour les APPELS — un message est
silencieux, il ne dérange personne à la mosquée.

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

import contextlib
import contextvars
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

#: Canaux SILENCIEUX (décision fondateur 07/09/2026) : ils ouvrent à
#: `message_heure_debut` et ignorent la pause de la prière du vendredi. Tout
#: autre canal (`appel`, `visite`) suit la fenêtre d'APPEL. Les valeurs sont
#: celles de `parametres.CanalRelance` / `crm.RelanceEtape.canal`, reprises en
#: littéral : ce module ne dépend d'aucun modèle.
CANAUX_MESSAGE = frozenset({'whatsapp', 'email'})

#: Ouverture par défaut des messages quand la société n'a rien saisi.
DEFAUT_MESSAGE_DEBUT = datetime.time(8, 30)
#: Ouverture par défaut des appels — 9 h, jamais 8 h 30 (07/09/2026).
DEFAUT_APPEL_DEBUT = datetime.time(9, 0)


#: Cache LOCAL à une opération (jamais global, jamais entre requêtes) : le
#: profil société et les jours ouvrés sont relus à CHAQUE appel de fenêtre —
#: 3 requêtes par jour parcouru, ~7 000 requêtes et 24 s pour dater les
#: touches de 272 leads en production (07/09/2026). Une opération longue
#: s'enveloppe dans `with cache_local():` ; hors contexte, rien n'est mis en
#: cache — les tests et les écrans ordinaires gardent le comportement exact.
_CACHE = contextvars.ContextVar('crm_horaires_cache', default=None)


@contextlib.contextmanager
def cache_local():
    """Mémorise profil et jours ouvrés le temps du bloc, puis oublie tout."""
    token = _CACHE.set({})
    try:
        yield
    finally:
        _CACHE.reset(token)


def _profil(company):
    if company is None:
        return None
    cache = _CACHE.get()
    cle = ('profil', getattr(company, 'pk', None))
    if cache is not None and cle in cache:
        return cache[cle]
    try:
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
    except Exception:  # noqa: BLE001 — jamais bloquant, défauts assumés
        logger.warning('crm.horaires: profil illisible', exc_info=True)
        return None
    if cache is not None:
        cache[cle] = profil
    return profil


def _jour_ouvre(d, company):
    """`is_jour_ouvre` de `notifications.calendar_utils`, mémorisé dans le
    cache local quand il est actif (une date + une société = une réponse)."""
    cache = _CACHE.get()
    cle = ('ouvre', getattr(company, 'pk', None), d)
    if cache is not None and cle in cache:
        return cache[cle]
    from apps.notifications.calendar_utils import is_jour_ouvre
    ouvre = is_jour_ouvre(d, company)
    if cache is not None:
        cache[cle] = ouvre
    return ouvre


def _heure(profil, champ, defaut):
    valeur = getattr(profil, champ, None) if profil is not None else None
    return valeur if isinstance(valeur, datetime.time) else defaut


def est_un_message(canal):
    """`canal` désigne-t-il une touche ÉCRITE (WhatsApp / e-mail) ?

    Tolère `None` et une valeur inconnue : dans le doute, c'est la fenêtre
    d'APPEL — la plus tardive et la plus prudente — qui s'applique."""
    return str(canal or '').lower() in CANAUX_MESSAGE


def _ouverture(profil, canal):
    """L'heure d'ouverture du jour pour CE canal (hors Ramadan/dimanche)."""
    if est_un_message(canal):
        return _heure(profil, 'message_heure_debut', DEFAUT_MESSAGE_DEBUT)
    return _heure(profil, 'appel_heure_debut', DEFAUT_APPEL_DEBUT)


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


def fenetre_du_jour(d, company, *, dimanche=False, canal='appel'):
    """`(debut, fin, pause)` du jour `d`, ou ``None`` si non appelable.

    `pause` est ``(debut, fin)`` le vendredi (prière), sinon ``None``.
    `dimanche=True` renvoie la fenêtre dominicale 16 h-19 h du Protocole v3 —
    réservée à la touche marquée `dimanche_ok`, jamais au reste.

    `canal` (07/09/2026) décide de la seule chose qui SÉPARE les deux
    fenêtres : l'ouverture (`message_heure_debut` pour WhatsApp/e-mail,
    `appel_heure_debut` sinon) et la pause du vendredi, qui ne s'applique
    qu'aux appels. La fermeture, le Ramadan et le dimanche sont communs.
    """
    profil = _profil(company)
    if dimanche and d.weekday() == 6:
        return (DIMANCHE_DEBUT, DIMANCHE_FIN, None)
    if not _jour_ouvre(d, company):
        return None
    if est_en_ramadan(d, company, profil=profil):
        # Pendant le Ramadan, la fenêtre entière se resserre — et la pause du
        # vendredi n'a plus lieu d'être (elle tombe hors de 10 h-14 h). Elle
        # est COMMUNE aux deux canaux : c'est la journée entière qui se
        # déplace, pas seulement l'heure des appels.
        return (_heure(profil, 'ramadan_appel_debut', datetime.time(10, 0)),
                _heure(profil, 'ramadan_appel_fin', datetime.time(14, 0)),
                None)
    debut = _ouverture(profil, canal)
    fin = _heure(profil, 'appel_heure_fin', datetime.time(20, 0))
    pause = None
    if d.weekday() == 4 and not est_un_message(canal):  # vendredi, appels
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


def est_dans_fenetre(dt, company, *, dimanche=False, canal='appel'):
    """L'instant `dt` est-il dans la fenêtre de son jour, pour ce `canal` ?"""
    local = _local(dt)
    fenetre = fenetre_du_jour(local.date(), company, dimanche=dimanche,
                              canal=canal)
    if fenetre is None:
        return False
    debut, fin, pause = fenetre
    heure = local.time()
    if not (debut <= heure < fin):
        return False
    if pause is not None and pause[0] <= heure < pause[1]:
        return False
    return True


def prochain_creneau_appel(dt, company, *, dimanche=False, canal='appel'):
    """Le prochain instant JOIGNABLE à partir de `dt` (inclus), pour `canal`.

    Renvoie `dt` inchangé s'il est déjà dans la fenêtre. Sinon, dans l'ordre :
    la pause du vendredi pousse à sa fin ; avant l'ouverture on attend
    l'ouverture ; après la fermeture (ou un jour non ouvré) on passe au
    prochain jour ouvré à son heure d'ouverture. Sortie AWARE, dans le même
    fuseau que l'entrée.

    `canal` porte la décision du 07/09/2026 : une touche WhatsApp/e-mail se
    pose dès 08:30, un appel jamais avant 09:00. Le NOM de la fonction reste
    historique — elle recale désormais toutes les touches, pas seulement les
    appels."""
    tz_entree = dt.tzinfo or datetime.timezone.utc
    local = _local(dt)
    jour = local.date()
    for _ in range(_MAX_JOURS):
        fenetre = fenetre_du_jour(jour, company, dimanche=dimanche,
                                  canal=canal)
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


#: Heure par défaut du rendez-vous dominical du Protocole v3 : au milieu de la
#: fenêtre 16 h-19 h, jamais à son bord.
DIMANCHE_HEURE_DEFAUT = datetime.time(16, 30)


def prochain_dimanche(dt, heure=DIMANCHE_HEURE_DEFAUT):
    """Le prochain DIMANCHE appelable à partir de `dt` (inclus), à `heure`.

    `prochain_creneau_appel` ne sait que RECALER un instant dans la fenêtre de
    SON jour : il ne déplace jamais une touche vers un autre jour de la
    semaine. Une touche « appel du dimanche » calculée en J+5 depuis un
    mercredi tombait donc un lundi — le seul rendez-vous dominical du
    protocole n'avait jamais lieu un dimanche. C'est cette fonction, et elle
    seule, qui PLACE une touche sur un dimanche.

    `dt` déjà dominical et avant la fermeture (19 h) → CE dimanche, à
    `max(dt, heure)` (on ne remonte jamais dans le passé) ; sinon le dimanche
    suivant à `heure`. Entrée et sortie AWARE, dans le fuseau de l'entrée."""
    tz_entree = dt.tzinfo or datetime.timezone.utc
    local = _local(dt)
    if local.weekday() == 6 and local.time() < DIMANCHE_FIN:
        candidat = max(local, _combiner(local.date(), heure))
        return candidat.astimezone(tz_entree)
    # `(6 - weekday) % 7` vaut 0 le dimanche : le `or 7` envoie alors au
    # dimanche SUIVANT (cas « dimanche après 19 h »).
    delta = (6 - local.weekday()) % 7 or 7
    cible = local.date() + datetime.timedelta(days=delta)
    return _combiner(cible, heure).astimezone(tz_entree)


def minutes_ouvrees_entre(a, b, company, *, canal='whatsapp'):
    """Minutes d'ouverture écoulées entre `a` et `b` (0 si `b <= a`).

    C'est LA mesure du KPI « premier contact » : une nuit ou un week-end
    complet vaut 0 minute. La pause du vendredi est retranchée pour les
    appels.

    Le défaut est `whatsapp`, PAS `appel` (07/09/2026) : la première prise de
    contact du protocole est un MESSAGE, posé dès 08:30. Compter ce délai sur
    la fenêtre d'appel (09:00) ferait disparaître les 30 premières minutes de
    la journée — un lead de nuit rappelé par message à 08:35 afficherait 0
    minute écoulée alors que Meryem a bien travaillé 5 minutes, et l'escalade
    `escalader_premier_contact` ne partirait jamais avant 9 h."""
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
        fenetre = fenetre_du_jour(jour, company, canal=canal)
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

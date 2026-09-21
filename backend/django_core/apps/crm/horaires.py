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


def _est_ferie(d, company):
    """CAD41 — `d` est-il un jour FÉRIÉ pour la société ?

    Distinct de ``_jour_ouvre``, qui répond « non » aussi bien pour un férié
    que pour un samedi : la touche dominicale du Protocole v3 est justement
    posée un jour NON ouvré, et elle doit pourtant s'effacer devant l'Aïd.
    Lecture par la surface cross-app documentée (``feries_entre``), jamais un
    import de ``notifications.models``. Mémorisé comme ``_jour_ouvre``.
    """
    cache = _CACHE.get()
    cle = ('ferie', getattr(company, 'pk', None), d)
    if cache is not None and cle in cache:
        return cache[cle]
    from apps.notifications.calendar_utils import feries_entre
    ferie = bool(feries_entre(company, d, d))
    if cache is not None:
        cache[cle] = ferie
    return ferie


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


def fenetre_du_jour(d, company, *, dimanche=False, samedi=False,
                    canal='appel'):
    """`(debut, fin, pause)` du jour `d`, ou ``None`` si non appelable.

    `pause` est ``(debut, fin)`` le vendredi (prière), sinon ``None``.
    `dimanche=True` renvoie la fenêtre dominicale 16 h-19 h du Protocole v3 —
    réservée à la touche marquée `dimanche_ok`, jamais au reste.
    `samedi=True` (CAD43) ouvre le SAMEDI à la seule touche marquée
    `samedi_ok`, dans la fenêtre ORDINAIRE de son canal : rien n'est ouvert
    pour les autres touches, et si la société a déjà coché le samedi comme
    jour ouvré, ce drapeau ne change rien.

    `canal` (07/09/2026) décide de la seule chose qui SÉPARE les deux
    fenêtres : l'ouverture (`message_heure_debut` pour WhatsApp/e-mail,
    `appel_heure_debut` sinon) et la pause du vendredi, qui ne s'applique
    qu'aux appels. La fermeture, le Ramadan et le dimanche sont communs.
    """
    profil = _profil(company)
    if dimanche and d.weekday() == 6:
        # CAD41 — la branche dominicale ne court-circuite plus NI les fériés
        # NI le Ramadan. Avant, `return` partait ici sans rien vérifier : un
        # Aïd tombant un dimanche recevait quand même l'appel de 16:30, et
        # pendant le Ramadan la touche restait posée à 16:30 en plein jeûne,
        # dans le creux pré-ftour (jusqu'à 4 dimanches par an).
        if _est_ferie(d, company):
            # `None` = ce dimanche est inutilisable ; `prochain_creneau_appel`
            # passe alors au dimanche SUIVANT (jamais au lundi : la touche
            # dominicale ne se transforme pas en touche de semaine).
            return None
        if est_en_ramadan(d, company, profil=profil):
            return (_heure(profil, 'ramadan_appel_debut', datetime.time(9, 0)),
                    _heure(profil, 'ramadan_appel_fin', datetime.time(15, 0)),
                    None)
        return (DIMANCHE_DEBUT, DIMANCHE_FIN, None)
    if samedi and d.weekday() == 5 and not _jour_ouvre(d, company):
        # CAD43 — symétrique de la branche dominicale, pour la seule touche
        # marquée `samedi_ok` : le samedi reste fermé à TOUTES les autres.
        # Aucune fenêtre inventée — c'est la fenêtre ordinaire du canal (un
        # message dès l'ouverture des messages, un appel jamais avant celle
        # des appels). Comme le dimanche (CAD41), le férié et le Ramadan
        # priment.
        if _est_ferie(d, company):
            return None
        if est_en_ramadan(d, company, profil=profil):
            return (_heure(profil, 'ramadan_appel_debut', datetime.time(9, 0)),
                    _heure(profil, 'ramadan_appel_fin', datetime.time(15, 0)),
                    None)
        return (_ouverture(profil, canal),
                _heure(profil, 'appel_heure_fin', datetime.time(20, 0)),
                None)
    if not _jour_ouvre(d, company):
        return None
    if est_en_ramadan(d, company, profil=profil):
        # CAD39 — DÉCISION FONDATEUR du 21/09/2026, pas un effet de bord du
        # `return` anticipé : pendant le Ramadan la fenêtre est COMMUNE aux
        # appels et aux messages (c'est la journée entière qui se déplace,
        # pas seulement l'heure des appels), et AUCUNE fenêtre du soir n'est
        # ouverte après le ftour — les WhatsApp se tapent à la main, on ne
        # demande à personne de travailler le soir. La pause du vendredi n'a
        # plus lieu d'être : elle tombe au bord de la fenêtre du mois.
        # Le repli 09:00-15:00 est la référence nationale (CAD38, annonce du
        # Ministère de la Transition numérique du 10/02/2026) ; il ne sert
        # qu'aux profils sans valeur enregistrée.
        return (_heure(profil, 'ramadan_appel_debut', datetime.time(9, 0)),
                _heure(profil, 'ramadan_appel_fin', datetime.time(15, 0)),
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


def est_dans_fenetre(dt, company, *, dimanche=False, samedi=False,
                     canal='appel'):
    """L'instant `dt` est-il dans la fenêtre de son jour, pour ce `canal` ?"""
    local = _local(dt)
    fenetre = fenetre_du_jour(local.date(), company, dimanche=dimanche,
                              samedi=samedi, canal=canal)
    if fenetre is None:
        return False
    debut, fin, pause = fenetre
    heure = local.time()
    if not (debut <= heure < fin):
        return False
    if pause is not None and pause[0] <= heure < pause[1]:
        return False
    return True


def prochain_creneau_appel(dt, company, *, dimanche=False, samedi=False,
                           canal='appel'):
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
                                  samedi=samedi, canal=canal)
        if fenetre is not None:
            debut, fin, pause = fenetre
            candidat = local if jour == local.date() else _combiner(jour, debut)
            heure = candidat.time()
            if (dimanche and jour.weekday() == 6 and heure >= fin
                    and est_en_ramadan(jour, company)):
                # CAD41 — pendant le Ramadan, la fenêtre dominicale ferme à
                # 15 h : l'heure canonique 16 h 30 du Protocole v3 n'existe
                # tout simplement pas ce jour-là. La touche est REPLACÉE dans
                # la fenêtre du mois, CE dimanche — jamais repoussée d'une
                # semaine, jamais transformée en appel de semaine. C'est la
                # même nature de geste que `prochain_dimanche`, qui PLACE la
                # touche : on ne recale pas un instant vécu, on choisit
                # l'heure d'un rendez-vous.
                candidat = _combiner(jour, debut)
                heure = debut
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
        # CAD41 — une touche DOMINICALE inutilisable (Aïd tombant un
        # dimanche) saute au dimanche SUIVANT, jamais au lundi : sinon le
        # seul rendez-vous dominical du protocole se transformerait en appel
        # de semaine, exactement ce que `prochain_dimanche` évite.
        if dimanche and jour.weekday() == 6:
            jour += datetime.timedelta(days=7)
        else:
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


# ── CAD-I ── CAD88 ──────────────────────────────────────────────────────────
# Le KPI de premier contact NEUTRALISE le week-end : « une nuit ou un week-end
# complet vaut 0 minute » (docstring ci-dessus). C'est la bonne mesure de
# l'OBJECTIF — on ne reproche à personne de dormir — mais c'est une très
# mauvaise mesure de CE QU'A VÉCU LE CLIENT : un lead arrivé vendredi 20:00 et
# traité lundi 08:30 s'affiche conforme alors qu'il a attendu soixante heures.
# Tant que la mesure neutralise ce retard, le samedi (CAD43) ne peut pas
# s'arbitrer sur des faits.
#
# La réponse n'est PAS de changer le calcul ouvré — il reste l'objectif, au
# bit près — c'est d'AJOUTER une colonne à côté de lui. Les deux se lisent
# ensemble ou ne veulent rien dire.
def minutes_calendaires_entre(a, b):
    """Minutes de CALENDRIER écoulées entre ``a`` et ``b`` (0 si ``b <= a``).

    Le temps tel que le CLIENT l'a vécu : la nuit, le week-end et les jours
    fériés comptent. Aucune notion de société, d'horaires ni de canal — c'est
    précisément ce qui la distingue de ``minutes_ouvrees_entre``, qu'elle ne
    remplace jamais.
    """
    if a is None or b is None:
        return 0
    if b <= a:
        return 0
    return int((b - a).total_seconds() // 60)


# ── CAD146 (audit L3 cadence, 21/09/2026) — diaspora et fuseau horaire ───────
#
# CONSTAT : toutes les fenêtres et tous les recalages de ce module raisonnent
# en Africa/Casablanca (voir `CASABLANCA` ci-dessus), sans aucune notion du
# fuseau du LEAD. Un Marocain résidant en Europe reçoit donc son appel de
# 09:00 à 08:00 chez lui ; un lead du Golfe le reçoit à 11:00.
#
# DÉCISION (21/09/2026) : NE RIEN CONSTRUIRE tant que CADM7 (comptage SQL en
# lecture seule des numéros à indicatif étranger, action du fondateur — la
# lecture en production a été REFUSÉE par le classificateur de sécurité de la
# session d'audit, ce n'est donc pas une tâche de build) n'a pas donné de
# chiffre. C'est peut-être un cas marginal ; sans le comptage, ajouter un
# fuseau par lead serait de la complexité pour un volume inconnu — contraire
# à la doctrine du groupe CAD (zéro chiffre inventé, y compris un volume).
#
# QUAND le comptage existe : si le volume le justifie, stocker le fuseau du
# lead (nouveau champ sur `crm.Lead`, PROCHAIN à `ville`/`whatsapp`) et
# recaler ICI les touches dessus, en gardant les fenêtres de la SOCIÉTÉ
# (`fenetre_du_jour`) comme bornes — jamais une fenêtre individuelle sans
# limite. Ce commentaire est la trace de la décision ; ne pas la re-soulever
# sans le chiffre de CADM7.

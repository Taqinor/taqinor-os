"""
Analytique O&M (FG279) — indicateurs de supervision par système installé.

Calcule, à partir des `ProductionReading` d'UN système, les indicateurs
classiques d'exploitation-maintenance :

  * Performance Ratio (PR) — production réelle / production attendue sur la
    fenêtre (l'attendu vient de `MonitoringConfig.expected_annual_kwh` ; sans
    référence semée, PR non calculé — CIQ643, aucun attendu inventé).
  * Disponibilité — part des jours de la fenêtre couverts par au moins un
    relevé (proxy raisonnable sans télémétrie d'onduleur dédiée).
  * Soiling (salissure) — dérive du PR mensuel : un PR mensuel qui décroît
    régulièrement signale un encrassement progressif (estimation, pas une
    mesure d'irradiance).
  * Dégradation annualisée — pente du PR sur les 12 derniers mois ramenée en
    %/an (proxy de la dégradation des modules + dérive d'encrassement).

100 % LECTURE : aucune écriture, aucun appel réseau. Réutilise la logique
d'attendu du service N52 sans la dupliquer.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from core.analytics_db import analytics_queryset

from .models import CleaningEvent, ProductionReading, UnderperformanceFlag
from .services import (
    attendu_intervalles, debut_couverture, fenetre_couverte,
    get_or_create_config, production_couverte, releves_recouvrant,
)

# Fenêtre par défaut (jours) d'analyse O&M.
DEFAULT_WINDOW_DAYS = 365

# FG283 — perte de PR (points de %) au-delà de laquelle on recommande un
# nettoyage, et nombre de jours sans nettoyage déclenchant aussi la reco
# (régions poussiéreuses).
SOILING_PR_DROP_PCT = Decimal('5')
SOILING_MAX_DAYS_SINCE_CLEAN = 120


def _q(value, places='0.01'):
    return Decimal(str(value)).quantize(Decimal(places)) if value is not None else None


def serie_mensuelle(config, releves, debut, today):
    """AMON99 — série mensuelle ``[(1er du mois, kWh, attendu)]`` de
    ``[debut, today]`` : chaque relevé (``releves_recouvrant``) au prorata de
    ses jours dans le mois (``production_couverte``), attendu du mois sur ses
    seuls jours couverts (``attendu_intervalles`` ; None sans référence).
    Un mois sans aucun jour couvert est omis."""
    paires = [(jour, periode) for jour, periode, _kwh in releves]
    serie = []
    mois = debut.replace(day=1)
    while mois <= today:
        dernier = mois.replace(day=calendar.monthrange(mois.year, mois.month)[1])
        bornes = (max(mois, debut), min(dernier, today))
        intervalles = intervalles_couverts_par_releves(paires, *bornes)
        if intervalles:
            serie.append((mois, production_couverte(releves, *bornes),
                          attendu_intervalles(config, intervalles)))
        mois = dernier + timedelta(days=1)
    return serie


def jours_couverts_par_releves(releves, since, today):
    """ASAV64 — nombre de jours de ``[since, today]`` couverts par l'UNION
    des intervalles ``[date, date + period_days)`` des relevés (``releves`` =
    itérable de ``(date, period_days)``). Un relevé mensuel couvre ses 30
    jours ; deux relevés qui se chevauchent ne se comptent jamais deux fois."""
    return sum((fin - debut).days for debut, fin
               in intervalles_couverts_par_releves(releves, since, today))


def intervalles_couverts_par_releves(releves, since, today):
    """AMON22 — l'UNION des intervalles ``[date, date + period_days)`` des
    relevés, bornée à ``[since, today]`` : liste triée de ``(debut, fin)``
    disjoints, ``fin`` exclusive (base de ``jours_couverts_par_releves`` et
    de l'attendu de sous-performance sur les seuls jours couverts)."""
    fin_fenetre = today + timedelta(days=1)  # borne haute exclusive
    intervalles = []
    for jour, periode in releves:
        debut = max(jour, since)
        fin = min(jour + timedelta(days=max(int(periode or 1), 1)),
                  fin_fenetre)
        if fin > debut:
            intervalles.append((debut, fin))
    intervalles.sort()
    fusion = []
    for debut, fin in intervalles:
        if fusion and debut <= fusion[-1][1]:
            fusion[-1] = (fusion[-1][0], max(fin, fusion[-1][1]))
        else:
            fusion.append((debut, fin))
    return fusion


def fenetre_mesuree(installation, since, today, window_days):
    """AMON21 — ``(début, jours)`` de la fenêtre d'un indicateur : bornée au
    début de couverture (``debut_couverture`` : mise en service / premier
    relevé, comme l'attendu ASAV62) ; fenêtre entière si non bornée."""
    debut = debut_couverture(installation, since)
    if debut == since:
        return debut, window_days
    return debut, max((today - debut).days + 1, 0)


def _linear_slope(points):
    """Pente d'une régression linéaire simple sur [(x_int, y_float)].

    Renvoie None si moins de 2 points ou variance nulle.
    """
    n = len(points)
    if n < 2:
        return None
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sxx = sum(p[0] * p[0] for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    denom = (n * sxx) - (sx * sx)
    if denom == 0:
        return None
    return ((n * sxy) - (sx * sy)) / denom


def om_metrics(installation, *, window_days=DEFAULT_WINDOW_DAYS, today=None):
    """Indicateurs O&M d'un système sur la fenêtre récente.

    Renvoie un dict prêt à sérialiser. No-op gracieux (champs None) si aucune
    donnée de production ou aucun attendu n'est disponible.
    """
    today = today or timezone.localdate()
    since = today - timedelta(days=window_days)
    config = get_or_create_config(installation)

    # YHARD9 — lecture BI (relevés de production sur la fenêtre) : réplica si
    # configuré, no-op strict sinon. 100 % lecture. AMON21 — les relevés qui
    # RECOUVRENT la fenêtre, au prorata (``production_couverte``), et une
    # fenêtre bornée au début de couverture (mise en service / 1er relevé).
    releves = releves_recouvrant(
        installation, since, today,
        base=analytics_queryset(ProductionReading.objects))
    debut, jours_fenetre = fenetre_mesuree(installation, since, today,
                                           window_days)
    total_kwh = production_couverte(releves, debut, today)

    # AMON97 — PR : réel ET attendu sur la fenêtre réellement couverte
    # ([début de couverture ; min(aujourd'hui, dernier jour couvert)]).
    fenetre = fenetre_couverte(installation, releves, since, today)
    expected = attendu_intervalles(config, fenetre[2]) if fenetre else None
    pr_pct = availability_pct = None
    if fenetre and expected and expected > 0:
        reel = production_couverte(releves, fenetre[0], fenetre[1])
        pr_pct = _q((reel / expected) * Decimal('100'))

    # Disponibilité : jours couverts (UNION des intervalles des relevés,
    # ASAV64) / jours de la fenêtre BORNÉE, plafonnée à 100 % ; ``None``
    # sans relevé (jamais un faux 0 %).
    if releves and jours_fenetre > 0:
        jours_couverts = jours_couverts_par_releves(
            [(jour, periode) for jour, periode, _kwh in releves],
            debut, today)
        availability_pct = _q(min(
            Decimal(jours_couverts) / Decimal(jours_fenetre)
            * Decimal('100'), Decimal('100')))

    # PR mensuel pour soiling + dégradation. ASAV63/AMON99 — chaque relevé
    # au prorata de ses jours dans le mois, attendu du mois sur ses seuls
    # jours couverts (au profil, AMON29). ``complet`` = mois entier dans
    # [début de couverture ; dernier jour couvert] : seuls ces mois portent
    # la pente (un mois partiel n'est jamais une dérive).
    fin_couverte = fenetre[1] if fenetre else today
    monthly_pr = []
    pr_points = []
    for idx, (month, kwh, attendu_mois) in enumerate(
            serie_mensuelle(config, releves, debut, today)):
        ratio = (kwh / attendu_mois) * Decimal('100') if attendu_mois else None
        complet = _mois_complet(month.strftime('%Y-%m'), debut, fin_couverte)
        if ratio is not None and complet:
            pr_points.append((idx, float(ratio)))
        monthly_pr.append({
            'month': month.strftime('%Y-%m'),
            'kwh': _q(kwh),
            'pr_pct': _q(ratio) if ratio is not None else None,
            'complet': complet,
        })

    # Dégradation/soiling : pente du PR mensuel (points/mois) → %/an.
    slope = _linear_slope(pr_points)
    degradation_pct_per_year = _q(slope * 12) if slope is not None else None
    # Soiling probable si la pente est négative et significative (> 0,5 %/mois).
    soiling_suspected = bool(slope is not None and slope < -0.5)

    return {
        'installation': installation.id,
        'window_days': window_days,
        'production_kwh': _q(total_kwh),
        'expected_kwh': _q(expected) if expected is not None else None,
        'pr_pct': pr_pct,
        'availability_pct': availability_pct,
        'degradation_pct_per_year': degradation_pct_per_year,
        'soiling_suspected': soiling_suspected,
        'monthly_pr': monthly_pr,
    }


def _mois_complet(mois, debut, today):
    """AMON44 — le mois ``'AAAA-MM'`` est-il entier dans [debut ; today] ?"""
    annee, num = (int(x) for x in mois.split('-'))
    premier = date(annee, num, 1)
    dernier = date(annee, num, calendar.monthrange(annee, num)[1])
    return premier >= debut and dernier <= today


def soiling_assessment(installation, *, window_days=DEFAULT_WINDOW_DAYS,
                       today=None):
    """FG283 — estime la perte par salissure et recommande un nettoyage.

    Compare le PR mensuel le PLUS RÉCENT à la meilleure baseline de PR mensuel
    de la fenêtre (proxy de l'état « propre »). La chute = perte estimée par
    salissure (points de %). Recommande un nettoyage si la chute dépasse le
    seuil OU si trop de jours se sont écoulés depuis le dernier nettoyage.
    100 % lecture.
    """
    today = today or timezone.localdate()
    metrics = om_metrics(installation, window_days=window_days, today=today)

    # AMON44 — dernier nettoyage = saisi au monitoring OU étape de nettoyage
    # cochée sur un ticket SAV du système.
    from apps.sav.selectors_supervision import dernier_nettoyage_sav
    last_clean = (CleaningEvent.objects
                  .filter(installation=installation, date__lte=today)
                  .order_by('-date').values_list('date', flat=True).first())
    nettoyage_sav = dernier_nettoyage_sav(
        installation.company_id, installation.pk, today)
    if nettoyage_sav and (last_clean is None or nettoyage_sav > last_clean):
        last_clean = nettoyage_sav
    days_since_clean = (today - last_clean).days if last_clean else None

    # AMON44 — mois COMPLETS depuis le dernier nettoyage (au profil mensuel,
    # AMON29) : base = moyenne des deux premiers, courant = le dernier ;
    # moins de 3 mois ⇒ aucune estimation (jamais une saison prise pour
    # une salissure).
    debut = last_clean + timedelta(days=1) if last_clean else (
        today - timedelta(days=window_days))
    complets = [
        m['pr_pct'] for m in metrics['monthly_pr']
        if m['pr_pct'] is not None and m['complet']
        and _mois_complet(m['month'], debut, today)]
    pr_drop = current_pr = baseline_pr = None
    if len(complets) >= 3:
        current_pr = complets[-1]
        baseline_pr = _q((complets[0] + complets[1]) / 2)
        pr_drop = _q(baseline_pr - current_pr)

    recommend = False
    reasons = []
    if pr_drop is not None and pr_drop >= SOILING_PR_DROP_PCT:
        recommend = True
        reasons.append('chute de PR significative')
    if (days_since_clean is not None
            and days_since_clean >= SOILING_MAX_DAYS_SINCE_CLEAN):
        recommend = True
        reasons.append('délai depuis le dernier nettoyage')
    if last_clean is None and complets:
        # Jamais nettoyé et PR dégradé : on recommande aussi.
        if pr_drop is not None and pr_drop >= SOILING_PR_DROP_PCT:
            reasons.append('aucun nettoyage enregistré')

    return {
        'installation': installation.id,
        'current_pr_pct': current_pr,
        'baseline_pr_pct': baseline_pr,
        'estimated_soiling_loss_pct': pr_drop,
        'last_cleaning_date': last_clean.isoformat() if last_clean else None,
        'days_since_cleaning': days_since_clean,
        'recommend_cleaning': recommend,
        'reasons': reasons,
    }


def _jours_panne_dans_fenetre(installation, since, today):
    """NTNRG32 — nombre de jours COUVERTS par un ``UnderperformanceFlag``
    ouvert (ou fermé après ``since``) dans la fenêtre ``[since, today]``.

    Un flag toujours ouvert compte jusqu'à ``today`` ; un flag fermé compte
    jusqu'à sa date de clôture (bornée à ``today``). Les flags antérieurs à
    la fenêtre sont tronqués à ``since``. Un système sans flag renvoie 0
    (jamais une exception)."""
    jours = 0
    flags = (UnderperformanceFlag.objects
             .filter(installation=installation)
             .filter(Q(date_cloture__isnull=True) | Q(date_cloture__date__gte=since)))
    for flag in flags:
        # ``.date()`` sur un datetime relu de la base donnerait le jour UTC :
        # tant que l'heure marocaine était décalée (UTC+1 jusqu'au 19/09/2026 ;
        # décret n° 2.26.530 : UTC+0 depuis le 20/09), un flag ouvert à minuit
        # heure locale comptait un jour de panne de TROP (60 % devenaient
        # 70 %). Le lookup ``__date`` du filtre ci-dessus convertit, lui, dans
        # le fuseau du projet — on aligne le calcul Python dessus, quel que
        # soit le décalage en vigueur.
        debut = max(timezone.localtime(flag.date_creation).date(), since)
        fin = (min(timezone.localtime(flag.date_cloture).date(), today)
               if flag.date_cloture else today)
        if fin >= debut:
            jours += (fin - debut).days + 1
    return jours


def pertes_categorisees(installation, *, window_days=DEFAULT_WINDOW_DAYS,
                        today=None):
    """NTNRG32 — décompose les pertes de production PAR CATÉGORIE, au-delà
    du seul soiling (FG283) :

      * ``soiling_pct`` — perte estimée par salissure (``soiling_assessment``
        déjà FG283, réutilisée telle quelle) ;
      * ``ombrage_pct`` — proxy = chute de PR récurrente aux MÊMES heures
        solaires. TOUJOURS ``None`` aujourd'hui : ce module ne stocke que des
        relevés PÉRIODIQUES (``ProductionReading.period_days``), aucun relevé
        INFRA-JOURNALIER — dès qu'une source horaire existera, ce calcul
        pourra être ajouté SANS changer la forme du résultat ;
      * ``panne_pct`` — part de jours couverts par un drapeau de
        sous-performance OUVERT (N52) sur la fenêtre ;
      * ``curtailment_pct`` — part de jours portant un
        ``ProductionReading.motif_limitation`` renseigné (champ STRUCTURÉ,
        jamais un grep sur `note` en texte libre).

    Chaque catégorie SANS donnée exploitable renvoie ``None`` — jamais un 0
    trompeur qui laisserait croire à une perte nulle certaine.
    """
    today = today or timezone.localdate()
    since = today - timedelta(days=window_days)

    soiling = soiling_assessment(installation, window_days=window_days, today=today)
    soiling_pct = soiling['estimated_soiling_loss_pct']

    jours_panne = _jours_panne_dans_fenetre(installation, since, today)
    panne_pct = _q(Decimal(jours_panne) / Decimal(window_days) * Decimal('100'))

    jours_curtailment = (
        analytics_queryset(ProductionReading.objects)
        .filter(installation=installation, date__gte=since, date__lte=today)
        .exclude(motif_limitation='')
        .values('date').distinct().count())
    curtailment_pct = _q(
        Decimal(jours_curtailment) / Decimal(window_days) * Decimal('100'))

    return {
        'installation': installation.id,
        'window_days': window_days,
        'soiling_pct': soiling_pct,
        'ombrage_pct': None,
        'panne_pct': panne_pct,
        'curtailment_pct': curtailment_pct,
    }

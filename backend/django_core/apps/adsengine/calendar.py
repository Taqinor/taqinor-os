"""PUB78 — Calendrier créatif marocain (fenêtres saisonnières).

``CreativeBacklogItem.seasonal_tag`` était du texte libre sans source. Ce module
porte un CALENDRIER de référence (Ramadan mobile, Aïds, rentrée, canicule, saison
agricole post-récolte) qui :
  * se SEED de façon idempotente par société (``seed_calendar``) ;
  * alimente le TRI du backlog par proximité calendaire RÉELLE
    (``sort_backlog_items``) — un item dont la saison approche remonte ;
  * expose les fenêtres de recommandation (« préparer les créas Ramadan J-30 »,
    ``active_events`` / ``upcoming_windows``).

Les dates seedées sont des fenêtres de PLANIFICATION internes (éditables par le
fondateur) — jamais un chiffre client-facing. Ramadan/Aïds sont mobiles (lunaire)
et seedés en dates concrètes par année ; le fondateur ajuste au besoin.
"""
from __future__ import annotations

import datetime

# Repères 2026-2027 (approximatifs, éditables) — planification interne. Les dates
# lunaires (Ramadan/Aïds) sont des estimations ; la rentrée/canicule/saison
# agricole suivent le cycle marocain. ``lead_days`` = anticipation de préparation.
SEED_EVENTS = [
    # Ramadan (mobile). Fenêtre de préparation large (J-30).
    {'tag': 'ramadan', 'label': 'Ramadan', 'market_mode': '',
     'date_debut': datetime.date(2026, 2, 18),
     'date_fin': datetime.date(2026, 3, 19), 'lead_days': 30},
    {'tag': 'ramadan', 'label': 'Ramadan', 'market_mode': '',
     'date_debut': datetime.date(2027, 2, 8),
     'date_fin': datetime.date(2027, 3, 9), 'lead_days': 30},
    # Aïd al-Fitr (fin du Ramadan).
    {'tag': 'aid_fitr', 'label': 'Aïd al-Fitr', 'market_mode': '',
     'date_debut': datetime.date(2026, 3, 20),
     'date_fin': datetime.date(2026, 3, 22), 'lead_days': 14},
    # Aïd al-Adha.
    {'tag': 'aid_adha', 'label': 'Aïd al-Adha', 'market_mode': '',
     'date_debut': datetime.date(2026, 5, 27),
     'date_fin': datetime.date(2026, 5, 29), 'lead_days': 14},
    # Rentrée scolaire.
    {'tag': 'rentree', 'label': 'Rentrée scolaire', 'market_mode': '',
     'date_debut': datetime.date(2026, 9, 1),
     'date_fin': datetime.date(2026, 9, 15), 'lead_days': 21},
    # Canicule (pic de chaleur — argument climatisation solaire).
    {'tag': 'canicule', 'label': 'Canicule (été)', 'market_mode': '',
     'date_debut': datetime.date(2026, 7, 1),
     'date_fin': datetime.date(2026, 8, 31), 'lead_days': 30},
    # Saison agricole post-récolte (pompage solaire — mode marché agricole).
    {'tag': 'agricole_post_recolte', 'label': 'Saison agricole (post-récolte)',
     'market_mode': 'agricole',
     'date_debut': datetime.date(2026, 6, 15),
     'date_fin': datetime.date(2026, 8, 15), 'lead_days': 30},
]

# Proximité « très loin » attribuée à un item sans saison connue ou sans
# occurrence à venir : il passe APRÈS tous les items rattachés à une saison.
FAR_PROXIMITY = 10 ** 6


def seed_calendar(company):
    """PUB78 — Seed IDEMPOTENT du calendrier créatif d'une société.

    Crée chaque événement par ``get_or_create`` sur ``(company, tag,
    date_debut)`` (jamais d'écrasement ni de doublon). Renvoie le nombre
    d'événements CRÉÉS (0 au deuxième appel)."""
    from .models import CreativeCalendarEvent

    created = 0
    for spec in SEED_EVENTS:
        _obj, was_created = CreativeCalendarEvent.objects.get_or_create(
            company=company, tag=spec['tag'], date_debut=spec['date_debut'],
            defaults={
                'label': spec['label'], 'date_fin': spec['date_fin'],
                'lead_days': spec['lead_days'],
                'market_mode': spec.get('market_mode', ''),
            })
        if was_created:
            created += 1
    return created


def _events(company):
    from .models import CreativeCalendarEvent
    return CreativeCalendarEvent.objects.filter(company=company)


def active_events(company, *, today=None):
    """Événements dont la FENÊTRE DE RECOMMANDATION couvre ``today`` (préparer
    dès J-lead_days jusqu'à la fin de la saison). Ordre : début croissant."""
    today = today or datetime.date.today()
    return [e for e in _events(company).order_by('date_debut')
            if e.is_in_recommendation_window(today)]


def upcoming_windows(company, *, today=None, within_days=45):
    """Fenêtres de recommandation qui s'OUVRENT dans ``within_days`` jours (pour
    le nudge « préparer les créas <saison> J-N »). Renvoie une liste de dicts
    ``{tag, label, date_debut, jours_avant_debut, recommandation_ouverte}``."""
    today = today or datetime.date.today()
    horizon = today + datetime.timedelta(days=within_days)
    rows = []
    for e in _events(company).order_by('date_debut'):
        if e.date_fin < today:
            continue  # occurrence passée
        rec_start = e.recommendation_start()
        if rec_start <= horizon:
            rows.append({
                'tag': e.tag, 'label': e.label,
                'date_debut': e.date_debut.isoformat(),
                'jours_avant_debut': e.days_until_start(today),
                'recommandation_ouverte': e.is_in_recommendation_window(today),
            })
    return rows


def tag_proximity(company, tag, *, today=None):
    """Proximité calendaire (en jours) de la PROCHAINE occurrence non passée d'un
    ``tag`` : 0 si la saison est en cours, sinon le nombre de jours avant son
    début. ``None`` si aucune occurrence à venir pour ce tag (ou tag vide)."""
    if not tag:
        return None
    today = today or datetime.date.today()
    best = None
    for e in _events(company).filter(tag=tag):
        if e.date_fin < today:
            continue  # passée
        prox = 0 if e.is_in_season(today) else max(0, e.days_until_start(today))
        if best is None or prox < best:
            best = prox
    return best


def sort_backlog_items(company, items, *, today=None):
    """PUB78 — Trie des items de backlog par PROXIMITÉ CALENDAIRE réelle.

    Chaque item porte un ``seasonal_tag`` : les items rattachés à une saison en
    cours ou imminente remontent (proximité croissante) ; un item sans saison
    connue (ou dont la saison est passée) passe après, dans son ordre d'origine
    (``earliest_date`` puis ``id``, comme ``backlog.queue_for_campaign``).
    Ne modifie rien en base — renvoie une NOUVELLE liste triée."""
    today = today or datetime.date.today()
    cache = {}

    def _prox(tag):
        if tag not in cache:
            p = tag_proximity(company, tag, today=today)
            cache[tag] = FAR_PROXIMITY if p is None else p
        return cache[tag]

    def _key(item):
        earliest = getattr(item, 'earliest_date', None)
        return (
            _prox(getattr(item, 'seasonal_tag', '') or ''),
            earliest or datetime.date.max,
            getattr(item, 'id', 0) or 0,
        )

    return sorted(items, key=_key)

"""FG27 / QJ6 — Score de qualité d'un lead (0–100, sans ML).

Le score est une somme pondérée TRANSPARENTE de signaux déjà capturés.
Il ne remplace pas la priorité manuelle ; il l'enrichit (badge kanban, tri).

Pondérations (total max = 100) :
  Complétude du profil         30 pts max
    Champs renseignés (10 critères, 3 pts chacun)
  Facture électrique (budget)  20 pts max
    Montant facture_hiver en MAD/mois
  Canal d'acquisition          15 pts max
    Référence/appel entrant = fort ; Meta Ads = faible
  Type d'installation           8 pts max
    Industriel/commercial > résidentiel
  Recency                      12 pts max
    Plus récent = plus de points
  Signaux qualité solaire :
    regularisation_8221          5 pts   (loi 82-21 = projet structuré)
    whatsapp_opt_in              3 pts   (consentement = meilleure joignabilité)
    GPS présent (gps_lat)        3 pts   (localisation tracée = visite facilitée)
    Orientation favorable        2 pts   (Sud/Sud-Est/Sud-Ouest)
    Ombrage nul                  2 pts   (aucun = bon rendement)
  Signaux de maturité d'achat (QK2 — bonus, capés par le min(100)) :
    ownership                    6 pts max (propriétaire = décideur)
    project_timeline             8 pts max (immédiat > plus tard)
    financing_intent             6 pts max (comptant > indécis)
    roof_age                     2 pts max (toiture récente = pose simple)
    distributeur renseigné       2 pts     (donnée tarifaire qualifiée)

Le total brut peut dépasser 100 avec les bonus QK2 ; le score final reste
borné à 100 (min). Modifier les pondérations ici sans toucher le sérialiseur
ni la vue.
"""
from __future__ import annotations

from decimal import Decimal
from django.utils import timezone


# ── Pondérations ─────────────────────────────────────────────────────────────
_W_COMPLETENESS = 30   # 10 champs × 3 pts chacun
_W_BILL = 20           # facture hiver (MAD/mois)
_W_CANAL = 15          # canal d'acquisition
_W_TYPE = 8            # type d'installation
_W_RECENCY = 12        # recency (âge du lead)
# Signaux qualitatifs solaires (bonus fixes)
_W_82_21 = 5           # régularisation loi 82-21
_W_WA_OPT_IN = 3       # consentement WhatsApp
_W_GPS = 3             # GPS renseigné
_W_ORIENTATION = 2     # orientation favorable (panneau solaire)
_W_OMBRAGE = 2         # ombrage nul


# ── Scores par canal ─────────────────────────────────────────────────────────
# Canaux à forte intention d'achat = score max ; prospection froide = faible.
_CANAL_SCORES: dict[str, int] = {
    'reference': 15,        # Recommandation = très forte intention
    'telephone': 13,        # Appel entrant = fort
    'walk_in': 13,          # Visite physique = fort
    'whatsapp_ctwa': 11,    # Click-to-WhatsApp = moyen-fort
    'site_web': 9,          # Formulaire web = moyen
    'meta_ads': 7,          # Pub Meta = moyen-bas
    'autre': 5,
}


# ── Score par montant de facture hiver (MAD/mois) ────────────────────────────

def _bill_score(facture: Decimal | None) -> int:
    """Converti le montant de la facture hiver en points (0–20).

    Seuils calibrés sur le marché marocain des installations solaires :
    une facture >= 3 000 MAD/mois correspond à un système >= 3 kWc.
    """
    if facture is None:
        return 0
    f = float(facture)
    if f >= 10000:
        return 20
    if f >= 5000:
        return 17
    if f >= 3000:
        return 14
    if f >= 1500:
        return 10
    if f >= 1000:
        return 7
    if f >= 800:
        return 4
    return 2  # saisie mais en dessous du seuil rentable


# ── Scores par type d'installation ───────────────────────────────────────────
_TYPE_SCORES: dict[str, int] = {
    'industriel': 8,
    'commercial': 8,
    'agricole': 6,
    'residentiel': 4,
}

# ── Orientations favorables pour le solaire ──────────────────────────────────
_GOOD_ORIENTATIONS = {'sud', 'sud_est', 'sud_ouest'}


# ── Complétude ───────────────────────────────────────────────────────────────
# 10 champs clés de qualification (3 pts chacun = 30 pts max).
_COMPLETENESS_FIELDS = [
    'telephone', 'email', 'ville', 'type_installation',
    'facture_hiver', 'surface_toiture_m2', 'orientation', 'type_toiture',
    'whatsapp', 'raccordement',
]


def _completeness_score(lead) -> int:
    filled = sum(
        1 for f in _COMPLETENESS_FIELDS
        if getattr(lead, f, None) not in (None, '', False)
    )
    ratio = filled / len(_COMPLETENESS_FIELDS)
    return round(ratio * _W_COMPLETENESS)


# ── Recency ──────────────────────────────────────────────────────────────────
def _recency_score(lead) -> int:
    """Âge du lead en points : plus récent = plus de points."""
    now = timezone.now()
    dc = lead.date_creation
    # Rendre tz-aware si naïf (ne devrait pas arriver en prod mais défensif).
    if dc and hasattr(dc, 'tzinfo') and dc.tzinfo is None:
        from django.utils.timezone import make_aware
        dc = make_aware(dc)
    if dc is None:
        return 0
    age_days = (now - dc).days
    if age_days <= 1:
        return _W_RECENCY    # 12 pts — créé aujourd'hui ou hier
    if age_days <= 7:
        return 10
    if age_days <= 30:
        return 7
    if age_days <= 90:
        return 3
    return 1  # très vieux mais non perdu


# ── Signaux qualitatifs solaires ─────────────────────────────────────────────

def _solar_signals_score(lead) -> int:
    """Signaux de qualité propres au solaire marocain (bonus cumulables).

    - regularisation_8221 : le prospect a une installation existante à régulariser
      → projet défini et urgent → +5 pts.
    - whatsapp_opt_in : consentement WhatsApp donné → meilleure joignabilité → +3.
    - GPS (gps_lat non nul) : localisation tracée → visite préparable → +3.
    - Orientation favorable (Sud/Sud-Est/Sud-Ouest) → meilleur rendement → +2.
    - Ombrage nul → meilleur rendement → +2.
    """
    pts = 0
    if getattr(lead, 'regularisation_8221', False):
        pts += _W_82_21
    if getattr(lead, 'whatsapp_opt_in', None) is True:
        pts += _W_WA_OPT_IN
    if getattr(lead, 'gps_lat', None) not in (None, ''):
        pts += _W_GPS
    orientation = getattr(lead, 'orientation', None) or ''
    if orientation in _GOOD_ORIENTATIONS:
        pts += _W_ORIENTATION
    ombrage = getattr(lead, 'ombrage', None) or ''
    if ombrage == 'aucun':
        pts += _W_OMBRAGE
    return pts


# ── Signaux de maturité d'achat (QK2) ────────────────────────────────────────
# Pondérations des nouveaux signaux de qualification captés par le site
# (webhook QK1). Tous facultatifs : un lead sans ces champs garde exactement
# son score d'avant — les bonus ne font que révéler la maturité réelle.

_OWNERSHIP_SCORES: dict[str, int] = {
    'proprietaire': 6,   # décideur direct → très fort
    'autre': 1,          # copropriété/société… → faible mais non nul
    'locataire': 0,      # ne décide pas des travaux
}

_TIMELINE_SCORES: dict[str, int] = {
    'immediat': 8,       # prêt à signer
    '3_mois': 6,
    '6_mois': 3,
    'plus_tard': 1,      # simple curiosité
}

_FINANCING_SCORES: dict[str, int] = {
    'cash': 6,           # budget disponible
    'credit': 4,         # financement envisagé = projet réfléchi
    'indecis': 1,
}

_W_DISTRIBUTEUR = 2      # distributeur connu = donnée tarifaire qualifiée


def _roof_age_score(roof_age) -> int:
    """Toiture récente = pose simple (2 pts) ; vieillissante = 1 pt ; sinon 0."""
    if roof_age is None:
        return 0
    try:
        age = int(roof_age)
    except (TypeError, ValueError):
        return 0
    if age < 0:
        return 0
    if age <= 10:
        return 2
    if age <= 25:
        return 1
    return 0


def _readiness_score(lead) -> int:
    """QK2 — maturité d'achat déclarée (bonus cumulables, max 24 pts).

    ``getattr`` défensif : la fonction reste utilisable sur des objets
    partiels (tests, leads historiques d'avant la migration 0034)."""
    pts = 0
    pts += _OWNERSHIP_SCORES.get(getattr(lead, 'ownership', None) or '', 0)
    pts += _TIMELINE_SCORES.get(
        getattr(lead, 'project_timeline', None) or '', 0)
    pts += _FINANCING_SCORES.get(
        getattr(lead, 'financing_intent', None) or '', 0)
    pts += _roof_age_score(getattr(lead, 'roof_age', None))
    if getattr(lead, 'distributeur', None):
        pts += _W_DISTRIBUTEUR
    return pts


# ── Entrée publique ───────────────────────────────────────────────────────────

def compute_score(lead) -> int:
    """Calcule et retourne le score de qualité du lead (entier 0–100).

    N'effectue aucune écriture. Appelable depuis le sérialiseur, la vue,
    ou un service.  Alias : ``compute_lead_score``.
    """
    score = 0
    score += _completeness_score(lead)
    score += _bill_score(lead.facture_hiver)
    score += _CANAL_SCORES.get(lead.canal or '', 0)
    score += _TYPE_SCORES.get(lead.type_installation or '', 0)
    score += _recency_score(lead)
    score += _solar_signals_score(lead)
    score += _readiness_score(lead)
    return min(score, 100)


# Alias pour les imports qui utilisent le nom long (QJ6).
compute_lead_score = compute_score


# ── Décomposition (VX221) ─────────────────────────────────────────────────────
# Libellés FR courts des facteurs, pour le tooltip « pourquoi ce score ».
_FACTEUR_LABELS = {
    'completude': 'Profil complété',
    'facture': 'Facture élevée',
    'canal': 'Canal',
    'type': "Type d'installation",
    'recency': 'Lead récent',
    'solar': 'Signaux solaires',
    'readiness': "Maturité d'achat",
}


def score_reasons(lead) -> list[dict]:
    """VX221 — décompose le score en ses composantes NON NULLES, triées par
    points décroissants. PURE exposition des mêmes calculs que ``compute_score``
    (aucun recalcul de pondération différent) : le front affiche « pourquoi »
    sans dupliquer la logique. Chaque entrée = ``{'facteur', 'label', 'points'}``.

    Le total des ``points`` peut dépasser 100 (bonus QK2) ; le score exposé reste
    borné par ``compute_score``. On n'expose que les facteurs qui rapportent des
    points (> 0) pour rester lisible."""
    parts = [
        ('completude', _completeness_score(lead)),
        ('facture', _bill_score(lead.facture_hiver)),
        ('canal', _CANAL_SCORES.get(lead.canal or '', 0)),
        ('type', _TYPE_SCORES.get(lead.type_installation or '', 0)),
        ('recency', _recency_score(lead)),
        ('solar', _solar_signals_score(lead)),
        ('readiness', _readiness_score(lead)),
    ]
    reasons = [
        {
            'facteur': key,
            'label': _FACTEUR_LABELS[key],
            'points': pts,
        }
        for key, pts in parts if pts > 0
    ]
    reasons.sort(key=lambda r: r['points'], reverse=True)
    return reasons


def score_label(score: int) -> str:
    """Libellé FR court du score (pour badge kanban)."""
    if score >= 70:
        return 'Chaud'
    if score >= 45:
        return 'Tiède'
    return 'Froid'

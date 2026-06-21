"""FG27 — Calcul du score de qualité d'un lead (lecture seule, sans persistance).

Le score (0–100) est calculé à la volée depuis les champs existants du lead.
Il ne remplace pas la priorité manuelle ; il l'enrichit (badge kanban, tri).

Composantes (pondérées) :
  - Complétude du profil (30 pts max) : champs renseignés
  - Facture électrique / budget (25 pts max) : montant de la facture hiver
  - Canal d'acquisition (20 pts max) : canaux à intention plus forte
  - Type d'installation (10 pts max) : industriel/commercial > résidentiel
  - Recency (15 pts max) : plus le lead est récent, plus le score est élevé

La logique est documentée et testée ; modifier les pondérations ici sans toucher
le reste du code (sérialiseur, vue) suffit pour les futurs ajustements.
"""
from __future__ import annotations

from decimal import Decimal
from django.utils import timezone


# ── Pondérations ─────────────────────────────────────────────────────────────
_W_COMPLETENESS = 30
_W_BILL = 25
_W_CANAL = 20
_W_TYPE = 10
_W_RECENCY = 15


# ── Scores par canal ─────────────────────────────────────────────────────────
# Canaux à forte intention d'achat = score max ; prospection froide = score bas.
_CANAL_SCORES: dict[str, int] = {
    'reference': 20,       # Recommandation = très forte intention
    'telephone': 18,       # Appel entrant = fort
    'walk_in': 18,         # Visite physique = fort
    'whatsapp_ctwa': 15,   # Click-to-WhatsApp = moyen-fort
    'site_web': 12,        # Formulaire web = moyen
    'meta_ads': 10,        # Pub Meta = moyen-bas
    'autre': 8,
}

# ── Scores par montant de facture hiver (MAD/mois) ───────────────────────────
def _bill_score(facture: Decimal | None) -> int:
    if facture is None:
        return 0
    f = float(facture)
    if f >= 10000:
        return 25
    if f >= 5000:
        return 22
    if f >= 3000:
        return 18
    if f >= 1500:
        return 14
    if f >= 1000:
        return 10
    if f >= 800:
        return 7
    return 3  # saisie mais en dessous du seuil rentable


# ── Scores par type d'installation ───────────────────────────────────────────
_TYPE_SCORES: dict[str, int] = {
    'industriel': 10,
    'commercial': 10,
    'agricole': 8,
    'residentiel': 6,
}


# ── Complétude ───────────────────────────────────────────────────────────────
# Champs importants pour la qualification du lead (poids égaux).
_COMPLETENESS_FIELDS = [
    'telephone', 'email', 'ville', 'type_installation',
    'facture_hiver', 'surface_toiture_m2', 'orientation', 'type_toiture',
    'gps_lat', 'whatsapp',
]


def _completeness_score(lead) -> int:
    filled = sum(
        1 for f in _COMPLETENESS_FIELDS
        if getattr(lead, f, None) not in (None, '', False)
    )
    ratio = filled / len(_COMPLETENESS_FIELDS)
    return round(ratio * _W_COMPLETENESS)


# ── Recency ───────────────────────────────────────────────────────────────────
def _recency_score(lead) -> int:
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
        return _W_RECENCY        # 15 pts — créé aujourd'hui ou hier
    if age_days <= 7:
        return 12
    if age_days <= 30:
        return 8
    if age_days <= 90:
        return 4
    return 1  # très vieux mais non perdu


# ── Entrée publique ───────────────────────────────────────────────────────────

def compute_score(lead) -> int:
    """Calcule et retourne le score de qualité du lead (entier 0–100).

    N'effectue aucune écriture. Peut être appelé depuis le sérialiseur ou une vue.
    """
    score = 0
    score += _completeness_score(lead)
    score += _bill_score(lead.facture_hiver)
    score += _CANAL_SCORES.get(lead.canal or '', 0)
    score += _TYPE_SCORES.get(lead.type_installation or '', 0)
    score += _recency_score(lead)
    return min(score, 100)


def score_label(score: int) -> str:
    """Libellé FR court du score (pour badge kanban)."""
    if score >= 70:
        return 'Chaud'
    if score >= 45:
        return 'Tiède'
    return 'Froid'

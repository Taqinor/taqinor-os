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
    """Fraîcheur du DOSSIER en points : plus récent = plus de points.

    CAD133 (21/09/2026) — ce n'est plus l'âge du LEAD. Compter la date de
    CRÉATION donnait 1 point sur 12 à un prospect qui répond aujourd'hui après
    quatre mois de silence, exactement comme à un dossier mort. On part donc de
    la DERNIÈRE INTERACTION (``signaux.derniere_interaction`` : chatter,
    consultation de la proposition, réponse au questionnaire, rappel demandé)
    et on retombe sur la date de création quand il n'y en a aucune — ce qui est
    la vérité pour un lead que personne n'a encore touché.
    """
    now = timezone.now()
    from .signaux import derniere_interaction
    dc = derniere_interaction(lead) or lead.date_creation
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

def score_ajustement(lead) -> int:
    """CRX22 — delta PERSISTANT ajouté au score calculé (``Lead.score_ajustement``).

    Une automatisation (ou un correctif manuel) qui écrivait ``Lead.score``
    directement voyait son delta effacé au premier recalcul. Le delta a
    désormais SA colonne, et c'est le CALCUL qui l'applique : il survit à
    chaque ``recompute_lead_score``. ``getattr`` défensif — la fonction reste
    utilisable sur un objet partiel (tests, lead d'avant la migration 0087).
    """
    valeur = getattr(lead, 'score_ajustement', None)
    try:
        return int(valeur or 0)
    except (TypeError, ValueError):
        return 0


# ── CAD-K ── CAD94 — décision du 21/09/2026 ─────────────────────────────────
# AUCUN EFFET DES TENTATIVES DE CADENCE SUR LE SCORE — décision du
# 21/09/2026, à rouvrir sur les mesures de CAD87.
#
# L'audit L3 du 21/09/2026 constatait qu'un lead injoignable depuis cinq
# touches garde le même score qu'un lead frais. La tentation est d'en
# déduire une règle (« -N points par touche sans réponse ») : le fondateur a
# tranché l'inverse. On ne câble RIEN avant de mesurer. CAD87 dira si le
# nombre de touches consommées prédit quoi que ce soit — taux de joint par
# touche × heure × jour × canal, et signatures par nombre de touches
# consommées — et la règle s'écrira sur ces chiffres, ou ne s'écrira pas.
#
# Cette note est datée pour qu'un futur audit ne re-soulève pas la question
# sans les mesures : la rouvrir sans elles, c'est réinventer le même débat.
def compute_score(lead) -> int:
    """Calcule et retourne le score de qualité du lead (entier 0–100).

    N'effectue aucune écriture. Appelable depuis le sérialiseur, la vue,
    ou un service.  Alias : ``compute_lead_score``.

    CRX22 — l'ajustement persistant (``Lead.score_ajustement``) est appliqué
    ICI, avant le bornage : c'est le SEUL endroit qui décide de la valeur d'un
    score, badge, tri et « Ma file » compris.

    CAD94 (21/09/2026) — aucune composante ne lit les tentatives de cadence :
    voir la note datée juste au-dessus.
    """
    score = 0
    score += _completeness_score(lead)
    score += _bill_score(lead.facture_hiver)
    score += _CANAL_SCORES.get(lead.canal or '', 0)
    score += _TYPE_SCORES.get(lead.type_installation or '', 0)
    score += _recency_score(lead)
    score += _solar_signals_score(lead)
    score += _readiness_score(lead)
    # CAD133 — ce que le client FAIT, à côté de ce qu'il a DIT. Poids
    # PROVISOIRES, à valider contre les scores réels de production (CADM7)
    # avant d'être figés : voir la note en tête de `_behaviour_score`.
    score += _behaviour_score(lead)
    score += score_ajustement(lead)
    # Un ajustement négatif ne doit jamais produire un score négatif.
    return max(0, min(score, 100))


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
    # CRX22 — l'ajustement persistant est un facteur comme un autre : le
    # tooltip « pourquoi ce score » ne doit pas cacher un delta appliqué.
    'ajustement': 'Ajustement',
}


def score_reasons(lead) -> list[dict]:
    """VX221 — décompose le score en ses composantes NON NULLES, triées par
    points décroissants. PURE exposition des mêmes calculs que ``compute_score``
    (aucun recalcul de pondération différent) : le front affiche « pourquoi »
    sans dupliquer la logique. Chaque entrée = ``{'facteur', 'label', 'points'}``.

    Le total des ``points`` peut dépasser 100 (bonus QK2) ; le score exposé reste
    borné par ``compute_score``. On n'expose que les facteurs qui rapportent des
    points (> 0) pour rester lisible — SAUF l'ajustement CRX22, montré aussi
    quand il est NÉGATIF : un score rabaissé à la main doit s'expliquer."""
    parts = [
        ('completude', _completeness_score(lead)),
        ('facture', _bill_score(lead.facture_hiver)),
        ('canal', _CANAL_SCORES.get(lead.canal or '', 0)),
        ('type', _TYPE_SCORES.get(lead.type_installation or '', 0)),
        ('recency', _recency_score(lead)),
        ('solar', _solar_signals_score(lead)),
        ('readiness', _readiness_score(lead)),
        ('ajustement', score_ajustement(lead)),
    ]
    reasons = [
        {
            'facteur': key,
            'label': _FACTEUR_LABELS[key],
            'points': pts,
        }
        for key, pts in parts
        if pts > 0 or (key == 'ajustement' and pts != 0)
    ]
    reasons.sort(key=lambda r: r['points'], reverse=True)
    return reasons


# ── CAD-K ── CAD133 — la composante COMPORTEMENT ────────────────────────────
#
# Audit L3 du 21/09/2026. Le score n'additionnait que des DÉCLARATIONS de
# capture ; ce que le client FAIT — ouvrir sa proposition, y revenir, la lire
# en détail, répondre au questionnaire, demander un rappel, décrocher — ne
# pesait rien. Tous ces signaux étaient DÉJÀ en base : rien n'est capté en
# plus (``apps/crm/signaux.py`` les rassemble, `ventes` est lu par son
# selector).
#
# LES POIDS SONT PROVISOIRES, ET C'EST ÉCRIT. Le round 2 de l'audit l'exige :
# « VALIDER les poids contre les scores réels de production (CADM7) avant de
# les figer — les poids actuels sont annoncés "calibrés Maroc" sans source ».
# Ils suivent donc l'ORDRE de force des signaux (revenir sur sa proposition
# dit plus que l'avoir ouverte une fois), pas une calibration qui n'existe
# pas ; le total est volontairement modeste pour ne pas écraser les
# composantes déclaratives avant cette validation.
_W_COMPORTEMENT = {
    'proposition_ouverte': 3,    # il a regardé
    'proposition_rouverte': 5,   # il y est REVENU — le signal le plus fort
    'lue_en_detail': 4,          # il a lu au-delà du premier écran
    'questionnaire_repondu': 4,  # il a passé du temps sur NOTRE formulaire
    'rappel_demande': 5,         # il a demandé qu'on l'appelle
    'client_joint': 3,           # on l'a eu au bout du fil
}


def _behaviour_score(lead) -> int:
    """CAD133 — points de COMPORTEMENT, jamais de déclaration.

    Lecture seule et tolérante : un signal illisible vaut « absent » (voir
    ``signaux``), et le total reste borné par le ``min(…, 100)`` de
    ``compute_score`` comme les bonus QK2.
    """
    from .signaux import signaux_comportement

    signaux = signaux_comportement(lead)
    return sum(points for cle, points in _W_COMPORTEMENT.items()
               if signaux.get(cle))


def score_label(score: int) -> str:
    """Libellé FR court du score (pour badge kanban)."""
    if score >= 70:
        return 'Chaud'
    if score >= 45:
        return 'Tiède'
    return 'Froid'

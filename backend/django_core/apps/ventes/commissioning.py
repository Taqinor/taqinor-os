"""FG274-FG275 — calculs purs de la recette IEC 62446 & des courbes I-V.

Fonctions PURES (sans Django) réutilisées par les viewsets pour DÉRIVER côté
serveur le résultat de recette et le verdict « défaut détecté » d'une courbe I-V
— jamais lus du corps de la requête. Aucun prix.
"""
from __future__ import annotations

# Tolérance par défaut sur l'écart de puissance mesuré vs attendu (%).
DEFAULT_PMAX_TOLERANCE_PCT = 8.0

# FG287 — facteur d'émission moyen du réseau électrique marocain
# (kg CO₂ / kWh). Valeur de référence appliquée côté serveur pour dériver le CO₂
# évité ; jamais lue du corps de la requête.
DEFAULT_GRID_CO2_KG_PER_KWH = 0.72

# FG278 — seuil de PR par défaut sous lequel la réception est refusée.
DEFAULT_PR_ACCEPTANCE = 0.75


def _to_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_commissioning_result(*, isolement_ok=None, polarite_ok=None,
                                 continuite_terre_ok=None,
                                 controle_onduleur_ok=None,
                                 has_defective_iv=False):
    """FG274 — résultat global de la recette à partir des essais.

    Règles :
    * un essai explicitement ``False`` (ou un string I-V défectueux) →
      ``non_conforme`` ;
    * tous les essais renseignés ``True`` et aucun défaut → ``conforme`` ;
    * essais partiellement renseignés (aucun False) → ``en_cours``.

    ``has_defective_iv`` : au moins une courbe I-V hors tolérance.
    Renvoie une valeur de ``CommissioningTest.Resultat``.
    """
    checks = [isolement_ok, polarite_ok, continuite_terre_ok,
              controle_onduleur_ok]
    if any(c is False for c in checks) or has_defective_iv:
        return 'non_conforme'
    if all(c is True for c in checks):
        return 'conforme'
    return 'en_cours'


def evaluate_iv_curve(*, pmax_mesure_w=None, pmax_attendu_w=None,
                      tolerance_pct=DEFAULT_PMAX_TOLERANCE_PCT):
    """FG275 — écart Pmax (%) et verdict défaut d'une courbe I-V.

    L'écart est ``(mesuré - attendu) / attendu × 100`` (négatif = sous-
    performance). Un écart NÉGATIF dont l'amplitude dépasse la tolérance signale
    un module/string défectueux. Renvoie ``(ecart_pct, defaut_detecte)`` ;
    ``(None, False)`` si les données sont insuffisantes (jamais d'exception).
    """
    mesure = _to_float(pmax_mesure_w)
    attendu = _to_float(pmax_attendu_w)
    try:
        tol = float(tolerance_pct)
    except (TypeError, ValueError):
        tol = DEFAULT_PMAX_TOLERANCE_PCT
    if tol < 0:
        tol = DEFAULT_PMAX_TOLERANCE_PCT
    if mesure is None or attendu is None or attendu <= 0:
        return None, False
    ecart = round((mesure - attendu) / attendu * 100.0, 2)
    # Sous-performance au-delà de la tolérance = défaut.
    defaut = ecart < -tol
    return ecart, defaut


def compute_reception_pr(*, energie_mesuree_kwh=None, energie_attendue_kwh=None,
                         pr_mesure=None, pr_attendu=None,
                         pr_seuil_acceptation=None):
    """FG278 — dérive PR mesuré, écart (%) et verdict d'un test de réception.

    Si ``pr_mesure`` n'est pas fourni mais que les énergies mesurée et attendue
    le sont, on dérive ``pr_mesure = pr_attendu × (mesurée / attendue)`` (le PR
    attendu rapporté au ratio d'énergie réalisé). L'écart relatif est
    ``(pr_mesure - pr_attendu) / pr_attendu × 100``. Le verdict est ``refuse`` si
    ``pr_mesure`` tombe sous le seuil d'acceptation, ``accepte`` s'il est ≥ seuil,
    ``en_attente`` faute de données. Renvoie ``(pr_mesure, ecart_pct, verdict)``.
    Jamais d'exception.
    """
    e_mes = _to_float(energie_mesuree_kwh)
    e_att = _to_float(energie_attendue_kwh)
    pr_m = _to_float(pr_mesure)
    pr_a = _to_float(pr_attendu)
    seuil = _to_float(pr_seuil_acceptation)
    if seuil is None:
        seuil = DEFAULT_PR_ACCEPTANCE
    # Dériver le PR mesuré depuis les énergies si non fourni.
    if pr_m is None and e_mes is not None and e_att is not None and e_att > 0 \
            and pr_a is not None:
        pr_m = round(pr_a * (e_mes / e_att), 4)
    ecart = None
    if pr_m is not None and pr_a is not None and pr_a > 0:
        ecart = round((pr_m - pr_a) / pr_a * 100.0, 2)
    if pr_m is None:
        verdict = 'en_attente'
    elif pr_m < seuil:
        verdict = 'refuse'
    else:
        verdict = 'accepte'
    return pr_m, ecart, verdict


def compute_co2_evite(*, energie_kwh=None,
                      facteur_co2_kg_kwh=DEFAULT_GRID_CO2_KG_PER_KWH):
    """FG287 — CO₂ évité (en tonnes) pour une énergie verte produite (kWh).

    ``CO₂ évité (t) = énergie (kWh) × facteur (kg/kWh) / 1000``. Le facteur réseau
    par défaut est appliqué côté serveur. Renvoie ``(facteur, co2_t)`` ;
    ``(facteur, None)`` si l'énergie est absente. Jamais d'exception.
    """
    try:
        facteur = float(facteur_co2_kg_kwh)
    except (TypeError, ValueError):
        facteur = DEFAULT_GRID_CO2_KG_PER_KWH
    if facteur < 0:
        facteur = DEFAULT_GRID_CO2_KG_PER_KWH
    energie = _to_float(energie_kwh)
    if energie is None:
        return round(facteur, 4), None
    co2_t = round(energie * facteur / 1000.0, 3)
    return round(facteur, 4), co2_t

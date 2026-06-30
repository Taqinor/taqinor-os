"""FG274-FG275 — calculs purs de la recette IEC 62446 & des courbes I-V.

Fonctions PURES (sans Django) réutilisées par les viewsets pour DÉRIVER côté
serveur le résultat de recette et le verdict « défaut détecté » d'une courbe I-V
— jamais lus du corps de la requête. Aucun prix.
"""
from __future__ import annotations

# Tolérance par défaut sur l'écart de puissance mesuré vs attendu (%).
DEFAULT_PMAX_TOLERANCE_PCT = 8.0


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

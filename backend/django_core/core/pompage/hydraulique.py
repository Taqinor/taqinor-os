"""AGR109 — hydraulique du pompage solaire (noyau pur ``core.pompage``).

Fonctions DÉPLACÉES telles quelles depuis ``apps/calepinage/services/pompage.py``
(CAL156) : interpolation du débit à une HMT sur la courbe constructeur
(:func:`debit_a_hmt`, jumelle de ``solar.js debitAtHmt``) et HMT de puits itérée
(:func:`hmt_puits_iteree`). Comportement OCTET-IDENTIQUE ; le module calepinage
garde des ré-exports.

Noyau PUR : stdlib seulement, aucune dépendance Django, aucune I/O.
"""
from __future__ import annotations


def _flottant(valeur, defaut=None):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return defaut


# ═══════════════════════════════════════════════════════════════════════════
# CAL156 — HMT calculée par puits (niveau statique + rabattement + pertes),
# ITÉRATIVE puisque la hauteur dépend du débit délivré par la pompe.
# ═══════════════════════════════════════════════════════════════════════════

def debit_a_hmt(courbe, hmt):
    """Port Python de ``frontend/src/features/ventes/solar.js debitAtHmt`` —
    MÊME interpolation linéaire, MÊME comportement aux bornes (au-delà de la
    capacité de la pompe ⇒ 0 ; en-deçà du dernier point mesuré ⇒ borné au
    dernier point). Deux implémentations d'une seule formule ne doivent
    JAMAIS diverger : toute modification ici doit être reportée côté JS (et
    inversement) — un test de parité (CAL158) les confronte sur un jeu de cas
    committé.
    """
    if not courbe:
        return None
    debits = courbe.get('debits_m3h')
    hmts = courbe.get('hmt_m')
    if not debits or not hmts or len(debits) < 2 or len(debits) != len(hmts):
        return None
    h = _flottant(hmt)
    if h is None or h <= 0:
        return None
    d = [float(x) for x in debits]
    hh = [float(x) for x in hmts]
    if h > hh[0]:
        return 0.0
    if h <= hh[-1]:
        return round(d[-1], 1)
    for i in range(len(hh) - 1):
        if h <= hh[i] and h > hh[i + 1]:
            t = (hh[i] - h) / (hh[i] - hh[i + 1])
            return round(d[i] + t * (d[i + 1] - d[i]), 1)
    return None


#: Nom historique (CAL156/CAL158) — gardé pour les appelants et le différentiel.
_debit_a_hmt = debit_a_hmt


#: Les cinq données de puits EXIGÉES pour calculer une HMT (au lieu de la
#: saisir) — toute absence fait retomber sur la HMT saisie, ANNONCÉE comme
#: telle (jamais une HMT calculée à moitié, sur des données incomplètes).
_CHAMPS_PUITS_REQUIS = (
    'niveau_statique_m', 'coefficient_rabattement_m_par_m3h',
    'longueur_tuyauterie_m', 'coefficient_frottement',
    'hauteur_refoulement_m',
)


def hmt_puits_iteree(*, courbe_pompe=None, hmt_saisie=None,
                     niveau_statique_m=None,
                     coefficient_rabattement_m_par_m3h=None,
                     longueur_tuyauterie_m=None, coefficient_frottement=None,
                     hauteur_refoulement_m=None, debit_initial_m3h=None,
                     max_iterations=20, tolerance_m3h=0.05):
    """CAL156 — HMT = niveau statique + rabattement(débit) + pertes de
    charge(longueur, débit, coefficient SAISI) + hauteur de refoulement,
    ITÉRÉE jusqu'à convergence avec la courbe pompe (la hauteur dépend du
    débit, le débit dépend de la hauteur).

    ``coefficient_rabattement_m_par_m3h`` : rabattement SPÉCIFIQUE du puits
    (m de rabattement par m³/h pompé) — une donnée de PUITS RÉEL (essai de
    pompage), jamais un coefficient de la littérature. ``coefficient_frottement``
    : coefficient de pertes de charge de la tuyauterie posée — SAISI, jamais
    une valeur Hazen-Williams par défaut (CLAUDE.md : « aucun coefficient
    inventé »). Modèle de pertes : ``coefficient_frottement × longueur_m ×
    débit²`` — la forme quadratique standard d'une perte de charge régulière,
    le coefficient absorbant matériau/diamètre/rugosité (tous SAISIS via ce
    seul coefficient plutôt que reconstruits depuis une table interne).

    DONNÉE DE PUITS MANQUANTE (l'une des cinq) ⇒ repli sur ``hmt_saisie``,
    ``source: 'saisie'`` — jamais une HMT calculée sur des données
    incomplètes. Rend toujours
    ``{hmt_m, source, composantes, debit_convergence_m3h, iterations}``.
    """
    donnees = {
        'niveau_statique_m': niveau_statique_m,
        'coefficient_rabattement_m_par_m3h': coefficient_rabattement_m_par_m3h,
        'longueur_tuyauterie_m': longueur_tuyauterie_m,
        'coefficient_frottement': coefficient_frottement,
        'hauteur_refoulement_m': hauteur_refoulement_m,
    }
    if any(donnees[champ] is None for champ in _CHAMPS_PUITS_REQUIS):
        return {
            'hmt_m': _flottant(hmt_saisie),
            'source': 'saisie',
            'composantes': None,
            'debit_convergence_m3h': None,
            'iterations': 0,
        }

    niveau = float(niveau_statique_m)
    coef_rabattement = float(coefficient_rabattement_m_par_m3h)
    longueur = float(longueur_tuyauterie_m)
    coef_frottement = float(coefficient_frottement)
    refoulement = float(hauteur_refoulement_m)

    premier_point = (courbe_pompe or {}).get('debits_m3h') or []
    debit = _flottant(debit_initial_m3h)
    if debit is None:
        debit = (float(premier_point[len(premier_point) // 2])
                 if premier_point else 1.0)
    if debit <= 0:
        debit = 1.0

    composantes = None
    hmt = niveau + refoulement
    for iteration in range(1, max_iterations + 1):
        rabattement = coef_rabattement * debit
        pertes = coef_frottement * longueur * (debit ** 2)
        hmt = niveau + rabattement + pertes + refoulement
        composantes = {
            'niveau_statique_m': round(niveau, 3),
            'rabattement_m': round(rabattement, 3),
            'pertes_charge_m': round(pertes, 3),
            'hauteur_refoulement_m': round(refoulement, 3),
        }
        nouveau_debit = debit_a_hmt(courbe_pompe, hmt)
        if nouveau_debit is None:
            # HMT hors de la capacité de la pompe (ou courbe inexploitable) :
            # on rend la dernière HMT calculée, sans point de convergence
            # inventé.
            return {
                'hmt_m': round(hmt, 2), 'source': 'calculee',
                'composantes': composantes, 'debit_convergence_m3h': None,
                'iterations': iteration,
            }
        if abs(nouveau_debit - debit) <= tolerance_m3h:
            return {
                'hmt_m': round(hmt, 2), 'source': 'calculee',
                'composantes': composantes,
                'debit_convergence_m3h': round(nouveau_debit, 2),
                'iterations': iteration,
            }
        debit = nouveau_debit

    return {
        'hmt_m': round(hmt, 2), 'source': 'calculee',
        'composantes': composantes, 'debit_convergence_m3h': round(debit, 2),
        'iterations': max_iterations,
    }

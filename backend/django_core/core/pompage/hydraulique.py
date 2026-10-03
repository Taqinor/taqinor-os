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


# ═══════════════════════════════════════════════════════════════════════════
# AGR111 — HMT PAR COMPOSANTES : niveau dynamique + dénivelé + pertes
# Hazen-Williams + pertes singulières + pression de service.
# ═══════════════════════════════════════════════════════════════════════════

#: Conversion PHYSIQUE de la pression en hauteur d'eau : 1 bar = 10⁵ Pa ;
#: h = p / (ρ·g) avec ρ = 1000 kg/m³ et g = 9,80665 m/s² (pesanteur normale,
#: 3e CGPM 1901) ⇒ 10,197 m par bar.
METRES_PAR_BAR = 10.197

#: Matériaux dont le coefficient Hazen-Williams vient de la table AGR110
#: (``hazen_williams_c_pvc_pehd``). Tout autre matériau exige un C SAISI.
MATERIAUX_C_TABLE = frozenset({"pvc", "pehd"})

#: Champ nommé par l'alerte quand le C d'un matériau hors table manque.
CHAMP_C_HAZEN_WILLIAMS = "hmt.conduite.c_hazen_williams"


def pertes_hazen_williams(*, longueur_m, debit_m3h, diametre_interieur_mm,
                          c_hazen_williams):
    """Pertes de charge linéaires (m), formule de Hazen-Williams (SI) :
    hf = 10,67·L·Q^1,852 / (C^1,852·d^4,8655), Q en m³/s, d en m.

    Une donnée absente, nulle ou négative ⇒ ``None`` (jamais un défaut)."""
    longueur = _flottant(longueur_m)
    debit = _flottant(debit_m3h)
    diametre = _flottant(diametre_interieur_mm)
    c = _flottant(c_hazen_williams)
    if None in (longueur, debit, diametre, c):
        return None
    if longueur < 0 or debit < 0 or diametre <= 0 or c <= 0:
        return None
    q = debit / 3600.0
    d = diametre / 1000.0
    return 10.67 * longueur * q ** 1.852 / (c ** 1.852 * d ** 4.8655)


def _norme_materiau(materiau):
    texte = (materiau or "").strip().lower()
    for avant, apres in (("é", "e"), ("è", "e"), ("-", ""), (" ", "")):
        texte = texte.replace(avant, apres)
    return texte or None


def _provenance_saisie(provenances, cle):
    """Provenance d'une entrée SAISIE — celle fournie par l'appelant
    (forme unique ``{origine, detail, date}`` du Groupe AGR) sinon ``saisie``."""
    fournie = (provenances or {}).get(cle)
    if fournie:
        return {"origine": fournie.get("origine", "saisie"),
                "detail": fournie.get("detail"),
                "date": fournie.get("date")}
    return {"origine": "saisie", "detail": None, "date": None}


def _resoudre_c(materiau, c_saisi):
    """(C, provenance, alerte) — saisi d'abord, sinon table AGR110 pour
    PVC/PEHD, sinon ``None`` + alerte nommant le champ."""
    from core.pompage.hypotheses import hypothese

    c = _flottant(c_saisi)
    if c is not None and c > 0:
        return c, {"origine": "saisie", "detail": None, "date": None}, None
    if _norme_materiau(materiau) in MATERIAUX_C_TABLE:
        entree = hypothese("hazen_williams_c_pvc_pehd")
        return (float(entree.valeur),
                {"origine": "calculee",
                 "detail": "hypotheses_pompage.json › hazen_williams_c_pvc_pehd",
                 "date": None},
                None)
    alerte = {
        "code": "c_hazen_williams_manquant",
        "champ": CHAMP_C_HAZEN_WILLIAMS,
        "message": ("Matériau de conduite « %s » hors table (PVC/PEHD) : "
                    "saisir son coefficient Hazen-Williams C — pertes de "
                    "charge non calculées." % (materiau or "non renseigné")),
    }
    return None, None, alerte


def _une_passe(debit, *, niveau_dynamique_m, niveau_statique_m,
               rabattement_specifique_m_par_m3h, longueur_conduite_m,
               diametre_interieur_mm, c, coefficient_frottement):
    """Niveau dynamique et pertes linéaires pour un débit donné."""
    niveau = _flottant(niveau_dynamique_m)
    niveau_mesure = niveau is not None
    if niveau is None:
        statique = _flottant(niveau_statique_m)
        rabattement = _flottant(rabattement_specifique_m_par_m3h)
        if statique is not None and rabattement is not None \
                and debit is not None:
            niveau = statique + rabattement * debit
    pertes = None
    if debit is not None:
        if c is not None:
            pertes = pertes_hazen_williams(
                longueur_m=longueur_conduite_m, debit_m3h=debit,
                diametre_interieur_mm=diametre_interieur_mm,
                c_hazen_williams=c)
        if pertes is None and coefficient_frottement is not None:
            # Chemin historique CAL156 conservé : coef × L × Q² (coef SAISI).
            coef = _flottant(coefficient_frottement)
            longueur = _flottant(longueur_conduite_m)
            if coef is not None and longueur is not None:
                pertes = coef * longueur * debit ** 2
    return niveau, niveau_mesure, pertes


def _arrondi(valeur, chiffres=1):
    return None if valeur is None else round(valeur, chiffres)


def hmt_composantes(*, hmt_saisie=None, courbe_pompe=None, debit_m3h=None,
                    niveau_dynamique_m=None, niveau_statique_m=None,
                    rabattement_specifique_m_par_m3h=None, denivele_m=None,
                    longueur_conduite_m=None, diametre_interieur_mm=None,
                    materiau_conduite=None, c_hazen_williams=None,
                    coefficient_frottement=None, pertes_singulieres_m=None,
                    pression_service_bar=None, provenances=None,
                    max_iterations=20, tolerance_m3h=0.05):
    """AGR111 — HMT = niveau dynamique + dénivelé + pertes linéaires
    (Hazen-Williams) + pertes singulières + pression de service × 10,197 m/bar.

    * Niveau dynamique : MESURÉ (``niveau_dynamique_m``), sinon statique +
      rabattement spécifique × débit (donnée d'essai de pompage).
    * Pertes linéaires : Hazen-Williams ; C SAISI, sinon C de la table AGR110
      pour PVC/PEHD ; autre matériau sans C ⇒ pertes ``None`` + alerte
      nommant ``hmt.conduite.c_hazen_williams``. Le chemin
      ``coefficient_frottement`` (CAL156 : coef × L × Q²) reste accepté.
    * Pertes singulières et pression de service : SAISIES, sans défaut.
    * Avec une ``courbe_pompe``, débit et HMT sont ITÉRÉS jusqu'à convergence
      (logique CAL156) ; sinon le calcul se fait au ``debit_m3h`` fourni.

    Composante manquante ⇒ repli sur ``hmt_saisie``, ``source: 'saisie'``
    (jamais une HMT calculée à moitié) ; les composantes connues restent
    servies avec leur provenance. Rend ``{valeur_m, composantes, provenance,
    source, debit_convergence_m3h, iterations, manquantes, alertes}``.
    """
    alertes = []
    c, prov_c = None, None
    if any(v is not None for v in (longueur_conduite_m, diametre_interieur_mm,
                                   materiau_conduite, c_hazen_williams)):
        c, prov_c, alerte_c = _resoudre_c(materiau_conduite, c_hazen_williams)
        if alerte_c and coefficient_frottement is None:
            alertes.append(alerte_c)

    denivele = _flottant(denivele_m)
    singulieres = _flottant(pertes_singulieres_m)
    pression_bar = _flottant(pression_service_bar)
    pression_m = (pression_bar * METRES_PAR_BAR
                  if pression_bar is not None else None)

    debit = _flottant(debit_m3h)
    if debit is None and courbe_pompe:
        points = courbe_pompe.get("debits_m3h") or []
        if points:
            debit = float(points[len(points) // 2])
    if debit is not None and debit <= 0:
        debit = None

    passe = dict(niveau_dynamique_m=niveau_dynamique_m,
                 niveau_statique_m=niveau_statique_m,
                 rabattement_specifique_m_par_m3h=(
                     rabattement_specifique_m_par_m3h),
                 longueur_conduite_m=longueur_conduite_m,
                 diametre_interieur_mm=diametre_interieur_mm, c=c,
                 coefficient_frottement=coefficient_frottement)

    def _total(niv, pts):
        termes = (niv, denivele, pts, singulieres, pression_m)
        return None if any(t is None for t in termes) else sum(termes)

    niveau, niveau_mesure, pertes = _une_passe(debit, **passe)
    hmt = _total(niveau, pertes)
    iterations = 0
    convergence = None
    if hmt is not None and courbe_pompe:
        for iterations in range(1, max_iterations + 1):
            nouveau = debit_a_hmt(courbe_pompe, hmt)
            if nouveau is None:
                break
            if nouveau <= 0:
                convergence = 0.0  # au-delà du point d'arrêt de la pompe
                break
            if abs(nouveau - debit) <= tolerance_m3h:
                convergence = round(nouveau, 2)
                break
            debit = nouveau
            niveau, niveau_mesure, pertes = _une_passe(debit, **passe)
            hmt = _total(niveau, pertes)
            if hmt is None:
                break
        else:
            convergence = round(debit, 2)

    composantes = {
        "niveau_dynamique_m": _arrondi(niveau),
        "denivele_m": _arrondi(denivele),
        "pertes_lineaires_m": _arrondi(pertes),
        "pertes_singulieres_m": _arrondi(singulieres),
        "pression_service_m": _arrondi(pression_m),
    }
    if niveau is None:
        prov_niveau = None
    elif niveau_mesure:
        prov_niveau = _provenance_saisie(provenances, "niveau_dynamique_m")
    else:
        prov_niveau = {"origine": "calculee",
                       "detail": "niveau statique + rabattement spécifique × débit",
                       "date": None}
    provenance = {
        "niveau_dynamique_m": prov_niveau,
        "denivele_m": (None if denivele is None
                       else _provenance_saisie(provenances, "denivele_m")),
        "pertes_lineaires_m": (
            None if pertes is None else
            {"origine": "calculee",
             "detail": ("Hazen-Williams" if c is not None
                        else "coefficient_frottement × L × Q² (CAL156)"),
             "date": None}),
        "c_hazen_williams": prov_c,
        "pertes_singulieres_m": (
            None if singulieres is None
            else _provenance_saisie(provenances, "pertes_singulieres_m")),
        "pression_service_m": (
            None if pression_m is None else
            {"origine": "calculee",
             "detail": "pression de service saisie × 10,197 m/bar",
             "date": None}),
    }
    if hmt is None:
        return {
            "valeur_m": _flottant(hmt_saisie),
            "composantes": composantes,
            "provenance": provenance,
            "source": "saisie",
            "debit_convergence_m3h": None,
            "iterations": iterations,
            "manquantes": [k for k, v in composantes.items() if v is None],
            "alertes": alertes,
        }
    return {
        "valeur_m": round(hmt, 1),
        "composantes": composantes,
        "provenance": provenance,
        "source": "calculee",
        "debit_convergence_m3h": convergence,
        "iterations": iterations,
        "manquantes": [],
        "alertes": alertes,
    }

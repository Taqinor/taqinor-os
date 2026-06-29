"""FG253 — Aide au calcul de charge structure toiture.

Module PUR (aucune écriture base, aucun effet de bord) : estime la surcharge
permanente apportée par une installation PV (kg/m²) et la compare à la capacité
portante admissible selon le TYPE de toiture, avec une ALERTE en cas de
dépassement.

C'est une AIDE à la DÉCISION (catégorie DECISION) — un garde-fou indicatif pour
le dossier technique, PAS une note de calcul de structure réglementaire. Le
message le rappelle ; un bureau d'études reste requis pour la validation finale.

Jamais de prix / marge en sortie ; uniquement des grandeurs physiques (kg, m²).
"""
from __future__ import annotations

# ── Capacités portantes admissibles indicatives par type de toiture ───────────
# Surcharge permanente ADDITIONNELLE tolérable (kg/m²) au-delà du poids propre
# déjà existant. Valeurs PRUDENTES / indicatives marché Maroc, à confirmer par
# un bureau d'études. La clé est un type normalisé ; libellé FR + capacité.
ROOF_TYPES = {
    "tole_bac_acier": {
        "label": "Tôle / bac acier (sur pannes)",
        "capacite_kg_m2": 15.0,
        "note": "Charpente légère : vérifier l'entraxe des pannes.",
    },
    "fibrociment": {
        "label": "Fibrociment / plaques ondulées",
        "capacite_kg_m2": 10.0,
        "note": "Support fragile : prévoir des chemins de circulation.",
    },
    "dalle_beton": {
        "label": "Dalle béton (terrasse)",
        "capacite_kg_m2": 120.0,
        "note": "Forte capacité ; vérifier l'étanchéité et le lestage.",
    },
    "tuiles": {
        "label": "Tuiles (charpente bois)",
        "capacite_kg_m2": 25.0,
        "note": "Crochets sur chevrons : contrôler l'état de la charpente.",
    },
    "ombriere": {
        "label": "Ombrière / structure dédiée",
        "capacite_kg_m2": 30.0,
        "note": "Structure dimensionnée pour le PV.",
    },
    "autre": {
        "label": "Autre / inconnu",
        "capacite_kg_m2": 15.0,
        "note": "Capacité par défaut prudente — à confirmer.",
    },
}

DEFAULT_ROOF_TYPE = "autre"

# Poids surfacique d'un module PV posé, structure de fixation INCLUSE (kg/m²).
# Un module verre-tôle pèse ~12 kg pour ~2,2 m² ≈ 5,5 kg/m² ; on ajoute rails +
# fixations (~3,5 kg/m²) → ~9 kg/m² par défaut, surchargeable.
DEFAULT_MODULE_KG_M2 = 9.0

# Coefficient de sécurité appliqué à la charge estimée avant comparaison.
SAFETY_FACTOR = 1.1


def _f(value, default=0.0):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if v >= 0 else default


def list_roof_types():
    """Liste des types de toiture supportés (pour un menu déroulant front)."""
    return [
        {"key": k, "label": v["label"],
         "capacite_kg_m2": v["capacite_kg_m2"], "note": v["note"]}
        for k, v in ROOF_TYPES.items()
    ]


def compute_roof_load(*, roof_type=DEFAULT_ROOF_TYPE,
                      n_modules=0,
                      poids_module_kg=None,
                      surface_module_m2=2.2,
                      module_kg_m2=None,
                      surface_toiture_m2=None,
                      capacite_kg_m2=None):
    """FG253 — surcharge PV (kg/m²) vs capacité du type de toiture + alerte.

    Deux façons d'estimer la surcharge surfacique :

    * Si ``module_kg_m2`` est fourni → c'est la charge surfacique directe du
      champ PV (modules + fixations).
    * Sinon, on déduit la charge surfacique à partir du POIDS d'un module et de
      sa SURFACE (``poids_module_kg`` / ``surface_module_m2``). À défaut de
      poids module, on retombe sur ``DEFAULT_MODULE_KG_M2``.

    ``surface_toiture_m2`` (si fournie) sert à calculer la charge TOTALE (kg) et
    n'a pas d'effet sur la comparaison surfacique. ``capacite_kg_m2`` force la
    capacité admissible (sinon dérivée du type).

    Retourne un dict JSON-sérialisable :
      {roof_type, roof_label, charge_pv_kg_m2, charge_majoree_kg_m2,
       capacite_kg_m2, marge_kg_m2, ratio, depassement (bool),
       severite ('ok'|'attention'|'depassement'), charge_totale_kg,
       message, note, avertissement}
    Jamais d'exception sur entrée incomplète ; jamais de prix.
    """
    rt = roof_type if roof_type in ROOF_TYPES else DEFAULT_ROOF_TYPE
    spec = ROOF_TYPES[rt]

    cap = _f(capacite_kg_m2, 0.0) or float(spec["capacite_kg_m2"])

    # Charge surfacique du champ PV (kg/m²).
    if module_kg_m2 is not None:
        charge = _f(module_kg_m2, DEFAULT_MODULE_KG_M2)
    elif poids_module_kg is not None:
        surf = _f(surface_module_m2, 2.2) or 2.2
        charge = _f(poids_module_kg, 0.0) / surf
    else:
        charge = DEFAULT_MODULE_KG_M2

    charge_majoree = round(charge * SAFETY_FACTOR, 2)
    marge = round(cap - charge_majoree, 2)
    ratio = round(charge_majoree / cap, 3) if cap > 0 else None
    depassement = cap > 0 and charge_majoree > cap

    n = max(0, int(_f(n_modules, 0)))
    surf_toit = _f(surface_toiture_m2, 0.0)
    if surf_toit > 0:
        charge_totale = round(charge * surf_toit, 1)
    elif n > 0:
        surf = _f(surface_module_m2, 2.2) or 2.2
        charge_totale = round(charge * n * surf, 1)
    else:
        charge_totale = None

    if depassement:
        severite = "depassement"
        message = (
            f"Dépassement : la surcharge PV estimée "
            f"({charge_majoree} kg/m²) dépasse la capacité admissible "
            f"indicative ({cap} kg/m²) pour « {spec['label']} ». "
            f"Renforcement structurel ou étude bureau d'études requis.")
    elif cap > 0 and charge_majoree > cap * 0.8:
        severite = "attention"
        message = (
            f"À surveiller : la surcharge PV ({charge_majoree} kg/m²) "
            f"approche la capacité admissible ({cap} kg/m²) pour "
            f"« {spec['label']} ». Validation bureau d'études conseillée.")
    else:
        severite = "ok"
        message = (
            f"OK (indicatif) : surcharge PV {charge_majoree} kg/m² sous la "
            f"capacité admissible {cap} kg/m² pour « {spec['label']} ».")

    return {
        "roof_type": rt,
        "roof_label": spec["label"],
        "charge_pv_kg_m2": round(charge, 2),
        "charge_majoree_kg_m2": charge_majoree,
        "capacite_kg_m2": round(cap, 2),
        "marge_kg_m2": marge,
        "ratio": ratio,
        "depassement": depassement,
        "severite": severite,
        "charge_totale_kg": charge_totale,
        "facteur_securite": SAFETY_FACTOR,
        "message": message,
        "note": spec["note"],
        "avertissement": (
            "Estimation indicative — ne remplace pas une note de calcul "
            "de structure. La validation par un bureau d'études reste "
            "requise."),
    }

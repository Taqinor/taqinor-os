"""FG246 / FG247 / FG249 — Calculs d'ingénierie solaire (conception électrique).

Module PUR (aucune écriture base, aucun effet de bord) regroupant trois
calculateurs réutilisés par l'écran de devis et, à terme, le pont toiture 3D :

* ``string_design`` (FG246) — répartit N panneaux sur les entrées MPPT d'un
  onduleur, vérifie Vmp/Voc des chaînes à FROID contre la fenêtre de tension
  onduleur, et rapporte le ratio DC/AC.
* ``match_inverter`` (FG247) — propose l'onduleur compatible du catalogue pour
  une configuration panneaux donnée, en gardant les mots-clés de classification
  ALIGNÉS sur ``quote_engine/builder.py`` (réseau/injection, hybride, batterie,
  panneau).
* ``optimize_orientation`` (FG249) — balaie inclinaison/azimut autour du site
  via l'intégration PVGIS EXISTANTE (``apps.parametres.pvgis``) pour retourner
  l'orientation optimale ; repli gracieux hors-ligne (la fonction PVGIS retombe
  déjà sur l'hypothèse manuelle, jamais d'exception réseau).

CONTRAINTES :
* Les onduleurs/panneaux du catalogue (``stock.Produit``) ne portent PAS de
  fiche électrique complète (Voc/Vmp/Vmppt/Vmax). On utilise donc des
  paramètres électriques par défaut SENSÉS (silicium cristallin) avec repli sûr,
  en extrayant du nom produit ce qui est extractible (puissance W, kW onduleur).
* Aucun prix d'achat / marge n'apparaît jamais dans une sortie — ce module ne
  manipule que des grandeurs électriques publiques.
* Aucune dépendance pip nouvelle ; PVGIS via le client stdlib existant.
"""
from __future__ import annotations

import math
import re

# ── Paramètres électriques par défaut (module silicium cristallin) ────────────
# Valeurs marché conservatrices pour un panneau PV mono/poly courant. Tout est
# surchargeable par l'appelant via le dict ``module``.
#
# * ``vmp`` / ``voc`` aux conditions STC (25 °C) — référence d'un panneau ~60–72
#   cellules. À défaut de fiche produit, on s'appuie sur ces valeurs et le
#   coefficient de température pour borner la fenêtre.
# * ``temp_coeff_voc`` : coefficient de température du Voc (%/°C), négatif :
#   le Voc MONTE quand il fait FROID (cas dimensionnant pour la borne haute).
DEFAULT_MODULE = {
    "vmp": 34.0,           # tension au point de puissance max (V), STC
    "voc": 41.0,           # tension circuit ouvert (V), STC
    "temp_coeff_voc": -0.27,   # %/°C (négatif)
    "temp_coeff_vmp": -0.35,   # %/°C (négatif) — Vmp chute plus vite
    "puissance_w": 450,    # puissance crête (W) — repli si non lisible du nom
}

# Fenêtre onduleur par défaut (onduleur string résidentiel/commercial typique).
# Surchargeable via ``inverter``.
DEFAULT_INVERTER_WINDOW = {
    "v_min": 90.0,       # tension de démarrage / minimale DC (V)
    "v_max": 600.0,      # tension DC max absolue (V) — ne JAMAIS dépasser
    "v_mppt_min": 120.0,  # bas de la plage MPPT (V)
    "v_mppt_max": 500.0,  # haut de la plage MPPT (V)
    "n_mppt": 2,         # nombre d'entrées MPPT
    "ac_kw": None,       # puissance AC nominale (kW) — pour le ratio DC/AC
}

# Conditions de température de référence pour le calcul à froid / à chaud.
STC_TEMP_C = 25.0          # conditions standard (Voc/Vmp donnés à 25 °C)
DEFAULT_COLD_TEMP_C = -5.0   # température cellule mini de dimensionnement (hiver Maroc montagne)
DEFAULT_HOT_TEMP_C = 70.0    # température cellule maxi (été, module chaud)

# Ratio DC/AC maximal toléré pour considérer un onduleur « assez gros ».
MAX_DC_AC = 1.35

_WATT_RE = re.compile(r"(\d{3,4})\s*(?:wc|w)\b", re.IGNORECASE)
_KW_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:kw|kva)\b", re.IGNORECASE)
_KWH_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*kwh\b", re.IGNORECASE)


def parse_watt(text: str):
    """Puissance panneau (W) lue dans un nom/désignation, sinon None."""
    m = _WATT_RE.search(text or "")
    return int(m.group(1)) if m else None


def parse_kw(text: str):
    """Puissance (kW/kVA) lue dans un nom — exclut d'abord les « kWh »."""
    cleaned = _KWH_RE.sub(" ", text or "")
    m = _KW_RE.search(cleaned)
    return float(m.group(1).replace(",", ".")) if m else None


# ── Classification ALIGNÉE sur quote_engine/builder.py (mots-clés identiques) ──
def is_panel(designation: str, produit_nom: str = "") -> bool:
    blob = f"{designation} {produit_nom}".lower()
    return "panneau" in blob or "panneaux" in blob


def is_battery(designation: str) -> bool:
    return "batterie" in (designation or "").lower()


def is_hybrid_inverter(designation: str) -> bool:
    d = (designation or "").lower()
    return "onduleur" in d and "hybride" in d


def is_reseau_inverter(designation: str) -> bool:
    d = (designation or "").lower()
    return "onduleur" in d and (
        "réseau" in d or "reseau" in d or "injection" in d)


def is_any_inverter(designation: str) -> bool:
    return is_hybrid_inverter(designation) or is_reseau_inverter(designation)


def _as_kw(value):
    try:
        v = float(value)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


# ═════════════════════════════════════════════════════════════════════════════
# FG246 — Calcul de chaînes (string design) & vérification du ratio DC/AC
# ═════════════════════════════════════════════════════════════════════════════
def _voltage_at_temp(v_stc: float, temp_coeff_pct_per_c: float,
                     cell_temp_c: float) -> float:
    """Tension à ``cell_temp_c`` à partir d'une tension STC (25 °C).

    ``temp_coeff_pct_per_c`` est en %/°C (négatif). À FROID (temp < 25 °C) la
    tension MONTE (coeff négatif × écart négatif = positif).
    """
    delta = cell_temp_c - STC_TEMP_C
    return v_stc * (1.0 + (temp_coeff_pct_per_c / 100.0) * delta)


def string_design(n_panels, module=None, inverter=None,
                  cold_temp_c=DEFAULT_COLD_TEMP_C,
                  hot_temp_c=DEFAULT_HOT_TEMP_C):
    """FG246 — répartit ``n_panels`` panneaux sur les MPPT et vérifie la fenêtre.

    Distribue les panneaux en chaînes série équilibrées sur les ``n_mppt``
    entrées de l'onduleur, choisit une longueur de chaîne qui respecte les
    bornes de tension, puis VÉRIFIE :

    * Voc de la chaîne à FROID (``cold_temp_c``) ≤ ``v_max`` (sécurité absolue).
    * Vmp de la chaîne à FROID dans la plage MPPT haute (``v_mppt_max``).
    * Vmp de la chaîne à CHAUD (``hot_temp_c``) ≥ ``v_mppt_min`` (démarrage MPPT).
    * Vmp à chaud ≥ ``v_min`` (démarrage onduleur).

    Et rapporte le ratio DC/AC (puissance crête DC ÷ puissance AC onduleur).

    Paramètres
    ----------
    n_panels : nombre total de panneaux.
    module : dict de paramètres électriques module (défaut ``DEFAULT_MODULE``).
    inverter : dict de fenêtre onduleur (défaut ``DEFAULT_INVERTER_WINDOW``).
    cold_temp_c / hot_temp_c : températures cellule de dimensionnement (°C).

    Retourne un dict JSON-sérialisable ``{n_panels, n_mppt, strings,
    panels_per_string, dc_kw, ac_kw, dc_ac_ratio, voltages{...}, checks{...},
    ok, warnings[]}``. Ne lève jamais sur des entrées dégradées : sur 0 panneau,
    retourne une structure vide cohérente.
    """
    mod = {**DEFAULT_MODULE, **(module or {})}
    inv = {**DEFAULT_INVERTER_WINDOW, **(inverter or {})}

    try:
        n = int(n_panels)
    except (TypeError, ValueError):
        n = 0
    n_mppt = max(1, int(inv.get("n_mppt") or 1))

    warnings = []

    vmp_stc = float(mod["vmp"])
    voc_stc = float(mod["voc"])
    panel_w = float(mod.get("puissance_w") or DEFAULT_MODULE["puissance_w"])

    v_max = float(inv["v_max"])
    v_min = float(inv["v_min"])
    v_mppt_min = float(inv["v_mppt_min"])
    v_mppt_max = float(inv["v_mppt_max"])

    # Tensions unitaires aux températures de dimensionnement.
    voc_cold = _voltage_at_temp(voc_stc, mod["temp_coeff_voc"], cold_temp_c)
    vmp_cold = _voltage_at_temp(vmp_stc, mod["temp_coeff_vmp"], cold_temp_c)
    vmp_hot = _voltage_at_temp(vmp_stc, mod["temp_coeff_vmp"], hot_temp_c)

    if n <= 0:
        return {
            "n_panels": 0, "n_mppt": n_mppt, "strings": 0,
            "panels_per_string": 0, "string_layout": [],
            "dc_kw": 0.0, "ac_kw": _as_kw(inv.get("ac_kw")),
            "dc_ac_ratio": None,
            "voltages": {}, "checks": {}, "ok": False,
            "warnings": ["aucun panneau à répartir"],
        }

    # ── Longueur de chaîne admissible (bornée par le Voc à froid) ──
    # Max modules avant de dépasser v_max au Voc froid (sécurité absolue).
    max_by_voc = int(math.floor(v_max / voc_cold)) if voc_cold > 0 else n
    # Max modules avant de dépasser le haut de la plage MPPT au Vmp froid.
    max_by_mppt = int(math.floor(v_mppt_max / vmp_cold)) if vmp_cold > 0 else n
    # Min modules pour démarrer le MPPT au Vmp chaud (le pire cas bas).
    min_by_mppt = int(math.ceil(v_mppt_min / vmp_hot)) if vmp_hot > 0 else 1
    min_by_start = int(math.ceil(v_min / vmp_hot)) if vmp_hot > 0 else 1
    min_len = max(1, min_by_mppt, min_by_start)
    max_len = max(1, min(max_by_voc, max_by_mppt))

    window_too_narrow = False
    if max_len < min_len:
        window_too_narrow = True
        warnings.append(
            "fenêtre de tension trop étroite pour ce module : aucune longueur "
            "de chaîne ne respecte à la fois la borne haute (froid) et le "
            "démarrage MPPT (chaud) — vérifier le couple module/onduleur")
        # On garde quand même une répartition « best effort » bornée par v_max.
        max_len = max(1, max_by_voc)
        min_len = 1

    # ── Répartition équilibrée sur les MPPT ──
    # On vise une longueur de chaîne qui partitionne n en chaînes ÉGALES sur les
    # entrées MPPT, dans [min_len, max_len], la plus longue possible.
    panels_per_string, strings = _choose_string_layout(
        n, n_mppt, min_len, max_len)

    uneven = False
    if panels_per_string == 0:
        # Aucun découpage propre — repli : chaînes de longueur bornée.
        uneven = True
        panels_per_string = min(n, max_len)
        strings = int(math.ceil(n / panels_per_string))
        warnings.append(
            "répartition non homogène : les chaînes ne sont pas toutes de "
            "longueur égale (vérifier la conception)")

    # Disposition réelle des chaînes par MPPT (équilibrée).
    string_layout = _distribute_strings(strings, n_mppt)

    # ── Tensions au niveau CHAÎNE ──
    string_voc_cold = round(voc_cold * panels_per_string, 1)
    string_vmp_cold = round(vmp_cold * panels_per_string, 1)
    string_vmp_hot = round(vmp_hot * panels_per_string, 1)
    string_vmp_stc = round(vmp_stc * panels_per_string, 1)

    # ── Vérifications ──
    checks = {
        # Sécurité absolue : Voc froid sous le V_max DC.
        "voc_cold_under_vmax": string_voc_cold <= v_max,
        # Vmp froid sous le haut de plage MPPT.
        "vmp_cold_under_mppt_max": string_vmp_cold <= v_mppt_max,
        # Vmp chaud au-dessus du bas de plage MPPT.
        "vmp_hot_over_mppt_min": string_vmp_hot >= v_mppt_min,
        # Vmp chaud au-dessus du démarrage onduleur.
        "vmp_hot_over_vmin": string_vmp_hot >= v_min,
    }
    if not checks["voc_cold_under_vmax"]:
        warnings.append(
            f"Voc à froid {string_voc_cold} V > V_max onduleur {v_max} V — "
            "chaîne trop longue, RISQUE matériel (réduire le nombre de modules "
            "par chaîne)")
    if not checks["vmp_cold_under_mppt_max"]:
        warnings.append(
            f"Vmp à froid {string_vmp_cold} V > haut de plage MPPT {v_mppt_max} "
            "V — l'onduleur écrête, perte de production")
    if not checks["vmp_hot_over_mppt_min"]:
        warnings.append(
            f"Vmp à chaud {string_vmp_hot} V < bas de plage MPPT {v_mppt_min} V "
            "— chaîne trop courte, MPPT hors plage en été")
    if not checks["vmp_hot_over_vmin"]:
        warnings.append(
            f"Vmp à chaud {string_vmp_hot} V < démarrage onduleur {v_min} V")

    # ── Ratio DC/AC ──
    dc_kw = round(n * panel_w / 1000.0, 3)
    ac_kw = _as_kw(inv.get("ac_kw"))
    dc_ac_ratio = round(dc_kw / ac_kw, 3) if ac_kw and ac_kw > 0 else None
    if dc_ac_ratio is not None:
        if dc_ac_ratio > 1.5:
            warnings.append(
                f"ratio DC/AC {dc_ac_ratio} élevé (> 1.5) — surdimensionnement "
                "DC important, écrêtage probable")
        elif dc_ac_ratio < 1.0:
            warnings.append(
                f"ratio DC/AC {dc_ac_ratio} faible (< 1.0) — onduleur "
                "surdimensionné par rapport au champ PV")

    ok = all(checks.values()) and not uneven and not window_too_narrow

    return {
        "n_panels": n,
        "n_mppt": n_mppt,
        "strings": strings,
        "panels_per_string": panels_per_string,
        "string_layout": string_layout,
        "dc_kw": dc_kw,
        "ac_kw": ac_kw,
        "dc_ac_ratio": dc_ac_ratio,
        "voltages": {
            "voc_cold": string_voc_cold,
            "vmp_cold": string_vmp_cold,
            "vmp_hot": string_vmp_hot,
            "vmp_stc": string_vmp_stc,
            "cold_temp_c": cold_temp_c,
            "hot_temp_c": hot_temp_c,
        },
        "checks": checks,
        "ok": ok,
        "warnings": warnings,
    }


def _choose_string_layout(n, n_mppt, min_len, max_len):
    """Choisit (panels_per_string, strings) : chaînes ÉGALES, longueur valide.

    Cherche une partition de ``n`` en chaînes ÉGALES telle que la longueur de
    chaîne ∈ [min_len, max_len], en privilégiant un usage équilibré des entrées
    MPPT (nombre de chaînes multiple de n_mppt) puis les chaînes les plus
    longues (moins de câblage). Renvoie ``(0, 0)`` si aucune partition égale
    n'existe.
    """
    best = (0, 0)
    best_score = None
    # On essaie tous les nombres de chaînes de 1 à n.
    for strings in range(1, n + 1):
        if n % strings != 0:
            continue
        length = n // strings
        if length < min_len or length > max_len:
            continue
        # Score : préférer un nombre de chaînes multiple de n_mppt (réparti
        # également), puis les chaînes les plus longues (moins de câblage).
        balanced = 0 if strings % n_mppt == 0 else 1
        score = (balanced, -length)
        if best_score is None or score < best_score:
            best_score = score
            best = (length, strings)
    return best


def _distribute_strings(strings, n_mppt):
    """Répartit ``strings`` chaînes sur ``n_mppt`` entrées, le plus égal possible.

    Renvoie une liste de longueur ``n_mppt`` : nombre de chaînes par MPPT.
    """
    base = strings // n_mppt
    extra = strings % n_mppt
    return [base + (1 if i < extra else 0) for i in range(n_mppt)]


# ═════════════════════════════════════════════════════════════════════════════
# FG247 — Appariement module–onduleur depuis le catalogue
# ═════════════════════════════════════════════════════════════════════════════
def match_inverter(produits, *, n_panels, panel_w=None, hybrid=False,
                   module=None, inverter_window=None,
                   cold_temp_c=DEFAULT_COLD_TEMP_C,
                   hot_temp_c=DEFAULT_HOT_TEMP_C):
    """FG247 — propose l'onduleur catalogue compatible pour une config panneaux.

    Parcourt ``produits`` (itérable de ``stock.Produit``), retient les onduleurs
    de la bonne FAMILLE — hybride si ``hybrid`` sinon réseau/injection, mots-clés
    ALIGNÉS sur ``builder.py`` — puis choisit le plus petit onduleur (kW) dont :

    * la puissance AC supporte un ratio DC/AC raisonnable (≤ ``MAX_DC_AC``) ;
    * la fenêtre de tension accepte au moins une longueur de chaîne valide pour
      le module (réutilise ``string_design`` pour la vérif Vmp/Voc à froid).

    Le nom du produit fournit la puissance kW (``parse_kw``) ; faute de fiche
    électrique au catalogue, la fenêtre onduleur reste celle par défaut
    (surchargeable via ``inverter_window``). Aucun prix d'achat n'est lu.

    Retourne un dict ``{inverter, ac_kw, dc_kw, dc_ac_ratio, string_design,
    compatible, candidates_considered, reason}`` ; ``inverter`` est le
    ``Produit`` choisi (ou None si aucun ne convient).
    """
    mod = {**DEFAULT_MODULE, **(module or {})}
    if panel_w:
        try:
            mod["puissance_w"] = float(panel_w)
        except (TypeError, ValueError):
            pass

    try:
        n = int(n_panels)
    except (TypeError, ValueError):
        n = 0

    dc_kw = round(n * float(mod["puissance_w"]) / 1000.0, 3)

    family_pred = is_hybrid_inverter if hybrid else is_reseau_inverter
    # Candidats : bonne famille, puissance lisible, prix de vente réel (jamais
    # un produit « prix à renseigner » — même garde que l'auto-fill).
    candidates = []
    for p in produits:
        nom = getattr(p, "nom", "") or ""
        if not family_pred(nom):
            continue
        kw = parse_kw(nom)
        if kw is None or kw <= 0:
            continue
        prix = getattr(p, "prix_vente", None)
        try:
            priced = prix is not None and float(prix) > 0
        except (TypeError, ValueError):
            priced = False
        if not priced:
            continue
        candidates.append((p, kw))

    # Tri : plus petite puissance d'abord (puis id stable).
    candidates.sort(key=lambda x: (x[1], getattr(x[0], "id", 0) or 0))

    considered = len(candidates)
    chosen = None
    chosen_kw = None
    chosen_design = None
    chosen_ratio = None
    reason = ""

    for p, kw in candidates:
        ratio = (dc_kw / kw) if kw > 0 else None
        # Onduleur trop petit pour le champ (ratio DC/AC excessif) → suivant.
        if ratio is not None and ratio > MAX_DC_AC:
            continue
        window = {**DEFAULT_INVERTER_WINDOW, **(inverter_window or {}),
                  "ac_kw": kw}
        design = string_design(
            n, module=mod, inverter=window,
            cold_temp_c=cold_temp_c, hot_temp_c=hot_temp_c)
        if design["ok"]:
            chosen, chosen_kw = p, kw
            chosen_design, chosen_ratio = design, design["dc_ac_ratio"]
            reason = ("onduleur le plus petit respectant ratio DC/AC et "
                      "fenêtre de tension")
            break

    if chosen is None and candidates:
        # Aucun candidat parfait : on retient le plus gros (meilleur ratio) en
        # le signalant, plutôt que de ne rien proposer.
        p, kw = candidates[-1]
        window = {**DEFAULT_INVERTER_WINDOW, **(inverter_window or {}),
                  "ac_kw": kw}
        chosen_design = string_design(
            n, module=mod, inverter=window,
            cold_temp_c=cold_temp_c, hot_temp_c=hot_temp_c)
        chosen, chosen_kw = p, kw
        chosen_ratio = chosen_design["dc_ac_ratio"]
        reason = ("aucun onduleur catalogue parfaitement compatible — plus "
                  "grosse puissance retenue, vérifier la conception")

    if chosen is None:
        reason = ("aucun onduleur "
                  + ("hybride" if hybrid else "réseau/injection")
                  + " chiffrable au catalogue pour cette configuration")

    return {
        "inverter": chosen,
        "ac_kw": chosen_kw,
        "dc_kw": dc_kw,
        "dc_ac_ratio": chosen_ratio,
        "string_design": chosen_design,
        "compatible": bool(chosen_design and chosen_design.get("ok")),
        "candidates_considered": considered,
        "reason": reason,
    }


# ═════════════════════════════════════════════════════════════════════════════
# FG249 — Optimisation inclinaison / azimut (balayage via PVGIS existant)
# ═════════════════════════════════════════════════════════════════════════════
# Convention d'azimut founder (= PVGIS aspect) : Sud 0 / Est −90 / Ouest +90.
DEFAULT_TILT_RANGE = (0, 60, 5)        # (min, max, pas) en degrés
DEFAULT_AZIMUTH_RANGE = (-90, 90, 15)  # (min, max, pas), Sud=0


def _frange(start, stop, step):
    """Plage inclusive d'entiers de ``start`` à ``stop`` par pas ``step``."""
    if step <= 0:
        return [int(start)]
    vals = []
    v = int(start)
    while v <= int(stop):
        vals.append(v)
        v += int(step)
    if vals and vals[-1] != int(stop):
        vals.append(int(stop))
    return vals


def optimize_orientation(settings, lat, lon, *, peakpower_kwc=1.0,
                         tilt_range=DEFAULT_TILT_RANGE,
                         azimuth_range=DEFAULT_AZIMUTH_RANGE,
                         fetch=None):
    """FG249 — balaie (inclinaison, azimut) → orientation au productible maximal.

    Réutilise l'intégration PVGIS EXISTANTE
    (``apps.parametres.pvgis.fetch_productible``, injectable via ``fetch`` pour
    les tests) : pour chaque couple (tilt, azimuth) de la grille, on demande le
    productible (kWh/kWc/an) et on retient le maximum. La fonction PVGIS retombe
    déjà sur l'hypothèse manuelle hors-ligne (jamais d'exception réseau), donc ce
    balayage fonctionne aussi sans réseau (toutes les cases renvoient alors la
    même valeur manuelle → l'orientation par défaut société est retenue).

    Paramètres
    ----------
    settings : ``TariffSettings`` (défauts inclinaison/azimut + repli manuel).
    lat, lon : coordonnées GPS du site.
    peakpower_kwc : puissance crête pour la requête (1 → kWh/kWc/an direct).
    tilt_range / azimuth_range : ``(min, max, pas)`` en degrés.
    fetch : surcharge de ``fetch_productible`` (signature identique) — pour les
        tests, on injecte un stub qui ne touche pas le réseau.

    Retourne ``{best{tilt, azimuth, productible_kwh_kwc, source}, grid[...],
    evaluated, source, default_orientation{tilt, azimuth}, gain_vs_default_pct}``.
    Ne lève jamais sur PVGIS indisponible.
    """
    if fetch is None:
        from apps.parametres.pvgis import fetch_productible as fetch

    tilts = _frange(*tilt_range)
    azimuths = _frange(*azimuth_range)

    default_tilt = int(getattr(settings, "inclinaison_defaut_deg", 30) or 30)
    default_azimuth = int(getattr(settings, "azimut_defaut_deg", 0) or 0)

    grid = []
    best = None
    default_prod = None
    any_pvgis = False

    for tilt in tilts:
        for az in azimuths:
            res = fetch(settings, lat, lon, peakpower_kwc=peakpower_kwc,
                        tilt=tilt, azimuth=az)
            prod = res.get("productible_kwh_kwc")
            src = res.get("source")
            if src == "pvgis":
                any_pvgis = True
            cell = {
                "tilt": tilt, "azimuth": az,
                "productible_kwh_kwc": prod, "source": src,
            }
            grid.append(cell)
            if prod is not None and (
                    best is None or prod > best["productible_kwh_kwc"]):
                best = cell
            if tilt == default_tilt and az == default_azimuth and prod is not None:
                default_prod = prod

    # Productible à l'orientation par défaut société : on l'interroge à part
    # s'il n'est pas tombé sur une case de la grille (gain de référence).
    if default_prod is None:
        res = fetch(settings, lat, lon, peakpower_kwc=peakpower_kwc,
                    tilt=default_tilt, azimuth=default_azimuth)
        default_prod = res.get("productible_kwh_kwc")
        if res.get("source") == "pvgis":
            any_pvgis = True

    gain_pct = None
    if best and default_prod and default_prod > 0:
        gain_pct = round(
            (best["productible_kwh_kwc"] - default_prod) / default_prod * 100, 1)

    return {
        "best": best,
        "grid": grid,
        "evaluated": len(grid),
        "source": "pvgis" if any_pvgis else "manual",
        "default_orientation": {
            "tilt": default_tilt, "azimuth": default_azimuth,
            "productible_kwh_kwc": default_prod,
        },
        "gain_vs_default_pct": gain_pct,
    }

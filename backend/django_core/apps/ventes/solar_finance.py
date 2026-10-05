"""SPL260 — tarifs et finance du moteur solaire (déplacés de ``solar_design.py``).

Tranches time-of-use (CALX274/275), économie net-metering (FG259),
mécanisme de compensation du surplus (CALX276), escalade tarifaire + VAN/TRI
(FG260, CALX279), dégradation des modules (FG262) et modèle PPA (FG263).
Module pur : bibliothèque standard + ``apps.parametres.tariff`` (fondation,
ni Django ni modèle) + les helpers FEUILLES de ``solar_base`` ; il n'importe
jamais ``solar_design`` en retour (``compare_scenarios`` y importe
``tariff_escalation_projection``, seule arête retour).

Déplacement « move only » : corps, docstrings, constantes et littéraux sont
OCTET-IDENTIQUES — prouvé par ``tests/test_split_devis_solar.py`` (golden
``split_sd_finance`` + digests de comportement).
"""
from __future__ import annotations

from apps.ventes.solar_base import (
    _coerce_series,
    _hypothese,
    _omission,
    _source_defaut,
    _taux_ou_none,
)

# CALX274 — le motif « aucun tarif horaire saisi » a UNE rédaction, celle du
# service tarifaire de la FONDATION ``apps.parametres`` (module pur : stdlib
# seulement, ni Django ni modèle — l'import de tête reste sûr, comme ci-dessus).
from apps.parametres.tariff import MOTIF_TOU_NON_SAISI as _MOTIF_TOU_NON_SAISI
from apps.parametres.tariff import saison_du_mois as _saison_du_mois
from apps.parametres.tariff import (  # CALX276 — une rédaction, une liste
    MECANISMES_COMPENSATION,
    MOTIF_MECANISME_NON_SAISI,
    MOTIF_TARIF_RACHAT_ABSENT,
)
from apps.parametres.tariff import (  # CALX279
    MENTION_INDEXATION_NON_SAISIE as _MENTION_INDEXATION_NON_SAISIE,
)


# ── FG259 — Économie net-metering / injection surplus (loi 13-09, MT/HT) ──────
# Valorise le SURPLUS solaire INJECTÉ au réseau (issu de FG258 :
# production − autoconsommation, heure par heure) selon la règle de
# compensation marocaine (loi 13-09, moyenne/haute tension) et un tarif
# TIME-OF-USE par tranche horaire (pointe / pleine / creuse).
#
# RÈGLE DE COMPENSATION (net-metering 13-09, modèle transparent) :
#   * L'énergie INJECTÉE pendant une tranche n'est COMPENSÉE qu'à hauteur de
#     l'énergie SOUTIRÉE (importée du réseau) dans la même tranche — c'est le
#     principe du « net » : on solde les flux d'une même période tarifaire.
#     Au-delà, le surplus est « excédentaire » (spill) : par défaut NON
#     valorisé (la loi 13-09 ne rémunère pas l'excédent au MT), valorisable à
#     un tarif résiduel facultatif ``spill_tariff`` si l'appelant le fournit.
#   * Le surplus compensé est valorisé au TARIF de sa propre tranche (il efface
#     un kWh qui aurait été facturé à ce tarif-là).
#   * Un PLAFOND annuel global facultatif (``annual_cap_kwh``) borne l'énergie
#     totale compensée (certains contrats limitent la compensation à un % de la
#     conso annuelle) ; il s'applique sur l'énergie déjà éligible, tranche par
#     tranche, des plus chères aux moins chères (maximise l'économie client).
#   * Le réglage existant ``surplus_injecte_compense`` (toggle) : OFF →
#     l'injection n'est PAS compensée du tout → économie 0 (et tout le surplus
#     bascule en « non compensé »).
#
# Module PUR : aucune base, aucun réseau, aucun prix d'achat/marge. Les entrées
# numériques ne sont JAMAIS rejetées (liberté de saisie du founder) — les
# valeurs illisibles/négatives sont ramenées à 0, jamais d'exception, division
# par zéro bornée.

# ── Tranches time-of-use ONEE par défaut (MT général, ordre des heures) ───────
# Affectation heure-de-journée → tranche (24 valeurs, index 0 = 00 h … 23 h).
# Modèle marché courant : creuse la nuit, pleine en journée, pointe le soir
# (18 h–22 h, le pic de demande nationale). Surchargeable via ``hour_tranches``.
DEFAULT_HOUR_TRANCHES = [
    "creuse", "creuse", "creuse", "creuse", "creuse", "creuse",  # 00–05 h
    "creuse", "pleine", "pleine", "pleine", "pleine", "pleine",  # 06–11 h
    "pleine", "pleine", "pleine", "pleine", "pleine", "pleine",  # 12–17 h
    "pointe", "pointe", "pointe", "pointe", "pleine", "creuse",  # 18–23 h
]

# CALX274 — PLUS AUCUN TARIF PAR TRANCHE PAR DÉFAUT. Les anciens 1,45 / 1,15 /
# 0,85 MAD/kWh (``DEFAULT_TRANCHE_TARIFFS``, commentés « à CONFIRMER par le
# founder selon le contrat ONEE réel ») n'avaient aucune source et étaient
# appliqués dès qu'un appelant ne passait rien. Les tarifs par tranche sont
# désormais SAISIS par la société (``apps.parametres.selectors.tou_pour``) ;
# sans eux, ``net_metering_savings`` publie ``economie: None`` + ``motif``.
#: Motif publié quand aucun tarif par tranche n'est fourni — il NOMME le
#: réglage société à renseigner. UNE seule rédaction, celle de
#: ``apps.parametres.tariff`` (module pur, app de fondation : l'import ne tire
#: pas Django — ce module reste importable sans configuration).
MOTIF_TARIFS_TOU_ABSENTS = _MOTIF_TOU_NON_SAISI

# Ordre canonique des tranches (du plus cher au moins cher) pour l'allocation
# du plafond annuel : on compense d'abord les kWh les plus chers.
_TRANCHE_ORDER = ["pointe", "pleine", "creuse"]

# ── CALX275 — tranches horaires PAR SAISON ───────────────────────────────────
# Une grille saisie peut porter un découpage par saison ``{saison: [24]}``
# (saisons ``apps.parametres.tariff.SAISONS_TOU``, mois = trimestres
# météorologiques ``MOIS_PAR_SAISON_TOU``). L'heure d'un mois prend le
# découpage de SA saison ; à défaut celui d'``annuel`` ; à défaut elle est
# publiée ``tranche: None`` avec son motif — jamais « pleine » par défaut.

#: Jours par mois d'une année non bissextile (8 760 h) — calendrier civil.
_JOURS_PAR_MOIS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _libelle_heure(valeur):
    """Libellé de tranche normalisé (minuscule), ou ``None`` s'il est vide."""
    texte = str(valeur).strip().lower() if valeur is not None else ""
    return texte or None


def tranches_du_mois(hour_tranches, mois=None):
    """CALX275 — la tranche de chacune des 24 heures d'un MOIS donné.

    ``hour_tranches`` : liste de 24 libellés (toute l'année — comportement
    historique, inchangé) ou ``{saison: [24 libellés]}``. ``mois`` : 1-12,
    ou ``None`` quand la courbe ne dit pas son mois (journée type).

    Rend 24 dicts ``{heure, saison, tranche, motif}`` : ``saison`` = le
    découpage réellement employé (``annuel`` pour une liste plate) ;
    ``tranche`` = ``None`` quand aucune saison saisie ne couvre ce mois, avec
    un ``motif`` qui nomme la saison manquante. Ne lève jamais.
    """
    if not isinstance(hour_tranches, dict):
        liste = list(hour_tranches or [])
        if not liste:
            motif = ("omis : aucun découpage horaire fourni "
                     "(tou_heures)")
            return [{"heure": h, "saison": None, "tranche": None,
                     "motif": motif} for h in range(24)]
        return [{"heure": h, "saison": "annuel",
                 "tranche": _libelle_heure(liste[h % len(liste)]),
                 "motif": None} for h in range(24)]

    saison = _saison_du_mois(mois) if mois is not None else None
    employee = None
    if saison and hour_tranches.get(saison):
        employee = saison
    elif hour_tranches.get("annuel"):
        employee = "annuel"
    if employee is None:
        if saison is None:
            motif = ("omis : mois de l'heure inconnu et aucun découpage "
                     "« annuel » saisi (tou_heures.annuel) — l'heure ne "
                     "peut être rattachée à aucune saison")
        else:
            motif = (f"omis : aucune tranche horaire saisie pour la saison "
                     f"« {saison} » (mois {int(mois)}) ni pour « annuel » "
                     f"(tou_heures.{saison})")
        return [{"heure": h, "saison": None, "tranche": None,
                 "motif": motif} for h in range(24)]
    liste = list(hour_tranches[employee])
    return [{"heure": h, "saison": employee,
             "tranche": _libelle_heure(liste[h % len(liste)]) if liste
             else None,
             "motif": None} for h in range(24)]


def _mois_de_l_heure(index, n_heures, mois_des_heures=None):
    """Mois (1-12) de l'heure ``index`` d'une courbe de ``n_heures`` heures.

    ``mois_des_heures`` (liste explicite, un mois par heure) PRIME. Sinon le
    mois se DÉDUIT des deux seules formes dont la longueur le dit :
    288 heures = 12 journées types mensuelles (convention de ``etude.py``),
    8 760 / 8 784 heures = une année civile heure par heure. Toute autre
    longueur (journée type, semaine…) ⇒ ``None`` : le mois est inconnu.
    """
    if mois_des_heures is not None:
        try:
            m = int(mois_des_heures[index])
        except (IndexError, TypeError, ValueError):
            return None
        return m if 1 <= m <= 12 else None
    if n_heures == 288:
        return index // 24 + 1
    if n_heures in (8760, 8784):
        jour = index // 24
        jours = list(_JOURS_PAR_MOIS)
        if n_heures == 8784:
            jours[1] = 29
        for numero, nb in enumerate(jours, start=1):
            if jour < nb:
                return numero
            jour -= nb
    return None


def net_metering_savings(injected_curve=None, import_curve=None, *,
                         hour_tranches=None, tranche_tariffs=None,
                         surplus_injecte_compense=True,
                         days_per_year=None, spill_tariff=None,
                         annual_cap_kwh=None,
                         compensation_ratio=None,
                         mois_des_heures=None):
    """FG259 — économie annuelle du surplus injecté, valorisé par tranche TOU.

    Croise le SURPLUS INJECTÉ horaire (kWh/h, typiquement
    ``production[h] − autoconsommé[h]`` issu de :func:`hourly_self_consumption`)
    et le SOUTIRAGE RÉSEAU horaire (import, kWh/h) avec un découpage TIME-OF-USE
    (pointe / pleine / creuse) pour appliquer la règle de compensation
    net-metering (loi 13-09, MT/HT) :

        compensé[tranche] = min(injecté[tranche],
                                import[tranche] × compensation_ratio)
        économie[tranche] = compensé[tranche] × tarif[tranche]

    Le reste (``injecté − compensé``) est l'EXCÉDENT non absorbé par le
    soutirage de la même tranche : non valorisé par défaut, ou au tarif
    résiduel ``spill_tariff`` si fourni.

    Paramètres
    ----------
    injected_curve : itérable du surplus injecté horaire (kWh/h) — n'importe
        quelle longueur multiple de 24 (journée type, semaine, année 8760 h).
        Les heures sont mappées sur ``hour_tranches`` modulo 24. Valeurs
        illisibles/négatives → 0 (jamais de rejet).
    import_curve : itérable du soutirage réseau horaire (kWh/h), même mapping.
        Absent → soutirage nul → rien à compenser (économie 0).
    hour_tranches : liste de 24 libellés de tranche par heure (défaut
        ``DEFAULT_HOUR_TRANCHES``, publié dans ``hypotheses`` avec sa
        provenance : découpage du module, non validé par une société). Un
        libellé vide retombe sur « pleine » (comportement historique). CALX275
        — ou ``{saison: [24 libellés]}`` : chaque heure prend le découpage de
        la saison de SON mois (:func:`tranches_du_mois`), sinon « annuel »,
        sinon elle part dans ``non_attribue`` avec son motif (et l'économie
        est ``None`` si du surplus y tombe).
    mois_des_heures : mois (1-12) de chaque heure de la courbe (CALX275).
        Absent, le mois se déduit des seules longueurs qui le disent (288 h =
        12 journées types, 8 760 / 8 784 h = une année civile) ; sinon il est
        inconnu et seule la saison « annuel » s'applique.
    tranche_tariffs : dict ``{tranche: MAD/kWh}`` SAISI par la société
        (``apps.parametres.selectors.tou_pour``). CALX274 — AUCUN défaut :
        ``None`` ⇒ ``economie: None`` + ``motif`` (:data:`MOTIF_TARIFS_TOU_ABSENTS`)
        et ``omissions`` nomme ``tranche_tariffs`` ; une tranche compensée sans
        tarif rend elle aussi l'économie ``None`` en la nommant, jamais un 0.
    surplus_injecte_compense : réglage EXISTANT (toggle). False → l'injection
        n'est PAS compensée → économie 0, tout le surplus en « non compensé ».
    days_per_year : facteur d'annualisation si la courbe est une journée type
        (24 h → ×365). Si la courbe couvre déjà l'année (≥ 8760 h), passer 1.
    spill_tariff : tarif résiduel (MAD/kWh) du surplus EXCÉDENTAIRE non
        compensé (rachat éventuel) ; None → non valorisé (cas 13-09 MT).
    annual_cap_kwh : plafond annuel d'énergie compensée (kWh/an) ; None → pas
        de plafond. Appliqué des tranches les plus chères aux moins chères.
    compensation_ratio : fraction du soutirage compensable par l'injection
        (1.0 = compensation intégrale) ; borné à [0, 1].

    Retourne un dict JSON-sérialisable ::

        {compense, hours, periods, days_per_year,
         tranches: {nom: {injected_kwh, import_kwh, compensated_kwh,
                          spilled_kwh, tariff, savings_mad}},
         injected_kwh, import_kwh, compensated_kwh, spilled_kwh,
         annual_compensated_kwh, annual_injected_kwh,
         savings_mad_per_period, annual_savings_mad,
         annual_spill_value_mad, annual_cap_kwh, compensation_ratio,
         economie, motif, omissions: [{cle, motif}],
         hypotheses: [{cle, valeur, source}], warnings: []}

    ``economie`` = ``annual_savings_mad`` (CALX274) : ``None`` quand un tarif
    manque, avec ``motif`` qui nomme le réglage ; ``motif`` vaut ``None`` quand
    l'économie est chiffrée.

    Ne lève jamais : toggle OFF / courbes vides → économie 0 (le régime ne
    compense rien), tarifs absents → économie ``None`` + motif, division par
    zéro bornée.
    """
    warnings = []
    omissions = []
    hypotheses = []

    injected = _coerce_series(injected_curve)
    imported = _coerce_series(import_curve)

    # CALX275 — un découpage PAR SAISON ``{saison: [24]}`` : l'heure prend la
    # tranche de la saison de SON mois (``tranches_du_mois``), jamais celle
    # d'une autre saison, jamais « pleine » supposée.
    saisonnier = isinstance(hour_tranches, dict) and bool(hour_tranches)
    tranches_by_hour = [] if saisonnier else (
        list(hour_tranches) if hour_tranches else [])
    if not saisonnier and not tranches_by_hour:
        tranches_by_hour = list(DEFAULT_HOUR_TRANCHES)
        hypotheses.append({
            "cle": "hour_tranches",
            "valeur": list(DEFAULT_HOUR_TRANCHES),
            "source": ("découpage horaire par défaut du module "
                       "(apps/ventes/solar_design.py DEFAULT_HOUR_TRANCHES) — "
                       "non validé par la société"),
            "couvre": ["tranches"],
        })

    # CALX274 — les tarifs sont ceux FOURNIS, et eux seuls (aucune fusion avec
    # une grille par défaut) ; libellés normalisés en minuscules comme les
    # heures. ``None`` = aucune grille saisie.
    if tranche_tariffs:
        tariffs = {str(k or "").strip().lower(): v
                   for k, v in dict(tranche_tariffs).items()}
    else:
        tariffs = None
        omissions.append({"cle": "tranche_tariffs",
                          "motif": MOTIF_TARIFS_TOU_ABSENTS})

    def _tariff(name):
        """Tarif de la tranche, ``None`` s'il n'est pas fourni ou illisible."""
        if tariffs is None or name not in tariffs:
            return None
        try:
            t = float(tariffs[name])
        except (TypeError, ValueError):
            return None
        if t != t:  # NaN
            return None
        return t if t >= 0 else 0.0

    # CALX286 — les deux défauts restants sont PUBLIÉS (valeurs inchangées).
    ratio = _taux_ou_none(compensation_ratio)
    if ratio is None:
        ratio = 1.0
        hypotheses.append(_hypothese(
            "compensation_ratio", 1.0,
            "non fourni — compensation kWh pour kWh, la définition même du "
            "net-metering (aucun abattement supposé)",
            ["compensation_ratio"]))
    if ratio < 0.0:
        ratio = 0.0
    if ratio > 1.0:
        ratio = 1.0

    days = _taux_ou_none(days_per_year)
    if days is None:
        days = 365.0
        hypotheses.append(_hypothese(
            "days_per_year", 365,
            "non fourni — la courbe est lue comme UNE journée type, "
            "annualisée sur les 365 jours du calendrier",
            ["periods", "days_per_year", "annual_injected_kwh",
             "annual_compensated_kwh", "annual_savings_mad",
             "annual_spill_value_mad", "economie"]))
    if days <= 0:
        days = 1.0

    # ── Agrégation des flux PAR TRANCHE (modèle sur la période fournie) ──
    names = []
    libelles_saisis = tranches_by_hour
    if saisonnier:
        libelles_saisis = [lib for liste in hour_tranches.values()
                           for lib in (liste or [])]
    for label in libelles_saisis:
        key = (label or "pleine").lower()
        if key not in names:
            names.append(key)
    # Toujours exposer les tranches tarifées même si la courbe ne les touche pas.
    for key in (tariffs or {}):
        k = (key or "").lower()
        if k and k not in names:
            names.append(k)

    agg = {n: {"injected": 0.0, "import": 0.0} for n in names}
    # CALX275 — l'énergie des heures qu'aucune saison saisie ne couvre : elle
    # n'est rattachée à AUCUNE tranche (ni compensée, ni valorisée) et son
    # motif est publié.
    non_attribue = {"injected_kwh": 0.0, "import_kwh": 0.0, "heures": 0,
                    "motifs": []}
    par_mois = {}

    n_hours = max(len(injected), len(imported))
    for h in range(n_hours):
        inj = injected[h] if h < len(injected) else 0.0
        imp = imported[h] if h < len(imported) else 0.0
        if saisonnier:
            mois = _mois_de_l_heure(h, n_hours, mois_des_heures)
            if mois not in par_mois:
                par_mois[mois] = tranches_du_mois(hour_tranches, mois)
            entree = par_mois[mois][h % 24]
            if entree["tranche"] is None:
                non_attribue["injected_kwh"] += inj
                non_attribue["import_kwh"] += imp
                non_attribue["heures"] += 1
                # Le motif publié est celui des heures qui PORTENT de
                # l'énergie (celles dont la valeur manque vraiment) ; les
                # heures vides ne le fixent qu'à défaut.
                cle_motifs = "motifs" if (inj > 0 or imp > 0) else "vides"
                liste = non_attribue.setdefault(cle_motifs, [])
                if entree["motif"] not in liste:
                    liste.append(entree["motif"])
                continue
            label = entree["tranche"]
        else:
            label = tranches_by_hour[h % len(tranches_by_hour)]
        key = (label or "pleine").lower()
        if key not in agg:
            key = "pleine"
            if "pleine" not in agg:
                agg["pleine"] = {"injected": 0.0, "import": 0.0}
                names.append("pleine")
        agg[key]["injected"] += inj
        agg[key]["import"] += imp

    compense = bool(surplus_injecte_compense)
    if not compense:
        warnings.append(
            "compensation de l'injection désactivée "
            "(surplus_injecte_compense = False) — économie nulle, surplus non "
            "valorisé")

    # ── Compensation par tranche (cap = soutirage de la tranche × ratio) ──
    tranche_out = {}
    total_injected = 0.0
    total_import = 0.0
    for name in names:
        inj = round(agg[name]["injected"], 6)
        imp = round(agg[name]["import"], 6)
        total_injected += inj
        total_import += imp
        if compense:
            compensable = min(inj, imp * ratio)
            if compensable < 0.0:
                compensable = 0.0
        else:
            compensable = 0.0
        tranche_out[name] = {
            "injected_kwh": round(inj, 3),
            "import_kwh": round(imp, 3),
            "eligible_kwh": round(compensable, 6),  # avant plafond annuel
            "compensated_kwh": 0.0,
            "spilled_kwh": 0.0,
            "tariff": (None if _tariff(name) is None
                       else round(_tariff(name), 4)),
            "savings_mad": 0.0,
        }

    # ── Plafond annuel : allouer l'énergie compensée des tranches chères → pas ──
    # Le plafond est exprimé en kWh/AN ; on le convertit en kWh sur la PÉRIODE
    # fournie (÷ days) pour l'appliquer sur l'énergie de la période.
    cap_period = None
    try:
        if annual_cap_kwh is not None:
            cap_annual = float(annual_cap_kwh)
            if cap_annual >= 0:
                cap_period = cap_annual / days if days > 0 else cap_annual
    except (TypeError, ValueError):
        cap_period = None

    # Ordre d'allocation : tranches connues du plus cher au moins cher, puis le
    # reste par tarif décroissant (toute tranche custom).
    def _alloc_key(name):
        try:
            rank = _TRANCHE_ORDER.index(name)
        except ValueError:
            rank = len(_TRANCHE_ORDER)
        return (-(_tariff(name) or 0.0), rank, name)

    remaining_cap = cap_period
    tranches_sans_tarif = []
    for name in sorted(names, key=_alloc_key):
        out = tranche_out[name]
        eligible = out["eligible_kwh"]
        if remaining_cap is not None:
            comp = min(eligible, max(0.0, remaining_cap))
            remaining_cap = max(0.0, remaining_cap - comp)
        else:
            comp = eligible
        spilled = max(0.0, out["injected_kwh"] - comp)
        out["compensated_kwh"] = round(comp, 3)
        out["spilled_kwh"] = round(spilled, 3)
        t = _tariff(name)
        if not compense:
            # Le régime ne compense rien : l'économie est nulle PAR LE RÉGIME,
            # quel que soit le tarif (aucun kWh n'est effacé).
            out["savings_mad"] = 0.0
        elif t is None:
            # CALX274 — un kWh compensé sans tarif saisi n'a AUCUNE valeur
            # publiable : ni 0 (faux), ni un tarif supposé. Une tranche qui
            # n'a rien compensé vaut 0 quel que soit son tarif.
            out["savings_mad"] = None if comp > 0 else 0.0
            if comp > 0 and tariffs is not None:
                tranches_sans_tarif.append(name)
        else:
            out["savings_mad"] = round(comp * t, 2)

    if cap_period is not None and total_injected > 0:
        total_eligible = sum(t["eligible_kwh"] for t in tranche_out.values())
        if total_eligible > cap_period:
            warnings.append(
                "plafond annuel de compensation atteint — une partie du "
                "surplus éligible n'est pas valorisée")

    # ── Totaux sur la période + annualisation ──
    period_compensated = round(
        sum(t["compensated_kwh"] for t in tranche_out.values()), 3)
    period_spilled = round(
        sum(t["spilled_kwh"] for t in tranche_out.values()), 3)
    motif = None
    if not compense:
        savings_per_period = 0.0
    elif tariffs is None:
        # CALX274 — aucune grille saisie : l'économie est OMISE, jamais
        # chiffrée sur les anciens 1,45 / 1,15 / 0,85 « à confirmer ».
        savings_per_period = None
        motif = MOTIF_TARIFS_TOU_ABSENTS
    elif non_attribue["injected_kwh"] > 0:
        # CALX275 — du surplus tombe à des heures qu'aucune saison saisie ne
        # couvre : sa valeur est inconnue, l'économie totale aussi.
        savings_per_period = None
        motif = non_attribue["motifs"][0]
        omissions.append({"cle": "hour_tranches", "motif": motif})
    elif tranches_sans_tarif:
        savings_per_period = None
        premiere = sorted(tranches_sans_tarif)[0]
        motif = (f"omis : la tranche « {premiere} » compense de l'énergie "
                 f"mais n'a aucun tarif saisi (tou_tarifs.{premiere})")
        omissions.append({"cle": f"tranche_tariffs.{premiere}",
                          "motif": motif})
    else:
        savings_per_period = round(
            sum(t["savings_mad"] or 0.0 for t in tranche_out.values()), 2)
    if motif:
        warnings.append(f"économie du surplus {motif}")

    # Valeur du surplus excédentaire (spill) au tarif résiduel facultatif.
    spill_value_period = 0.0
    spill_rate = None
    if spill_tariff is not None:
        try:
            spill_rate = float(spill_tariff)
        except (TypeError, ValueError):
            spill_rate = None
        if spill_rate is not None and spill_rate < 0:
            spill_rate = 0.0
    if spill_rate:
        spill_value_period = round(period_spilled * spill_rate, 2)

    annual_savings = (None if savings_per_period is None
                      else round(savings_per_period * days, 2))
    annual_spill_value = round(spill_value_period * days, 2)
    annual_compensated = round(period_compensated * days, 3)
    annual_injected = round(total_injected * days, 3)

    if compense and total_injected > 0 and period_compensated <= 0:
        warnings.append(
            "surplus injecté mais aucun soutirage simultané par tranche à "
            "compenser — vérifier la courbe d'import ou envisager du stockage")

    return {
        "compense": compense,
        "hours": n_hours,
        "periods": days,
        "days_per_year": round(days, 2),
        "tranches": tranche_out,
        "injected_kwh": round(total_injected, 3),
        "import_kwh": round(total_import, 3),
        "compensated_kwh": period_compensated,
        "spilled_kwh": period_spilled,
        "annual_injected_kwh": annual_injected,
        "annual_compensated_kwh": annual_compensated,
        "savings_mad_per_period": savings_per_period,
        "annual_savings_mad": annual_savings,
        "annual_spill_value_mad": annual_spill_value,
        "spill_tariff": spill_rate,
        "annual_cap_kwh": annual_cap_kwh,
        "compensation_ratio": round(ratio, 4),
        # CALX275 — l'énergie des heures sans tranche (aucune saison saisie ne
        # couvre leur mois) : hors des tranches ET des totaux ci-dessus.
        "non_attribue": {
            "injected_kwh": round(non_attribue["injected_kwh"], 3),
            "import_kwh": round(non_attribue["import_kwh"], 3),
            "heures": non_attribue["heures"],
            "tranche": None,
            "motif": ((non_attribue["motifs"]
                       or non_attribue.get("vides") or [None])[0]),
        },
        # CALX274 — l'économie sous son nom canonique, son motif quand elle
        # est omise, et ce qui a servi / manqué, nommé.
        "economie": annual_savings,
        "motif": motif,
        "omissions": omissions,
        "hypotheses": hypotheses,
        "warnings": warnings,
    }


# ── CALX276 — Mécanisme de compensation du surplus, TYPÉ ──────────────────────
# Trois mécanismes SAISIS par la société (``apps.parametres.tariff.
# MECANISMES_COMPENSATION``), au pas MENSUEL :
#
#   * ``injection_totale`` — toute la production est vendue au tarif de
#     rachat ; AUCUNE autoconsommation n'est valorisée (« Buy All, Sell All »).
#   * ``surplus`` — l'autoconsommation efface la facture (valorisée par le
#     modèle « deux factures », hors d'ici) et seul le SURPLUS injecté est
#     vendu au tarif de rachat (« Net Billing »).
#   * ``net_metering_report`` — le kWh injecté efface un kWh soutiré ; le
#     crédit d'un mois excédentaire est REPORTÉ sur les mois suivants, dans une
#     fenêtre de ``report_periode`` mois, au terme de laquelle le SOLDE est
#     publié (et valorisé au tarif de rachat s'il est saisi, sinon omis).
#
# Aucun tarif par défaut : sans tarif de rachat saisi, la vente est OMISE avec
# ``MOTIF_TARIF_RACHAT_ABSENT`` (la loi 82-21 n'en publie aucun) ; sans tarif
# de soutirage fourni, l'économie du net-metering est omise elle aussi.


def _serie_mensuelle(valeurs):
    """Série mensuelle (kWh) : illisible/négatif → 0, jamais d'exception."""
    return _coerce_series(valeurs)


def compensation_surplus(*, mecanisme=None, injection_kwh_mois=None,
                         import_kwh_mois=None, production_kwh_mois=None,
                         tarif_rachat_mad_kwh=None, tarif_import_mad_kwh=None,
                         report_periode=None, plafond_annuel_kwh=None,
                         ratio_compensation=None):
    """CALX276 — valorise le surplus selon le mécanisme SAISI par la société.

    Paramètres (tous au pas mensuel, kWh) : ``injection_kwh_mois`` (surplus
    injecté), ``import_kwh_mois`` (soutirage), ``production_kwh_mois``
    (production totale — requise par ``injection_totale``). Les réglages
    viennent de ``apps.parametres.tariff.mecanisme_depuis_reglages``.

    Rend ``{mecanisme, mois: [...], vendu_kwh, compense_kwh,
    autoconsommation_valorisee, autoconsommation_valorisee_kwh,
    soldes_fin_periode: [{periode, fin_mois, solde_kwh, valeur_mad}],
    solde_fin_periode_kwh, vente_mad, economie_surplus_mad, motif,
    omissions, hypotheses}``. ``economie_surplus_mad`` est ``None`` — avec son
    ``motif`` — dès qu'un réglage manque ; jamais 0 par défaut. Ne lève jamais.
    """
    omissions = []
    hypotheses = []
    resultat = {
        "mecanisme": None, "mois": [], "vendu_kwh": 0.0, "compense_kwh": 0.0,
        "autoconsommation_valorisee": None,
        "autoconsommation_valorisee_kwh": None,
        "soldes_fin_periode": [], "solde_fin_periode_kwh": None,
        "vente_mad": None, "economie_surplus_mad": None, "motif": None,
        "omissions": omissions, "hypotheses": hypotheses,
    }
    meca = mecanisme.strip() if isinstance(mecanisme, str) else ""
    if meca not in MECANISMES_COMPENSATION:
        resultat["motif"] = (
            MOTIF_MECANISME_NON_SAISI if not meca else
            f"omis : mécanisme de compensation « {meca} » inconnu "
            "(mecanisme_compensation)")
        omissions.append({"cle": "mecanisme_compensation",
                          "motif": resultat["motif"]})
        return resultat
    resultat["mecanisme"] = meca

    def _positif_ou_none(valeur):
        try:
            v = float(valeur)
        except (TypeError, ValueError):
            return None
        return v if v == v and v >= 0 else None

    ratio = _positif_ou_none(ratio_compensation)
    if ratio is None:
        ratio = 1.0
        hypotheses.append({
            "cle": "ratio_compensation", "valeur": 1.0,
            "source": ("non saisi — compensation kWh pour kWh, la définition "
                       "même du mécanisme (aucun abattement supposé)")})
    ratio = min(ratio, 1.0)
    plafond = _positif_ou_none(plafond_annuel_kwh)
    tarif_rachat = _positif_ou_none(tarif_rachat_mad_kwh)
    if tarif_rachat is not None and tarif_rachat <= 0:
        tarif_rachat = None
    tarif_import = _positif_ou_none(tarif_import_mad_kwh)

    injection = _serie_mensuelle(injection_kwh_mois)
    soutirage = _serie_mensuelle(import_kwh_mois)
    production = _serie_mensuelle(production_kwh_mois)

    def _borne_annuelle(kwh):
        if plafond is None:
            return kwh
        return min(kwh, plafond)

    def _vente(kwh):
        if tarif_rachat is None:
            if MOTIF_TARIF_RACHAT_ABSENT not in [o["motif"] for o in omissions]:
                omissions.append({"cle": "tarif_rachat_mad_kwh",
                                  "motif": MOTIF_TARIF_RACHAT_ABSENT})
            return None
        return round(kwh * tarif_rachat, 2)

    if meca in ("injection_totale", "surplus"):
        if meca == "injection_totale":
            base = production
            resultat["autoconsommation_valorisee"] = False
            resultat["autoconsommation_valorisee_kwh"] = 0.0
            if not production_kwh_mois:
                omissions.append({
                    "cle": "production_kwh_mois",
                    "motif": ("omis : l'injection totale vend TOUTE la "
                              "production — production mensuelle non "
                              "fournie (production_kwh_mois)")})
                resultat["motif"] = omissions[-1]["motif"]
                return resultat
        else:
            base = injection
            resultat["autoconsommation_valorisee"] = True
        vendu = _borne_annuelle(sum(base) * ratio)
        resultat["mois"] = [{"mois": i + 1, "vendu_kwh": round(v * ratio, 3)}
                            for i, v in enumerate(base)]
        resultat["vendu_kwh"] = round(vendu, 3)
        resultat["vente_mad"] = _vente(vendu)
        resultat["economie_surplus_mad"] = resultat["vente_mad"]
        if resultat["vente_mad"] is None:
            resultat["motif"] = MOTIF_TARIF_RACHAT_ABSENT
        return resultat

    # ── net_metering_report : compensation mensuelle + report du crédit ──
    resultat["autoconsommation_valorisee"] = True
    try:
        periode = int(report_periode)
    except (TypeError, ValueError):
        periode = 0
    if periode < 1:
        motif = ("omis : le net-metering avec report exige la période de "
                 "report saisie (report_periode, en mois)")
        omissions.append({"cle": "report_periode", "motif": motif})
        resultat["motif"] = motif
        return resultat

    n_mois = max(len(injection), len(soutirage))
    credit = 0.0
    compense_total = 0.0
    reste_plafond = plafond
    lignes = []
    soldes = []

    def _clore(numero_periode, fin_mois, solde):
        soldes.append({
            "periode": numero_periode, "fin_mois": fin_mois,
            "solde_kwh": round(solde, 3),
            "valeur_mad": (None if tarif_rachat is None
                           else round(solde * tarif_rachat, 2)),
        })

    for i in range(n_mois):
        if i and i % periode == 0:
            _clore(i // periode, i, credit)   # fin de fenêtre : solde publié
            credit = 0.0
        if i and i % 12 == 0 and plafond is not None:
            reste_plafond = plafond             # plafond ANNUEL : nouvel an
        inj = injection[i] if i < len(injection) else 0.0
        imp = soutirage[i] if i < len(soutirage) else 0.0
        genere = inj * ratio
        credit_entrant = credit
        direct = min(imp, genere)
        depuis_credit = min(imp - direct, credit_entrant)
        compense = direct + depuis_credit
        if reste_plafond is not None:
            compense_borne = min(compense, max(0.0, reste_plafond))
            reste_plafond -= compense_borne
            # Ce que le plafond refuse ne consomme pas de crédit reporté.
            depuis_credit = max(0.0, depuis_credit - (compense - compense_borne))
            direct = compense_borne - depuis_credit
            compense = compense_borne
        credit = credit_entrant - depuis_credit + (genere - direct)
        compense_total += compense
        lignes.append({
            "mois": i + 1, "injection_kwh": round(inj, 3),
            "import_kwh": round(imp, 3),
            "credit_genere_kwh": round(genere, 3),
            "credit_entrant_kwh": round(credit_entrant, 3),
            "credit_consomme_kwh": round(depuis_credit, 3),
            "compense_kwh": round(compense, 3),
            "credit_reporte_kwh": round(credit, 3),
        })
    if n_mois:
        _clore((n_mois - 1) // periode + 1, n_mois, credit)

    resultat["mois"] = lignes
    resultat["compense_kwh"] = round(compense_total, 3)
    resultat["soldes_fin_periode"] = soldes
    resultat["solde_fin_periode_kwh"] = soldes[-1]["solde_kwh"] if soldes \
        else 0.0
    if tarif_rachat is None and soldes and soldes[-1]["solde_kwh"] > 0:
        omissions.append({"cle": "tarif_rachat_mad_kwh",
                          "motif": MOTIF_TARIF_RACHAT_ABSENT})
    if tarif_import is None:
        motif = ("omis : le kWh compensé efface un kWh soutiré — tarif de "
                 "soutirage non fourni (tarif_import_mad_kwh)")
        omissions.append({"cle": "tarif_import_mad_kwh", "motif": motif})
        resultat["motif"] = motif
    else:
        resultat["economie_surplus_mad"] = round(
            compense_total * tarif_import, 2)
    return resultat


# ── FG260 — Escalade tarifaire ONEE sur 20–25 ans + VAN/TRI ──────────────────
# Projette, année par année, la facture d'électricité ÉVITÉE (économie) sur un
# horizon long (20–25 ans) en tenant compte de DEUX dérives bien réelles :
#
#   * l'ESCALADE TARIFAIRE annuelle (l'INDEXATION saisie par la société —
#     CALX279 ; sans saisie, 0 % avec la mention « aucune indexation saisie »,
#     la décision fondateur QRES54 de ``quote_engine/pricing.py``) qui POUSSE
#     l'économie vers le HAUT (chaque kWh évité coûte de plus en plus cher) ;
#   * la DÉGRADATION des modules (~0,5 %/an) qui ÉRODE la production donc
#     l'énergie évitée, TIRANT l'économie vers le bas.
#
# L'économie de l'année ``y`` (base 1) = économie_année1
#     × (1 + escalade)^(y-1)        ← le tarif monte
#     × (1 - dégradation)^(y-1)     ← la production baisse
#
# À partir du flux de trésorerie (économies annuelles − coût initial en année 0)
# on calcule la VAN (NPV, valeur actualisée nette au taux d'actualisation) et le
# TRI (IRR, taux qui annule la VAN), ce dernier par BISSECTION puis affinage
# Newton — STDLIB pure, jamais de boucle infinie (itérations plafonnées), renvoie
# None si le flux n'admet pas de TRI (pas de changement de signe / non-convergence).
#
# Module PUR : aucune base, aucun réseau, aucun prix d'achat/marge. Les entrées
# numériques ne sont JAMAIS rejetées (liberté de saisie du founder) — seules les
# valeurs absurdes sont bornées pour éviter une division par zéro.

# CALX279 — ANCIEN taux d'escalade « marché » (6 %/an, sans source). Il
# CONTREDISAIT ``TARIFF_ESCALATION = 0.0`` (``quote_engine/pricing.py``,
# décision fondateur) : AUCUNE fonction de ce module ne le lit plus
# (indexation saisie, sinon 0 % + mention). Conservé comme nom seulement.
DEFAULT_TARIFF_ESCALATION = 0.06        # 6 %/an — NON sourcé, jamais implicite
#: Mention publiée par une projection faite sans indexation saisie.
MENTION_INDEXATION_NON_SAISIE = _MENTION_INDEXATION_NON_SAISIE
# CALX286 — dégradation et actualisation « marché », NON sourcées : aucune
# fonction de ce module ne les applique plus d'office (grandeurs dépendantes
# ``None`` + ``omissions``). ``apps/ventes/etude.py`` les passe EXPLICITEMENT
# pour garder ses résultats (D12) jusqu'aux réglages société de CALX281/284.
DEFAULT_MODULE_DEGRADATION = 0.005      # 0,5 %/an
DEFAULT_DISCOUNT_RATE = 0.05            # 5 %/an
# Horizon de projection par défaut (années).
DEFAULT_HORIZON_YEARS = 25
# Bornes de l'horizon admissible (le métier vise 20–25 ans, on tolère 1..40).
_MIN_HORIZON_YEARS = 1
_MAX_HORIZON_YEARS = 40


def _npv(rate, cashflows):
    """Valeur actualisée nette d'une suite de flux (flux[0] = année 0).

    ``cashflows[t]`` est actualisé par ``(1 + rate)**t``. ``rate`` = -1 est
    interdit (division par zéro) — renvoie ``float('inf')`` pour rester monotone
    côté solveur (sans lever).
    """
    if rate <= -1.0:
        return float("inf")
    total = 0.0
    for t, cf in enumerate(cashflows):
        total += cf / ((1.0 + rate) ** t)
    return total


def _irr(cashflows, *, low=-0.9999, high=10.0, tol=1e-7, max_iter=200):
    """TRI (taux annulant la VAN) par bissection + affinage Newton, ou None.

    Cherche la racine de ``_npv(rate)`` sur ``[low, high]`` quand la VAN y change
    de signe ; sinon renvoie None (flux sans TRI). Plafonné à ``max_iter`` — pas
    de boucle infinie. Un dernier pas de Newton affine la racine de bissection.
    """
    # Il faut au moins un flux positif ET un flux négatif pour qu'un TRI existe.
    if not any(cf > 0 for cf in cashflows) or not any(cf < 0 for cf in cashflows):
        return None

    f_low = _npv(low, cashflows)
    f_high = _npv(high, cashflows)
    if f_low == 0.0:
        return round(low, 6)
    if f_high == 0.0:
        return round(high, 6)
    # Pas de changement de signe sur l'intervalle → pas de racine bracketée ici.
    if (f_low > 0) == (f_high > 0):
        return None

    a, b = low, high
    fa = f_low
    rate = a
    for _ in range(max_iter):
        rate = (a + b) / 2.0
        fr = _npv(rate, cashflows)
        if abs(fr) < tol or (b - a) / 2.0 < tol:
            break
        if (fr > 0) == (fa > 0):
            a, fa = rate, fr
        else:
            b = rate

    # Affinage Newton (dérivée numérique) sans jamais sortir des bornes.
    for _ in range(20):
        fr = _npv(rate, cashflows)
        if abs(fr) < tol:
            break
        h = 1e-6
        deriv = (_npv(rate + h, cashflows) - fr) / h
        if deriv == 0.0:
            break
        step = fr / deriv
        new_rate = rate - step
        if not (low < new_rate < high):
            break
        rate = new_rate

    return round(rate, 6)


def tariff_escalation_projection(*, annual_savings_year1,
                                 upfront_cost=0.0,
                                 escalation_rate=None,
                                 degradation_rate=None,
                                 horizon_years=None,
                                 discount_rate=None,
                                 baseline_bill_year1=None):
    """FG260 — projette facture/économies sur 20–25 ans + VAN (NPV) & TRI (IRR).

    Construit le tableau année par année du flux de trésorerie d'une installation
    PV : l'économie de l'année 1 escalade chaque année au rythme tarifaire ONEE
    (``escalation_rate``) tout en s'érodant de la dégradation modules
    (``degradation_rate``), face à un coût initial unique (``upfront_cost``) en
    année 0.

    Paramètres
    ----------
    annual_savings_year1 : économie (facture évitée) de la 1re année (MAD/an).
    upfront_cost : investissement initial TTC (MAD), placé en flux d'année 0.
    escalation_rate : indexation tarifaire annuelle (fraction) PASSÉE par
        l'appelant — celle SAISIE par la société
        (``apps.parametres.selectors.indexation_pour``). CALX279 : absente ou
        illisible ⇒ projection à indexation NULLE (0 %, décision fondateur
        QRES54) avec la mention :data:`MENTION_INDEXATION_NON_SAISIE` dans
        ``summary.indexation_mention`` et ``hypotheses`` — jamais 6 %.
    degradation_rate : dégradation annuelle de la production (fraction).
        CALX286 — AUCUN défaut : absente ⇒ les économies de chaque année, les
        cumuls, la VAN, le TRI et les retours valent ``None`` et
        ``omissions`` nomme ``degradation_rate``.
    horizon_years : durée de projection (20–25 visés ; borné 1..40). Absente
        ⇒ ``DEFAULT_HORIZON_YEARS`` publiée dans ``hypotheses``.
    discount_rate : taux d'actualisation pour la VAN (fraction). CALX286 —
        absent ⇒ VAN, économies actualisées et retour actualisé ``None`` avec
        une entrée ``omissions`` ; le TRI, qui n'en dépend pas, reste publié.
    baseline_bill_year1 : facture ONEE de base year-1 (MAD/an), pour projeter la
        facture brute escaladée (optionnel ; sinon non renseignée).

    Retourne un dict JSON-sérialisable ::

        {schedule: [{year, escalated_tariff_factor, degradation_factor,
                     annual_savings, projected_bill, cumulative_savings,
                     net_cumulative, discounted_savings}],
         summary: {horizon_years, escalation_rate, degradation_rate,
                   discount_rate, upfront_cost, total_savings,
                   total_discounted_savings, npv, irr, payback_year,
                   discounted_payback_year, savings_year1, savings_last_year,
                   indexation_mention},
         omissions: [...], hypotheses: [...], warnings: []}

    Ne lève JAMAIS sur entrées dégradées : valeurs illisibles → omises (taux)
    ou 0 (montants), horizon hors bornes ramené dans [1, 40], division par
    zéro gardée, TRI = None si le flux n'en admet pas (pas de boucle infinie).
    """
    warnings = []
    omissions = []
    hypotheses = []

    def _num(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    savings1 = _num(annual_savings_year1)
    cost0 = _num(upfront_cost)
    # CALX279 — l'indexation est celle PASSÉE (saisie société) ; sans elle,
    # 0 % DÉCLARÉ, jamais un taux « marché » implicite.
    esc = _taux_ou_none(escalation_rate)
    indexation_mention = None
    if esc is None:
        esc = 0.0
        indexation_mention = MENTION_INDEXATION_NON_SAISIE
        hypotheses.append({
            "cle": "escalation_rate", "valeur": 0.0,
            "source": (f"{MENTION_INDEXATION_NON_SAISIE} — projection à tarif "
                       "constant (décision fondateur QRES54, "
                       "quote_engine/pricing.py TARIFF_ESCALATION)"),
            "couvre": ["summary.escalation_rate"]})
    # CALX286 — dégradation et actualisation FOURNIES, sinon omises.
    deg = _taux_ou_none(degradation_rate)
    if deg is None:
        omissions.append(_omission(
            "degradation_rate",
            "omis : dégradation annuelle des modules non fournie "
            "(degradation_rate) — les économies des années suivantes, les "
            "cumuls, la VAN, le TRI et les retours en dépendent",
            ["schedule.degradation_factor", "schedule.annual_savings",
             "schedule.cumulative_savings", "schedule.net_cumulative",
             "schedule.discounted_savings", "summary"]))
    disc = _taux_ou_none(discount_rate)
    if disc is None:
        omissions.append(_omission(
            "discount_rate",
            "omis : taux d'actualisation non fourni (discount_rate) — la VAN, "
            "les économies actualisées et le retour actualisé en dépendent",
            ["schedule.discounted_savings", "summary.npv",
             "summary.total_discounted_savings",
             "summary.discounted_payback_year"]))

    # Horizon : entier borné dans [1, 40] (le métier vise 20–25).
    horizon_lu = _taux_ou_none(horizon_years)
    if horizon_lu is None:
        horizon = DEFAULT_HORIZON_YEARS
        hypotheses.append(_hypothese(
            "horizon_years", DEFAULT_HORIZON_YEARS,
            _source_defaut("DEFAULT_HORIZON_YEARS"),
            ["summary.horizon_years"]))
    else:
        horizon = int(round(horizon_lu))
    if horizon < _MIN_HORIZON_YEARS:
        horizon = _MIN_HORIZON_YEARS
        warnings.append("horizon ramené à 1 an (minimum)")
    elif horizon > _MAX_HORIZON_YEARS:
        horizon = _MAX_HORIZON_YEARS
        warnings.append("horizon plafonné à 40 ans (maximum)")

    base_bill1 = None
    if baseline_bill_year1 is not None:
        base_bill1 = _num(baseline_bill_year1)

    # Garde-fous métier (avertissements, jamais de rejet).
    if esc < 0:
        warnings.append("taux d'escalade négatif — le tarif baisse, inhabituel")
    if deg is not None and not (0.0 <= deg < 1.0):
        warnings.append("taux de dégradation hors [0, 1[ — vérifier la saisie")
    if disc is not None and disc <= -1.0:
        warnings.append(
            "taux d'actualisation ≤ -100 % — VAN non calculable, ramené à 0")
        disc = 0.0

    schedule = []
    cumulative = 0.0
    discounted_total = 0.0
    payback_year = None
    discounted_payback_year = None
    discounted_cumulative_net = -cost0
    # Flux de trésorerie : année 0 = -coût initial, puis économies escaladées.
    cashflows = [-cost0]

    for y in range(1, horizon + 1):
        esc_factor = (1.0 + esc) ** (y - 1)

        projected_bill = None
        if base_bill1 is not None:
            # La facture ONEE brute escalade au même rythme tarifaire.
            projected_bill = round(base_bill1 * esc_factor, 2)

        if deg is None:
            # CALX286 — sans dégradation fournie, aucune économie d'année
            # n'est publiée (ni supposée constante, ni érodée d'un taux choisi
            # ici).
            schedule.append({
                "year": y,
                "escalated_tariff_factor": round(esc_factor, 6),
                "degradation_factor": None,
                "annual_savings": None,
                "projected_bill": projected_bill,
                "cumulative_savings": None,
                "net_cumulative": None,
                "discounted_savings": None,
            })
            continue

        # Dégradation bornée : (1 - deg) ne doit pas devenir négatif.
        deg_step = 1.0 - deg if deg < 1.0 else 0.0
        deg_factor = deg_step ** (y - 1)
        annual_savings = savings1 * esc_factor * deg_factor

        cumulative += annual_savings
        net_cumulative = cumulative - cost0

        # Actualisation : le flux de l'année y est divisé par (1+disc)^y.
        discounted = None
        if disc is not None:
            discounted = (annual_savings / ((1.0 + disc) ** y)
                          if disc > -1.0 else 0.0)
            discounted_total += discounted
            discounted_cumulative_net += discounted
            if discounted_payback_year is None \
                    and discounted_cumulative_net >= 0:
                discounted_payback_year = y

        cashflows.append(annual_savings)

        if payback_year is None and net_cumulative >= 0:
            payback_year = y

        schedule.append({
            "year": y,
            "escalated_tariff_factor": round(esc_factor, 6),
            "degradation_factor": round(deg_factor, 6),
            "annual_savings": round(annual_savings, 2),
            "projected_bill": projected_bill,
            "cumulative_savings": round(cumulative, 2),
            "net_cumulative": round(net_cumulative, 2),
            "discounted_savings": (None if discounted is None
                                   else round(discounted, 2)),
        })

    calcule = deg is not None
    actualise = calcule and disc is not None
    npv = round(_npv(disc, cashflows), 2) if actualise else None
    irr = _irr(cashflows) if calcule else None

    if calcule and payback_year is None and cost0 > 0:
        warnings.append(
            "retour sur investissement non atteint sur l'horizon — l'économie "
            "cumulée ne couvre pas le coût initial")
    if calcule and irr is None and cost0 > 0:
        warnings.append(
            "TRI non calculable (flux sans changement de signe ou non "
            "convergent) — vérifier coût initial et économies")

    summary = {
        "horizon_years": horizon,
        "escalation_rate": round(esc, 6),
        "degradation_rate": None if deg is None else round(deg, 6),
        "discount_rate": None if disc is None else round(disc, 6),
        "upfront_cost": round(cost0, 2),
        "savings_year1": round(savings1, 2),
        "savings_last_year": (
            round(schedule[-1]["annual_savings"], 2)
            if calcule and schedule else (0.0 if calcule else None)),
        "total_savings": round(cumulative, 2) if calcule else None,
        "total_discounted_savings": (round(discounted_total, 2)
                                     if actualise else None),
        "net_total": round(cumulative - cost0, 2) if calcule else None,
        "npv": npv,
        "irr": irr,
        "payback_year": payback_year,
        "discounted_payback_year": (discounted_payback_year
                                    if actualise else None),
        # CALX279 — « aucune indexation saisie » quand l'appelant n'a passé
        # aucun taux (projection à 0 %), sinon None.
        "indexation_mention": indexation_mention,
    }

    return {
        "schedule": schedule,
        "summary": summary,
        "omissions": omissions,
        "hypotheses": hypotheses,
        "warnings": warnings,
    }


# ── FG262 — Modélisation de la dégradation des modules sur la durée ───────────
# Applique une COURBE DE DÉGRADATION des modules PV à la production projetée et la
# confronte à la GARANTIE de puissance du constructeur. Un panneau perd une
# fraction de sa puissance chaque année (vieillissement) — souvent précédée d'une
# chute initiale (LID, Light Induced Degradation) plus forte la 1re année. Les
# constructeurs garantissent un plancher de production à des jalons (ex. ≥ 90 % à
# 10 ans, ≥ 80 % à 25 ans) : sous ce plancher, le constructeur compense.
#
# Le facteur de production de l'année ``y`` (base 1) part de 1.0 (production
# nominale STC year-1) et décroît selon DEUX modèles au choix :
#
#   * "compound" (défaut, réaliste) — chute initiale ``year1_degradation`` (LID)
#     appliquée une fois, puis dégradation annuelle COMPOSÉE :
#         facteur(y) = (1 - year1_degradation) × (1 - taux)^(y - 1)
#   * "linear" — chute linéaire constante à partir de 1.0 :
#         facteur(y) = 1 - year1_degradation - taux × (y - 1)
#
# Chaque jalon de garantie (``warranty_floors`` : {année: plancher}) est vérifié :
# si le facteur de l'année jalon tombe SOUS le plancher garanti, l'année est
# signalée (le constructeur compenserait l'écart). On rapporte aussi, par jalon,
# la première année où le facteur passe sous le plancher.
#
# Module PUR : aucune base, aucun réseau, aucun prix. Les entrées numériques ne
# sont JAMAIS rejetées (liberté de saisie du founder) — les valeurs illisibles
# sont ramenées à un défaut sensé, division par zéro gardée, jamais d'exception.

# Garantie de puissance linéaire constructeur par défaut (Tier-1 silicium) :
# ≥ 90 % à 10 ans, ≥ 80 % à 25 ans — jalons les plus répandus du marché.
DEFAULT_WARRANTY_FLOORS = {10: 0.90, 25: 0.80}
# Chute initiale (LID) par défaut la 1re année, avant la dégradation linéaire.
DEFAULT_YEAR1_DEGRADATION = 0.02        # 2 % la 1re année (LID typique)


def module_degradation_curve(production_year1=None, *,
                             annual_degradation_rate=None,
                             year1_degradation=None,
                             horizon_years=None,
                             warranty_floors=None,
                             curve="compound"):
    """FG262 — courbe de dégradation modules + confrontation à la garantie.

    Construit, année par année (base 1), le FACTEUR de production (fraction de la
    production nominale year-1, départ 1.0) et la production ABSOLUE projetée, en
    appliquant une chute initiale (LID) ``year1_degradation`` puis une
    dégradation annuelle ``annual_degradation_rate`` selon le modèle ``curve`` :

    * ``"compound"`` (défaut) — dégradation COMPOSÉE :
      ``facteur(y) = (1 - year1_degradation) × (1 - taux)^(y - 1)``.
    * ``"linear"`` — dégradation LINÉAIRE :
      ``facteur(y) = 1 - year1_degradation - taux × (y - 1)`` (planché à 0).

    Chaque jalon de ``warranty_floors`` ({année: plancher fractionnaire}, défaut
    ``{10: 0.90, 25: 0.80}``) est vérifié : si le facteur de l'année jalon tombe
    SOUS le plancher garanti, l'année est marquée ``warranty_breach`` (le
    constructeur compenserait l'écart).

    Paramètres
    ----------
    production_year1 : production nominale de la 1re année (kWh/an). Si absente /
        illisible, seuls les facteurs sont calculés (production absolue = None).
    annual_degradation_rate : dégradation annuelle (fraction). CALX286 — AUCUN
        défaut : absente ⇒ facteurs, productions et verdicts de garantie
        ``None`` avec une entrée ``omissions`` (le 0,5 %/an d'avant n'est plus
        supposé ; l'étude le passe explicitement, D12).
    year1_degradation : chute initiale LID la 1re année (fraction). Absente ⇒
        ``DEFAULT_YEAR1_DEGRADATION`` publiée dans ``hypotheses``.
    horizon_years : durée de projection (années ; bornée [1, 40]). Absente ⇒
        ``DEFAULT_HORIZON_YEARS`` publiée dans ``hypotheses``.
    warranty_floors : dict {année: plancher fractionnaire}. Absent ⇒
        ``DEFAULT_WARRANTY_FLOORS`` publiés dans ``hypotheses``.
    curve : ``"compound"`` (défaut) ou ``"linear"``.

    Retourne un dict JSON-sérialisable ::

        {schedule: [{year, production_factor, production_kwh,
                     warranty_floor, warranty_breach}],
         warranty_checks: [{year, floor, factor, ok, shortfall_pct,
                            first_breach_year}],
         summary: {curve, horizon_years, annual_degradation_rate,
                   year1_degradation, factor_year1, factor_last_year,
                   total_production_kwh, any_warranty_breach,
                   first_breach_year},
         omissions: [...], hypotheses: [...], warnings: []}

    Ne lève JAMAIS sur entrées dégradées : horizon hors bornes ramené dans
    [1, 40], facteur planché à 0 (jamais négatif).
    """
    warnings = []
    omissions = []
    hypotheses = []

    def _num(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    prod1 = None
    if production_year1 is not None:
        prod1 = _num(production_year1, 0.0)
        if prod1 < 0:
            prod1 = 0.0
            warnings.append("production year-1 négative — ramenée à 0")

    deg = _taux_ou_none(annual_degradation_rate)
    if deg is None:
        omissions.append(_omission(
            "annual_degradation_rate",
            "omis : dégradation annuelle des modules non fournie "
            "(annual_degradation_rate) — à lire sur la garantie de puissance "
            "de la fiche module",
            ["schedule.production_factor", "schedule.production_kwh",
             "schedule.warranty_breach", "warranty_checks.factor",
             "warranty_checks.ok", "warranty_checks.shortfall_pct",
             "warranty_checks.first_breach_year", "summary"]))
    lid = _taux_ou_none(year1_degradation)
    if lid is None:
        lid = DEFAULT_YEAR1_DEGRADATION
        hypotheses.append(_hypothese(
            "year1_degradation", DEFAULT_YEAR1_DEGRADATION,
            _source_defaut("DEFAULT_YEAR1_DEGRADATION"),
            ["summary.year1_degradation", "schedule.production_factor",
             "schedule.production_kwh", "warranty_checks.factor",
             "summary.factor_year1", "summary.factor_last_year",
             "summary.total_production_kwh"]))

    # Garde-fous métier (avertissements, jamais de rejet).
    if deg is not None and not (0.0 <= deg < 1.0):
        warnings.append(
            "taux de dégradation annuel hors [0, 1[ — vérifier la saisie")
    if not (0.0 <= lid < 1.0):
        warnings.append("chute initiale (LID) hors [0, 1[ — vérifier la saisie")

    mode = "linear" if str(curve or "").lower() == "linear" else "compound"

    # Horizon : entier borné dans [1, 40] (le métier vise 20–25).
    horizon_lu = _taux_ou_none(horizon_years)
    if horizon_lu is None:
        horizon = DEFAULT_HORIZON_YEARS
        hypotheses.append(_hypothese(
            "horizon_years", DEFAULT_HORIZON_YEARS,
            _source_defaut("DEFAULT_HORIZON_YEARS"),
            ["summary.horizon_years"]))
    else:
        horizon = int(round(horizon_lu))
    if horizon < _MIN_HORIZON_YEARS:
        horizon = _MIN_HORIZON_YEARS
        warnings.append("horizon ramené à 1 an (minimum)")
    elif horizon > _MAX_HORIZON_YEARS:
        horizon = _MAX_HORIZON_YEARS
        warnings.append("horizon plafonné à 40 ans (maximum)")

    # ── Planchers de garantie (normalisés en {int année: float plancher}) ──
    floors = {}
    if warranty_floors is None:
        src_floors = DEFAULT_WARRANTY_FLOORS
        hypotheses.append(_hypothese(
            "warranty_floors", dict(DEFAULT_WARRANTY_FLOORS),
            _source_defaut("DEFAULT_WARRANTY_FLOORS"),
            ["warranty_checks", "schedule.warranty_floor"]))
    else:
        src_floors = warranty_floors
    try:
        items = list(src_floors.items())
    except AttributeError:
        items = []
        warnings.append("warranty_floors illisible — garantie ignorée")
    for k, v in items:
        try:
            year_k = int(round(float(k)))
            floor_v = float(v)
        except (TypeError, ValueError):
            continue
        if year_k < 1:
            continue
        # Plancher exprimé en % (ex. 80) → fraction.
        if floor_v > 1.0:
            floor_v = floor_v / 100.0
        if floor_v < 0.0:
            floor_v = 0.0
        floors[year_k] = floor_v

    def _factor(year):
        """Facteur de production de l'année ``year`` (base 1), planché à 0."""
        if deg is None:
            return None
        if mode == "linear":
            f = 1.0 - lid - deg * (year - 1)
        else:
            head = (1.0 - lid) if lid < 1.0 else 0.0
            tail = (1.0 - deg) if deg < 1.0 else 0.0
            f = head * (tail ** (year - 1))
        return f if f > 0.0 else 0.0

    schedule = []
    total_production = 0.0
    first_breach_year = None
    for y in range(1, horizon + 1):
        brut = _factor(y)
        factor = None if brut is None else round(brut, 6)
        production_kwh = None
        if prod1 is not None and factor is not None:
            production_kwh = round(prod1 * factor, 2)
            total_production += production_kwh
        floor = floors.get(y)
        breach = (None if factor is None
                  else floor is not None and factor < floor - 1e-9)
        if breach and first_breach_year is None:
            first_breach_year = y
        schedule.append({
            "year": y,
            "production_factor": factor,
            "production_kwh": production_kwh,
            "warranty_floor": floor,
            "warranty_breach": breach,
        })

    # ── Vérification par jalon de garantie ──
    warranty_checks = []
    any_breach = None if deg is None else False
    for year_k in sorted(floors):
        floor_v = floors[year_k]
        if deg is None:
            warranty_checks.append({
                "year": year_k, "floor": round(floor_v, 6), "factor": None,
                "ok": None, "shortfall_pct": None, "first_breach_year": None,
            })
            continue
        # Facteur au jalon (recalculé même si le jalon dépasse l'horizon).
        factor_k = round(_factor(year_k), 6)
        ok = factor_k >= floor_v - 1e-9
        shortfall = 0.0 if ok else round((floor_v - factor_k) * 100.0, 2)
        # Première année où le facteur passe sous CE plancher.
        fb = None
        for yy in range(1, max(year_k, horizon) + 1):
            if _factor(yy) < floor_v - 1e-9:
                fb = yy
                break
        if not ok:
            any_breach = True
            warnings.append(
                f"garantie année {year_k} : facteur {round(factor_k * 100, 1)} %"
                f" < plancher {round(floor_v * 100, 1)} % — le constructeur "
                "compenserait l'écart")
        warranty_checks.append({
            "year": year_k,
            "floor": round(floor_v, 6),
            "factor": factor_k,
            "ok": ok,
            "shortfall_pct": shortfall,
            "first_breach_year": fb,
        })

    summary = {
        "curve": mode,
        "horizon_years": horizon,
        "annual_degradation_rate": None if deg is None else round(deg, 6),
        "year1_degradation": round(lid, 6),
        "factor_year1": (schedule[0]["production_factor"]
                         if schedule and deg is not None
                         else (1.0 if deg is not None else None)),
        "factor_last_year": (schedule[-1]["production_factor"]
                             if schedule and deg is not None
                             else (1.0 if deg is not None else None)),
        "total_production_kwh": (
            round(total_production, 2)
            if prod1 is not None and deg is not None else None),
        "any_warranty_breach": any_breach,
        "first_breach_year": first_breach_year,
    }

    return {
        "schedule": schedule,
        "warranty_checks": warranty_checks,
        "summary": summary,
        "omissions": omissions,
        "hypotheses": hypotheses,
        "warnings": warnings,
    }


# ── FG263 — Modèle financier PPA / tiers-investisseur (client sans capex) ─────
# Modélise un PPA (Power Purchase Agreement) : un TIERS-INVESTISSEUR finance,
# installe et exploite la centrale ; le CLIENT ne paie AUCUN capex et achète
# l'énergie produite au compteur à un tarif PPA (MAD/kWh) — toujours INFÉRIEUR
# au tarif réseau évité, sinon le client n'a aucun intérêt à signer. Le module
# rend les DEUX perspectives, année par année :
#
#   * CÔTÉ INVESTISSEUR — revenu = production_année × tarif_PPA (le tarif PPA
#     peut escalader d'un taux annuel ``ppa_escalation``). En face : un capex
#     initial (année 0) et un O&M annuel (qui peut escalader d'un taux
#     ``om_escalation``, typiquement l'inflation). Le flux net actualisé donne
#     la VAN, le TRI et le payback de l'investisseur (réutilise ``_npv``/``_irr``
#     de FG260 — solveur de TRI BORNÉ, jamais de boucle infinie).
#   * CÔTÉ CLIENT — économie = production_année × (tarif_réseau − tarif_PPA). Le
#     tarif réseau évité escalade au rythme ONEE (``grid_escalation``) tandis que
#     le tarif PPA suit son propre ``ppa_escalation`` : tant que le réseau monte
#     plus vite que le PPA, l'économie du client S'ÉLARGIT. Le client n'a aucun
#     capex, donc son flux est purement positif (économies actualisées).
#
# La PRODUCTION année par année suit la DÉGRADATION des modules (convention
# FG262 : chute initiale LID ``year1_degradation`` puis dégradation annuelle
# composée ``degradation_rate``) — moins d'énergie produite chaque année, donc
# moins de revenu investisseur ET moins d'économie client.
#
# Module PUR : aucune base, aucun réseau, aucun prix d'achat/marge. Les entrées
# numériques ne sont JAMAIS rejetées (liberté de saisie du founder) — les
# valeurs illisibles sont ramenées à un défaut sensé, division par zéro gardée,
# jamais d'exception.

# CALX287 — PLUS AUCUN TARIF PPA PAR DÉFAUT. L'ancien « placeholder marché »
# de 0,90 MAD/kWh n'avait aucune citation : ``ppa_model`` exige désormais le
# tarif SAISI (seule provenance admise : le tarif de rachat réglé par la
# société, ``apps.parametres.tariff.mecanisme_depuis_reglages`` →
# ``tarif_rachat_mad_kwh``, CALX276) et, sans lui, rend ``None`` + motif.
#: Motif publié quand ``ppa_model`` est appelé sans tarif PPA.
MOTIF_TARIF_PPA_ABSENT = (
    "omis : aucun tarif PPA saisi (ppa_tariff) — le tarif de rachat se règle "
    "dans Paramètres → Tarification & ROI (surplus_prix_kwh_ttc), jamais un "
    "tarif « marché » supposé")
# Escalade annuelle par défaut du tarif PPA (souvent indexée inflation).
DEFAULT_PPA_ESCALATION = 0.02           # 2 %/an
# Escalade annuelle par défaut de l'O&M investisseur (inflation).
DEFAULT_OM_ESCALATION = 0.02            # 2 %/an
# Durée de contrat PPA par défaut (années) — 20 ans est le standard marché.
DEFAULT_PPA_TERM_YEARS = 20


def ppa_model(*, annual_production_kwh,
              ppa_tariff=None,
              grid_tariff=None,
              ppa_escalation=None,
              grid_escalation=None,
              term_years=None,
              capex=0.0,
              annual_om=0.0,
              om_escalation=None,
              degradation_rate=None,
              year1_degradation=None,
              discount_rate=None):
    """FG263 — modèle financier PPA / tiers-investisseur (client sans capex).

    Simule un Power Purchase Agreement : le tiers-investisseur paie le capex et
    l'O&M, le client achète l'énergie au tarif PPA (MAD/kWh) sans aucun capex.
    Rend les DEUX perspectives année par année.

    Production : ``annual_production_kwh`` (production nominale year-1) DÉGRADÉE
    selon la convention FG262 (chute initiale LID ``year1_degradation`` puis
    dégradation composée ``degradation_rate``) :
    ``production(y) = prod1 × (1 - year1_degradation) × (1 - degradation_rate)^(y-1)``.

    Côté INVESTISSEUR (année ``y``, base 1) :

    * revenu = ``production(y) × ppa_tariff × (1 + ppa_escalation)^(y-1)`` ;
    * O&M = ``annual_om × (1 + om_escalation)^(y-1)`` ;
    * flux net = revenu − O&M ; flux d'année 0 = ``-capex``.
    * VAN / TRI / payback investisseur via ``_npv``/``_irr`` (FG260, solveur
      borné — jamais de boucle infinie).

    Côté CLIENT (année ``y``) :

    * tarif réseau évité = ``grid_tariff × (1 + grid_escalation)^(y-1)`` ;
    * économie = ``production(y) × (tarif_réseau − tarif_PPA_année)`` (le client
      paie le PPA au lieu du réseau) — peut devenir négative une année si le PPA
      dépasse le réseau (signalé) ;
    * le client n'a AUCUN capex : net = somme des économies actualisées.

    Paramètres
    ----------
    annual_production_kwh : production nominale year-1 (kWh/an).
    ppa_tariff : tarif PPA payé par le client (MAD/kWh), SAISI — CALX287 :
        obligatoire ; absent ⇒ ``schedule``/``investor``/``client``/``summary``
        à ``None`` et ``motif`` = :data:`MOTIF_TARIF_PPA_ABSENT` (nomme
        ``ppa_tariff``). Seule provenance admise : le tarif de rachat réglé par
        la société (``apps.parametres.tariff.mecanisme_depuis_reglages``).
    grid_tariff : tarif réseau évité year-1 (MAD/kWh). Requis pour la perspective
        client ; absent → économies client non calculées (None).
    ppa_escalation / grid_escalation : escalades annuelles (fractions).
    term_years : durée du contrat (années ; bornée [1, 40]).
    capex : investissement initial du tiers-investisseur (MAD, année 0).
    annual_om : O&M year-1 de l'investisseur (MAD/an).
    om_escalation : escalade annuelle de l'O&M (fraction).
    degradation_rate / year1_degradation : dégradation modules (FG262).
    discount_rate : taux d'actualisation (VAN, des deux côtés).

    Retourne un dict JSON-sérialisable ::

        {schedule: [{year, production_kwh, production_factor,
                     ppa_tariff_year, grid_tariff_year,
                     investor_revenue, investor_om, investor_net,
                     investor_discounted_net,
                     client_savings, client_discounted_savings,
                     client_cumulative_savings}],
         investor: {capex, total_revenue, total_om, total_net, npv, irr,
                    payback_year, discounted_payback_year,
                    total_discounted_net},
         client: {grid_tariff_year1, ppa_tariff_year1, total_savings,
                  total_discounted_savings, savings_year1, savings_last_year,
                  net_benefit} | None,
         summary: {term_years, ppa_tariff, ppa_escalation, grid_escalation,
                   degradation_rate, discount_rate, total_production_kwh},
         warnings: []}

    Ne lève JAMAIS sur entrées dégradées : durée hors bornes ramenée dans
    [1, 40], division par zéro gardée, TRI = None si le flux n'en admet pas
    (pas de boucle infinie).

    CALX286 — AUCUN défaut financier muet : ``degradation_rate`` absent ⇒
    le modèle n'est PAS calculé (production, revenus et économies en
    dépendent) et rend ``schedule``/``investor``/``client``/``summary`` à
    ``None`` avec ``motif`` + ``omissions`` ; ``discount_rate`` absent ⇒
    VAN et valeurs actualisées ``None`` ; ``grid_escalation`` absente ⇒ 0 %
    avec la mention « aucune indexation saisie » (CALX279) ; les autres
    défauts restants (escalades PPA / O&M, durée, LID) sont publiés dans
    ``hypotheses`` avec leur provenance.
    """
    warnings = []
    omissions = []
    hypotheses = []

    def _num(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _ou_hypothese(valeur, cle, defaut, nom_constante, couvre):
        lu = _taux_ou_none(valeur)
        if lu is not None:
            return lu
        hypotheses.append(_hypothese(cle, defaut, _source_defaut(nom_constante),
                                     couvre))
        return defaut

    prod1 = _num(annual_production_kwh)
    if prod1 < 0:
        prod1 = 0.0
        warnings.append("production year-1 négative — ramenée à 0")

    # CALX287 — le tarif PPA est OBLIGATOIRE : absent ou illisible, le
    # modèle n'est pas calculé (jamais un 0,90 supposé).
    ppa = _taux_ou_none(ppa_tariff)
    if ppa is None:
        omissions.append(_omission("ppa_tariff", MOTIF_TARIF_PPA_ABSENT,
                                   ["schedule", "investor", "client",
                                    "summary"]))
        return {"schedule": None, "investor": None, "client": None,
                "summary": None, "motif": MOTIF_TARIF_PPA_ABSENT,
                "omissions": omissions, "hypotheses": hypotheses,
                "warnings": warnings}
    ppa_esc = _ou_hypothese(
        ppa_escalation, "ppa_escalation", DEFAULT_PPA_ESCALATION,
        "DEFAULT_PPA_ESCALATION",
        ["summary.ppa_escalation", "schedule.ppa_tariff_year",
         "schedule.investor_revenue", "investor", "client"])
    grid_esc = _taux_ou_none(grid_escalation)
    if grid_esc is None:
        grid_esc = 0.0
        hypotheses.append(_hypothese(
            "grid_escalation", 0.0,
            f"{MENTION_INDEXATION_NON_SAISIE} — tarif réseau constant "
            "(décision fondateur QRES54)",
            ["summary.grid_escalation"]))
    capex0 = _num(capex)
    om1 = _num(annual_om)
    om_esc = _ou_hypothese(
        om_escalation, "om_escalation", DEFAULT_OM_ESCALATION,
        "DEFAULT_OM_ESCALATION",
        ["summary.om_escalation", "schedule.investor_om", "investor"])
    lid = _ou_hypothese(
        year1_degradation, "year1_degradation", DEFAULT_YEAR1_DEGRADATION,
        "DEFAULT_YEAR1_DEGRADATION",
        ["summary.year1_degradation", "schedule.production_factor",
         "schedule.production_kwh", "summary.total_production_kwh"])
    deg = _taux_ou_none(degradation_rate)
    disc = _taux_ou_none(discount_rate)

    grid1 = None
    if grid_tariff is not None:
        grid1 = _num(grid_tariff)
        if grid1 < 0:
            grid1 = 0.0
            warnings.append("tarif réseau négatif — ramené à 0")

    # ── Durée du contrat : entier borné dans [1, 40] ──
    term = int(round(_ou_hypothese(
        term_years, "term_years", DEFAULT_PPA_TERM_YEARS,
        "DEFAULT_PPA_TERM_YEARS", ["summary.term_years"])))
    if term < _MIN_HORIZON_YEARS:
        term = _MIN_HORIZON_YEARS
        warnings.append("durée ramenée à 1 an (minimum)")
    elif term > _MAX_HORIZON_YEARS:
        term = _MAX_HORIZON_YEARS
        warnings.append("durée plafonnée à 40 ans (maximum)")

    if deg is None:
        motif = ("omis : dégradation annuelle des modules non fournie "
                 "(degradation_rate) — la production, les revenus et les "
                 "économies de chaque année en dépendent")
        omissions.append(_omission("degradation_rate", motif,
                                   ["schedule", "investor", "client",
                                    "summary"]))
        return {"schedule": None, "investor": None, "client": None,
                "summary": None, "motif": motif, "omissions": omissions,
                "hypotheses": hypotheses, "warnings": warnings}
    disc_fourni = disc is not None
    if not disc_fourni:
        omissions.append(_omission(
            "discount_rate",
            "omis : taux d'actualisation non fourni (discount_rate) — VAN et "
            "valeurs actualisées non publiées",
            ["schedule.investor_discounted_net",
             "schedule.client_discounted_savings", "investor.npv",
             "investor.total_discounted_net",
             "investor.discounted_payback_year",
             "client.total_discounted_savings"]))
        disc = 0.0  # calcul interne seulement : les sorties actualisées → None

    # Garde-fous métier (avertissements, jamais de rejet).
    if not (0.0 <= deg < 1.0):
        warnings.append("taux de dégradation hors [0, 1[ — vérifier la saisie")
    if not (0.0 <= lid < 1.0):
        warnings.append("chute initiale (LID) hors [0, 1[ — vérifier la saisie")
    if disc <= -1.0:
        warnings.append(
            "taux d'actualisation ≤ -100 % — VAN non calculable, ramené à 0")
        disc = 0.0
    if grid1 is not None and grid1 <= ppa:
        warnings.append(
            "tarif PPA ≥ tarif réseau year-1 — le client ne fait aucune "
            "économie au départ, vérifier l'intérêt du contrat")

    def _deg_factor(year):
        """Facteur de production de l'année ``year`` (base 1), planché à 0 — convention FG262."""
        head = (1.0 - lid) if lid < 1.0 else 0.0
        tail = (1.0 - deg) if deg < 1.0 else 0.0
        f = head * (tail ** (year - 1))
        return f if f > 0.0 else 0.0

    schedule = []
    total_production = 0.0
    investor_total_revenue = 0.0
    investor_total_om = 0.0
    investor_total_net = 0.0
    investor_discounted_total = 0.0
    investor_payback_year = None
    investor_disc_payback_year = None
    investor_disc_cumulative = -capex0
    # Flux investisseur : année 0 = -capex, puis (revenu − O&M) chaque année.
    investor_cashflows = [-capex0]

    client_total_savings = 0.0
    client_discounted_total = 0.0
    client_cumulative = 0.0
    has_client = grid1 is not None

    for y in range(1, term + 1):
        factor = _deg_factor(y)
        production = prod1 * factor
        total_production += production

        ppa_year = ppa * ((1.0 + ppa_esc) ** (y - 1))

        # ── Investisseur ──
        revenue = production * ppa_year
        om = om1 * ((1.0 + om_esc) ** (y - 1))
        net = revenue - om
        investor_total_revenue += revenue
        investor_total_om += om
        investor_total_net += net
        investor_cashflows.append(net)

        if disc > -1.0:
            disc_net = net / ((1.0 + disc) ** y)
        else:
            disc_net = 0.0
        investor_discounted_total += disc_net
        investor_disc_cumulative += disc_net

        investor_cumulative_net = investor_total_net - capex0
        if investor_payback_year is None and investor_cumulative_net >= 0 \
                and capex0 > 0:
            investor_payback_year = y
        if investor_disc_payback_year is None and investor_disc_cumulative >= 0 \
                and capex0 > 0:
            investor_disc_payback_year = y

        # ── Client ──
        grid_year = None
        client_savings = None
        client_disc_savings = None
        if has_client:
            grid_year = grid1 * ((1.0 + grid_esc) ** (y - 1))
            # Le client paie le PPA au lieu du réseau : économie sur l'écart.
            client_savings = production * (grid_year - ppa_year)
            client_total_savings += client_savings
            client_cumulative += client_savings
            if disc > -1.0:
                client_disc_savings = client_savings / ((1.0 + disc) ** y)
            else:
                client_disc_savings = 0.0
            client_discounted_total += client_disc_savings

        schedule.append({
            "year": y,
            "production_kwh": round(production, 2),
            "production_factor": round(factor, 6),
            "ppa_tariff_year": round(ppa_year, 4),
            "grid_tariff_year": (
                round(grid_year, 4) if grid_year is not None else None),
            "investor_revenue": round(revenue, 2),
            "investor_om": round(om, 2),
            "investor_net": round(net, 2),
            "investor_discounted_net": round(disc_net, 2),
            "client_savings": (
                round(client_savings, 2)
                if client_savings is not None else None),
            "client_discounted_savings": (
                round(client_disc_savings, 2)
                if client_disc_savings is not None else None),
            "client_cumulative_savings": (
                round(client_cumulative, 2) if has_client else None),
        })

    investor_npv = round(_npv(disc, investor_cashflows), 2)
    investor_irr = _irr(investor_cashflows)

    if investor_payback_year is None and capex0 > 0:
        warnings.append(
            "retour sur investissement non atteint sur la durée — le revenu PPA "
            "cumulé ne couvre pas le capex de l'investisseur")
    if investor_irr is None and capex0 > 0:
        warnings.append(
            "TRI investisseur non calculable (flux sans changement de signe ou "
            "non convergent) — vérifier capex et tarif PPA")

    investor = {
        "capex": round(capex0, 2),
        "total_revenue": round(investor_total_revenue, 2),
        "total_om": round(investor_total_om, 2),
        "total_net": round(investor_total_net, 2),
        "net_after_capex": round(investor_total_net - capex0, 2),
        "total_discounted_net": round(investor_discounted_total, 2),
        "npv": investor_npv,
        "irr": investor_irr,
        "payback_year": investor_payback_year,
        "discounted_payback_year": investor_disc_payback_year,
    }

    client = None
    if has_client:
        client = {
            "grid_tariff_year1": round(grid1, 4),
            "ppa_tariff_year1": round(ppa, 4),
            "total_savings": round(client_total_savings, 2),
            "total_discounted_savings": round(client_discounted_total, 2),
            "savings_year1": (
                round(schedule[0]["client_savings"], 2) if schedule else 0.0),
            "savings_last_year": (
                round(schedule[-1]["client_savings"], 2) if schedule else 0.0),
            # Le client n'a aucun capex : son bénéfice net = économies cumulées.
            "net_benefit": round(client_total_savings, 2),
        }

    summary = {
        "term_years": term,
        "ppa_tariff": round(ppa, 4),
        "ppa_escalation": round(ppa_esc, 6),
        "grid_escalation": round(grid_esc, 6),
        "om_escalation": round(om_esc, 6),
        "degradation_rate": round(deg, 6),
        "year1_degradation": round(lid, 6),
        "discount_rate": round(disc, 6) if disc_fourni else None,
        "annual_om_year1": round(om1, 2),
        "total_production_kwh": round(total_production, 2),
        "production_year1": round(prod1, 2),
    }

    if not disc_fourni:
        # CALX286 — sans taux d'actualisation fourni, aucune valeur
        # actualisée n'est publiée (le calcul interne à 0 % reste interne).
        for ligne in schedule:
            ligne["investor_discounted_net"] = None
            ligne["client_discounted_savings"] = None
        investor["npv"] = None
        investor["total_discounted_net"] = None
        investor["discounted_payback_year"] = None
        if client is not None:
            client["total_discounted_savings"] = None

    return {
        "schedule": schedule,
        "investor": investor,
        "client": client,
        "summary": summary,
        "motif": None,
        "omissions": omissions,
        "hypotheses": hypotheses,
        "warnings": warnings,
    }

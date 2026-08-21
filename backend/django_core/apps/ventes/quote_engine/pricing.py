"""ROI / savings math — loi 82-21 self-consumption-first model.

Pure formulas (Morocco GHI irradiance + per-utility tariff tranches). No I/O,
no network, no Django — safe to call on the fly when generating a quote PDF.

TARIFF POLICY (loi 82-21, June 2026)
--------------------------------------
Savings are SELF-CONSUMPTION-FIRST: only self-consumed kWh are valued.
Surplus injected to the grid is NOT valued — the ANRE BT residential
net-billing tariff is unpublished/unconfirmed; including it would be
fabricating income.

Q7 (décision fondateur du 20/08/2026) — UN SEUL BARÈME NATIONAL : la grille
ONEE vérifiée (SÉLECTIVE au-delà de 150 kWh/mois — franchir une marche
re-tarife TOUT le mois), identique à celle de l'estimateur public. Les trois
distributeurs (ONEE, Lydec, Redal) la lisent ; le nom du distributeur n'est
plus qu'un LIBELLÉ. Les anciennes grilles « approximatives » Lydec/Redal sont
supprimées : jamais vérifiées, elles faisaient diverger la facture d'un même
client selon un champ de formulaire. Une société dont la grille réelle diffère
la SAISIT (Paramètres → Tarification & ROI, ``TariffSettings``), et un devis
peut la surcharger via ``etude_params``.

All tables are TTC tariffs (the customer pays TTC, so the avoided cost
is the TTC tariff).
"""
from __future__ import annotations

# ── Utility tranche tables ─────────────────────────────────────────────────────
# Tarifs TTC (MAD/kWh, TVA incluse) au 2026 — grille NATIONALE vérifiée (Q7).
# Source: barèmes ONEE/distributeurs publiés (résidentiel BT, compteur monophasé).
# Ces constantes sont les SEULS prix de référence ; aucun autre fichier ne doit
# porter de prix kWh en dur. Le vendeur peut les surcharger via etude_params.
#
# Format : liste de (plafond_kWh_mensuel, prix_MAD_kWh_TTC).
# La dernière tranche n'a pas de plafond (None = tranche supérieure).
#
# ═══ ORDRE FONDATEUR (18/08) — LE BARÈME RÉSIDENTIEL EST SÉLECTIF ═══════════
# « The client will go down in the price per kWh because he will be below 500
#   kWh per month — I want the new price per kWh to be used so the savings are
#   real. »
# Le barème BT résidentiel marocain n'est PAS purement progressif : il est
# progressif jusqu'au seuil (150 kWh/mois), puis SÉLECTIF — franchir une marche
# re-tarife la TOTALITÉ de la consommation du mois au prix de SA tranche. Un
# foyer à 700 kWh/mois paie donc 1,5958 MAD sur ses 700 kWh ; passé au solaire,
# son résiduel de 280 kWh retombe à 1,1676 MAD sur la totalité — c'est
# exactement la baisse de prix décrite par le fondateur, et elle vaut BEAUCOUP
# plus que les seuls kWh effacés au tarif marginal.


class TrancheTable(list):
    """Table de tranches ``[(plafond_kWh_mensuel | None, prix_MAD_kWh), …]``
    qui PEUT porter la règle SÉLECTIVE marocaine.

    Reste une ``list`` de paires à tous points de vue (itération, indexation,
    égalité avec une liste nue) : une table purement PROGRESSIVE (barème collé
    par le vendeur, surcharge société) est une simple liste et garde
    exactement son comportement historique.

    Attributs :
        selective_threshold  Conso mensuelle (kWh) au-delà de laquelle la
                             facturation bascule en SÉLECTIF (None = table
                             purement progressive).
        boundary_tolerance   Tolérance de bord (kWh) : on n'entre dans la
                             tranche supérieure qu'à +tolérance (bornes
                             nominales 200/300/500 → effectives 210/310/510).
    """

    def __init__(self, pairs, selective_threshold=None, boundary_tolerance=0.0):
        super().__init__(pairs)
        self.selective_threshold = selective_threshold
        self.boundary_tolerance = boundary_tolerance


# ONEE — barème « BASSE TENSION / usage domestique », prix consommateur TTC
# (TVA incluse — ne JAMAIS rajouter de TVA par-dessus). MÊME grille que
# l'estimateur public (apps/web/src/lib/estimatorBrainV2.ts ``REGIE_TARIFF``) —
# site et ERP annoncent désormais la même économie.
#
# SOURCE VÉRIFIÉE (consultée le 18/08/2026) — grille tarifaire officielle
# publiée par une régie de distribution régulée, qui applique le barème
# national : RADEEJ (El Jadida), « Basse Tension : Tarif en DH/kWh TTC »,
# https://radeej.ma/assets/espace%20client/elec%20tarif.pdf — les SIX valeurs
# ci-dessous en sont copiées telles quelles, ainsi que le mécanisme et la
# tolérance. Corroboration indépendante (page mise à jour le 18/08/2026) :
# https://kherba.com/tarifs — mêmes six taux au dix-millième.
#
#   · ≤ 150 kWh/mois → « Tarif Progressif » : 0–100 = 0,9010 ; 101–150 = 1,0732.
#   · > 150 kWh/mois → « Tarif Sélectif » (TOUTE la conso au tarif de SA
#     tranche) : 151–200 = 1,0732 ; 201–300 = 1,1676 ; 301–500 = 1,3817 ;
#     > 500 = 1,5958.
#   · Tolérance, citée mot pour mot par la source : « le tarif sélectif précité
#     sera appliqué en faisant bénéficier les clients d'une tolérance de
#     dépassement de 10 KWh/mois pour chaque tranche de consommation » — d'où
#     les bornes EFFECTIVES 210/310/510.
#
# BASE LÉGALE DU MÉCANISME (le « sélectif » n'est pas une interprétation) :
# arrêtés ministériels n° 2451.14 / 2682.14, BO n° 6275 bis du 22/07/2014,
# appliqués au 01/08/2014 ; le bulletin client Lydec d'août 2014 qui les relaie
# l'écrit noir sur blanc — « facturer la totalité de la consommation mensuelle
# au tarif de la tranche dans laquelle elle se situe » — et confirme le seuil
# de tolérance de 10 kWh. Le tarif de VENTE BT au consommateur n'est PAS publié
# par l'ANRE (elle ne régule que les tarifs d'usage du réseau) : il reste fixé
# par arrêté, d'où le recours aux grilles publiées par les distributeurs. Les
# taux TTC ci-dessus intègrent la hausse étalée sur 4 ans qui a suivi 2014 ;
# refonte tarifaire ANRE annoncée pour ~mars 2027 → re-vérifier à cette date.
#
# HAUT DE GRILLE — POINT OUVERT POUR LE FONDATEUR (18/08). Le fondateur a
# corrigé « ce n'est pas 1,4 mais ~1,69/1,7 » pour la tranche haute : sa
# correction de FOND est confirmée (l'ancien 1,4017 était bel et bien trop bas),
# mais le chiffre exact publié pour l'USAGE DOMESTIQUE > 500 kWh/mois est
# 1,5958. Les taux ~1,69–1,71 de la MÊME grille officielle appartiennent à
# d'AUTRES catégories d'usage : force motrice > 500 kWh = 1,6758 et éclairage
# patenté > 150 kWh = 1,7090 (bi-horaire domestique, heures de pointe = 2,2441).
# On encode donc le taux domestique VÉRIFIÉ, jamais un chiffre inventé ; si le
# fondateur produit une facture récente montrant 1,69 en domestique, cette seule
# ligne change (et son miroir JS).
#
# Remplace l'ancienne grille QX38 (100/250/400/∞ à 0,9010/1,0258/1,2515/1,4017),
# purement progressive et marquée « à confirmer » : elle contredisait la grille
# officielle sur les seuils ET sur les prix, et sous-estimait lourdement
# l'économie d'un foyer du haut de grille.
#
# ═══ ORDRE FONDATEUR (19/08/2026) — TVA 20 % DEPUIS LE 01/01/2026 ══════════
# « for the electricity price the price for tranche 6 is : 1.622856. the price
#   is changing per year, because they change the VAT... so correct all
#   prices and keep them changable in the settings ». La TVA marocaine sur
#   l'électricité est passée 16 % (2024) → 18 % (2025) → 20 % (depuis le
#   01/01/2026) : les SIX prix TTC ci-dessus (RADEEJ, 18/08/2026) étaient donc
#   encore au taux 2025 (18 %), pas au taux en vigueur. Le fondateur a confirmé
#   au dixième de dirham près (facture réelle) que la tranche 6 (> 500 kWh)
#   vaut désormais 1,622856 MAD/kWh TTC — l'ANCRE de la re-dérivation ci-dessous.
#
#   MÉTHODE (reproductible chaque année où la TVA change) : chaque prix TTC
#   2025 (18 %) ci-dessus divise par 1,18 pour retrouver sa base HT (arrondie
#   au cinquième de centime, cohérente avec l'ancre fondateur — HT tranche 6 =
#   1,622856 / 1,20 = 1,35238) ; le nouveau TTC = HT × (1 + taux TVA courant).
#   Bases HT retrouvées (identiques aux 2 décimales millièmes près quel que
#   soit le sens du calcul, TTC 2025 ↔ HT ↔ TTC 2026) :
#     0–100 kWh   : HT 0,76356 → 2025 (18 %) 0,9010  → 2026 (20 %) 0,916272
#     101–210 kWh : HT 0,90949 → 2025 (18 %) 1,0732  → 2026 (20 %) 1,091388
#     211–310 kWh : HT 0,98949 → 2025 (18 %) 1,1676  → 2026 (20 %) 1,187388
#     311–510 kWh : HT 1,17093 → 2025 (18 %) 1,3817  → 2026 (20 %) 1,405116
#     > 510 kWh   : HT 1,35238 → 2025 (18 %) 1,5958  → 2026 (20 %) 1,622856 ✓ ancre
#   PROCHAINE HAUSSE DE TVA : refaire exactement ce calcul (HT × nouveau taux)
#   sur les six bases HT ci-dessus — jamais repartir d'un TTC déjà taxé.
#
# ÉDITABLE PAR SOCIÉTÉ (19/08/2026) — ces six valeurs restent le DÉFAUT codé
# en dur ; une société peut les surcharger dans Paramètres → Tarification &
# ROI (apps/parametres ``TariffSettings.residential_tiers``, lu au calcul via
# ``apps.parametres.selectors.residential_tranches_for`` — voir builder.py).
# Sans surcharge enregistrée, ces défauts 2026 s'appliquent tels quels.
#
# SECONDE IMPLÉMENTATION INDÉPENDANTE — apps/parametres/models_tariff.py
# ``DEFAULT_RESIDENTIAL_TIERS`` + apps/parametres/tariff.py
# ``monthly_bill_residentiel`` (consommée par apps/ventes/etude.py, pas par le
# moteur de devis) portent la MÊME grille/règle, en Decimal, avec des bornes
# déjà EFFECTIVES au lieu de nominal+tolérance. Volontairement PAS unifiées
# (hors périmètre) — verrouillées d'accord par
# apps/ventes/tests/test_tariff_drift_lock.py : si l'une bouge seule, ce test
# passe au rouge. Le miroir JS frontend/src/features/ventes/solar.js
# ONEE_TRANCHES et le miroir site apps/web/src/lib/estimatorBrainV2.ts
# REGIE_TARIFF portent les MÊMES six valeurs 2026.
ONEE_TRANCHES = TrancheTable(
    [
        (100, 0.916272),    # progressif   0–100  — HT 0,76356 × TVA 20 % (2026)
        (150, 1.091388),    # progressif 101–150  — HT 0,90949 × TVA 20 % (2026)
        (200, 1.091388),    # sélectif 151–200, effectif 151–210 — idem
        (300, 1.187388),    # sélectif 201–300, effectif 211–310 — HT 0,98949 × 1,20
        (500, 1.405116),    # sélectif 301–500, effectif 311–510 — HT 1,17093 × 1,20
        (None, 1.622856),   # sélectif > 500,   effectif > 510   — HT 1,35238 × 1,20 (ancre fondateur)
    ],
    selective_threshold=150,
    boundary_tolerance=10,
)

# ── Q7 (décision fondateur du 20/08/2026) — UN SEUL BARÈME NATIONAL ──────────
# Les grilles « approximatives » Lydec et Redal DISPARAISSENT. Elles étaient
# inventées (« à confirmer avec tarif Lydec », trois paliers ronds jamais
# vérifiés) et produisaient, sur un même client, une facture différente de
# celle du barème national — puis un drapeau « approximatif » qui avouait le
# problème sans le corriger. Les trois distributeurs résolvent désormais sur LA
# grille nationale ci-dessus, éditable par société (Paramètres → Tarification &
# ROI). Le nom du distributeur reste un LIBELLÉ (il s'affiche, il ne calcule
# plus) : un délégataire dont la grille réelle diffère se saisit comme
# surcharge société, jamais comme approximation codée en dur.
UTILITY_TABLES = {
    "onee": ONEE_TRANCHES,
    "lydec": ONEE_TRANCHES,
    "redal": ONEE_TRANCHES,
}

# Taux d'autoconsommation par option (estimation documentée, pas de netting)
# Sans batterie : résidentiel marocain typique (pas d'injection valorisée)
AUTOCONSO_SANS = 0.60   # estimation — à affiner avec une étude de consommation
# ORDRE FONDATEUR (18/08) — le forfait « 85 % avec batterie » n'est PLUS le
# modèle : une batterie ne relève pas un taux, elle décale une quantité
# d'énergie RÉELLE égale à sa capacité, une fois par jour. AUTOCONSO_AVEC ne
# survit que comme REPLI documenté : devis explicitement « avec batterie » dont
# la capacité est inconnue (aucune ligne batterie chiffrable), ou taux forcé par
# le vendeur via ``etude_params['autoconso_avec']``. Dès qu'une capacité existe,
# le taux est DÉRIVÉ (``autoconso_avec_ratio``), jamais forfaitaire.
AUTOCONSO_AVEC = 0.85   # repli seulement — voir autoconso_avec_ratio()

# ── Modèle batterie ADDITIF (ordre fondateur 18/08) — MIROIR solar.js ────────
# autoconsommé_avec = 60 % × production + capacité_kWh × 1 cycle/jour.
# PLAFONDS (honnêteté : on ne vend jamais de l'énergie qui n'existe pas) :
#   • jamais plus que la production (la batterie ne décale que l'existant) ;
#   • jamais plus que la consommation réelle quand elle est connue.
BATTERY_CYCLES_PER_DAY = 1
DAYS_PER_YEAR = 365


def autoconso_avec_ratio(
    production_annuelle_kwh,
    battery_kwh,
    *,
    base: float = AUTOCONSO_SANS,
    fallback: float = AUTOCONSO_AVEC,
    conso_annuelle_kwh=None,
) -> float:
    """Taux d'autoconsommation EFFECTIF de l'option « avec batterie ».

    Miroir EXACT de ``solar.js autoconsoAvecRatio`` : mêmes entrées, mêmes
    plafonds, même résultat au chiffre près (un test de parité fixe les valeurs
    des deux côtés). Fonction pure.

    ``battery_kwh`` nul/inconnu → ``fallback`` (l'ancien forfait), seul cas où
    l'on n'a aucune capacité réelle à additionner.
    """
    try:
        prod = float(production_annuelle_kwh or 0)
        cap = float(battery_kwh or 0)
        conso = float(conso_annuelle_kwh or 0)
    except (TypeError, ValueError):
        return fallback
    if prod <= 0:
        return fallback
    if cap > 0:
        ratio = float(base) + (cap * BATTERY_CYCLES_PER_DAY * DAYS_PER_YEAR) / prod
    else:
        ratio = float(fallback)
    ratio = min(1.0, ratio)                      # plafond production
    if conso > 0:
        ratio = min(ratio, conso / prod)         # plafond consommation
    return ratio


# ── Pertes système : 20 % AU TOTAL (ordre fondateur, 18/08) ─────────────────
# QRES54 (2026-07-18) déduisait 14 % de plus du productible stocké — c'était un
# DOUBLE COMPTAGE : les productibles de ``productible.py`` (1651 Casablanca…)
# sont des sorties PVGIS demandées à ``loss=14`` (cf. apps/parametres/pvgis.py),
# donc 14 % de pertes sont DÉJÀ dedans. Le fondateur fixe le total à 20 % :
# on n'applique donc que le COMPLÉMENT, (1 − 20 %)/(1 − 14 %) ≈ 0,9302, pour
# passer d'un productible « net à 14 % » à un productible « net à 20 % ».
# Le nom PRODUCTION_DERATE est conservé (mêmes consommateurs), sa valeur
# change : 0,86 (faux, 26 % cumulés) → 0,9302 (20 % au total, exact).
# MIROIR solar.js SYSTEM_LOSS_TOTAL / PVGIS_BUILTIN_LOSS / PRODUCTIBLE_NET_FACTOR.
SYSTEM_LOSS_TOTAL = 0.20      # pertes système TOTALES retenues (fondateur 18/08)
PVGIS_BUILTIN_LOSS = 0.14     # pertes déjà incluses dans le productible stocké
PRODUCTION_DERATE = (1 - SYSTEM_LOSS_TOTAL) / (1 - PVGIS_BUILTIN_LOSS)

# Prix kWh ONEE de référence (FLAT) — utilisé quand AUCUNE donnée de conso n'est
# disponible. Valeur « raisonnable » de milieu de gamme ONEE ; le résultat est
# présenté comme une ESTIMATION approximative, jamais comme un chiffre précis.
_FALLBACK_KWH_PRICE = 1.20   # MAD/kWh — tranche milieu ONEE (à confirmer)

# Productible annuel de repli (kWh/kWc/an) — GHI moyen Maroc. Défaut historique
# 1240 CONSERVÉ pour byte-identité ; le builder peut le surcharger avec
# CompanyProfile.productible_kwh_kwc (DC2), auquel cas la production annuelle et
# le ROI suivent le repère de la société.
_DEFAULT_PRODUCTIBLE = 1240

# Label affiché quand on dégrade en estimation (pas de données tarifaires)
ESTIMATION_LABEL = "estimation"

# Q7 — plus AUCUNE table approximative : les trois distributeurs lisent la même
# grille nationale (éditable par société). L'ensemble reste défini, VIDE, pour
# les appelants qui l'importent encore ; il ne peut plus rien étiqueter.
APPROX_UTILITIES = frozenset()


def _resolve_tranches(utility=None, tranches_override=None):
    """Résout la table de tranches applicable.

    Returns:
        (table | None, approximatif: bool)
        ``table`` est None quand AUCUNE donnée tarifaire n'existe (l'appelant
        dégrade alors en estimation honnête). Q7 — ``approximatif`` vaut
        DÉSORMAIS toujours False : il n'existe plus de table estimée, les trois
        distributeurs lisant la grille nationale (éditable par société).
    """
    if tranches_override:
        # Une table SÉLECTIVE fournie telle quelle garde sa règle ; une liste de
        # paires nue (le cas du barème collé par le vendeur) reste progressive.
        if isinstance(tranches_override, TrancheTable):
            return tranches_override, False
        return list(tranches_override), False
    if utility and str(utility).lower() in UTILITY_TABLES:
        # Q7 — le distributeur est un LIBELLÉ : la grille est la même pour tous.
        return UTILITY_TABLES[str(utility).lower()], False
    return None, False


def _selective_rule(tranches) -> tuple | None:
    """(seuil_kWh, tolérance_kWh) si la table porte la règle SÉLECTIVE, sinon
    None (table purement progressive — comportement historique)."""
    seuil = getattr(tranches, "selective_threshold", None)
    if seuil is None or seuil <= 0:
        return None
    tol = getattr(tranches, "boundary_tolerance", 0.0) or 0.0
    return float(seuil), float(tol)


def _split_tranches(tranches: list, seuil: float) -> tuple:
    """Sépare une table plate en (bandes PROGRESSIVES ≤ seuil, bandes
    SÉLECTIVES > seuil). La bande ouverte (plafond None) est toujours sélective."""
    prog, sel = [], []
    for ceiling, price in tranches:
        if ceiling is not None and ceiling <= seuil:
            prog.append((ceiling, price))
        else:
            sel.append((ceiling, price))
    return prog, sel


def _progressive_bill(kwh_mensuel: float, bandes: list) -> float:
    """Facture PROGRESSIVE (MAD) : chaque kWh au prix de SA tranche."""
    total = 0.0
    remaining = float(kwh_mensuel)
    prev_ceiling = 0.0
    for ceiling, price in bandes:
        if ceiling is None:
            total += remaining * price
            remaining = 0.0
            break
        consumed = min(remaining, ceiling - prev_ceiling)
        total += consumed * price
        remaining -= consumed
        prev_ceiling = ceiling
        if remaining <= 0:
            break
    if remaining > 0 and bandes:
        total += remaining * bandes[-1][1]
    return total


def _monthly_bill_from_kwh(kwh_mensuel: float, tranches: list) -> float:
    """Facture mensuelle TTC (MAD) d'une consommation. SOURCE UNIQUE du prix
    d'un volume mensuel de kWh — miroir EXACT de ``billMAD``
    (apps/web/src/lib/estimatorBrainV2.ts) et de ``monthlyBillFromKwh``
    (frontend/src/features/ventes/solar.js).

    · Table PROGRESSIVE (Lydec, Redal, barème vendeur) : chaque kWh au prix de
      SA tranche — comportement historique inchangé.
    · Table SÉLECTIVE (ONEE, ordre fondateur 18/08) : progressif jusqu'au
      seuil, puis TOUTE la consommation au tarif de sa tranche (tolérance de
      bord incluse), avec un PLANCHER à la facture progressive du seuil — un
      client juste au-dessus du seuil ne paie jamais moins qu'au seuil.

    Monotone non décroissante par construction (les tarifs montent de tranche
    en tranche). 0 kWh → 0 MAD.
    """
    if kwh_mensuel is None or kwh_mensuel <= 0:
        return 0.0
    k = float(kwh_mensuel)
    rule = _selective_rule(tranches)
    if rule is None:
        return _progressive_bill(k, tranches)
    seuil, tol = rule
    prog, sel = _split_tranches(tranches, seuil)
    if k <= seuil:
        return _progressive_bill(k, prog)
    rate = sel[-1][1] if sel else _FALLBACK_KWH_PRICE
    for ceiling, price in sel:
        if ceiling is None or k <= ceiling + tol:
            rate = price
            break
    return max(k * rate, _progressive_bill(seuil, prog))


def _kwh_from_bill_bisect(bill: float, tranches: list) -> float:
    """Inverse NUMÉRIQUE de ``_monthly_bill_from_kwh`` pour une table
    SÉLECTIVE — miroir EXACT de ``billToAnnualKwh``
    (apps/web/src/lib/estimatorBrainV2.ts), au facteur 12 près (ici mensuel).

    RÉSOLUTION DES « TROUS » : une règle sélective rend la facture
    DISCONTINUE (à 210 kWh la facture saute de 210 × 1,0732 = 225,37 MAD à
    210 × 1,1676 = 245,20 MAD — aucune consommation ne produit 235 MAD). La
    dichotomie converge vers ``inf{ k : facture(k) ≥ montant }``, donc un
    montant tombé dans un trou est résolu à la BORNE BASSE du saut (ici
    210 kWh) : on ne fabrique jamais une consommation que le barème ne peut
    pas produire, et on choisit le côté PRUDENT (moins de kWh ⇒ système plus
    petit, économies plus petites — jamais l'inverse). Le miroir JS applique
    exactement la même règle.
    """
    lo = 0.0
    hi = 1000.0
    while _monthly_bill_from_kwh(hi, tranches) < bill and hi < 1e6:
        hi *= 2
    for _ in range(60):
        mid = (lo + hi) / 2
        if _monthly_bill_from_kwh(mid, tranches) < bill:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def kwh_from_bill(bill_mad, utility=None, tranches_override=None) -> dict:
    """QF1 — Inverse EXACT du barème : facture mensuelle (MAD TTC) → kWh/mois.

    · Table PROGRESSIVE : parcourt les tranches en accumulant leur coût jusqu'à
      retrouver la facture, puis interpole linéairement DANS la tranche atteinte
      (inversion analytique exacte du modèle progressif) — inchangé.
    · Table SÉLECTIVE (ONEE) : dichotomie sur ``_monthly_bill_from_kwh``
      (``_kwh_from_bill_bisect``), qui est le vrai inverse d'une fonction
      discontinue ; un montant tombé entre deux marches est résolu à la borne
      basse du saut (voir ``_kwh_from_bill_bisect``). Miroir exact du JS.

    Fonction pure, sans I/O.

    Returns dict:
        kwh_mensuel   float — consommation mensuelle estimée (kWh).
        approximatif  bool  — Q7 : TOUJOURS False. Il n'existe plus de table
                              estimée — les trois distributeurs lisent la
                              grille nationale. Conservé pour ne casser aucun
                              appelant.
        estimation    bool  — True quand AUCUNE table n'est disponible ou que la
                              facture est vide : le chiffre est une estimation
                              (prix plat de repli), jamais présenté comme précis.
        label         str   — ESTIMATION_LABEL quand ``estimation`` est True,
                              '' sinon (Q7 : plus aucune table estimée à
                              étiqueter « approximatif »).
    """
    try:
        bill = float(bill_mad or 0)
    except (TypeError, ValueError):
        bill = 0.0
    if bill <= 0:
        # Facture vide/négative → estimation étiquetée, jamais un chiffre précis.
        return {"kwh_mensuel": 0.0, "approximatif": False,
                "estimation": True, "label": ESTIMATION_LABEL}

    table, approx = _resolve_tranches(utility, tranches_override)
    if table is None:
        # Aucune donnée tarifaire → repli plat, étiqueté « estimation ».
        return {"kwh_mensuel": round(bill / _FALLBACK_KWH_PRICE, 1),
                "approximatif": True, "estimation": True,
                "label": ESTIMATION_LABEL}

    if _selective_rule(table) is not None:
        return {"kwh_mensuel": round(_kwh_from_bill_bisect(bill, table), 1),
                "approximatif": approx, "estimation": False,
                "label": "approximatif" if approx else ""}

    prev_ceiling = 0.0
    cost_so_far = 0.0
    kwh = None
    for ceiling, price in table:
        if ceiling is None:
            kwh = prev_ceiling + (bill - cost_so_far) / price
            break
        tranche_cost = (ceiling - prev_ceiling) * price
        if cost_so_far + tranche_cost >= bill:
            kwh = prev_ceiling + (bill - cost_so_far) / price
            break
        cost_so_far += tranche_cost
        prev_ceiling = ceiling
    if kwh is None:
        # Table sans tranche ouverte (dernier plafond fini) : extrapole au
        # dernier prix connu — comportement cohérent avec _weighted_kwh_price.
        kwh = prev_ceiling + (bill - cost_so_far) / table[-1][1]
    return {"kwh_mensuel": round(kwh, 1), "approximatif": approx,
            "estimation": False, "label": "approximatif" if approx else ""}


def annual_bill_from_kwh(monthly_kwh, utility=None, tranches_override=None) -> dict:
    """QF1 — Facture annuelle TTC (MAD) d'une consommation mensuelle, valorisée
    au barème du distributeur (ONEE sélectif, Lydec/Redal progressifs — voir
    ``_monthly_bill_from_kwh``). Fonction pure.

    Returns dict:
        bill_mensuel  float — facture mensuelle TTC (MAD).
        bill_annuel   float — facture annuelle TTC (MAD) = mensuelle × 12.
        approximatif  bool  — Q7 : toujours False (plus de table estimée).
        estimation    bool  — True quand aucune table n'est disponible (repli
                              plat) ou consommation vide : chiffre étiqueté
                              « estimation », jamais présenté comme précis.
        label         str   — même convention que ``kwh_from_bill``.
    """
    try:
        kwh = float(monthly_kwh or 0)
    except (TypeError, ValueError):
        kwh = 0.0
    if kwh <= 0:
        return {"bill_mensuel": 0.0, "bill_annuel": 0.0,
                "approximatif": False, "estimation": True,
                "label": ESTIMATION_LABEL}

    table, approx = _resolve_tranches(utility, tranches_override)
    if table is None:
        mensuel = kwh * _FALLBACK_KWH_PRICE
        return {"bill_mensuel": round(mensuel, 2),
                "bill_annuel": round(mensuel * 12, 2),
                "approximatif": True, "estimation": True,
                "label": ESTIMATION_LABEL}

    mensuel = _monthly_bill_from_kwh(kwh, table)
    return {"bill_mensuel": round(mensuel, 2),
            "bill_annuel": round(mensuel * 12, 2),
            "approximatif": approx, "estimation": False,
            "label": "approximatif" if approx else ""}


def _weighted_kwh_price(kwh_mensuel: float, tranches: list) -> float:
    """Prix EFFECTIF du kWh (MAD/kWh) pour une consommation mensuelle donnée :
    la facture du mois divisée par ses kWh — une seule source de vérité, celle
    de ``_monthly_bill_from_kwh``.

    · Table PROGRESSIVE : moyenne pondérée des tranches traversées (identique
      au comportement historique).
    · Table SÉLECTIVE (ONEE) : le prix de SA tranche, appliqué à toute la
      consommation — c'est LE « new price per kWh » de l'ordre fondateur, qui
      BAISSE dès que le client repasse sous une marche (700 kWh → 1,5958 ;
      280 kWh → 1,1676).

    Quand ``kwh_mensuel`` vaut 0, renvoie le prix de la première tranche
    (plancher), comme avant.

    Args:
        kwh_mensuel: Monthly kWh consumption.
        tranches:    List of (ceiling_kWh | None, price_MAD_kWh).
                     None ceiling means "no upper bound."

    Returns:
        Effective price in MAD/kWh, or first-tranche price if no consumption.
    """
    if kwh_mensuel <= 0:
        return tranches[0][1] if tranches else _FALLBACK_KWH_PRICE
    return _monthly_bill_from_kwh(kwh_mensuel, tranches) / kwh_mensuel


def _avg_kwh_price_from_tranches(
    conso_annuelle_kwh: float | None,
    utility: str | None,
    tranches_override: list | None,
) -> tuple[float, bool]:
    """Return (prix_moyen_MAD_kWh, is_estimated).

    Priority:
      1. Caller-supplied ``tranches_override`` list.
      2. ``utility`` name matched in UTILITY_TABLES.
      3. Fallback flat price (_FALLBACK_KWH_PRICE) — ``is_estimated = True``.

    When annual consumption is available, converts it to monthly average for the
    weighted-tranche calculation.
    """
    if tranches_override:
        table = tranches_override
    elif utility and utility.lower() in UTILITY_TABLES:
        table = UTILITY_TABLES[utility.lower()]
    else:
        # No tariff data → honest fallback
        return _FALLBACK_KWH_PRICE, True

    kwh_mensuel = (conso_annuelle_kwh / 12) if conso_annuelle_kwh else 0.0
    prix = _weighted_kwh_price(kwh_mensuel, table)
    return prix, False


def two_bills_savings(
    production_kwh,
    conso_annuelle_kwh,
    autoconso_ratio,
    utility=None,
    tranches_override=None,
) -> dict | None:
    """QF2 — Modèle « deux factures » (économies RÉELLES, au barème).

    facture annuelle SANS solaire  = consommation valorisée au barème ;
    facture annuelle AVEC solaire = consommation résiduelle (après les kWh
    autoconsommés) valorisée au barème — au MÊME barème, mais éventuellement
    dans une tranche PLUS BASSE : sur une grille sélective (ONEE), redescendre
    sous une marche re-tarife TOUTE la consommation restante, ce qui vaut plus
    que les seuls kWh effacés (ordre fondateur 18/08) ;
    économie = facture_sans − facture_avec.

    Le mois est l'unité de tarification : on ne divise jamais l'année avant de
    tarifer (le seuil des marches est MENSUEL).

    Self-consumption-first (loi 82-21) : seuls les kWh autoconsommés réduisent
    la facture — le surplus injecté ne vaut rien (tarif ANRE BT non publié).

    Retourne ``None`` quand il manque une VRAIE donnée (pas de table tarifaire,
    pas de consommation, pas de production) : l'appelant dégrade alors vers
    l'ancienne estimation, étiquetée comme telle. Fonction pure.

    Returns dict:
        facture_sans   int  — facture annuelle TTC sans solaire (MAD).
        facture_avec   int  — facture annuelle TTC avec solaire (MAD).
        economie       int  — facture_sans − facture_avec (≥ 0).
        autoconso_kwh  int  — kWh autoconsommés retenus (plafonnés à la conso).
        approximatif   bool — Q7 : toujours False (plus de table estimée).
    """
    table, approx = _resolve_tranches(utility, tranches_override)
    if table is None:
        return None
    try:
        conso = float(conso_annuelle_kwh or 0)
        prod = float(production_kwh or 0)
        ratio = float(autoconso_ratio or 0)
    except (TypeError, ValueError):
        return None
    if conso <= 0 or prod <= 0 or ratio <= 0:
        return None

    facture_sans = round(_monthly_bill_from_kwh(conso / 12, table) * 12)
    autoconso_kwh = min(prod * ratio, conso)
    residuel = max(0.0, conso - autoconso_kwh)
    facture_avec = round(_monthly_bill_from_kwh(residuel / 12, table) * 12)
    # Économie dérivée des factures ARRONDIES : la chaîne affichée
    # facture_sans − facture_avec = économie est exacte au dirham.
    return {
        "facture_sans": facture_sans,
        "facture_avec": facture_avec,
        "economie": max(0, facture_sans - facture_avec),
        "autoconso_kwh": round(autoconso_kwh),
        "approximatif": approx,
    }


# ── QX39 — hypothèses du cashflow 25 ans (source unique, miroir solar.js) ─────
# Documentées et rendues sur le PDF/la proposition ; jamais un chiffre inventé.
CASHFLOW_YEARS = 25
PANEL_DEGRADATION = 0.005        # 0,5 %/an — perte de production annuelle
# QRES54 (fondateur, 2026-07-18) — AUCUNE hausse tarifaire supposée : la
# projection est à tarif constant (la légende du graphe le dit — le modèle
# doit le FAIRE ; l'ancien +2 %/an la contredisait). Seule la dégradation
# panneau (0,5 %/an) érode les économies. Toute hausse réelle du tarif ne
# peut qu'améliorer le résultat.
TARIFF_ESCALATION = 0.0
BATTERY_ROUNDTRIP = 0.90         # rendement aller-retour batterie (option 2)
# ── Q1 (décision fondateur du 20/08/2026) — PROVISION DE REMPLACEMENT ONDULEUR ─
# Le principe mi-vie (IEA PVPS) est confirmé : l'onduleur se remplace vers
# l'année 12. Le MONTANT, lui, n'est plus un pourcentage forfaitaire du CAPEX
# (l'ancien « ≈ 8 % de l'investissement » ne correspondait au prix d'AUCUN
# onduleur réel) : c'est le PRIX TTC de la ligne onduleur du devis, tel qu'il
# est facturé. Aucune ligne onduleur identifiable ⇒ AUCUNE provision, et
# l'hypothèse affichée le DIT. Le palier de la courbe est plus creux qu'avant :
# c'est le chiffre vrai.
INVERTER_REPLACE_YEAR = 12       # remplacement onduleur (année) — optionnel


def compute_cashflow_payback(
    investment: float,
    economie_annee1: float,
    *,
    battery: bool = False,
    years: int = CASHFLOW_YEARS,
    degradation: float = PANEL_DEGRADATION,
    escalation: float = TARIFF_ESCALATION,
    battery_roundtrip: float = BATTERY_ROUNDTRIP,
    battery_share: float | None = None,
    inverter_replace_year: int | None = INVERTER_REPLACE_YEAR,
    inverter_replace_cost: float | None = None,
) -> dict:
    """QX39 — cashflow 25 ans honnête + payback par croisement du cumul à zéro.

    Chaque année : l'économie de base (année 1) est érodée par la dégradation
    panneau (0,5 %/an) MAIS améliorée par l'escalade tarifaire documentée ; la
    batterie applique son rendement aller-retour UNIQUEMENT quand l'option
    porte réellement du stockage (M9 — l'abattement était appliqué
    inconditionnellement, y compris à un devis sans batterie).

    Q1 — ``inverter_replace_cost`` est le PRIX RÉEL de l'onduleur du devis, en
    MAD TTC, retranché à ``inverter_replace_year``. ``None`` ⇒ aucune provision
    (jamais un pourcentage de repli).
    Le payback = première année où le cumul devient ≥ 0 (interpolé dans l'année).
    Renvoie le cashflow annuel, le cumul, le payback (années) et le gain net.

    Z5 (ORDRE FONDATEUR, 20/08/2026) — ``battery_share`` : PART de l'économie qui
    transite RÉELLEMENT par la batterie (0..1). Le rendement aller-retour ne
    s'applique QU'À elle. Sans ce paramètre, le moteur multipliait TOUTE
    l'économie de l'option 2 par 0,90 — y compris la part autoconsommée
    DIRECTEMENT au fil du soleil (le socle de 60 %), qui n'entre jamais dans la
    batterie et ne subit donc aucune perte de charge/décharge. Cette double
    peine allongeait le payback de l'option batterie et rabotait son gain net.
    ``None`` (défaut) conserve le comportement historique pour les appelants
    directs qui n'ont pas la décomposition.
    """
    inv = float(investment or 0)
    base = float(economie_annee1 or 0)
    if base <= 0 or inv <= 0:
        return {
            "payback_years": 0.0, "cashflow": [], "cumulative": [],
            "net_gain": 0.0, "years": years,
        }

    # Z5 — facteur batterie EFFECTIF : la perte aller-retour ne frappe que la
    # part réellement stockée puis restituée. ``battery_share=None`` → forfait
    # historique (0,90 sur tout) ; ``0`` → aucune perte (rien ne transite par la
    # batterie) ; ``1`` → toute l'économie transite (identique au forfait).
    batt_factor = 1.0
    if battery:
        if battery_share is None:
            batt_factor = float(battery_roundtrip)
        else:
            try:
                part = max(0.0, min(1.0, float(battery_share)))
            except (TypeError, ValueError):
                part = 1.0
            batt_factor = 1.0 - (1.0 - float(battery_roundtrip)) * part

    cashflow, cumulative = [], []
    cumul = -inv
    payback = None
    prev_cumul = -inv
    for y in range(1, years + 1):
        prod_factor = (1 - degradation) ** (y - 1)      # dégradation panneau
        tarif_factor = (1 + escalation) ** (y - 1)      # escalade tarifaire
        year_saving = base * prod_factor * tarif_factor
        if battery:
            year_saving *= batt_factor
        year_cf = year_saving
        if (inverter_replace_year and inverter_replace_cost
                and y == inverter_replace_year):
            year_cf -= float(inverter_replace_cost)
        cashflow.append(round(year_cf))
        prev_cumul = cumul
        cumul += year_cf
        cumulative.append(round(cumul))
        # Croisement à zéro → payback interpolé dans l'année.
        if payback is None and cumul >= 0:
            span = cumul - prev_cumul
            frac = (0 - prev_cumul) / span if span else 0.0
            payback = round((y - 1) + frac, 1)

    if payback is None:
        payback = float(years)  # jamais rentabilisé sur l'horizon
    return {
        "payback_years": payback,
        "cashflow": cashflow,
        "cumulative": cumulative,
        "net_gain": round(cumul),
        "years": years,
    }


def _fr_pct(v) -> str:
    """0.5 -> '0,5' ; 2.0 -> '2' (French decimal comma, no trailing zero)."""
    s = f"{float(v):g}"
    return s.replace(".", ",")


def _fr_mad(v) -> str:
    """12345 -> '12 345' (espace fine insécable, format des documents)."""
    return f"{int(round(float(v))):,}".replace(",", " ")


def cashflow_assumptions(inverter_replace_cost=None,
                         stockage: bool = False) -> dict:
    """QX39 — hypothèses documentées du cashflow, rendues sur le PDF/la
    proposition (autoconsommation d'abord ; rachat BT surplus toujours non
    publié ; plafond d'injection 20 % pré-intégré via l'autoconso).

    QRES1 — chaque idée tient en UNE note (la loi 82-21 et le plafond
    d'injection fusionnés ; plus de « performance garantie 25 ans » redondant
    avec les garanties produit) et les pourcentages s'écrivent à la française
    (« 0,5 %/an », jamais « 0.5 »)."""
    # ── M9 (audit du 19/08/2026) — LES DEUX HYPOTHÈSES CACHÉES SONT DITES ────
    # Le rendement aller-retour batterie (90 %) et la provision de remplacement
    # onduleur à l'année 12 changent le résultat affiché ; elles étaient
    # appliquées en silence. Elles s'écrivent désormais dans le bloc
    # « Nos hypothèses », comme la dégradation panneau.
    notes = [
        "Loi 82-21 : seuls les kWh autoconsommés réduisent la facture — "
        "le surplus injecté n'est pas rémunéré (plafond d'injection 20 % "
        "intégré).",
        f"Dégradation panneau {_fr_pct(round(PANEL_DEGRADATION * 100, 2))} "
        "%/an intégrée ; aucune hausse du tarif électrique supposée — "
        "projection à tarif constant, toute hausse réelle améliore votre "
        "résultat.",
    ]
    if stockage:
        notes.append(
            f"Stockage : rendement aller-retour batterie "
            f"{round(BATTERY_ROUNDTRIP * 100)} % appliqué aux kWh qui "
            "transitent par la batterie.")
    # Q1 — le MONTANT de la provision est le prix RÉEL de l'onduleur du devis ;
    # sans ligne onduleur identifiable, la projection le dit au lieu de
    # provisionner un pourcentage inventé.
    if inverter_replace_cost:
        # Z4 (ordre fondateur, 20/08/2026) — cette provision était SILENCIEUSE :
        # elle est le SEUL décrochement de la courbe de rentabilité, et rien ne
        # l'expliquait au client ; une courbe qui change de pente sans raison
        # énoncée se lit comme une erreur. Q1 va plus loin que Z4 : le montant
        # n'est plus « 8 % de l'investissement » (un forfait qui ne
        # correspondait au prix d'AUCUN onduleur réel) mais le prix FACTURÉ de
        # l'onduleur de ce devis. La raison ET le vrai chiffre voyagent ensemble.
        notes.append(
            f"Provision de remplacement de l'onduleur en année "
            f"{INVERTER_REPLACE_YEAR} : {_fr_mad(inverter_replace_cost)} MAD "
            "(le prix de l'onduleur de ce devis) — c'est le palier visible sur "
            "la courbe de rentabilité.")
    else:
        notes.append(
            "Projection établie hors provision de remplacement onduleur "
            "(aucun onduleur chiffré sur ce devis).")
    return {
        "years": CASHFLOW_YEARS,
        "degradation_pct": round(PANEL_DEGRADATION * 100, 2),
        "escalation_pct": round(TARIFF_ESCALATION * 100, 1),
        "battery_roundtrip_pct": round(BATTERY_ROUNDTRIP * 100),
        "battery_roundtrip_applique": bool(stockage),
        "inverter_replace_year": INVERTER_REPLACE_YEAR,
        # Montant RÉEL provisionné (MAD TTC) ou None — lu par la légende de la
        # courbe 25 ans, qui affiche le chiffre plutôt qu'un pourcentage.
        "inverter_replace_cost": (round(float(inverter_replace_cost))
                                  if inverter_replace_cost else None),
        "notes": notes,
    }


#: CJ2a — écart RELATIF de puissance au-delà duquel un bloc horaire est jugé
#: PÉRIMÉ. Le bloc est calculé pour une puissance donnée ; si le devis a été
#: repuissancé depuis (lignes éditées, panneaux ajoutés) sans que l'étude soit
#: rafraîchie, ses économies ne décrivent plus CE devis. 2 % absorbe les
#: arrondis kWc/panneaux sans laisser passer un vrai changement de taille.
_HORAIRE_TOLERANCE_KWC = 0.02


def _lire_etude_horaire(bloc, puissance_kwc=None) -> dict | None:
    """CJ2a — lit le bloc ``etude_params['etude_horaire']`` de façon DÉFENSIVE.

    Renvoie ``None`` dès que le bloc est absent, malformé, ou ne porte pas les
    grandeurs indispensables (production et consommation strictement
    positives) : l'appelant garde alors son modèle « factures » ou son forfait
    étiqueté. Un bloc douteux ne doit JAMAIS remplacer un calcul honnête.

    La série mensuelle n'est retenue que si elle compte exactement 12 mois :
    une série partielle (un mois sans forme PVGIS) reste une information utile
    dans le bloc d'étude, mais ne peut pas servir de répartition annuelle.

    Fonction pure — ``pricing`` n'importe rien (pas même ``etude_horaire``) :
    il reçoit un dict déjà calculé, exactement comme il reçoit ``etude``.
    """
    if not isinstance(bloc, dict):
        return None
    annuel = bloc.get("annuel")
    mois = bloc.get("mois")
    if not isinstance(annuel, dict) or not isinstance(mois, list):
        return None
    try:
        prod = float(annuel.get("production_kwh") or 0)
        conso = float(annuel.get("consommation_kwh") or 0)
        eco_sans = float(annuel.get("economie_sans_mad") or 0)
        eco_avec = float(annuel.get("economie_avec_mad") or 0)
        auto_sans = float(annuel.get("taux_autoconso_sans") or 0)
        auto_avec = float(annuel.get("taux_autoconso_avec") or 0)
    except (TypeError, ValueError):
        return None
    if prod <= 0 or conso <= 0:
        return None
    if len(mois) != 12:
        return None

    # GARDE ANTI-PÉRIMÉ : le bloc dit pour quelle puissance il a été calculé.
    # Si le devis ne fait plus cette puissance, ses chiffres décrivent une
    # AUTRE installation — on préfère le repli honnête à un chiffre précis et
    # faux (c'est la même logique que la règle Z2, appliquée à la fraîcheur).
    if puissance_kwc:
        try:
            kwc_bloc = float(bloc.get("kwc") or 0)
            kwc_devis = float(puissance_kwc)
        except (TypeError, ValueError):
            return None
        if kwc_bloc <= 0 or kwc_devis <= 0:
            return None
        if abs(kwc_bloc - kwc_devis) / kwc_devis > _HORAIRE_TOLERANCE_KWC:
            return None
    try:
        eco_s_monthly = [round(float(m["economie_sans_mad"])) for m in mois]
        eco_a_monthly = [round(float(m["economie_avec_mad"])) for m in mois]
    except (TypeError, ValueError, KeyError):
        return None

    # ── CJ2b — LA SÉRIE « AVANT » DU BLOC HORAIRE ────────────────────────────
    # Douze factures MENSUELLES, reconstituées par le barème à partir de la
    # consommation du mois — laquelle descend elle-même des factures RÉELLES
    # du client (inversion du barème, cf. ``etude_horaire.profil_depuis_
    # factures``). Ce n'est donc PAS le proxy circulaire que M1 a tué (« facture
    # ≈ économie supposée ÷ taux forfaitaire ») : la chaîne part d'un montant
    # réellement payé et y revient. Elle rend au document sa série « avant »
    # quand le client n'a donné qu'une facture d'hiver au lieu des douze.
    #
    # Garde STRICTE, comme partout ailleurs ici : douze valeurs numériques
    # strictement positives, sinon ``None`` — le reste du bloc reste utilisable
    # (les économies ne dépendent pas de cette série).
    factures_avant = None
    try:
        _candidats = [float(m["facture_avant_mad"]) for m in mois]
        if len(_candidats) == 12 and all(v > 0 for v in _candidats):
            factures_avant = [round(v) for v in _candidats]
    except (TypeError, ValueError, KeyError):
        factures_avant = None

    def _entier(valeur):
        try:
            return round(float(valeur))
        except (TypeError, ValueError):
            return None

    return {
        "prod_kwh": round(prod),
        "eco_sans": round(eco_sans),
        "eco_avec": round(eco_avec),
        "autoconso_sans": auto_sans,
        "autoconso_avec": auto_avec,
        "facture_sans": _entier(annuel.get("facture_avant_mad")),
        "facture_avec_s": _entier(annuel.get("facture_apres_sans_mad")),
        "facture_avec_a": _entier(annuel.get("facture_apres_avec_mad")),
        "eco_s_monthly": eco_s_monthly,
        "eco_a_monthly": eco_a_monthly,
        # CJ2b — série « avant » + provenance de la consommation, pour que le
        # document sache si la VARIATION mensuelle est mesurée ou répétée.
        "factures_avant_monthly": factures_avant,
        "source_consommation": (bloc.get("source_consommation") or None),
    }


def calculate_savings_roi(
    puissance_kwc: float,
    total_sans: float,
    total_avec: float,
    *,
    conso_annuelle_kwh: float | None = None,
    utility: str | None = None,
    tarif_kwh_override: float | None = None,
    tranches_override: list | None = None,
    autoconso_sans: float = AUTOCONSO_SANS,
    autoconso_avec: float = AUTOCONSO_AVEC,
    battery_kwh: float | None = None,
    productible: float | None = None,
    fallback_tarif_kwh: float | None = None,
    # M9 — l'option 2 porte-t-elle RÉELLEMENT du stockage ? L'abattement de
    # rendement aller-retour (×0,90) était appliqué inconditionnellement, y
    # compris à un devis SANS batterie : la projection était pénalisée par un
    # équipement absent. None ⇒ déduit de ``battery_kwh``.
    stockage_present: bool | None = None,
    # Q1 — prix TTC RÉEL de l'onduleur de chaque option (provision de
    # remplacement à l'année 12). None ⇒ aucune provision pour cette option.
    inverter_cost_sans: float | None = None,
    inverter_cost_avec: float | None = None,
    # CJ2a — bloc ``etude_params['etude_horaire']`` calculé par
    # ``apps.ventes.etude_horaire``. Présent et valide ⇒ il REMPLACE le modèle
    # forfaitaire (voir le bloc « LE MODÈLE HORAIRE PREND LA MAIN » plus bas).
    # Absent ⇒ comportement byte-identique à avant CJ2a.
    etude_horaire: dict | None = None,
) -> dict:
    """Auto-compute annual production, savings and ROI — loi 82-21 model.

    SELF-CONSUMPTION-FIRST (loi 82-21): savings = self-consumed kWh × avoided
    tariff.  Surplus injected to the grid is NOT valued (ANRE BT net-billing
    tariff is unpublished; adding it would fabricate income).

    Tariff resolution order (first wins):
      1. ``tarif_kwh_override`` (explicit flat price — seller sets it)
      2. ``tranches_override`` (caller-supplied schedule)
      3. ``utility`` name → ONEE / Lydec / Redal table
      4. _FALLBACK_KWH_PRICE (flat 1.20 MAD/kWh) — labelled ESTIMATION

    When the fallback fires, the returned dict carries ``savings_estimated=True``
    so callers can label the figure « estimation » and never show it as precise.

    Formulas:
      production_annuelle   = kwc × 1 240 kWh/kWc/an  (GHI moyen Maroc)
      economie_opt1 (sans)  = production × autoconso_sans_eff × prix_kWh
                              où autoconso_sans_eff = min(autoconso_sans,
                              conso/production) quand la conso est connue —
                              on ne valorise jamais des kWh que le client ne
                              consomme pas (correctif 18/08).
      economie_opt2 (avec)  = production × autoconso_avec × prix_kWh
                              où autoconso_avec est DÉRIVÉ de la capacité
                              batterie quand ``battery_kwh`` est fourni
                              (60 % + capacité × 1 cycle/jour, plafonné) —
                              ordre fondateur 18/08.
      roi                   = total_option / economie_annuelle
      monthly               = economie_annuelle × facteur_saisonnier

    Returns a dict directly usable to fill the premium PDF data dict.
    Additional keys vs. the legacy dict:
      ``savings_estimated``   True when tariff data was absent → degrade honestly.
      ``autoconso_sans``      Self-consumption ratio used for option 1.
      ``autoconso_avec``      Self-consumption ratio used for option 2.
      ``tarif_kwh``           Effective kWh price used for the calculation.
      ``utility``             Distributor name resolved (or None).
    """
    # DC2 — productible : repère société (CompanyProfile.productible_kwh_kwc)
    # quand fourni, sinon défaut historique 1240 (byte-identique).
    # Pertes système 20 % AU TOTAL (fondateur 18/08) : le productible stocké
    # étant déjà net de 14 % (PVGIS loss=14), on n'applique que le complément
    # PRODUCTION_DERATE ≈ 0,9302. Toute la chaîne (économies, factures par
    # tranches, couverture, cashflow) raisonne sur cette production NETTE.
    prod_factor = float(productible) if productible and productible > 0 \
        else _DEFAULT_PRODUCTIBLE
    production_annuelle = round(
        puissance_kwc * prod_factor * PRODUCTION_DERATE)

    # Tariff resolution
    if tarif_kwh_override is not None and tarif_kwh_override > 0:
        prix_kwh = float(tarif_kwh_override)
        savings_estimated = False
    else:
        prix_kwh, savings_estimated = _avg_kwh_price_from_tranches(
            conso_annuelle_kwh, utility, tranches_override)
        # DC2 — quand aucune donnée tarifaire n'existe (repli 1.20 « estimation »),
        # préférer le tarif ONEE de la société (CompanyProfile.onee_tarif_kwh) s'il
        # est fourni. Reste marqué « estimation » (pas de données de conso).
        if savings_estimated and fallback_tarif_kwh and fallback_tarif_kwh > 0:
            prix_kwh = float(fallback_tarif_kwh)

    # ORDRE FONDATEUR (18/08) — taux « avec batterie » DÉRIVÉ de la capacité
    # réellement chiffrée sur le devis (60 % + capacité × 1 cycle/jour,
    # plafonné par la production ET par la consommation connue). Sans capacité
    # (``battery_kwh`` absent/0), l'ancien forfait ``autoconso_avec`` reste le
    # repli — aucun devis existant ne change de chiffre sans raison.
    autoconso_avec = autoconso_avec_ratio(
        production_annuelle, battery_kwh,
        base=autoconso_sans, fallback=autoconso_avec,
        conso_annuelle_kwh=conso_annuelle_kwh)

    # ── PLAFOND CONSOMMATION DU CÔTÉ « SANS » (correctif 18/08) ──────────────
    # ``autoconso_avec_ratio`` plafonne le côté AVEC par la consommation réelle
    # (on ne décale pas des kWh que le client ne consomme pas) — le côté SANS,
    # lui, restait au forfait 0,60 de la PRODUCTION. Sur une petite conso face
    # à une grosse production, le modèle « estimation » valorisait donc côté
    # SANS des kWh inexistants et l'option BATTERIE économisait MOINS que
    # l'option sans batterie sur le PDF client (8 kWc / 5 000 kWh/an /
    # 10 kWh : 6 644 MAD sans contre 6 000 MAD avec).
    #   autoconso_sans_eff = min(autoconso_sans, conso / production)
    #   autoconso_avec     = max(autoconso_avec, autoconso_sans_eff)
    # Le second plancher tient l'INVARIANT « avec ≥ sans » même quand le
    # vendeur force un ``autoconso_avec`` plus bas que le taux sans batterie.
    # Sur le modèle « factures » le plafond est un NO-OP exact
    # (``two_bills_savings`` borne déjà les kWh autoconsommés à la conso) :
    # aucun devis existant ne change de chiffre. MIROIR solar.js computeROI.
    autoconso_sans_eff = float(autoconso_sans)
    try:
        _conso_plafond = float(conso_annuelle_kwh or 0)
    except (TypeError, ValueError):
        _conso_plafond = 0.0
    if _conso_plafond > 0 and production_annuelle > 0:
        autoconso_sans_eff = min(
            autoconso_sans_eff, _conso_plafond / production_annuelle)
    autoconso_avec = max(autoconso_avec, autoconso_sans_eff)

    # Self-consumption-first savings (loi 82-21: only self-consumed kWh valued)
    economie_opt1 = round(production_annuelle * autoconso_sans_eff * prix_kwh)
    economie_opt2 = round(production_annuelle * autoconso_avec * prix_kwh)

    # QF2 — modèle « deux factures » (réel, par tranche) : quand une VRAIE
    # consommation ET une table tarifaire existent (et qu'aucun prix plat
    # vendeur ne force l'ancien modèle), l'économie devient
    # facture_sans − facture_avec, les deux factures valorisées PAR TRANCHE.
    # Sinon : ancienne approximation production × autoconso × prix, étiquetée
    # « estimation » — aucun chiffre inventé.
    savings_model = "estimation"
    facture_sans = facture_avec_s = facture_avec_a = None
    factures_approximatif = False
    if not (tarif_kwh_override is not None and tarif_kwh_override > 0):
        _tb_s = two_bills_savings(
            production_annuelle, conso_annuelle_kwh, autoconso_sans_eff,
            utility=utility, tranches_override=tranches_override)
        _tb_a = two_bills_savings(
            production_annuelle, conso_annuelle_kwh, autoconso_avec,
            utility=utility, tranches_override=tranches_override)
        if _tb_s and _tb_a:
            savings_model = "factures"
            economie_opt1 = _tb_s["economie"]
            economie_opt2 = _tb_a["economie"]
            facture_sans = _tb_s["facture_sans"]
            facture_avec_s = _tb_s["facture_avec"]
            facture_avec_a = _tb_a["facture_avec"]
            factures_approximatif = _tb_s["approximatif"]

    # ── CJ2a (ORDRE FONDATEUR) — LE MODÈLE HORAIRE PREND LA MAIN ────────────
    # « the total saving should be function of [saisons] and not just assuming
    # client will consume 60 % of total pv production but rather follow the
    # consumption curves fixed in the call ».
    #
    # Quand ``apps.ventes.etude_horaire`` a pu calculer (factures RÉELLES +
    # localisation PVGIS résolue), ses chiffres REMPLACENT tout ce qui précède :
    # ils sortent de l'intégration heure par heure de la production PVGIS réelle
    # contre la courbe de consommation RÉELLE du client, mois par mois, chaque
    # mois valorisé au barème. Les forfaits ``AUTOCONSO_SANS``/``AUTOCONSO_AVEC``
    # ne survivent que comme REPLI, quand le moteur horaire n'a rien pu ancrer —
    # et restent alors étiquetés « estimation » (règle Z2 : on omet plutôt que
    # de déguiser un forfait en mesure).
    #
    # Placé ICI, AVANT le cashflow : le payback, la part batterie et la courbe
    # 25 ans se recalculent tous sur les économies réelles. L'override
    # industriel/commercial de ``builder`` (étude saisie par le vendeur) passe
    # APRÈS et reste souverain — un chiffre saisi par un humain bat un calcul.
    eco_monthly_reel = None
    # CJ2b — série « avant » servie par le bloc horaire, et provenance de la
    # consommation qui la porte. Restent None hors modèle horaire : le document
    # garde alors EXACTEMENT son comportement d'avant.
    factures_avant_horaire = None
    source_consommation_horaire = None
    _h = _lire_etude_horaire(etude_horaire, puissance_kwc)
    if _h:
        savings_model = "horaire"
        savings_estimated = False
        factures_approximatif = False
        production_annuelle = _h["prod_kwh"]
        # Le productible RENDU doit décrire la production rendue, sinon
        # « production ÷ kWc » et « productible » se contrediraient sur la
        # même page. Ici il devient le productible NET réellement obtenu au
        # point du chantier (PVGIS × pertes), pas le repère société.
        if puissance_kwc:
            prod_factor = production_annuelle / float(puissance_kwc)
        economie_opt1 = _h["eco_sans"]
        economie_opt2 = _h["eco_avec"]
        autoconso_sans_eff = _h["autoconso_sans"]
        autoconso_avec = max(_h["autoconso_avec"], _h["autoconso_sans"])
        facture_sans = _h["facture_sans"]
        facture_avec_s = _h["facture_avec_s"]
        facture_avec_a = _h["facture_avec_a"]
        eco_monthly_reel = (_h["eco_s_monthly"], _h["eco_a_monthly"])
        factures_avant_horaire = _h.get("factures_avant_monthly")
        source_consommation_horaire = _h.get("source_consommation")

    # ── QX39 — retour sur investissement par CASHFLOW 25 ans (honnête) ────────
    # Le payback n'est plus un simple ratio année-1 (ni conservateur, ni
    # optimiste) : on cumule le cashflow réel avec dégradation panneau 0,5 %/an,
    # une hypothèse DOCUMENTÉE d'escalade tarifaire, le rendement aller-retour
    # de la batterie (option 2), et un remplacement onduleur optionnel. Le
    # payback = première année où le cumul devient positif (interpolée). Repli
    # sûr sur le ratio année-1 quand l'économie est nulle.
    # Z5 (ORDRE FONDATEUR, 20/08/2026) — le rendement aller-retour de la batterie
    # ne frappe QUE la part de l'économie qui transite par elle. Cette part est
    # DÉRIVÉE des taux déjà calculés : le socle ``autoconso_sans_eff`` est
    # autoconsommé DIRECTEMENT au fil du soleil (aucune charge/décharge), et seul
    # le supplément apporté par la capacité batterie
    # (``autoconso_avec - autoconso_sans_eff``) est stocké puis restitué. Avant
    # ce correctif, 0,90 s'appliquait à 100 % de l'économie : la part directe
    # payait une perte de batterie qu'elle ne subit pas, ce qui ALLONGEAIT
    # artificiellement le payback de l'option « avec batterie ».
    _batt_part = 0.0
    if autoconso_avec > 0:
        _batt_part = max(0.0, (autoconso_avec - autoconso_sans_eff)) / autoconso_avec
    # M9 (audit du 19/08/2026) — l'abattement ne s'applique QU'À une option qui
    # porte RÉELLEMENT du stockage : ``battery=True`` était codé en dur, donc un
    # devis sans batterie subissait quand même la perte d'un équipement absent.
    # Il se combine à Z5 : Z5 borne la perte à la part stockée, M9 la supprime
    # entièrement quand il n'y a rien à stocker.
    # Q1 (décision fondateur du 20/08/2026) — la provision de remplacement est
    # le prix TTC RÉEL de la ligne onduleur de CETTE option, jamais un
    # pourcentage du total ; aucune ligne onduleur ⇒ aucune provision.
    _stockage = (bool(battery_kwh and battery_kwh > 0)
                 if stockage_present is None else bool(stockage_present))
    cf_s = compute_cashflow_payback(
        total_sans, economie_opt1,
        inverter_replace_cost=inverter_cost_sans)
    cf_a = compute_cashflow_payback(
        total_avec, economie_opt2, battery=_stockage,
        battery_share=_batt_part,
        inverter_replace_cost=inverter_cost_avec)
    roi_opt1 = cf_s["payback_years"] if economie_opt1 > 0 else 0.0
    roi_opt2 = cf_a["payback_years"] if economie_opt2 > 0 else 0.0

    # Répartition mensuelle saisonnière.
    # CJ2a — quand le moteur horaire a calculé, les douze valeurs sont les
    # économies RÉELLEMENT calculées mois par mois (production PVGIS du mois ×
    # courbe de consommation du mois, valorisées au barème) : la saisonnalité
    # cesse d'être une clé de répartition. Sinon, repli sur les douze facteurs
    # historiques ci-dessous (somme = 1,000), qui restent une CLÉ de forme
    # appliquée à un total annuel — jamais douze calculs.
    if eco_monthly_reel:
        eco_s_monthly, eco_a_monthly = eco_monthly_reel
    else:
        _SF = [0.053, 0.062, 0.083, 0.098, 0.114, 0.116,
               0.116, 0.101, 0.087, 0.070, 0.052, 0.048]
        eco_s_monthly = [round(economie_opt1 * f) for f in _SF]
        eco_a_monthly = [round(economie_opt2 * f) for f in _SF]

    return {
        "prod_kwh":         production_annuelle,
        "eco_s_ann":        economie_opt1,
        "eco_a_ann":        economie_opt2,
        "eco_a_cumul":      economie_opt2,   # même taux utilisé pour la courbe ROI
        "roi_s":            roi_opt1,
        "roi_a":            roi_opt2,
        "eco_s_monthly":    eco_s_monthly,
        "eco_a_monthly":    eco_a_monthly,
        # Metadata for honest rendering
        "savings_estimated": savings_estimated,
        # Taux SANS batterie EFFECTIVEMENT appliqué (plafonné par la conso).
        "autoconso_sans":   autoconso_sans_eff,
        "autoconso_avec":   autoconso_avec,
        "tarif_kwh":        prix_kwh,
        "utility":          utility,
        # Modèle d'économie effectivement employé, du plus fort au plus faible :
        #   'horaire'    — CJ2a : intégration heure par heure de la production
        #                  PVGIS réelle contre la courbe de consommation réelle
        #                  du client, mois par mois, valorisée au barème ;
        #   'factures'   — QF2 : facture_sans − facture_avec, par tranche, mais
        #                  sur un taux d'autoconsommation forfaitaire ;
        #   'estimation' — repli étiqueté : production × forfait × prix moyen.
        "savings_model":    savings_model,
        # CJ2b — les douze factures « avant » reconstituées par le moteur
        # horaire (None hors modèle 'horaire'), et la provenance de la
        # consommation qui les porte ('facture_hiver', 'facture_hiver_ete',
        # 'factures_mensuelles_reelles', 'kwh_mensuels_saisis'). Le document
        # s'en sert pour retrouver son graphe mensuel ET pour dire honnêtement
        # si la VARIATION d'un mois à l'autre est mesurée ou répétée.
        "factures_avant_monthly": factures_avant_horaire,
        "source_consommation":    source_consommation_horaire,
        "facture_sans":     facture_sans,
        "facture_avec_s":   facture_avec_s,
        "facture_avec_a":   facture_avec_a,
        "factures_approximatif": factures_approximatif,
        # QK4 — productible réellement utilisé (kWh/kWc/an), pour transparence.
        "productible":      prod_factor,
        # QX39 — cashflow 25 ans honnête (dégradation/escalade/batterie/onduleur)
        # + hypothèses documentées, rendus sur le PDF/la proposition.
        "cashflow_sans":    cf_s["cumulative"],
        "cashflow_avec":    cf_a["cumulative"],
        "net_gain_sans":    cf_s["net_gain"],
        "net_gain_avec":    cf_a["net_gain"],
        # Les hypothèses RENDUES décrivent CE devis : provision onduleur réelle
        # (ou son absence explicite) et abattement batterie seulement s'il
        # s'applique. L'option affichée en priorité est l'option 2 quand elle
        # existe, sinon l'option 1 — même choix que la courbe 25 ans.
        "cashflow_assumptions": cashflow_assumptions(
            inverter_replace_cost=(inverter_cost_avec if _stockage
                                   else inverter_cost_sans),
            stockage=_stockage),
    }

"""CJ2a — Barème BIDIRECTIONNEL kWh ⇄ MAD, ÉTALONNÉ SUR FACTURES RÉELLES.

ORDRE FONDATEUR (CJ2) : « the consumption curve should be derived from client
consumption, back-calculating the kwh he consumed looking at his bill and
tranches » et « don't forget the rent of compteur and media tax in both
calculators kwh→mad and mad→kwh ».

SOURCE PRIMAIRE : TROIS FACTURES RÉELLES du fondateur (SRM Casablanca-Settat,
BT DOMESTIQUE, même compteur, zone Nouaceur). Elles ne sont pas un « à
confirmer » de plus : elles PROUVENT le modèle, ligne à ligne, au centime.

  FACTURE A — n° 643769639 du 08/05/2026, période 22/03→21/04/2026, 30 jours,
              359 kWh, TVA 20 %.
              énergie 359 × 1,15142 HT = 413,36 → 496,03 TTC
              location compteur 18,28 HT → 21,94 TTC
              entretien branchement 15,00 HT → 18,00 TTC
              TPPAN 47,33 HT → 56,80 TTC
              TOTAL 592,77 TTC · en espèces 594,25 (timbre 0,25 %)
  FACTURE B — 20/12/2025, période 20/10→20/11/2025, 31 jours, 572 kWh, TVA 18 %.
  FACTURE C — 20/01/2026, période 20/11→19/12/2025, 29 jours, 432 kWh, TVA 18 %.

Le modèle codé ici REPRODUIT LA FACTURE A À 0,01 MAD PRÈS, total et timbre
compris (test ``test_bareme_factures_reelles``).

CE QUE LES FACTURES TRANCHENT (des questions qui traînaient « à confirmer ») :

* Le barème est bien SÉLECTIF : 359 kWh sont facturés EN ENTIER au prix de la
  tranche 5, pas tranche par tranche. Prouvé.
* La TPPAN est bien PROGRESSIVE (0,10 / 0,15 / 0,20), avec des BORNES
  PRORATISÉES AUX JOURS de la période — plus une inférence : 100 × 0,10 +
  100 × 0,15 + 159 × 0,20 = 56,80, exactement la ligne de la facture A.
* La TPPAN EST ASSUJETTIE À LA TVA : le barème 1996 produit le montant TTC, et
  le HT imprimé n'en est que la décomposition (TTC ÷ 1,20 = 47,33). L'inconnue
  est levée.
* Il y a DEUX lignes fixes, pas une : location du compteur ET entretien du
  branchement. La seconde manquait à toutes nos estimations.
* Le timbre de 0,25 % est bien un FRAIS DE MODE DE PAIEMENT (espèces) et non
  une composante du kWh : exclu du calcul, comme prévu.

CE QUE LES FACTURES CORRIGENT (voir :data:`DIVERGENCES_PRICING`) : la tranche 5
2026 vaut 1,381704 TTC, PAS 1,405116. Le repo avait extrapolé le passage de TVA
18 → 20 % « à HT constant » ; la facture A montre que c'est le TTC qui est resté
constant (le HT a été ABAISSÉ de 1,17094 à 1,15142). Deux factures le prouvent
sur la tranche 5 (A en 2026, C en 2025 : même TTC 1,3817).

PAS DE TROISIÈME IMPLÉMENTATION DU BARÈME. Ce module réutilise la mécanique
progressif/sélectif de ``pricing._monthly_bill_from_kwh`` et son type
``TrancheTable``. Il n'y touche pas : ``pricing.ONEE_TRANCHES`` reste
INCHANGÉE, donc ``test_tariff_drift_lock`` reste vert et AUCUN devis existant
ne change de chiffre. Les corrections prouvées vivent ici, dans le moteur
CJ2a, et sont listées pour que le fondateur décide de les propager.

Fonctions PURES : aucun I/O, aucun ORM, aucun Django (comme ``pricing.py``).
"""
from __future__ import annotations

from .pricing import (
    ONEE_TRANCHES,
    TrancheTable,
    _monthly_bill_from_kwh,
    _resolve_tranches,
)

# ════════════════════════════════════════════════════════════════════════════
# 1. MILLÉSIMES — un barème par année de TVA, chacun avec sa PROVENANCE
# ════════════════════════════════════════════════════════════════════════════
# La TVA sur l'électricité suit la trajectoire de la loi de finances 2024 :
# 14 % → 16 % (2024) → 18 % (2025) → 20 % (2026). Les factures montrent que
# les lignes N'ONT PAS TOUTES LE MÊME TAUX à une date donnée (facture B,
# décembre 2025 : énergie 18 %, location du compteur 15 %, entretien 20 %) —
# d'où un taux PAR LIGNE et non un taux global.
#
# Un millésime est nécessaire pour deux raisons concrètes : reproduire une
# facture 2025 que le client présente, et savoir de quelle année vient chaque
# prix qu'on affiche.

#: Millésime appliqué par défaut (l'année en vigueur).
MILLESIME_COURANT = 2026

# ── PRIX TTC PAR TRANCHE, AVEC PROVENANCE LIGNE À LIGNE ─────────────────────
# `PROVENANCE_TRANCHES` documente, pour CHAQUE tranche de CHAQUE millésime,
# d'où sort le nombre. « facture » = prouvé par une facture réelle ci-dessus.
# « extrapolé » = déduit d'une hypothèse, donc discutable — et signalé.
#
# HYPOTHÈSE EN CONFLIT, NON TRANCHÉE ICI (il faut une facture) :
#   · mécanisme OBSERVÉ (tranche 5, deux factures) : au changement de TVA, le
#     prix TTC reste CONSTANT et le HT est ajusté à la baisse ;
#   · mécanisme SUPPOSÉ par le repo (pricing.py) : le HT reste constant et le
#     TTC monte mécaniquement.
# Les deux ne peuvent pas être vrais en même temps. Pour les tranches sans
# facture 2026, on GARDE la valeur actuelle du repo (aucun chiffre ne bouge
# sans preuve) et on note l'alternative. Voir :data:`DIVERGENCES_PRICING`.

#: Barème 2025 — TTC. Les tranches 5 et 6 sont PROUVÉES par les factures C et B.
TRANCHES_2025 = TrancheTable(
    [
        (100, 0.901000),    # extrapolé (repo) — aucune facture T1 2025
        (150, 1.073200),    # extrapolé (repo) — aucune facture T2 2025
        (200, 1.073200),    # extrapolé (repo) — aucune facture T3 2025
        (300, 1.167600),    # extrapolé (repo) — aucune facture T4 2025
        (500, 1.381709),    # PROUVÉ facture C : 1,17094 HT × 1,18
        (None, 1.595808),   # PROUVÉ facture B : 1,35238 HT × 1,18
    ],
    selective_threshold=150,
    boundary_tolerance=10,
)

#: Barème 2026 — TTC. SEULE la tranche 5 est prouvée ; elle CORRIGE le repo.
TRANCHES_2026 = TrancheTable(
    [
        (100, 0.916272),    # extrapolé (repo, HT constant) — non prouvé 2026
        (150, 1.091388),    # extrapolé (repo, HT constant) — non prouvé 2026
        (200, 1.091388),    # extrapolé (repo, HT constant) — non prouvé 2026
        (300, 1.187388),    # extrapolé (repo, HT constant) — non prouvé 2026
        (500, 1.381704),    # PROUVÉ facture A : 1,15142 HT × 1,20 — CORRIGE
                            # le 1,405116 du repo (TTC constant, pas HT).
        (None, 1.622856),   # CONFLIT — voir DIVERGENCES_PRICING
    ],
    selective_threshold=150,
    boundary_tolerance=10,
)

#: Ce que le moteur CJ2a calcule DIFFÉREMMENT de ``pricing.ONEE_TRANCHES``, et
#: pourquoi. Rendu tel quel dans le bloc d'étude pour que l'écart soit VISIBLE
#: et non enfoui. Un test épingle cette liste : elle ne peut pas dériver en
#: silence, et le jour où le fondateur propage la correction dans
#: ``pricing.py``, il faudra la mettre à jour EXPRÈS.
DIVERGENCES_PRICING = (
    {
        'tranche': '311-510 kWh (T5), millésime 2026',
        'valeur_moteur': 1.381704,
        'valeur_pricing': 1.405116,
        'statut': 'corrigé',
        'preuve': "facture SRM n° 643769639 du 08/05/2026 : 359 kWh × "
                  "1,15142 HT = 413,36 HT / 496,03 TTC. Corroboré par la "
                  "facture du 20/01/2026 (T5 2025 = 1,3817 TTC) : le TTC est "
                  "resté CONSTANT au passage TVA 18 → 20 %, le HT a baissé. "
                  "Le repo avait supposé l'inverse (HT constant).",
    },
    {
        'tranche': '> 510 kWh (T6), millésime 2026',
        'valeur_moteur': 1.622856,
        'valeur_pricing': 1.622856,
        'statut': 'conflit_non_tranché',
        'preuve': "AUCUNE facture T6 de 2026 disponible. Le 1,622856 du repo "
                  "se dit « ancré sur facture réelle » (HT 1,35238 × 1,20) ; "
                  "mais le mécanisme PROUVÉ sur T5 (TTC constant) donnerait "
                  "1,5958. Les deux valeurs sont plausibles et incompatibles. "
                  "On GARDE la valeur du repo (ne rien bouger sans preuve) — "
                  "À TRANCHER sur la prochaine facture T6 2026.",
    },
)

#: Taux de TVA PAR LIGNE et par millésime — relevés sur les factures.
#: La TPPAN n'y figure pas : son barème produit directement un montant TTC
#: (prouvé facture A), le taux ne sert donc qu'à re-afficher son HT.
TVA_PAR_MILLESIME = {
    2026: {'energie': 0.20, 'location': 0.20, 'entretien': 0.20, 'tppan': 0.20},
    # Facture B (décembre 2025) : trois taux DIFFÉRENTS sur la même facture.
    2025: {'energie': 0.18, 'location': 0.15, 'entretien': 0.20, 'tppan': 0.18},
}

MILLESIMES = {
    2026: TRANCHES_2026,
    2025: TRANCHES_2025,
}

# ── CHARGES FIXES MENSUELLES (HT) — relevées sur les trois factures ─────────
# Identiques sur les trois relevés (même compteur, même zone). Ce sont des
# DÉFAUTS SOURCÉS, pas des constantes universelles : une autre zone / un autre
# calibre de compteur peut différer, d'où le réglage société
# ``parametres.TariffSettings.redevance_compteur_mad_mois`` qui les remplace
# en bloc quand il est renseigné.
CHARGE_LOCATION_COMPTEUR_HT = 18.28    # « LOCATION DU COMPTEUR », 3 factures
CHARGE_ENTRETIEN_BRANCHEMENT_HT = 15.00  # « ENTRETIEN DU BRANCHEMENT », idem

CHARGES_FIXES_SOURCE = (
    'factures SRM Casablanca-Settat du fondateur (08/05/2026, 20/12/2025, '
    '20/01/2026) — location du compteur 18,28 HT + entretien du branchement '
    '15,00 HT ; montants identiques sur les trois relevés'
)

# ── TIMBRE ESPÈCES — DÉLIBÉRÉMENT HORS CALCUL ──────────────────────────────
# Facture A : 592,77 en virement/prélèvement, 594,25 en espèces — soit
# exactement +0,25 %. C'est un FRAIS DE MODE DE PAIEMENT, pas une composante
# du prix du kWh : l'inclure ferait dépendre l'économie solaire de la façon
# dont le client règle sa facture. Exposé comme constante pour qui veut
# l'afficher, jamais appliqué par :func:`facture_mad`.
TIMBRE_ESPECES_PCT = 0.0025


# ════════════════════════════════════════════════════════════════════════════
# 2. TPPAN — taxe pour la promotion du paysage audiovisuel national
# ════════════════════════════════════════════════════════════════════════════
# Barème : article 16 du dahir n° 1-96-77 du 29/06/1996 (loi de finances
# n° 8-96), BO n° 4391 bis — texte relayé par la HACA. Plafond 100 MAD/mois
# corroboré par la page officielle Lydec.
#
# VÉRIFIÉ SUR FACTURE (A, 30 jours, 359 kWh) :
#     100 × 0,10 + 100 × 0,15 + 159 × 0,20 = 56,80 → ligne TPPAN = 56,80 TTC.
# Empilement PROGRESSIF et montant TTC : les deux étaient « inférés », ils sont
# maintenant PROUVÉS.
#
# BORNES PRORATISÉES AUX JOURS de la période de relevé (100 × j/30 et
# 200 × j/30) — c'est ce qui approche le mieux les périodes non standard :
#     facture B (31 j, 572 kWh) : calculé 98,90 · facturé 98,86 (écart 0,04)
#     facture C (29 j, 432 kWh) : calculé 71,90 · facturé 71,85 (écart 0,05)
# Sans proratisation l'écart serait de 0,45 à 0,54 — dix fois pire. Le résidu
# de ~0,05 MAD (0,05 %) est une convention d'arrondi du système de facturation
# que deux relevés ne suffisent pas à reconstituer ; il est MESURÉ, pas ignoré,
# et épinglé par les tests avec cette tolérance explicite.
#
# NOTE DE MODÉLISATION : nos mois sont CALENDAIRES (28/30/31 jours) alors que
# les relevés sont à cheval (22/03→21/04). C'est une approximation assumée :
# sur une année entière les jours se compensent exactement (365 = Σ des mois).
TPPAN_TRANCHES = (
    (100, 0.10),    # 0–100 kWh (proratisés) — art. 16, dahir 1-96-77
    (200, 0.15),    # 101–200 kWh (proratisés) — idem
    (None, 0.20),   # au-delà — idem
)

#: Jours de référence des bornes du barème TPPAN (un mois « plein »).
TPPAN_JOURS_REFERENCE = 30.0

#: Plafond mensuel de la TPPAN (MAD TTC) — art. 16 + page officielle Lydec.
#: NON proratisé faute d'observation : aucune des trois factures ne l'atteint
#: (la plus haute, 98,86 à 572 kWh, en approche sans le toucher).
TPPAN_PLAFOND_MAD_MOIS = 100.0

#: Seuil d'exonération (kWh/mois). DEUX sources officielles se contredisent :
#: le texte de 1996 dit ≤ 50 kWh, la page actuelle de Lydec dit ≤ 200 kWh
#: (relèvement rapporté « depuis 2012 », texte modificatif non localisé). Les
#: trois factures du fondateur sont TOUTES au-dessus de 200 kWh : elles ne
#: départagent pas. On retient Lydec (source de régie la plus récente) en
#: PARAMÈTRE, jamais en dur.
#:
#: RÉSERVE HONNÊTE : à 200 kWh ce seuil crée une marche de 35 MAD (0 juste en
#: dessous, 35 juste au-dessus), ce qui est inhabituel pour une taxe ; le seuil
#: de 1996 (50 kWh) en produirait une bien plus douce. Une seule facture de
#: petit consommateur (< 200 kWh/mois) trancherait — à demander.
TPPAN_EXONERATION_KWH_MOIS = 200.0

TPPAN_SOURCE = (
    'art. 16 dahir 1-96-77 (BO 4391 bis, relayé HACA) ; barème progressif, '
    'bornes proratisées aux jours et montant TTC VÉRIFIÉS sur la facture SRM '
    'du 08/05/2026 (56,80 MAD à 359 kWh sur 30 jours) ; seuil d\'exonération '
    '(200 kWh, source Lydec) non départagé par les factures disponibles'
)


def _num(valeur, defaut=0.0):
    """Flottant tolérant (illisible/``None`` → ``defaut``) — jamais d'exception."""
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return float(defaut)


def tppan_mad(kwh_mensuel, *, jours=TPPAN_JOURS_REFERENCE,
              exoneration_kwh=TPPAN_EXONERATION_KWH_MOIS,
              plafond_mad=TPPAN_PLAFOND_MAD_MOIS):
    """TPPAN TTC due sur une période de ``jours`` jours consommant ``kwh_mensuel``.

    Empilement PROGRESSIF de :data:`TPPAN_TRANCHES` sur la TOTALITÉ de la
    consommation, bornes proratisées aux jours, plafonné. Le résultat est un
    montant TTC (le barème 1996 produit directement le TTC — prouvé facture A).

    Monotone non décroissante en ``kwh_mensuel`` : propriété exigée par
    l'inversion, qui procède par dichotomie sur la facture TOTALE.
    """
    kwh = _num(kwh_mensuel)
    if kwh <= 0:
        return 0.0
    if exoneration_kwh is not None and kwh <= _num(exoneration_kwh):
        return 0.0

    ratio = _num(jours, TPPAN_JOURS_REFERENCE) / TPPAN_JOURS_REFERENCE
    if ratio <= 0:
        ratio = 1.0

    total = 0.0
    restant = kwh
    borne_basse = 0.0
    for plafond, prix in TPPAN_TRANCHES:
        if plafond is None:
            total += restant * prix
            break
        borne_haute = plafond * ratio
        tranche = min(restant, max(0.0, borne_haute - borne_basse))
        total += tranche * prix
        restant -= tranche
        borne_basse = borne_haute
        if restant <= 0:
            break
    if plafond_mad is not None:
        total = min(total, _num(plafond_mad))
    return total


# ════════════════════════════════════════════════════════════════════════════
# 3. FACTURE : kWh → MAD
# ════════════════════════════════════════════════════════════════════════════

def charges_fixes_ttc(millesime=MILLESIME_COURANT):
    """Total TTC des DEUX lignes fixes (location compteur + entretien).

    Chaque ligne porte SON taux de TVA : en décembre 2025 la location était à
    15 % et l'entretien à 20 % SUR LA MÊME FACTURE — un taux global unique
    donnerait un montant faux.

    2026 : 18,28 × 1,20 + 15,00 × 1,20 = 39,94 MAD/mois.
    """
    taux = TVA_PAR_MILLESIME.get(millesime, TVA_PAR_MILLESIME[MILLESIME_COURANT])
    return (CHARGE_LOCATION_COMPTEUR_HT * (1.0 + taux['location'])
            + CHARGE_ENTRETIEN_BRANCHEMENT_HT * (1.0 + taux['entretien']))


def _tranches_effectives(tranches=None, millesime=MILLESIME_COURANT):
    """Table de tranches à employer — surcharge société, sinon millésime.

    Ne construit AUCUNE nouvelle grille : soit la surcharge société déjà
    résolue par l'appelant, soit le barème du millésime demandé, soit — dernier
    recours — ``pricing.ONEE_TRANCHES``.
    """
    if tranches is not None:
        table, _ = _resolve_tranches(None, tranches)
        if table is not None:
            return table
    return MILLESIMES.get(millesime) or ONEE_TRANCHES


def facture_mad(kwh_mensuel, *, jours=TPPAN_JOURS_REFERENCE,
                millesime=MILLESIME_COURANT, tranches=None,
                charges_fixes_mad=None, tppan=True,
                exoneration_kwh=TPPAN_EXONERATION_KWH_MOIS):
    """kWh/mois → facture mensuelle TTC DÉTAILLÉE (MAD), comme la vraie facture.

    Composantes rendues SÉPARÉMENT (jamais un total opaque), dans l'ordre où
    elles apparaissent sur la facture SRM ::

        {energie_mad, location_entretien_mad, tppan_mad, total_mad,
         charges_fixes_source, millesime, tppan_source}

    · ``energie_mad`` — mécanique progressif(≤150)/sélectif(>150, tolérance
      10 kWh) de ``pricing._monthly_bill_from_kwh``, appliquée au barème du
      millésime (prix déjà TTC, aucune TVA ajoutée).
    · ``location_entretien_mad`` — les DEUX lignes fixes (:func:`charges_fixes_ttc`),
      ou la valeur société quand ``charges_fixes_mad`` est fourni.
    · ``tppan_mad`` — :func:`tppan_mad`, bornes proratisées à ``jours``.

    Fonction pure. ``kwh_mensuel`` ≤ 0 ⇒ énergie et TPPAN nulles, mais les
    charges fixes RESTENT dues (c'est la réalité d'un abonnement).
    """
    kwh = _num(kwh_mensuel)
    table = _tranches_effectives(tranches, millesime)

    energie = _monthly_bill_from_kwh(kwh, table) if kwh > 0 else 0.0
    taxe = tppan_mad(kwh, jours=jours,
                     exoneration_kwh=exoneration_kwh) if tppan else 0.0

    if charges_fixes_mad is None:
        fixes = charges_fixes_ttc(millesime)
        source_fixes = CHARGES_FIXES_SOURCE
    else:
        fixes = max(0.0, _num(charges_fixes_mad))
        source_fixes = 'réglage société'

    return {
        'energie_mad': energie,
        'location_entretien_mad': fixes,
        'tppan_mad': taxe,
        'total_mad': energie + fixes + taxe,
        'charges_fixes_source': source_fixes,
        'millesime': millesime,
        'tppan_source': TPPAN_SOURCE if tppan else '',
    }


# ════════════════════════════════════════════════════════════════════════════
# 4. INVERSION : MAD → kWh
# ════════════════════════════════════════════════════════════════════════════

def kwh_depuis_facture_mad(total_mad, *, jours=TPPAN_JOURS_REFERENCE,
                           millesime=MILLESIME_COURANT, tranches=None,
                           charges_fixes_mad=None, tppan=True,
                           exoneration_kwh=TPPAN_EXONERATION_KWH_MOIS):
    """MAD/mois → kWh/mois : l'INVERSE EXACT de :func:`facture_mad`.

    MÉTHODE. La facture totale ``f(kWh) = énergie + fixes + TPPAN`` est
    monotone non décroissante (chaque composante l'est). On l'inverse par
    DICHOTOMIE sur ``f`` ELLE-MÊME — c'est le seul inverse correct d'une
    fonction DISCONTINUE, et il absorbe naturellement le fait que la TPPAN
    dépend elle aussi du kWh cherché : là où une soustraction préalable
    exigerait une itération de point fixe (« retirer la TPPAN, inverser,
    recalculer la TPPAN, recommencer »), la dichotomie résout le point fixe
    d'un seul coup, sans critère de convergence à régler ni biais résiduel.

    LES « TROUS » DU BARÈME SÉLECTIF. Au-delà de 150 kWh la facture SAUTE aux
    bornes de tranche : aucune consommation ne produit un montant tombé dans le
    saut. La dichotomie converge vers ``inf{ k : f(k) ≥ montant }``, donc un tel
    montant est résolu à la BORNE BASSE — le côté PRUDENT (moins de kWh ⇒
    système plus petit ⇒ économies annoncées plus petites, jamais l'inverse).
    Même règle que ``pricing._kwh_from_bill_bisect`` et que son miroir JS.

    Retourne ``{kwh_mensuel, energie_mad, location_entretien_mad, tppan_mad,
    charges_fixes_source}``. ``total_mad`` ≤ 0 ⇒ 0 kWh (jamais un chiffre
    fabriqué). Un montant qui ne couvre même pas les charges fixes rend 0 kWh :
    aucune consommation ne peut produire une facture aussi basse.
    """
    montant = _num(total_mad)

    def _detail(kwh):
        return facture_mad(
            kwh, jours=jours, millesime=millesime, tranches=tranches,
            charges_fixes_mad=charges_fixes_mad, tppan=tppan,
            exoneration_kwh=exoneration_kwh)

    def _sortie(kwh, detail):
        return {
            'kwh_mensuel': kwh,
            'energie_mad': detail['energie_mad'],
            'location_entretien_mad': detail['location_entretien_mad'],
            'tppan_mad': detail['tppan_mad'],
            'charges_fixes_source': detail['charges_fixes_source'],
        }

    if montant <= 0:
        return _sortie(0.0, _detail(0.0))

    plancher = _detail(0.0)
    if montant <= plancher['total_mad']:
        return _sortie(0.0, plancher)

    bas = 0.0
    haut = 1000.0
    while _detail(haut)['total_mad'] < montant and haut < 1e6:
        haut *= 2
    for _ in range(60):
        milieu = (bas + haut) / 2
        if _detail(milieu)['total_mad'] < montant:
            bas = milieu
        else:
            haut = milieu
    kwh = round((bas + haut) / 2, 1)
    return _sortie(kwh, _detail(kwh))


# ════════════════════════════════════════════════════════════════════════════
# 5. ÉCONOMIE — le modèle « deux factures », au MOIS
# ════════════════════════════════════════════════════════════════════════════

def economie_deux_factures_mad(kwh_avant, kwh_apres, *,
                               jours=TPPAN_JOURS_REFERENCE,
                               millesime=MILLESIME_COURANT, tranches=None,
                               charges_fixes_mad=None, tppan=True,
                               exoneration_kwh=TPPAN_EXONERATION_KWH_MOIS):
    """Économie MENSUELLE (MAD) = facture(avant) − facture(après).

    LE modèle « deux factures » du fondateur (18/08), appliqué au MOIS —
    l'unité des marches du barème : sur la grille SÉLECTIVE, redescendre sous
    une marche re-tarife TOUT le mois restant, ce qui vaut bien plus que les
    seuls kWh effacés. Jamais « kWh évités × prix moyen ».

    CE QUI S'ANNULE, CE QUI NE S'ANNULE PAS — et c'est ce qui rend le calcul
    honnête :
      · location du compteur + entretien du branchement : charges FIXES,
        identiques des deux côtés, donc STRICTEMENT SANS EFFET sur l'économie.
        Le client garde son abonnement même avec du solaire — le lui compter
        comme une économie serait un mensonge. Elles ne comptent QUE pour le
        back-calcul kWh↔MAD, qu'elles rendent plus juste.
      · TPPAN : elle SUIT le kWh, donc elle baisse avec la consommation et
        contribue RÉELLEMENT à l'économie.

    Résultat borné à ≥ 0 (le barème est monotone ; un négatif ne pourrait venir
    que d'un arrondi).
    """
    commun = {
        'jours': jours, 'millesime': millesime, 'tranches': tranches,
        'charges_fixes_mad': charges_fixes_mad, 'tppan': tppan,
        'exoneration_kwh': exoneration_kwh,
    }
    avant = facture_mad(kwh_avant, **commun)
    apres = facture_mad(kwh_apres, **commun)
    return {
        'facture_avant_mad': avant['total_mad'],
        'facture_apres_mad': apres['total_mad'],
        'economie_mad': max(0.0, avant['total_mad'] - apres['total_mad']),
    }

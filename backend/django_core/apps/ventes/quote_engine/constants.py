# Vendored from RedaSolar/devis-simulator — Morocco solar ROI/production constants.
# ---------- CONSTANTES VISUELLES ----------
BLUE_MAIN = "#0A5275"        # Bleu TAQINOR
BLUE_LIGHT = "#E6F1F7"
TEXT_DARK = "#222222"
ORANGE_ACCENT = "#F28E2B"
GREY_NEUTRAL = "#555555"

# ---------- CONSTANTES ROI / PRODUCTION ----------
# DC9 — SOURCE UNIQUE (côté Python) de la table d'irradiance GHI mensuelle du
# Maroc. `frontend/src/features/ventes/solar.js` porte la MÊME table (miroir
# obligatoire) ; un test de parité (test_dc9_ghi_parity.py) échoue si l'une
# dérive de l'autre. Ne modifier QU'ICI puis répercuter à l'identique dans
# solar.js (et inversement) — jamais l'une sans l'autre.
GHI = [83.99, 96.79, 133.43, 155.30, 175.28, 179.62, 179.56, 161.17, 137.03, 111.59, 81.91, 74.61]

# M1 (audit du 19/08/2026) — DÉRIVATION UNIQUE des poids mensuels normalisés
# (somme = 1). `public_views` en portait une SECONDE copie, table GHI recopiée
# chiffre par chiffre : deux tables identiques aujourd'hui, deux tables
# divergentes au premier ajustement — et le drift-lock DC9 ne surveille que
# celle-ci. Sert UNIQUEMENT à répartir un total annuel RÉEL sur 12 mois : on ne
# fabrique jamais le total, on le distribue.
MOROCCO_SOLAR_MONTHLY_WEIGHTS = [round(g / sum(GHI), 6) for g in GHI]
# AMOT27 — l'ANCIENNE clé fixe (non sourcée) de répartition mensuelle d'une
# économie annuelle. Conservée ICI, et seulement ici, pour les devis rendus
# aux règles d'origine (décision fondateur 08/10/2026) et pour les jeux de
# données de test historiques ; tout nouveau rendu répartit par
# ``MOROCCO_SOLAR_MONTHLY_WEIGHTS`` (la forme de la production imprimée).
CLE_SOLAIRE_MENSUELLE_HISTORIQUE = (0.053, 0.062, 0.083, 0.098, 0.114, 0.116,
                                    0.116, 0.101, 0.087, 0.070, 0.052, 0.048)
MOIS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

# AMOT47 (08/10/2026) — PRODUCTIBLE_DEFAUT, KWH_PRICE et EFFICIENCY sont
# supprimés (zéro lecteur hors tests) : le productible de repli vit dans
# ``productible.DEFAULT_PRODUCTIBLE``, le repère société dans
# ``CompanyProfile.productible_kwh_kwc`` (DC9).

# ---------- CONSTANTES IMPACT ENVIRONNEMENTAL (résidentiel) ----------
# M8 (audit du 19/08/2026) — SOURCE UNIQUE : le PDF résidentiel (cover.py +
# options.py) recopiait ces chiffres localement, et un arrondi divergeait déjà
# du site web pour le MÊME devis. Ils vivent ici, et ici seulement.
#
# CO2SRC (règle « chiffres vérifiés », 2026-08-26) — CE QUI RESTE ET POURQUOI.
# Le seul chiffre d'impact encore imprimé sur un PDF est la tonne ANNUELLE :
# elle se dérive d'une production RÉELLE du devis multipliée par le facteur
# d'émission du réseau marocain. Les deux « équivalences » qui l'accompagnaient
# (arbres, cumul 25 ans) ont été retirées de TOUS LES PDF parce qu'aucune
# source ne les porte (voir plus bas) — ne pas les y réintroduire sans source
# nommée. Le SITE a fait le même retrait de son côté dans le même lot
# (``apps/web`` n'exporte plus ``CO2_KG_PER_TREE_YEAR``) : les deux supports
# disent donc la même chose, et il n'existe plus aucune surface client où ces
# deux équivalences s'impriment.
#
# Facteur réseau marocain — mix électrique national, ≈0,81 t CO₂/MWh.
# SOURCE À PRÉCISER : la valeur est cohérente avec l'ordre de grandeur publié
# pour le facteur d'émission moyen du réseau (mix marocain fortement carboné)
# et elle est ALIGNÉE sur apps/web (``CO2_KG_PER_KWH``), mais ni ce dépôt ni le
# site ne nomment la publication ni son millésime. Le fondateur doit fournir la
# référence datée (organisme + année) ; d'ici là on garde la valeur — elle est
# la seule des trois à décrire une grandeur physique mesurée — et on n'invente
# AUCUNE citation.
CO2_T_PAR_MWH = 0.81
# AMOT47 (08/10/2026) — l'absorption « 22 kg/arbre/an » (sans source) est
# supprimée : plus aucun lecteur, ni rendu ni calcul.

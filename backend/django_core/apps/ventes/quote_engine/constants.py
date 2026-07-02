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
MOIS = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Août", "Sep", "Oct", "Nov", "Déc"]
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
EFFICIENCY = 0.8   # rendement global
KWH_PRICE = 1.75   # MAD/kWh FIXE (utilisé en interne — ne pas afficher dans les PDF/UI)

# DC9 — Productible annuel de RÉFÉRENCE (kWh/kWc/an). RÉCONCILIATION : le repère
# CANONIQUE est CompanyProfile.productible_kwh_kwc (défaut 1600), consommé par le
# moteur de devis via parametres.selectors.tariff_for (DC2/DC5). Cette constante
# porte ce MÊME défaut (1600) pour rester alignée avec le profil société. À ne
# pas confondre avec le repli PLAT de pricing._DEFAULT_PRODUCTIBLE (1240 ≈
# sum(GHI)×EFFICIENCY), utilisé UNIQUEMENT quand aucune donnée société n'est
# disponible ; dès qu'un devis porte une société, c'est le 1600 (ou la valeur
# éditée) du profil qui prime.
PRODUCTIBLE_DEFAUT = 1600

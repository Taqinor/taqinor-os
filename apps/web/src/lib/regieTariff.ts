// Barème RÉGIE (tranche « sélective ») — les deux tranches marginales hautes,
// publiées et stables. Source unique côté SITE PUBLIC, volontairement découplée
// du « cerveau » estimateur (`estimatorBrainV2.ts`), qui ne doit jamais être
// importé par une page publique (garde d'architecture : cf. estimatorPreview*.test.ts,
// « le script lourd reste hors de toute page publique »). Ces deux valeurs sont
// identiques à la grille sélective de `estimatorBrainV2.ts` (tranches 311–510 kWh
// et > 510 kWh).
//
// ORDRE FONDATEUR (19/08/2026) — TVA 20 % depuis le 01/01/2026 (16 % en 2024,
// 18 % en 2025) : re-dérivées HT × 1,20 ; ancre fondateur (facture réelle) =
// tranche > 510 kWh = 1,622856 MAD/kWh TTC. Détail de la dérivation :
// apps/ventes/quote_engine/pricing.py ONEE_TRANCHES (miroir exact). La
// fourchette « ≈ 1,41–1,62 MAD/kWh » remplace l'ancienne « ≈ 1,38–1,60 »
// documentée dans `billRange.ts` / `recharge-voiture-electrique-solaire.astro`.
export const REGIE_MARGINAL_RATE_SECOND = 1.405116; // MAD/kWh — tranche 311–510 kWh/mois
export const REGIE_MARGINAL_RATE_HIGH = 1.622856; // MAD/kWh — tranche > 510 kWh/mois

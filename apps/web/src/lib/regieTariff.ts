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
// apps/ventes/quote_engine/pricing.py ONEE_TRANCHES (miroir exact).
//
// QJW12 — DÉCISION FONDATEUR D5 (29/08/2026) : LA TRANCHE 311–510 kWh EST
// CORRIGÉE, 1,405116 → 1,381704 MAD/kWh TTC. Le 1,405116 n'était pas une mesure
// mais une EXTRAPOLATION (on avait supposé le HT constant au passage de TVA
// 18 → 20 %). La facture SRM n° 643769639 du 08/05/2026 (359 kWh, énergie
// 1,15142 HT × 1,20 = 1,381704 TTC) prouve l'inverse : c'est le TTC qui est resté
// constant et le HT qui a été abaissé — corroboré par la facture du 20/01/2026
// (même TTC 1,3817 sous TVA 18 %). VALEUR DE RÉFÉRENCE :
// apps/ventes/quote_engine/bareme.py, TRANCHES_2026 (T5) ; tout l'ERP l'a
// rejointe depuis D5, ce miroir public la rejoint ici. La fourchette du haut de
// grille redevient donc « ≈ 1,38–1,62 MAD/kWh ».
export const REGIE_MARGINAL_RATE_SECOND = 1.381704; // MAD/kWh — tranche 311–510 kWh/mois (prouvé facture SRM 08/05/2026)
export const REGIE_MARGINAL_RATE_HIGH = 1.622856; // MAD/kWh — tranche > 510 kWh/mois

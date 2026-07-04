// Barème RÉGIE (tranche « sélective ») — les deux tranches marginales hautes,
// publiées et stables. Source unique côté SITE PUBLIC, volontairement découplée
// du « cerveau » estimateur (`estimatorBrainV2.ts`), qui ne doit jamais être
// importé par une page publique (garde d'architecture : cf. estimatorPreview*.test.ts,
// « le script lourd reste hors de toute page publique »). Ces deux valeurs sont
// identiques à la grille sélective de `estimatorBrainV2.ts` (tranches 311–510 kWh
// et > 510 kWh) et à la fourchette « ≈ 1,38–1,60 MAD/kWh » déjà documentée dans
// `billRange.ts` / `recharge-voiture-electrique-solaire.astro`.
export const REGIE_MARGINAL_RATE_SECOND = 1.3817; // MAD/kWh — tranche 311–510 kWh/mois
export const REGIE_MARGINAL_RATE_HIGH = 1.5958; // MAD/kWh — tranche > 510 kWh/mois

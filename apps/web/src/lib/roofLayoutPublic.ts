/**
 * ACAL304 (D-ACAL-27, moitié site) — document `roof_layout` v2 ÉMIS par la capture
 * publique. Rien d'autre que ce que le visiteur a dessiné : ni pente, ni module, ni
 * puissance (aucun chiffre ajouté).
 *
 * Vit dans src/lib (type pur) pour que le contrat du tunnel (lib/tunnel/champs.ts)
 * le lise sans tirer les scripts DOM/Three/MapLibre de roofPro11 dans le
 * type-check de src/lib ; roofPro11/captureBoot.ts le réexporte.
 */
export interface RoofLayoutPublic {
  version: 2;
  pin: { lat: number; lng: number } | null;
  zones: Array<{ id: string; label: string; vertices: Array<[number, number]> }>;
  source: 'lead';
}

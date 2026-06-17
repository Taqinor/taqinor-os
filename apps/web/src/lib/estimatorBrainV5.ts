/**
 * CERVEAU V5 de l'estimateur (preview privé /preview/toiture-3d-pro-8). Module
 * PUR, testé (tests/estimatorBrainV5.test.ts). COMPOSE sur V3/V4 sans les modifier
 * (pro-3..pro-7 restent des baselines intactes). V5 cible le TOIT EN PENTE / TUILES,
 * choisi AVANT le tracé, avec PVGIS comme source de vérité de la production :
 *
 *  1. TYPE DE TOIT D'ABORD. L'écran demande « toit plat » ou « toit en pente /
 *     tuiles » AVANT de tracer. Plat → optimiseur V4 (grille fine, racks) inchangé.
 *     Pente → modèle affleurant (flush) : panneaux à PLAT sur la pente.
 *
 *  2. PENTE = INCLINAISON, FACE = AZIMUT, IMPOSÉS PAR LE TOIT. Rien à optimiser :
 *     le toit donne les deux. La pente est SAISIE (non mesurable sur l'imagerie
 *     satellite marocaine), la face confirmée à la boussole de la carte. Presets de
 *     pente tuile marocains réglables — 15° / 22° / 30° / 45°.
 *
 *  3. PRODUCTION = PVGIS À CE SEUL (pente, face), pose `mountingplace = 'building'`
 *     (panneaux affleurants moins ventilés → tournent plus chaud → rendement
 *     légèrement plus bas, et reflète honnêtement une face/pente off-sud). Le
 *     navigateur ne touche jamais PVGIS : le page-script passe par `/api/roof-yield`
 *     (une seule jambe) et retombe sur la table committée (« estimé ») si injoignable.
 *
 *  4. PAS DE PAS INTER-RANGÉES (panneaux coplanaires → aucune auto-ombre). Le pavage
 *     affleurant (V3 `packFlushPlane`) tuile dense, borné par la surface utile, le
 *     retrait de rive/faîte/égout et les keep-out d'obstacles. UN SEUL pan primaire
 *     (multi-pans hors périmètre de cette version).
 *
 * JAMAIS un devis : une fourchette indicative. Voir apps/web/BRAIN_V5_NOTES.md.
 */
import { aspectFromCompass } from './estimatorBrainV4';

export { aspectFromCompass };

/** Presets de pente tuile (deg), réglables au curseur 5–45°. */
export const PITCH_PRESETS_V5 = [15, 22, 30, 45] as const;

/** Pose PVGIS du toit en pente : panneaux affleurants, moins ventilés. */
export const PITCHED_MOUNTINGPLACE = 'building' as const;

/**
 * Jambe PVGIS d'un pan en pente : UNE seule jambe (un seul plan), à l'inclinaison =
 * pente du toit et à l'aspect = face du pan (converti boussole → aspect PVGIS :
 * Sud=0, Est=−90, Ouest=+90, Nord=180). À interroger en `mountingplace='building'`.
 */
export function pitchedPlaneLeg(
  pitchDeg: number,
  facingAzimuthDeg: number,
  kwc: number,
): { kwc: number; tiltDeg: number; aspect: number } {
  return { kwc, tiltDeg: pitchDeg, aspect: aspectFromCompass(facingAzimuthDeg) };
}

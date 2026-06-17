// Cerveau V5 — src/lib/estimatorBrainV5.ts (preview privé pro-8, toit en pente).
// Prouve : presets de pente incluant 45° ; pose PVGIS « building » (affleurant) ;
// jambe PVGIS d'un pan = UNE jambe à (pente, face) avec l'aspect correctement
// converti boussole → PVGIS. Compose sur V4 (aspectFromCompass) sans le modifier.
import { describe, expect, it } from 'vitest';
import { PITCH_PRESETS_V5, PITCHED_MOUNTINGPLACE, pitchedPlaneLeg } from '../src/lib/estimatorBrainV5';

describe('V5 — toit en pente (flush, PVGIS source de vérité)', () => {
  it('les presets de pente incluent 45° (en plus de 15/22/30)', () => {
    expect([...PITCH_PRESETS_V5]).toEqual([15, 22, 30, 45]);
  });

  it('la pose PVGIS du toit en pente est « building » (affleurant, moins ventilé)', () => {
    expect(PITCHED_MOUNTINGPLACE).toBe('building');
  });

  it('jambe PVGIS = UNE jambe à (pente, face), aspect converti boussole → PVGIS', () => {
    // Face plein sud (180°) → aspect 0, inclinaison = pente.
    expect(pitchedPlaneLeg(30, 180, 6)).toEqual({ kwc: 6, tiltDeg: 30, aspect: 0 });
    // Face est (90°) → aspect −90.
    expect(pitchedPlaneLeg(22, 90, 4).aspect).toBe(-90);
    // Face ouest (270°) → aspect +90.
    expect(pitchedPlaneLeg(15, 270, 4).aspect).toBe(90);
    // Une seule jambe (un seul plan primaire).
    expect(typeof pitchedPlaneLeg(45, 180, 5).tiltDeg).toBe('number');
  });
});

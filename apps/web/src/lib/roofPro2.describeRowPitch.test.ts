// ACAL255 — le libellé du pas inter-rangées dit le soleil de DIMENSIONNEMENT réellement
// appliqué (10 h solaire au solstice d'hiver), celui qui produit le pas du moteur V2 —
// plus l'élévation de midi (≈33° à 33,57°) qui contredisait le pas affiché.
import { describe, expect, it } from 'vitest';
import { describeRowPitch, DESIGN_SOLAR_HOUR_V2 } from './roofPro2';
import { DESIGN_SOLAR_HOUR, sunPositionWinterSolstice } from './estimatorBrainV2';

const LATITUDE = 33.57;

describe('ACAL255 — describeRowPitch au soleil de dimensionnement V2', () => {
  it('élévation affichée = élévation de dimensionnement V2 (≈26,2° à 33,57°)', () => {
    const d = describeRowPitch({ rowPitchM: 2, latitudeDeg: LATITUDE });
    const v2 = sunPositionWinterSolstice(LATITUDE, DESIGN_SOLAR_HOUR).elevationDeg;
    expect(d.designElevDeg).toBeCloseTo(v2, 9);
    expect(d.designElevDeg as number).toBeCloseTo(26.2, 1);
  });

  it("le libellé nomme le soleil de 10 h au solstice d'hiver, pas midi", () => {
    const { label } = describeRowPitch({ rowPitchM: 2, latitudeDeg: LATITUDE });
    expect(label).toContain('soleil de 10 h au solstice d’hiver');
    expect(label).not.toContain('midi');
  });

  it("l'heure miroir de roofPro2 reste égale à celle du moteur V2", () => {
    expect(DESIGN_SOLAR_HOUR_V2).toBe(DESIGN_SOLAR_HOUR);
  });

  it('en pose affleurante, aucune élévation (rangées jointives)', () => {
    expect(describeRowPitch({ rowPitchM: 1.2, latitudeDeg: LATITUDE, flush: true }).designElevDeg)
      .toBeNull();
  });
});

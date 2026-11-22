// ACAL585 — pavage en châssis N × M de l'atelier. Fichier neuf : module neuf.
import { describe, expect, it } from 'vitest';
import { packConfig } from '../../lib/estimatorBrainV2';
import { solveLive } from '../../lib/estimatorBrainV7';
import type { LngLat } from '../../lib/roof';
import { emettreChassis, lireChassis, noteChassis, optionChassis, validerChassis } from './chassisPavage';

const DEG2RAD = Math.PI / 180;
const DEG2M = DEG2RAD * 6378137;
const LNG0 = -7.62;
const LAT0 = 33.59;
const MODULE = { longM: 2.278, courtM: 1.134, epaisM: null, watt: 600 };
const PAN = { rangs: 2, modulesParRang: 10, jeuEntreRangsM: 0.03, source: 'notice du châssis' };

function rect(wEW: number, hNS: number): LngLat[] {
  const dLng = wEW / 2 / (DEG2M * Math.cos(LAT0 * DEG2RAD));
  const dLat = hNS / 2 / DEG2M;
  return [
    [LNG0 - dLng, LAT0 - dLat],
    [LNG0 + dLng, LAT0 - dLat],
    [LNG0 + dLng, LAT0 + dLat],
    [LNG0 - dLng, LAT0 + dLat],
  ];
}

const solve = (chassis: ReturnType<typeof optionChassis>) =>
  solveLive(rect(30, 12), LAT0, 4000, [], { orientation: 'south', tiltDeg: 15, layout: 'portrait', margin: 'keep' }, { module: MODULE, chassis });

describe('ACAL585 — châssis N × M', () => {
  it('2 × 10 sur un pan sud ⇒ compte multiple de 20 et note « n châssis de 2 × 10 posés »', () => {
    const avec = solve(optionChassis(PAN));
    expect(avec.winner.fitCount).toBeGreaterThan(0);
    expect(avec.winner.fitCount % 20).toBe(0);
    const pack = packConfig(rect(30, 12), LAT0, { family: 'south', tiltDeg: 15, module: MODULE, chassis: optionChassis(PAN) });
    expect(noteChassis(pack, pack.portrait)).toBe(`${pack.portrait.count / 20} châssis de 2 × 10 posés`);
  });

  it('Est-Ouest ⇒ motif « poses au sud seulement », pavage inchangé', () => {
    const base = { family: 'eastwest' as const, tiltDeg: 10, module: MODULE };
    const sans = packConfig(rect(30, 12), LAT0, base);
    const avec = packConfig(rect(30, 12), LAT0, { ...base, chassis: optionChassis(PAN) });
    expect(noteChassis(avec, avec.best)).toBe('châssis 2 × 10 : poses au sud seulement');
    expect(avec.best.count).toBe(sans.best.count);
  });

  it('1 × 1 ou rien saisi ⇒ aucune option, pavage identique à celui d’aujourd’hui', () => {
    expect(optionChassis(undefined)).toBeUndefined();
    expect(optionChassis({ rangs: 1, modulesParRang: 1, source: 'x' })).toBeUndefined();
    expect(JSON.stringify(solve(optionChassis({ rangs: 1, modulesParRang: 1, source: 'x' })).winner)).toBe(JSON.stringify(solve(undefined).winner));
  });

  it('aller-retour du document : la clé revient telle quelle, aucune clé sans saisie', () => {
    expect(emettreChassis(PAN)).toEqual({ chassis: PAN });
    expect(lireChassis(JSON.parse(JSON.stringify(PAN)))).toEqual(PAN);
    expect(emettreChassis(undefined)).toEqual({});
    expect(emettreChassis({ rangs: 2, modulesParRang: 10, source: 'x' })).toEqual({}); // jeu manquant dès 2 rangs
  });

  it('saisie : champs vides ⇒ aucun châssis ; valeur ≤ 0 ou source vide refusées en nommant le champ', () => {
    expect(validerChassis('', '', '', '')).toEqual({ ok: true, chassis: null });
    expect(validerChassis('0', '10', '0,03', 's')).toMatchObject({ ok: false, champ: 'rangs' });
    expect(validerChassis('2', '-1', '0,03', 's')).toMatchObject({ ok: false, champ: 'modules' });
    expect(validerChassis('2', '10', '', 's')).toMatchObject({ ok: false, champ: 'jeu' });
    expect(validerChassis('2', '10', '0,03', ' ')).toMatchObject({ ok: false, champ: 'source' });
    expect(validerChassis('2', '10', '0,03', 'notice')).toEqual({ ok: true, chassis: { rangs: 2, modulesParRang: 10, jeuEntreRangsM: 0.03, source: 'notice' } });
  });
});

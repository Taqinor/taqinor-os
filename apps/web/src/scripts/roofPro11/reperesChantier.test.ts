// @vitest-environment jsdom
// ACAL593 — couche « Repères de chantier » : lecture/écriture de `reperesChantier` (contrat ACAL599),
// rayon SAISI jamais par défaut, refus qui nomme le champ.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { racineDepot } from './harnaisAtelier';
import {
  CHAMP_RAYON, TYPES_REPERE, cercleDuRepere, createReperesUi, emettreReperesChantier, lireReperesChantier, reperesGeoJSON, validerRayon,
  type RepereChantier,
} from './reperesChantier';

const SCHEMA = JSON.parse(readFileSync(join(racineDepot(), 'backend', 'django_core', 'apps', 'calepinage',
  'contract_samples', 'roof_layout_v2.schema.json'), 'utf8')) as {
  properties: Record<string, unknown>; $defs: { repereChantier: { properties: { type: { enum: string[] } } } };
};

const ancre = (o: Partial<RepereChantier> = {}): RepereChantier =>
  ({ id: 'r1', type: 'ancre_antichute', texte: 'côté rue', rayonM: 2, point: [-7.62, 33.58], ...o });

describe('ACAL593 — reperesChantier', () => {
  it('le contrat porte la clé racine et les mêmes types que l’atelier', () => {
    expect(SCHEMA.properties).toHaveProperty('reperesChantier');
    expect(Object.keys(TYPES_REPERE).sort()).toEqual([...SCHEMA.$defs.repereChantier.properties.type.enum].sort());
  });

  it('poser, sérialiser, relire : identique', () => {
    const doc = emettreReperesChantier([ancre()]);
    expect(lireReperesChantier(JSON.parse(JSON.stringify(doc)))).toEqual([ancre()]);
    const c = cercleDuRepere(ancre());
    expect(c).not.toBeNull();
    // le cercle est à 2 m du point (projection locale)
    const [lng, lat] = c![0];
    const dE = (lng - -7.62) * Math.cos((33.58 * Math.PI) / 180) * 6378137 * (Math.PI / 180);
    const dN = (lat - 33.58) * 6378137 * (Math.PI / 180);
    expect(Math.hypot(dE, dN)).toBeCloseTo(2, 1);
  });

  it('sans rayon ⇒ rayonM null et aucun cercle', () => {
    const [r] = lireReperesChantier({ reperesChantier: [{ id: 'r2', type: 'acces', point: [-7.62, 33.58] }] });
    expect(r.rayonM).toBeNull();
    expect(cercleDuRepere(r)).toBeNull();
    expect(reperesGeoJSON([r]).features).toHaveLength(1); // le point seul
  });

  it('rayon vide, nul ou négatif refusé en nommant le champ', () => {
    for (const s of ['', '0', '-1', 'abc']) {
      const v = validerRayon(s);
      expect(v.ok).toBe(false);
      if (!v.ok) expect(v.motif).toContain(CHAMP_RAYON);
    }
    expect(validerRayon('2,5')).toEqual({ ok: true, rayonM: 2.5 });
  });

  it('aucun repère ⇒ aucune clé ; entrée hors contrat écartée', () => {
    expect(emettreReperesChantier([])).toEqual({});
    expect(emettreReperesChantier(undefined)).toEqual({});
    expect(lireReperesChantier({ reperesChantier: [{ id: '', type: 'acces', point: [0, 0] }, { id: 'x', type: 'inconnu', point: [0, 0] }] })).toEqual([]);
  });

  it('panneau : rayon vide refusé sous le champ ; 2 m posé au tap, listé, retiré', () => {
    document.body.innerHTML = '<ul id="rp9-mesure-list"></ul>';
    const ctx = {} as Parameters<typeof createReperesUi>[0];
    const ui = createReperesUi(ctx, {});
    const poser = document.getElementById('rp9-repere-poser') as HTMLButtonElement;
    poser.click();
    const err = document.getElementById('rp9-repere-erreur')!;
    expect(err.hidden).toBe(false);
    expect(err.textContent).toContain(CHAMP_RAYON);
    expect(ui.handleMapClick([-7.62, 33.58])).toBe(false); // pas armé : le tap n'est pas consommé
    (document.getElementById('rp9-repere-rayon') as HTMLInputElement).value = '2';
    (document.getElementById('rp9-repere-texte') as HTMLInputElement).value = 'côté rue';
    poser.click();
    expect(err.hidden).toBe(true);
    expect(ui.handleMapClick([-7.62, 33.58])).toBe(true);
    expect(ctx.reperesChantier).toMatchObject([{ type: 'ancre_antichute', texte: 'côté rue', rayonM: 2, point: [-7.62, 33.58] }]);
    (document.querySelector('[data-repere-retirer]') as HTMLButtonElement).click();
    expect(ctx.reperesChantier).toEqual([]);
  });
});

// QJR632 — parité contrat ↔ page : toute colonne que le serveur dit « écrite »
// (colonnes_ecrites du contrat QJR512) doit avoir un contrôle sur la page,
// c'est-à-dire figurer dans collectSectionRaw de [token].astro.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { EQUIPEMENT_KEYS } from '../src/lib/questionnaire';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const contrat = JSON.parse(
  read('../../../backend/django_core/apps/crm/contract_samples/questionnaire_lead.json'),
) as { colonnes_ecrites: Record<string, string[]> };
const src = read('../src/pages/questionnaire/[token].astro');
const debut = src.indexOf('function collectSectionRaw');
const fin = src.indexOf('function ', debut + 10);
const collect = src.slice(debut, fin);

describe('questionnaire — parité colonnes_ecrites ↔ collectSectionRaw', () => {
  it('collectSectionRaw est bien localisé', () => {
    expect(debut).toBeGreaterThan(0);
    expect(collect.length).toBeGreaterThan(200);
  });

  for (const [section, colonnes] of Object.entries(contrat.colonnes_ecrites)) {
    for (const col of colonnes) {
      it(`${section}.${col} a un contrôle sur la page`, () => {
        // Les équipements oui/non sont posés via la boucle EQUIPEMENT_KEYS.
        const viaBoucle = collect.includes('EQUIPEMENT_KEYS') && (EQUIPEMENT_KEYS as readonly string[]).includes(col);
        expect(collect.includes(col) || viaBoucle).toBe(true);
      });
    }
  }
});

// AGW408 — choix fermés du bloc pompage IDENTIQUES au contrat lead_pompage.json.
describe('questionnaire — pompage : choix fermés = contrat', () => {
  const lp = JSON.parse(
    read('../../../backend/django_core/apps/crm/contract_samples/lead_pompage.json'),
  ) as { colonnes: Array<{ nom: string; choix?: string[] }> };
  const choix = (nom: string) => lp.colonnes.find((c) => c.nom === nom)?.choix;

  it('source_eau / irrigation_methode / pompe_alim_actuelle', async () => {
    const lib = await import('../src/lib/questionnaire');
    expect([...lib.SOURCE_EAU_VALUES]).toEqual(choix('source_eau'));
    expect([...lib.IRRIGATION_METHODE_VALUES]).toEqual(choix('irrigation_methode'));
    expect([...lib.POMPE_ALIM_VALUES]).toEqual(choix('pompe_alim_actuelle'));
  });

  it('page : champs numériques step="any" et 12 mois en boutons', () => {
    expect(src).toContain('data-mois={m}');
    expect(src).toContain('MOIS_IRRIGATION_VALUES');
    const bloc = src.slice(src.indexOf("id === 'pompage'"), src.indexOf("id === 'toiture'"));
    expect(bloc).not.toMatch(/step="1"/);
    expect(bloc).toContain('step="any"');
  });
});

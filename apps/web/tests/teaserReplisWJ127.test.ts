// WJ127 — REPLI TEASER HONNÊTE POUR LES CAS SANS ESTIMATION.
//
// LE DÉFAUT CORRIGÉ (finding 2 de la revue adversariale Fable du 16/07). Les
// cartes d'erreur/edge du tunnel — `mt-estimate-toolarge` (facture
// résidentielle hors plafond), `mt-estimate-toolarge-pro` (site C&I au-delà de
// l'échelle du simulateur) et la carte de rappel agricole quand l'hydraulique
// manque — vivent TOUTES à l'intérieur de `#mt-doc`. Or WJ125 masque `#mt-doc`
// sur le parcours public. Résultat : un visiteur industriel à 2 000 000 MAD ne
// voyait plus le message honnête « à cette échelle, étude dédiée », seulement
// l'accroche générique « Recevez votre étude complète… ».
//
// Et la parité a11y était INVERSÉE : `announceEstimate` disait bien la vérité
// au lecteur d'écran sur ces chemins, l'écran ne la montrait pas.
//
// Le correctif : deux accroches de repli FIGURE-FREE dans la carte teaser
// elle-même, révélées par `showEstimateTeaser(mode, variante)` sur exactement
// ces chemins, dans les trois locales.
//
// Lecture SOURCE en texte, même convention que teaserGateWJ125.test.ts : ces
// micro-interactions DOM ne se montent pas sous vitest.

import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const PAGES = {
  FR: read('../src/pages/devis/mon-toit.astro'),
  EN: read('../src/pages/en/devis/mon-toit.astro'),
  AR: read('../src/pages/ar/devis/mon-toit.astro'),
} as const;

// Motifs de FUITE de chiffre dimensionnant — repris VERBATIM de
// teaserGateWJ125.test.ts : le repli honnête ne doit rien divulguer de plus que
// l'accroche générique qu'il remplace.
const FIGURE_LEAK = /\bkWc\b|\bkWh\b|\bMAD\b|\bDH\b|dirham|m³|%|panneaux|panels|\/\s*mois|\/\s*month|\/\s*an\b|\/\s*yr\b|\/\s*سنة/i;

/** Le bloc markup d'une accroche de repli, `id` inclus, jusqu'à sa fermeture. */
function hookBlock(src: string, id: string): string {
  const start = src.indexOf(`id="${id}"`);
  expect(start, `${id} absent`).toBeGreaterThan(-1);
  const end = src.indexOf('</p>', start);
  expect(end).toBeGreaterThan(start);
  return src.slice(start, end);
}

describe.each(Object.entries(PAGES))('WJ127 — %s : les deux accroches de repli existent', (_label, src) => {
  it('la carte teaser porte `mt-teaser-hook-etude` et `mt-teaser-hook-rappel`, masquées par défaut', () => {
    for (const id of ['mt-teaser-hook-etude', 'mt-teaser-hook-rappel']) {
      const bloc = hookBlock(src, id);
      // `hidden` par défaut : le chemin nominal n'en montre aucune.
      expect(bloc, id).toContain('hidden');
      // Elles vivent bien DANS la carte teaser, pas dans `#mt-doc` masqué.
      expect(src.indexOf(`id="${id}"`)).toBeGreaterThan(src.indexOf('id="mt-teaser"'));
      expect(src.indexOf(`id="${id}"`)).toBeLessThan(src.indexOf('id="mt-doc"'));
    }
  });

  it('aucune des deux ne divulgue de chiffre', () => {
    for (const id of ['mt-teaser-hook-etude', 'mt-teaser-hook-rappel']) {
      expect(hookBlock(src, id), id).not.toMatch(FIGURE_LEAK);
    }
  });

  it('elles annoncent une reprise de contact, pas une estimation', () => {
    const etude = hookBlock(src, 'mt-teaser-hook-etude');
    const rappel = hookBlock(src, 'mt-teaser-hook-rappel');
    // Chaque accroche promet un rappel humain — la seule chose vraie sur ces
    // chemins, puisqu'aucun chiffre n'a pu être calculé.
    expect(etude + rappel).toMatch(/conseiller|adviser|مستشار/i);
  });
});

describe.each(Object.entries(PAGES))('WJ127 — %s : les chemins edge basculent bien sur le repli', (_label, src) => {
  it('`showEstimateTeaser` accepte une variante et pilote les quatre accroches', () => {
    expect(src).toContain("type VarianteTeaser = 'standard' | 'etude' | 'rappel';");
    expect(src).toContain("function showEstimateTeaser(m: string, variante: VarianteTeaser = 'standard')");
    // Le chemin nominal ne montre QUE l'accroche toit ou pompage.
    expect(src).toContain("if (roofHook) roofHook.hidden = isAgri || variante !== 'standard';");
    expect(src).toContain("if (pumpHook) pumpHook.hidden = !isAgri || variante !== 'standard';");
    expect(src).toContain("if (etudeHook) etudeHook.hidden = variante !== 'etude';");
    expect(src).toContain("if (rappelHook) rappelHook.hidden = variante !== 'rappel';");
  });

  it("les deux chemins « trop grand » C&I et le résidentiel appellent la variante « étude »", () => {
    // Trois appels 'etude' : plafond C&I saisi, refus 'too_large' du moteur, et
    // facture résidentielle hors plafond.
    const etudeCalls = (src.match(/showEstimateTeaser\(mode, 'etude'\)/g) ?? []).length;
    expect(etudeCalls).toBe(3);
  });

  it('le rappel agricole (hydraulique manquante) appelle la variante « rappel »', () => {
    const rappelCalls = (src.match(/showEstimateTeaser\(mode, 'rappel'\)/g) ?? []).length;
    expect(rappelCalls).toBe(1);
  });

  it('chaque bascule reste gatée sur PUBLIC_ESTIMATE_GATED (jamais un repli hors parcours public)', () => {
    for (const m of src.match(/showEstimateTeaser\(mode, '(?:etude|rappel)'\)/g) ?? []) {
      const i = src.indexOf(m);
      expect(src.slice(Math.max(0, i - 40), i)).toContain('PUBLIC_ESTIMATE_GATED');
    }
  });
});

describe('WJ127 — parité voyant / lecteur d’écran sur les chemins sans estimation', () => {
  it("l'accroche « étude dédiée » dit la MÊME chose que l'annonce aria-live (FR)", () => {
    // L'annonce existante : « À cette échelle, votre site relève d'une étude
    // dédiée — un ingénieur vous contacte. » L'accroche visible doit porter le
    // même fait : échelle → étude dédiée → reprise de contact.
    const etude = hookBlock(PAGES.FR, 'mt-teaser-hook-etude');
    expect(PAGES.FR).toContain("À cette échelle, votre site relève d'une étude dédiée");
    expect(etude).toContain('À cette échelle');
    expect(etude).toContain('étude dédiée');
  });

  it("l'accroche « rappel » dit la MÊME chose que l'annonce pompage (FR)", () => {
    const rappel = hookBlock(PAGES.FR, 'mt-teaser-hook-rappel');
    expect(PAGES.FR).toContain('Le pompage se dimensionne sur votre profondeur');
    expect(rappel).toContain('se dimensionne');
  });

  it('les deux accroches sont traduites dans les trois locales', () => {
    // FR et AR partagent une page à double couche data-fr/data-ar ; EN a sa
    // propre page. Aucune des trois ne doit rester sur le texte d'une autre.
    for (const id of ['mt-teaser-hook-etude', 'mt-teaser-hook-rappel']) {
      expect(hookBlock(PAGES.FR, id), `FR ${id}`).toContain('data-ar=');
      expect(hookBlock(PAGES.AR, id), `AR ${id}`).toContain('data-ar=');
      // La page EN est mono-langue : pas de data-ar, mais du vrai anglais.
      expect(hookBlock(PAGES.EN, id), `EN ${id}`).not.toContain('data-ar=');
      expect(hookBlock(PAGES.EN, id), `EN ${id}`).toMatch(/adviser will call you back/);
    }
  });
});

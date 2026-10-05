// WJ111 (révisé parcours 3 profils) — le mode AGRICOLE ne doit JAMAIS afficher
// un chiffre RÉSIDENTIEL dérivé de la facture. `estimateFromBill`
// (billEstimate.ts) est un moteur résidentiel (barème domestique) : sans garde,
// un visiteur « Agricole (pompage, ferme) » recevait un kWc/économies calculé
// comme s'il était résidentiel — un chiffre FAUX qui ignore le vrai driver de
// dimensionnement (HMT × débit).
//
// GARDE D'ORIGINE PRÉSERVÉE : computeEstimate() gate sur `mode === 'agricole'`
// AVANT tout appel à estimateFromBill, et la branche agricole n'appelle JAMAIS
// estimateFromBill (elle sort — return — avant le calcul résidentiel).
//
// NOUVEAU CONTRAT (parcours 3 profils) : les chiffres agricoles LÉGITIMES
// viennent désormais de `estimateAgricole` (lib/estimatorAgricole.ts —
// dimensionnement pompage HMT × débit, miroir ERP solar.js), jamais du moteur
// facture résidentiel. Le résidentiel garde son chemin estimateFromBill intact.
// Lecture SOURCE sur les 3 fichiers du parcours (fr/en/ar) — même convention
// que perceivedPerfWJ34.test.ts (micro-interactions DOM non montables sous vitest).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const FR = read('../src/pages/devis/mon-toit.astro');
const EN = read('../src/pages/en/devis/mon-toit.astro');
const AR = read('../src/pages/ar/devis/mon-toit.astro');

// Corps de computeEstimate(), extraction tolérante aux refactors : fin au
// prochain `function` déclaré (ou fin de fichier), plus jamais un marqueur unique.
function computeEstimateBody(src: string): string {
  const start = src.indexOf('function computeEstimate(');
  expect(start).toBeGreaterThan(-1);
  let end = src.indexOf('function showEstimateSkeleton()', start + 1);
  if (end === -1) end = src.indexOf('\n    function ', start + 1);
  if (end === -1) end = src.indexOf('\nfunction ', start + 1);
  if (end === -1) end = src.length;
  expect(end).toBeGreaterThan(start);
  return src.slice(start, end);
}

describe.each([
  ['FR', FR],
  ['EN', EN],
  ['AR', AR],
])('WJ111 — %s mon-toit.astro : agricole n\'affiche jamais un chiffre résidentiel', (_label, src) => {
  it('computeEstimate() gate sur mode === \'agricole\' AVANT le calcul estimateFromBill', () => {
    const body = computeEstimateBody(src);
    const gateIdx = body.indexOf("mode === 'agricole'");
    expect(gateIdx).toBeGreaterThan(-1);
    const estimateCallIdx = body.indexOf('estimateFromBill(');
    // Le garde agricole doit apparaître AVANT le premier appel réel à
    // estimateFromBill dans le corps de la fonction (jamais après).
    expect(estimateCallIdx).toBeGreaterThan(-1);
    expect(gateIdx).toBeLessThan(estimateCallIdx);
  });

  it('la branche agricole SORT (return) avant tout appel à estimateFromBill', () => {
    const body = computeEstimateBody(src);
    const gateIdx = body.indexOf("mode === 'agricole'");
    const estimateCallIdx = body.indexOf('estimateFromBill(');
    // Entre le garde et le premier appel résidentiel, la branche agricole doit
    // rendre la main (return) : jamais un chiffre facture-résidentiel pour elle.
    const between = body.slice(gateIdx, estimateCallIdx);
    expect(between).toContain('return');
    expect(between).not.toContain('estimateFromBill(');
  });

  it('les chiffres agricoles viennent du moteur POMPAGE (estimateAgricole, lib dédiée)', () => {
    // Nouveau contrat : la branche agricole s'appuie sur estimateAgricole
    // (HMT × débit — miroir ERP), jamais sur le moteur facture résidentiel.
    expect(src).toContain('estimateAgricole');
    expect(src).toContain('lib/estimatorAgricole');
  });

  it('résidentiel : le chemin estimateFromBill reste intact (aucune régression)', () => {
    const body = computeEstimateBody(src);
    expect(body).toContain('estimateFromBill(');
  });
});

// ———————————————————————————————————————————————————————————————————————————
// AGW404 — plus de bande « économie carburant » : ni à l'écran, ni dans
// `estimateShown` (CRM), ni dans le message WhatsApp ; la carte montre la
// dépense DÉCLARÉE telle quelle ; le résidentiel est inchangé.
// ———————————————————————————————————————————————————————————————————————————
describe.each([
  ['FR', FR, 'MAD/mois', 'Dépense carburant déclarée'],
  ['EN', EN, 'MAD/month', 'Declared fuel spend'],
  ['AR', AR, 'درهم/شهر', 'نفقة الوقود المصرَّح بها'],
])('AGW404 — %s : économie carburant supprimée', (_label, src, unit, cardLabel) => {
  const code = src.replace(/^[ \t]*\/\/.*$/gm, '');
  it('aucune référence à fuelSaving* ni FUEL_SAVING dans la page', () => {
    expect(code).not.toMatch(/fuelSaving|FUEL_SAVING/);
  });
  it('la branche agricole ne pose aucun ecoMadYear* ni lastSavingsLabel non vide', () => {
    const debut = code.indexOf('function renderAgricoleEstimate(');
    expect(debut).toBeGreaterThan(-1);
    const fin = code.indexOf('announceEstimate(', debut);
    const corps = code.slice(debut, fin);
    expect(corps).not.toContain('ecoMadYear');
    expect(corps).not.toMatch(/lastSavingsLabel = (?!'';)/);
    expect(corps).toContain("lastSavingsLabel = '';");
  });
  it('la carte montre la dépense DÉCLARÉE (sans × 12 ni pourcentage), masquée si vide', () => {
    expect(code).toContain("const depenseDeclaree = num('mt-fuel-spend');");
    expect(code).toContain(`${unit}\``);
    expect(code).not.toMatch(/depenseDeclaree[^;]*\*\s*12/);
    expect(src).toContain(`<p class="mt-doc-kpi-label">${cardLabel}</p>`);
  });
});

// WJ111 — mode AGRICOLE ne doit JAMAIS afficher un chiffre résidentiel fabriqué.
// `estimateFromBill` (billEstimate.ts) est aveugle au mode : il ne lit que
// facture/repère/ville. Sans garde, un visiteur "Agricole (Pompage, ferme)"
// recevait donc un kWc/économies calculé comme s'il était résidentiel — un
// chiffre FAUX qui ignore le vrai driver de dimensionnement (HMT + débit
// souhaité). On vérifie ici, sur les 3 fichiers du parcours (fr/en/ar), que :
//  (1) `computeEstimate()` gate sur `mode === 'agricole'` AVANT tout calcul ;
//  (2) la carte numérique (mt-estimate-body) et les cartes "indisponible"
//      restent masquées dans ce cas, remplacées par la carte qualitative
//      dédiée #mt-estimate-agricole ;
//  (3) résidentiel/professionnel restent sur le chemin `estimateFromBill`
//      inchangé (aucune régression du calcul existant) ;
//  (4) la capture (formulaire/lead) n'est pas touchée par ce garde — lecture
//      SOURCE (même convention que perceivedPerfWJ34.test.ts) : ce sont des
//      micro-interactions DOM qu'on ne peut pas monter facilement sous vitest.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

const FR = read('../src/pages/devis/mon-toit.astro');
const EN = read('../src/pages/en/devis/mon-toit.astro');
const AR = read('../src/pages/ar/devis/mon-toit.astro');

function computeEstimateBody(src: string): string {
  const start = src.indexOf('function computeEstimate(');
  expect(start).toBeGreaterThan(-1);
  const end = src.indexOf('function showEstimateSkeleton()');
  expect(end).toBeGreaterThan(start);
  return src.slice(start, end);
}

describe.each([
  ['FR', FR],
  ['EN', EN],
  ['AR', AR],
])('WJ111 — %s mon-toit.astro : agricole n\'affiche jamais un chiffre résidentiel', (_label, src) => {
  it('la carte qualitative #mt-estimate-agricole existe (masquée par défaut)', () => {
    expect(src).toContain('id="mt-estimate-agricole"');
    const cardStart = src.indexOf('id="mt-estimate-agricole"');
    const cardTag = src.slice(cardStart - 40, cardStart + 40);
    expect(cardTag).toContain('hidden');
  });

  it('computeEstimate() gate sur mode === \'agricole\' AVANT le calcul estimateFromBill', () => {
    const body = computeEstimateBody(src);
    const gateIdx = body.indexOf("mode === 'agricole'");
    expect(gateIdx).toBeGreaterThan(-1);
    const estimateCallIdx = body.indexOf('estimateFromBill(');
    // Le garde agricole doit apparaître AVANT le premier appel réel à
    // estimateFromBill dans le corps de la fonction (jamais après).
    expect(gateIdx).toBeLessThan(estimateCallIdx);
  });

  it('en mode agricole : carte numérique + cartes "indisponible" masquées, carte qualitative affichée', () => {
    const body = computeEstimateBody(src);
    const gateStart = body.indexOf("mode === 'agricole'");
    const gateBlock = body.slice(gateStart, gateStart + 900);
    expect(gateBlock).toContain('card.hidden = true');
    expect(gateBlock).toContain('unavail.hidden = true');
    expect(gateBlock).toContain('toolarge.hidden = true');
    expect(gateBlock).toContain('agricoleEl.hidden = false');
    // Aucun nombre fabriqué : pas d'appel estimateFromBill dans ce bloc.
    expect(gateBlock).not.toContain('estimateFromBill(');
  });

  it('résidentiel/professionnel : le chemin estimateFromBill reste intact après le garde', () => {
    const body = computeEstimateBody(src);
    // WJ112 a étendu les options (exactKwhMonthly/ombrage) mais l'appel réel
    // reste sur la MÊME facture/repère/ville dérivés plus haut dans la fonction.
    expect(body).toMatch(/estimateFromBill\(bill, \{ lat, city[^}]*\}\)/);
  });

  it('le sélecteur de mode recalcule la carte en direct (bascule immédiate vers/depuis agricole)', () => {
    expect(src).toContain("if (!$('mt-estimate-body')?.hidden || !$('mt-estimate-agricole')?.hidden) computeEstimate();");
  });
});

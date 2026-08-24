// PV80 / CJ2b — LA CASE BATTERIE DU GRAPHE « VOTRE PRODUCTION ».
//
// Elle a disparu TROIS fois. La dernière : sur un devis batterie-seule, le
// backend servait `economies_mensuelles` sans figure « avec » (`avec === null`),
// le garde-fou CJ2b concluait « option non vendable » et retirait le calque
// batterie — donc la case, donc le dessin que le client venait chercher.
//
// Ces tests épinglent les invariants qui empêchent la 4ᵉ fois :
//   (1) le garde-fou CJ2b n'interdit RIEN quand le bloc est ABSENT (il ne dit
//       rien) — seul un bloc SERVI qui affirme `avec === null` interdit ;
//   (2) les trois formes de `courbes_journalieres.options`, de bout en bout :
//       ['sans','avec'] ⇒ la commande décochable ; ['avec'] ⇒ le calque montré
//       et ÉTIQUETÉ, sans rien à décocher ; ['sans'] ⇒ ni commande ni calque ;
//   (3) le rendu de la page suit la machine à états (les deux branches de la
//       commande existent, et le calque n'est jamais posé sur du vide).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { economiesInterdisentBatterie, economiesMensuelles, type ProposalResponse } from '../src/lib/proposition';
import {
  initialProductionState,
  productionLayers,
  setBatteryLayer,
  hasProductionBlock,
  type ProductionAvailability,
} from '../src/lib/propositionPage';

const PAGE = readFileSync(
  fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
  'utf-8',
);

const DOUZE = Array.from({ length: 12 }, (_, i) => 100 + i);

/** Le bloc `economies_mensuelles` tel que le backend le sert (clé RACINE). */
function withEco(eco: Record<string, unknown> | null): ProposalResponse {
  const p = {
    reference: 'DEV-202608-0023',
    date: '24/08/2026',
    client_name: 'Reda Kasri',
    statut: 'envoye',
    quote: { ref: 'DEV-202608-0023', date: '24/08/2026', client_name: 'Reda Kasri' },
    roof_image_url: null,
    option_totals: { sans_batterie: 0, avec_batterie: 96000, display_total: 96000, nb_options: 1 },
    accepted: false,
  } as unknown as ProposalResponse;
  return eco === null ? p : ({ ...p, economies_mensuelles: eco } as unknown as ProposalResponse);
}

// ════════════════════════════════════════════════════════════════════════════
describe('CJ2b — le garde-fou « option non vendable » ne parle que quand il SAIT', () => {
  it('bloc ABSENT → il n’interdit RIEN (c’est le cas de tous les devis d’avant)', () => {
    expect(economiesMensuelles(withEco(null))).toBeNull();
    expect(economiesInterdisentBatterie(null)).toBe(false);
    expect(economiesInterdisentBatterie(undefined)).toBe(false);
  });

  it('bloc SERVI avec sa figure « avec » → il n’interdit rien non plus', () => {
    const eco = economiesMensuelles(withEco({
      sans: DOUZE, total_sans: 1200, avec: DOUZE, total_avec: 1500,
      modele: 'horaire', estimation: false, devise: 'MAD',
    }));
    expect(eco?.avec).not.toBeNull();
    expect(economiesInterdisentBatterie(eco)).toBe(false);
  });

  it('bloc SERVI qui dit explicitement « pas de figure avec » → là, il interdit', () => {
    const eco = economiesMensuelles(withEco({
      sans: DOUZE, total_sans: 1200, avec: null, total_avec: null,
      modele: 'horaire', estimation: false, devise: 'MAD',
    }));
    expect(eco).not.toBeNull();
    expect(eco!.avec).toBeNull();
    expect(economiesInterdisentBatterie(eco)).toBe(true);
  });

  it('la page passe par CETTE fonction, plus par un `&&` au fil du code', () => {
    expect(PAGE).toContain('const ecoMensuellesForbidsBattery = economiesInterdisentBatterie(ecoMensuelles);');
    expect(PAGE).toContain('battery: showBatterySim && !!batteryInitial && !ecoMensuellesForbidsBattery,');
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('PV80 — les trois formes d’options, de la donnée au dessin', () => {
  const base: ProductionAvailability = {
    monthly: true, daily: true, variants: ['normal'], battery: true,
  };

  it('(a) devis DEUX options → la commande existe, décochée, et le calque suit le clic', () => {
    for (const avail of [
      { ...base, batteryOptions: ['sans', 'avec'] } as ProductionAvailability,
      base, // clé absente : STRICTEMENT le même comportement
    ]) {
      const s0 = initialProductionState(avail);
      const l0 = productionLayers({ ...s0, view: 'journee' }, avail);
      expect(l0.showBatteryToggle).toBe(true);
      expect(l0.batteryLocked).toBe(false);
      expect(l0.battery).toBe(false);
      // Cochée → le calque se dessine, et la courbe journalière RESTE là
      // (ordre fondateur 24/08 : le calque ne remplace plus le dessin).
      const on = setBatteryLayer(s0, true, avail);
      const l1 = productionLayers(on, avail);
      expect(l1.battery).toBe(true);
      expect(l1.daily).toBe(true);
      // …et décochée, il repart.
      expect(productionLayers(setBatteryLayer(on, false, avail), avail).battery).toBe(false);
    }
  });

  it('(b) devis BATTERIE SEULE → calque TOUJOURS affiché, aucune case à décocher', () => {
    const avail: ProductionAvailability = { ...base, batteryOptions: ['avec'] };
    const s0 = initialProductionState(avail);
    expect(s0.battery).toBe(true);
    const l0 = productionLayers(s0, avail);
    expect(l0.battery).toBe(true);
    expect(l0.batteryLocked).toBe(true);
    // Décocher est ignoré : il n'existe pas de variante sans stockage au devis.
    expect(productionLayers(setBatteryLayer(s0, false, avail), avail).battery).toBe(true);
  });

  it('(c) devis SANS batterie → ni commande, ni calque, et le bloc reste honnête', () => {
    const avail: ProductionAvailability = { ...base, batteryOptions: ['sans'] };
    const l = productionLayers({ ...initialProductionState(avail), view: 'journee', battery: true }, avail);
    expect(l.showBatteryToggle).toBe(false);
    expect(l.batteryLocked).toBe(false);
    expect(l.battery).toBe(false);
    // La courbe nue reprend toute la place — le chapitre n'est pas amputé.
    expect(l.daily).toBe(true);
    expect(hasProductionBlock(avail)).toBe(true);
  });

  it('le calque batterie ne survit JAMAIS à l’absence de courbe journalière', () => {
    const sansCourbe: ProductionAvailability = { ...base, daily: false, batteryOptions: ['avec'] };
    const l = productionLayers(initialProductionState(sansCourbe), sansCourbe);
    expect(l.battery).toBe(false);
    expect(l.showBatteryToggle).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('PV80 — le rendu de la page suit la machine à états (les DEUX branches)', () => {
  it('la commande n’est montée que si l’option est vendable, et se cache par les calques', () => {
    expect(PAGE).toContain('{productionAvailability.battery && (');
    expect(PAGE).toContain('hidden={!prodLayers.showBatteryToggle}');
  });

  it('branche « deux options » = un bouton décochable ; branche « verrouillée » = une étiquette', () => {
    expect(PAGE).toContain('{prodLayers.batteryLocked ? (');
    expect(PAGE).toContain('id="prod-battery-toggle"');
    expect(PAGE).toContain("aria-pressed={prodLayers.battery ? 'true' : 'false'}");
    expect(PAGE).toContain('data-fr="Avec batterie — l’option retenue à votre devis"');
  });

  it('le script client rejoue la MÊME machine à états (zéro divergence serveur/client)', () => {
    expect(PAGE).toContain('if (control) control.hidden = !layers.showBatteryToggle;');
    expect(PAGE).toContain("const batteryBtn = document.getElementById('prod-battery-toggle');");
  });
});

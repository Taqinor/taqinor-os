// RÉGRESSION — le bouton « Toit en pente » de l'estimateur (/preview/toiture-3d-pro-9)
// était INERTE : taper « Toit en pente » (ou « Toit plat ») dans la carte « Étape 2 ·
// type de toit » ne déclenchait AUCUN gestionnaire, sur mobile comme sur desktop.
//
// CAUSE — le câblage des puces `[data-rooftype]` vivait DANS `initRoofToolPro8`, qui ne
// s'exécute qu'APRÈS le boot de la carte (soumission d'adresse / « ouvrir la carte »).
// Sur la page fraîche, avant tout boot, les puces n'avaient donc aucun écouteur de clic.
//
// CORRECTIF — `createRoofTypeSelect` câble TOUTES les puces dès le chargement de la page
// (script de page, avant le boot) ; l'outil 3D s'y ABONNE au lieu de re-câbler.
//
// Ces tests reproduisent le bouton mort (clic → rien) PUIS prouvent qu'il répond.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { createRoofTypeSelect, type RoofTypeButton } from '../src/lib/roofTypeSelect';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

// — Stub DOM minimal (pas de jsdom : aucune dépendance ajoutée). Un tap (mobile) comme
//   un clic (desktop) déclenchent l'événement 'click' du navigateur ; `click()` joue
//   donc l'activation utilisateur des deux plateformes. —
class FakeButton implements RoofTypeButton {
  private attrs = new Map<string, string>();
  private clickHandlers: Array<() => void> = [];
  constructor(rooftype: string, pressed: boolean) {
    this.attrs.set('data-rooftype', rooftype);
    this.attrs.set('aria-pressed', String(pressed));
  }
  getAttribute(name: string): string | null {
    return this.attrs.has(name) ? (this.attrs.get(name) as string) : null;
  }
  setAttribute(name: string, value: string): void {
    this.attrs.set(name, value);
  }
  addEventListener(type: 'click', handler: () => void): void {
    if (type === 'click') this.clickHandlers.push(handler);
  }
  /** Simule l'activation réelle (tap mobile ou clic desktop → événement 'click'). */
  click(): void {
    for (const h of this.clickHandlers) h();
  }
  get pressed(): boolean {
    return this.getAttribute('aria-pressed') === 'true';
  }
}

const makeDoc = (buttons: FakeButton[]) => ({ querySelectorAll: (_s: string) => buttons });

describe('roofTypeSelect — le bouton « Toit en pente » répond (régression bouton inerte)', () => {
  it('un clic sur « Toit en pente » bascule en pente — AVANT tout boot de la carte', () => {
    const flat = new FakeButton('flat', true);
    const pitched = new FakeButton('pitched', false);
    const sel = createRoofTypeSelect(makeDoc([flat, pitched]));

    expect(sel.get()).toBe('flat'); // défaut du markup

    pitched.click(); // ← le geste exact de l'owner sur la page fraîche

    // Avant le correctif, aucun écouteur n'était attaché → ces assertions échouaient.
    expect(sel.get()).toBe('pitched');
    expect(pitched.pressed).toBe(true);
    expect(flat.pressed).toBe(false);
  });

  it('un clic sur « Toit plat » re-bascule en plat (les deux puces sont vivantes)', () => {
    const flat = new FakeButton('flat', true);
    const pitched = new FakeButton('pitched', false);
    const sel = createRoofTypeSelect(makeDoc([flat, pitched]));

    pitched.click();
    expect(sel.get()).toBe('pitched');

    flat.click();
    expect(sel.get()).toBe('flat');
    expect(flat.pressed).toBe(true);
    expect(pitched.pressed).toBe(false);
  });

  it('l’outil 3D (abonné) est notifié du choix — et SEULEMENT sur changement réel', () => {
    const flat = new FakeButton('flat', true);
    const pitched = new FakeButton('pitched', false);
    const sel = createRoofTypeSelect(makeDoc([flat, pitched]));

    const seen: string[] = [];
    sel.subscribe((t) => seen.push(t));

    pitched.click(); // flat → pitched : notifie
    pitched.click(); // pitched → pitched : NE notifie pas (idempotent)
    flat.click(); //    pitched → flat   : notifie

    expect(seen).toEqual(['pitched', 'flat']);
  });

  it('reflète toutes les puces partageant data-rooftype (carte d’étape + panneau de config)', () => {
    // Deux jeux de puces (la carte « Étape 2 » et le panneau de config post-tracé)
    // partagent l'attribut : un seul propriétaire les garde cohérentes.
    const firstFlat = new FakeButton('flat', true);
    const firstPitched = new FakeButton('pitched', false);
    const cfgFlat = new FakeButton('flat', true);
    const cfgPitched = new FakeButton('pitched', false);
    const sel = createRoofTypeSelect(makeDoc([firstFlat, firstPitched, cfgFlat, cfgPitched]));

    firstPitched.click();

    expect(sel.get()).toBe('pitched');
    for (const b of [firstPitched, cfgPitched]) expect(b.pressed).toBe(true);
    for (const b of [firstFlat, cfgFlat]) expect(b.pressed).toBe(false);
  });

  it('un choix « pente » fait avant le boot est honoré (l’outil lit get() au démarrage)', () => {
    const flat = new FakeButton('flat', true);
    const pitched = new FakeButton('pitched', false);
    const sel = createRoofTypeSelect(makeDoc([flat, pitched]));

    pitched.click(); // l'utilisateur choisit la pente AVANT de localiser son toit
    // … plus tard l'outil 3D boote et lit l'état canonique :
    expect(sel.get()).toBe('pitched');
  });

  it('set() programmatique reflète les puces et notifie (utilisé par l’Optimum, etc.)', () => {
    const flat = new FakeButton('flat', true);
    const pitched = new FakeButton('pitched', false);
    const sel = createRoofTypeSelect(makeDoc([flat, pitched]));
    const seen: string[] = [];
    sel.subscribe((t) => seen.push(t));

    sel.set('pitched');
    expect(pitched.pressed).toBe(true);
    expect(seen).toEqual(['pitched']);
  });
});

describe('roofTypeSelect — câblé EAGERLY dans la page (avant le boot de l’outil lourd)', () => {
  const page = read('../src/pages/preview/toiture-3d-pro-9.astro');
  const script = read('../src/scripts/roof-tool-pro9.ts');

  it('la page importe createRoofTypeSelect et le crée AVANT d’importer l’outil lourd', () => {
    expect(page).toContain("import { createRoofTypeSelect } from '../../lib/roofTypeSelect'");
    expect(page).toContain('createRoofTypeSelect(document)');
    // L'instanciation EAGER doit précéder l'import() paresseux de l'outil 3D : c'est ce
    // qui garantit que les puces répondent avant tout boot (la cause du bouton mort).
    expect(page.indexOf('createRoofTypeSelect(document)'))
      .toBeLessThan(page.indexOf("import('../../scripts/roof-tool-pro9.ts')"));
    // Le contrôleur est transmis à l'outil pour qu'il s'y abonne.
    expect(page).toContain('roofType: roofTypeSelect');
  });

  it('l’outil 3D s’ABONNE au contrôleur au lieu de re-câbler les puces lui-même', () => {
    expect(script).toContain('opts.roofType.subscribe(setRoofType)');
    expect(script).toContain('opts.roofType.get()');
  });

  it('importer createRoofTypeSelect ne tire AUCUNE dépendance lourde (lazy intact)', () => {
    const lib = read('../src/lib/roofTypeSelect.ts');
    expect(lib).not.toContain("from 'three'");
    expect(lib).not.toContain("from 'maplibre-gl'");
    expect(lib).not.toContain('import ');
  });
});

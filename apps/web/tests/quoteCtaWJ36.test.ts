// Garde-fou WJ36 — tous les CTA devis/étude du site pointent le parcours
// /devis/mon-toit (plus jamais l'ancien formulaire /contact#simulateur), et le
// CTA principal laiton est UN seul libellé répété verbatim (cta.primary).
// Lecture SOURCE en texte, sans build (convention sticky-cta-w59.test.ts).
//
// WJ38 (plus tard) : localiser le parcours EN/AR = construire les routes
// /en/devis/mon-toit + /ar/devis/mon-toit puis ajouter QUOTE_JOURNEY_PATH à
// STATIC_TRANSLATED dans src/i18n/pages.ts — les assertions ci-dessous sont
// écrites pour rester vertes après cette bascule.
import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

import { ui } from '../src/i18n/ui';
import { QUOTE_JOURNEY_PATH, quoteJourneyHref } from '../src/i18n/pages';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');

/** Tous les fichiers .astro/.md sous un dossier, récursivement. */
function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.(astro|md)$/.test(name)) out.push(p);
  }
  return out;
}

describe('WJ36 — le parcours devis est LA cible canonique', () => {
  it('QUOTE_JOURNEY_PATH = /devis/mon-toit et quoteJourneyHref ne casse jamais', () => {
    expect(QUOTE_JOURNEY_PATH).toBe('/devis/mon-toit');
    expect(quoteJourneyHref('fr')).toBe('/devis/mon-toit');
    // EN/AR : repli FR aujourd'hui, /en|/ar/devis/mon-toit après WJ38 —
    // dans les deux cas le chemin se termine par le parcours (jamais de 404).
    expect(quoteJourneyHref('en').endsWith('/devis/mon-toit')).toBe(true);
    expect(quoteJourneyHref('ar').endsWith('/devis/mon-toit')).toBe(true);
  });

  it('le libellé principal existe verbatim dans les trois locales', () => {
    expect((ui.fr as Record<string, string>)['cta.primary']).toBe('Obtenir mon étude gratuite');
    expect((ui.en as Record<string, string>)['cta.primary']).toBe('Get my free study');
    expect((ui.ar as Record<string, string>)['cta.primary']).toBe('احصل على دراستي المجانية');
  });

  it('plus AUCUN CTA vers /contact#simulateur hors previews', () => {
    const offenders: string[] = [];
    for (const dir of ['../src/pages', '../src/components', '../src/content', '../src/layouts']) {
      for (const f of walk(root(dir))) {
        // Les previews (outils d'estimation à ancre locale) sont hors périmètre WJ36.
        if (f.replace(/\\/g, '/').includes('/pages/preview/')) continue;
        const s = readFileSync(f, 'utf-8');
        if (s.includes('contact#simulateur') || s.includes("'/contact') + '#simulateur'")) {
          offenders.push(f);
        }
      }
    }
    expect(offenders).toEqual([]);
  });

  it('les surfaces partagées passent par le parcours (point de bascule WJ38 unique)', () => {
    const header = read('../src/components/Header.astro');
    const sticky = read('../src/components/StickyCta.astro');
    const band = read('../src/components/CtaBand.astro');
    // En-tête desktop + mobile : L(QUOTE_JOURNEY_PATH) + libellé verbatim.
    expect(header).toContain('L(QUOTE_JOURNEY_PATH)');
    expect(header).toContain("t('cta.primary')");
    // CTA collant + bande finale : quoteJourneyHref(locale).
    expect(sticky).toContain('quoteJourneyHref(locale)');
    expect(band).toContain('quoteJourneyHref(locale)');
    expect(band).toContain("t('cta.primary')");
  });

  it('le héros de l’accueil pointe le parcours (FR/EN/AR)', () => {
    expect(read('../src/pages/index.astro')).toContain('href="/devis/mon-toit"');
    expect(read('../src/pages/en/index.astro')).toContain("href={L('/devis/mon-toit')}");
    expect(read('../src/pages/ar/index.astro')).toContain("href={L('/devis/mon-toit')}");
  });

  it('la page /contact reste vivante (le formulaire n’est pas supprimé)', () => {
    const contact = read('../src/pages/contact.astro');
    expect(contact.length).toBeGreaterThan(0);
  });
});

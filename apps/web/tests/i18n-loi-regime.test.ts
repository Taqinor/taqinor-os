import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  REGIMES,
  REGIMES_BY_LOCALE,
  regimesFor,
  AUTORISATION_THRESHOLD_KW,
  DECLARATION_BT_MAX_KW,
} from '../src/lib/regime';

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf8');

describe('regimesFor — locale-aware regime data (W67)', () => {
  it('FR is the untouched source REGIMES', () => {
    expect(regimesFor('fr')).toBe(REGIMES);
    expect(REGIMES_BY_LOCALE.fr).toBe(REGIMES);
  });

  it('EN returns English titles', () => {
    const en = regimesFor('en');
    expect(en.declaration.title).toBe('Declaration regime');
    expect(en.accord.title).toBe('Connection-agreement regime');
    expect(en.autorisation.title).toBe('Authorization regime');
    // English summaries, not French.
    expect(en.declaration.summary).toMatch(/low voltage/i);
    expect(en.declaration.summary).not.toMatch(/basse tension/i);
    expect(en.autorisation.obligations.join(' ')).toMatch(/ANRE/);
  });

  it('AR returns Arabic titles', () => {
    const ar = regimesFor('ar');
    expect(ar.declaration.title).toBe('نظام التصريح');
    expect(ar.accord.title).toBe('نظام اتفاق الربط');
    expect(ar.autorisation.title).toBe('نظام الترخيص');
    // Arabic script present in summaries.
    expect(ar.declaration.summary).toMatch(/[؀-ۿ]/);
    expect(ar.autorisation.obligations.join(' ')).toMatch(/ANRE/);
  });

  it('every locale keeps the same 3 regime ids and obligation counts', () => {
    for (const locale of ['fr', 'en', 'ar'] as const) {
      const r = regimesFor(locale);
      expect(Object.keys(r).sort()).toEqual(['accord', 'autorisation', 'declaration']);
      expect(r.declaration.id).toBe('declaration');
      expect(r.accord.id).toBe('accord');
      expect(r.autorisation.id).toBe('autorisation');
      // Same structural shape as the FR source (3 obligations each).
      expect(r.declaration.obligations.length).toBe(REGIMES.declaration.obligations.length);
      expect(r.accord.obligations.length).toBe(REGIMES.accord.obligations.length);
      expect(r.autorisation.obligations.length).toBe(REGIMES.autorisation.obligations.length);
    }
  });

  it('thresholds are unchanged (law facts identical across locales)', () => {
    expect(AUTORISATION_THRESHOLD_KW).toBe(5000);
    expect(DECLARATION_BT_MAX_KW).toBe(11);
  });
});

describe('RegimeSelector source — locale branches', () => {
  const src = read('../src/components/RegimeSelector.astro');

  it('has fr/en/ar label branches', () => {
    expect(src).toMatch(/\bfr:\s*\{/);
    expect(src).toMatch(/\ben:\s*\{/);
    expect(src).toMatch(/\bar:\s*\{/);
  });

  it('keeps the French labels verbatim', () => {
    expect(src).toContain('Diagnostic immédiat');
    expect(src).toContain("Quel régime s'applique à votre installation ?");
    expect(src).toContain('Trois questions, réponse immédiate.');
    expect(src).toContain('Régime applicable');
    expect(src).toContain('Faire vérifier mon dossier');
  });

  it('feeds locale-aware regime data and localizes the contact link', () => {
    expect(src).toContain('regimesFor');
    expect(src).toContain('getLocaleFromPath');
    // W247 — le CTA « faites vérifier votre dossier » route désormais vers le
    // parcours de devis via quoteJourneyHref(locale) (helper locale-aware),
    // au lieu de localizeNavHref('/contact') : le lien reste localisé, mais
    // pointe vers /devis/mon-toit et non plus /contact.
    expect(src).toContain('quoteJourneyHref');
  });

  it('keeps the inline determineRegime thresholds identical', () => {
    expect(src).toContain('powerKw >= 5000');
    expect(src).toContain("voltage === 'BT' && powerKw < 11");
  });
});

describe('en/ & ar/ loi-82-21 pages (W67)', () => {
  const en = read('../src/pages/en/loi-82-21.astro');
  const ar = read('../src/pages/ar/loi-82-21.astro');

  it('import the shared Layout', () => {
    expect(en).toMatch(/import Layout from '\.\.\/\.\.\/layouts\/Layout\.astro'/);
    expect(ar).toMatch(/import Layout from '\.\.\/\.\.\/layouts\/Layout\.astro'/);
  });

  it('are not noindex', () => {
    expect(en).not.toContain('noindex');
    expect(ar).not.toContain('noindex');
  });

  it('use localizeNavHref for internal links', () => {
    expect(en).toContain('localizeNavHref');
    expect(ar).toContain('localizeNavHref');
  });

  it('contain a distinctive translated phrase and still reference 82-21', () => {
    expect(en).toContain('Three regimes, only one is yours');
    expect(en).toContain('82-21');
    expect(en).toContain('2-25-100');
    expect(ar).toContain('ثلاثة أنظمة، واحد فقط يعنيك');
    expect(ar).toContain('82-21');
    expect(ar).toContain('2-25-100');
  });

  it('keep the legal date and Latin digits exact', () => {
    expect(en).toContain('9 June 2026');
    expect(ar).toContain('9 يونيو 2026');
  });
});

describe('WAUD47 — /loi-82-21 : textes officiels et « à qui déposer »', async () => {
  const { SOURCES_OFFICIELLES_8221, DEPOT_8221, liensMorts } = await import('../src/lib/sources8221');
  it('3 liens officiels dans les 3 locales (composant partagé), sans société nommée', () => {
    expect(SOURCES_OFFICIELLES_8221.map((s) => s.id)).toEqual(['dahir', 'sgg', 'anre']);
    for (const f of ['../src/pages/loi-82-21.astro', '../src/pages/en/loi-82-21.astro', '../src/pages/ar/loi-82-21.astro']) {
      expect(read(f), f).toContain('<SourcesOfficielles8221');
    }
    for (const l of ['fr', 'en', 'ar'] as const) {
      expect(DEPOT_8221[l].p).not.toMatch(/Lydec|Redal|Amendis|SRM/);
      expect(DEPOT_8221[l].p + DEPOT_8221[l].h2).not.toMatch(/\d/); // ni durée, ni pénalité, ni numéro d'article
      for (const s of SOURCES_OFFICIELLES_8221) expect(s.label[l].length).toBeGreaterThan(10);
    }
    for (const s of SOURCES_OFFICIELLES_8221) expect(s.url).toMatch(/^https:\/\//);
  });
  it('lien mort détecté en CI (fetch simulé) : tout non-200 est signalé', async () => {
    expect(await liensMorts(async () => ({ status: 200 }))).toEqual([]);
    const mort = SOURCES_OFFICIELLES_8221[1].url;
    expect(await liensMorts(async (u) => ({ status: u === mort ? 404 : 200 }))).toEqual([mort]);
    expect(
      await liensMorts(async () => {
        throw new Error('réseau');
      }),
    ).toHaveLength(3);
  });
  it('aucune société de distribution nommée sur les pages loi 82-21', () => {
    for (const f of ['../src/pages/loi-82-21.astro', '../src/pages/en/loi-82-21.astro', '../src/pages/ar/loi-82-21.astro', '../src/lib/constants82_21.ts']) {
      expect(read(f), f).not.toMatch(/Lydec|Redal|Amendis/);
    }
  });
});

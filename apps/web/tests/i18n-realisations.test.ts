// i18n des réalisations + pages ville (W67) — vérifie que les libs de contenu
// (cityContent / caseStudies) sont locale-aware ADDITIVEMENT (FR inchangé, EN/AR
// distincts et non vides) et que chaque page EN/AR créée respecte le contrat
// SEO/i18n : import Layout, getStaticPaths où c'est une route dynamique, pas de
// noindex, jamais le mot « témoignage », usage de localizeNavHref, et émission
// du bon JSON-LD (Service pour les villes, Article pour les études). On confirme
// aussi que realisations.ts n'a pas été touché (faits/chiffres intacts).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { cityContentBySlug } from '../src/lib/cityContent';
import { caseStudyBySlug } from '../src/lib/caseStudies';
import { REALISATIONS, CITIES, realisationByRef } from '../src/lib/realisations';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

describe('cityContentBySlug — locale-aware, additif', () => {
  it('FR par défaut = inchangé ; EN et AR distincts et non vides', () => {
    const fr = cityContentBySlug('casablanca', 'fr');
    const frDefault = cityContentBySlug('casablanca'); // défaut = fr
    const en = cityContentBySlug('casablanca', 'en');
    const ar = cityContentBySlug('casablanca', 'ar');

    // Le défaut sans argument vaut EXACTEMENT le FR.
    expect(frDefault).toEqual(fr);

    // EN/AR diffèrent du FR sur chaque champ de prose principal.
    expect(en.heroLead).not.toBe(fr.heroLead);
    expect(ar.heroLead).not.toBe(fr.heroLead);
    expect(en.closer).not.toBe(fr.closer);
    expect(ar.closer).not.toBe(fr.closer);
    expect(en.pillars.study.body).not.toBe(fr.pillars.study.body);
    expect(ar.pillars.measure.body).not.toBe(fr.pillars.measure.body);

    // Aucun champ vide dans aucune locale.
    for (const cc of [fr, en, ar]) {
      for (const v of [cc.heroLead, cc.sunshineContext, cc.closer, cc.title, cc.description,
        cc.pillars.study.heading, cc.pillars.study.body,
        cc.pillars.measure.heading, cc.pillars.measure.body,
        cc.pillars.compliance.heading, cc.pillars.compliance.body]) {
        expect(v).toBeTruthy();
      }
    }
  });

  it('EN est bien de l’anglais, AR bien de l’arabe (heuristique de script)', () => {
    const en = cityContentBySlug('casablanca', 'en');
    const ar = cityContentBySlug('casablanca', 'ar');
    // Le hero EN contient des mots anglais courants ; pas d'arabe.
    expect(en.heroLead.toLowerCase()).toMatch(/\b(the|we|a|in|year)\b/);
    expect(en.heroLead).not.toMatch(/[؀-ۿ]/);
    // Le hero AR contient des caractères arabes.
    expect(ar.heroLead).toMatch(/[؀-ۿ]/);
  });

  it('le placeholder {intro} survit dans les trois locales (repli + dédiées)', () => {
    for (const loc of ['fr', 'en', 'ar'] as const) {
      // Le repli porte {intro} dans heroLead/closer/title pour toutes les locales.
      const fb = cityContentBySlug('slug-inexistant', loc);
      expect(fb.heroLead).toContain('{intro}');
      expect(fb.closer).toContain('{intro}');
      expect(fb.title).toContain('{intro}');
    }
  });

  it('les chiffres d’ensoleillement « ≈ » et « 82-21 » restent identiques toutes locales', () => {
    // Les CHIFFRES sont identiques en chiffres latins ; seul le séparateur de
    // milliers est typographié selon la locale (espace fine en FR/AR, virgule en
    // EN) — c'est un formatage naturel, pas une altération du nombre.
    const SEP = '[\\s ,]?'; // espace, espace fine, ou virgule
    for (const loc of ['fr', 'en', 'ar'] as const) {
      const cc = cityContentBySlug('casablanca', loc);
      // ≈ 2 950 / 2,950 doit apparaître dans le sunshineContext.
      expect(cc.sunshineContext).toMatch(new RegExp(`2${SEP}950`));
      // Le numéro de loi 82-21 reste exact dans le pilier conformité.
      expect(cc.pillars.compliance.body).toContain('82-21');
      // WB1 (2026-07-04) : le chiffre de production annuel « 14 271 » était
      // fabriqué — retiré du contenu Casablanca ; il ne doit jamais réapparaître.
      expect(cc.heroLead).not.toMatch(new RegExp(`14${SEP}271`));
    }
  });
});

describe('caseStudyBySlug — locale-aware, additif', () => {
  it('FR par défaut = inchangé ; EN et AR distincts et non vides', () => {
    const fr = caseStudyBySlug('casablanca-11-kwc', 'fr');
    const frDefault = caseStudyBySlug('casablanca-11-kwc');
    const en = caseStudyBySlug('casablanca-11-kwc', 'en');
    const ar = caseStudyBySlug('casablanca-11-kwc', 'ar');

    expect(frDefault).toEqual(fr);

    expect(en.situation).not.toBe(fr.situation);
    expect(ar.situation).not.toBe(fr.situation);
    expect(en.resume).not.toBe(fr.resume);
    expect(ar.resume).not.toBe(fr.resume);
    expect(en.title).not.toBe(fr.title);

    for (const cs of [fr, en, ar]) {
      for (const v of [cs.title, cs.description, cs.situation, cs.sizing, cs.install, cs.result, cs.resume]) {
        expect(v).toBeTruthy();
      }
    }
  });

  it('le FR du resume ne contient jamais de production annuelle fabriquée (WB1)', () => {
    // WB1 (2026-07-04) : la production annuelle fabriquée (21 406 / 14 271 /
    // 7 135) a été retirée partout, et les resumes de caseStudies.ts ont été
    // reformulés honnêtement (suivi Deye Cloud, sans chiffre projeté). On ne
    // vérifie donc plus une égalité octet-pour-octet avec realisations.ts —
    // seulement l'invariant d'intégrité : aucun chiffre annuel fabriqué ne
    // reparaît, et chaque resume reste non vide.
    const BANNED = /(21[\s,]?406|14[\s,]?271|7[\s,]?135)/;
    for (const r of REALISATIONS) {
      const cs = caseStudyBySlug(r.slug, 'fr');
      expect(cs.resume, r.ref).toBeTruthy();
      expect(cs.resume, r.ref).not.toMatch(BANNED);
    }
  });

  it('EN anglais / AR arabe (heuristique de script)', () => {
    const en = caseStudyBySlug('el-jadida-17-kwc', 'en');
    const ar = caseStudyBySlug('el-jadida-17-kwc', 'ar');
    expect(en.situation).not.toMatch(/[؀-ۿ]/);
    expect(ar.situation).toMatch(/[؀-ۿ]/);
  });

  it('les chiffres/réfs ne sont jamais altérés ni inventés ; aucune production annuelle fabriquée (WB1)', () => {
    // El Jadida 17 kWc : réf 468 présente dans toutes les locales, mais plus
    // aucun chiffre annuel « 21 406 » (WB1 : retiré, fabriqué) — le récit reste
    // honnête (suivi Deye Cloud, sans chiffre projeté).
    for (const loc of ['fr', 'en', 'ar'] as const) {
      const cs = caseStudyBySlug('el-jadida-17-kwc', loc);
      expect(cs.description).not.toMatch(/21[\s,]?406/);
      expect(cs.result).not.toMatch(/21[\s,]?406/);
      expect(cs.title).toContain('468');
      expect(cs.description).toMatch(/17[,.]04/);
    }
    // Nouaceur (production null) : aucune locale n’invente un chiffre de production.
    for (const loc of ['fr', 'en', 'ar'] as const) {
      const cs = caseStudyBySlug('nouaceur-4-kwc', loc);
      expect(cs.result).not.toMatch(/kWh/);
      // Le récit reste honnête sur l’absence de production publiée.
      expect(cs.description).toMatch(/3[\s.,]?72|NC-10\/25/);
    }
  });

  it('alts traduits indexés par nom de photo, repli FR si absent', () => {
    const en = caseStudyBySlug('el-jadida-17-kwc', 'en');
    // Chaque photo de la réf 468 a un nom ; l’alt EN est fourni et non vide.
    const r = realisationByRef('468')!;
    for (const p of r.photos) {
      const alt = en.alts[p.name] ?? p.alt;
      expect(alt).toBeTruthy();
    }
  });
});

describe('pages EN/AR créées — contrat SEO + i18n', () => {
  const pages = [
    '../src/pages/en/installation-solaire-[city].astro',
    '../src/pages/ar/installation-solaire-[city].astro',
    '../src/pages/en/realisations/index.astro',
    '../src/pages/ar/realisations/index.astro',
    '../src/pages/en/realisations/[slug].astro',
    '../src/pages/ar/realisations/[slug].astro',
  ];

  for (const f of pages) {
    it(`${f} importe Layout, pas de noindex, pas « témoignage », utilise localizeNavHref`, () => {
      const src = read(f);
      expect(src).toContain("layouts/Layout.astro");
      expect(src).toContain('<Layout');
      expect(src).not.toContain('noindex');
      expect(src).not.toContain('témoignage');
      expect(src).toContain('localizeNavHref');
      // jamais la formule de tarif interdite
      expect(src).not.toContain('1,4 MAD/kWh');
      // monte l’élévation comme les pages publiques
      expect(src).toContain('V2Enhance');
      expect(src).toContain('class="v2"');
    });
  }

  const dynamicPages = [
    '../src/pages/en/installation-solaire-[city].astro',
    '../src/pages/ar/installation-solaire-[city].astro',
    '../src/pages/en/realisations/[slug].astro',
    '../src/pages/ar/realisations/[slug].astro',
  ];
  for (const f of dynamicPages) {
    it(`${f} expose getStaticPaths (route dynamique)`, () => {
      expect(read(f)).toContain('getStaticPaths');
    });
  }

  it('les pages ville EN/AR émettent un JSON-LD Service', () => {
    for (const f of ['../src/pages/en/installation-solaire-[city].astro', '../src/pages/ar/installation-solaire-[city].astro']) {
      const src = read(f);
      expect(src).toContain("'@type': 'Service'");
      expect(src).toContain('application/ld+json');
      expect(src).toContain('areaServed');
    }
  });

  it('les études de cas EN/AR émettent un JSON-LD Article', () => {
    for (const f of ['../src/pages/en/realisations/[slug].astro', '../src/pages/ar/realisations/[slug].astro']) {
      const src = read(f);
      expect(src).toContain("'@type': 'Article'");
      expect(src).toContain('application/ld+json');
    }
  });

  it('chaque page a un titre + une description (>10) traduits passés au Layout', () => {
    for (const f of pages) {
      const src = read(f);
      // un attribut title= et description= sur le <Layout ...> (statique ou via const).
      expect(src).toMatch(/title=|const title/);
      expect(src).toMatch(/description=|const description/);
    }
  });
});

describe('realisations.ts — non touché (faits intacts)', () => {
  it('toujours 5 installations, total 43,48 kWc', () => {
    expect(REALISATIONS).toHaveLength(5);
    const total = REALISATIONS.reduce((s, r) => s + r.kwcNum, 0);
    expect(Number(total.toFixed(2))).toBe(43.48);
  });

  it('Nouaceur sans production ; réf. 134 sans onduleur/batterie', () => {
    expect(realisationByRef('NC-10/25')!.production).toBeNull();
    expect(realisationByRef('134')!.onduleur).toBeNull();
    expect(realisationByRef('134')!.batterie).toBeNull();
  });

  it('seule Casablanca a un chantier local (honnêteté hasLocalInstall)', () => {
    expect(CITIES.filter((c) => c.hasLocalInstall).map((c) => c.name)).toEqual(['Casablanca']);
  });
});

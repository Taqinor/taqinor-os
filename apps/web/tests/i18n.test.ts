// Socle i18n (W67) — locales, déduction depuis l'URL, préfixage, traduction
// avec repli FR, et PARITÉ des clés FR/EN/AR (aucune clé non traduite dans le
// chrome). Garde aussi que le FR reprend EXACTEMENT les libellés en ligne.
import { describe, expect, it } from 'vitest';
import { DEFAULT_LOCALE, LOCALES, LOCALE_DIR, isLocale } from '../src/i18n/config';
import { getLocaleFromPath, localizePath, stripLocale, useTranslations } from '../src/i18n/utils';
import { ui } from '../src/i18n/ui';

describe('config des locales', () => {
  it('FR par défaut, 3 locales, AR en rtl', () => {
    expect(DEFAULT_LOCALE).toBe('fr');
    expect([...LOCALES]).toEqual(['fr', 'en', 'ar']);
    expect(LOCALE_DIR.ar).toBe('rtl');
    expect(LOCALE_DIR.fr).toBe('ltr');
    expect(LOCALE_DIR.en).toBe('ltr');
    expect(isLocale('ar')).toBe(true);
    expect(isLocale('de')).toBe(false);
  });
});

describe('déduction & préfixage de chemin', () => {
  it('getLocaleFromPath', () => {
    expect(getLocaleFromPath('/')).toBe('fr');
    expect(getLocaleFromPath('/contact')).toBe('fr');
    expect(getLocaleFromPath('/en/contact')).toBe('en');
    expect(getLocaleFromPath('/ar/')).toBe('ar');
  });

  it('localizePath — FR sans préfixe, EN/AR préfixés', () => {
    expect(localizePath('/contact', 'fr')).toBe('/contact');
    expect(localizePath('/contact', 'en')).toBe('/en/contact');
    expect(localizePath('/contact', 'ar')).toBe('/ar/contact');
    expect(localizePath('/', 'ar')).toBe('/ar');
  });

  it('stripLocale enlève le préfixe', () => {
    expect(stripLocale('/en/contact')).toBe('/contact');
    expect(stripLocale('/ar/')).toBe('/');
    expect(stripLocale('/contact')).toBe('/contact');
  });
});

describe('traduction avec repli', () => {
  it('rend la bonne langue', () => {
    expect(useTranslations('fr')('nav.solutions')).toBe('Solutions');
    expect(useTranslations('en')('nav.residential')).toBe('Residential');
    expect(useTranslations('ar')('nav.faq')).toBe('الأسئلة الشائعة');
  });

  it('repli FR si une clé manque, sinon la clé brute', () => {
    // Clé inconnue → renvoyée telle quelle (jamais « undefined » affiché).
    expect(useTranslations('en')('cle.inexistante')).toBe('cle.inexistante');
  });
});

describe('parité & fidélité du dictionnaire', () => {
  const frKeys = Object.keys(ui.fr).sort();

  it('EN et AR couvrent exactement les mêmes clés que le FR', () => {
    expect(Object.keys(ui.en).sort()).toEqual(frKeys);
    expect(Object.keys(ui.ar).sort()).toEqual(frKeys);
  });

  it('aucune valeur vide dans aucune langue', () => {
    for (const loc of LOCALES) {
      for (const [k, v] of Object.entries(ui[loc])) {
        expect(v, `${loc}.${k} vide`).toBeTruthy();
      }
    }
  });

  it('le FR reprend EXACTEMENT les libellés déjà en ligne', () => {
    expect(ui.fr['nav.diagnosticCta']).toBe('Diagnostic gratuit');
    expect(ui.fr['nav.solutions']).toBe('Solutions');
    expect(ui.fr['footer.legal']).toBe('Mentions légales');
    expect(ui.fr['footer.tagline']).toBe(
      "Installations solaires dimensionnées par l'ingénierie, conformes à la loi 82-21.",
    );
  });
});

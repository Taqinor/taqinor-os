// Socle i18n (W67) — locales, déduction depuis l'URL, préfixage, traduction
// avec repli FR, et PARITÉ des clés FR/EN/AR (aucune clé non traduite dans le
// chrome). Garde aussi que le FR reprend EXACTEMENT les libellés en ligne.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { DEFAULT_LOCALE, LOCALES, LOCALE_DIR, isLocale } from '../src/i18n/config';
import { getLocaleFromPath, localizePath, stripLocale, useTranslations } from '../src/i18n/utils';
import { ui } from '../src/i18n/ui';
import { hasLocale, localesForPath, localizeNavHref, TRANSLATED_PATHS } from '../src/i18n/pages';

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

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
    // WB16 — la racine préfixée garde sa barre finale : `/ar` (sans barre)
    // serait 301-redirigé vers `/ar/` par trailingSlashRedirect
    // (worker/redirects.mjs), donc un hreflang/switcher ne doit jamais cibler
    // la forme sans barre.
    expect(localizePath('/', 'ar')).toBe('/ar/');
  });

  it('stripLocale enlève le préfixe', () => {
    expect(stripLocale('/en/contact')).toBe('/contact');
    expect(stripLocale('/ar/')).toBe('/');
    expect(stripLocale('/contact')).toBe('/contact');
  });

  it('stripLocale préserve la barre finale de façon cohérente (ERR70)', () => {
    // FR (sans préfixe) garde la barre finale…
    expect(stripLocale('/contact/')).toBe('/contact/');
    // …et EN/AR (avec préfixe) la gardent EXACTEMENT pareil → alternates
    // hreflang concordantes, jamais de 301 de canonicalisation de barre finale.
    expect(stripLocale('/en/contact/')).toBe('/contact/');
    expect(stripLocale('/ar/contact/')).toBe('/contact/');
    // Sans barre, les deux formes restent sans barre.
    expect(stripLocale('/en/contact')).toBe('/contact');
    expect(stripLocale('/contact')).toBe('/contact');
    // Racine de locale → racine `/` (jamais de double barre).
    expect(stripLocale('/en/')).toBe('/');
    expect(stripLocale('/en')).toBe('/');
  });

  it('les alternates hreflang concordent depuis FR et depuis EN (ERR70)', () => {
    // Toutes les locales DOIVENT produire le même ensemble d'URL alternates,
    // que la page courante soit la FR (/contact/) ou l'EN (/en/contact/).
    const fromFr = stripLocale('/contact/');
    const fromEn = stripLocale('/en/contact/');
    expect(fromFr).toBe(fromEn);
    for (const loc of ['fr', 'en', 'ar'] as const) {
      expect(localizePath(fromFr, loc)).toBe(localizePath(fromEn, loc));
    }
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
    expect(ui.fr['cta.primary']).toBe('Obtenir mon étude gratuite');
    expect(ui.fr['nav.solutions']).toBe('Solutions');
    expect(ui.fr['footer.legal']).toBe('Mentions légales');
    expect(ui.fr['footer.tagline']).toBe(
      "Installations solaires dimensionnées par l'ingénierie, conformes à la loi 82-21.",
    );
  });

  it('le FR du FORMULAIRE reprend EXACTEMENT les chaînes déjà en ligne', () => {
    // Toute chaîne du formulaire déplacée dans le dictionnaire doit garder son
    // libellé FR au caractère près (le rendu FR ne change pas d'un octet).
    const fr = ui.fr as Record<string, string>;
    expect(fr['form.progress'].replace('{step}', '1')).toBe('Étape 1 sur 3');
    expect(fr['form.submit']).toBe('Recevoir mon étude sur WhatsApp');
    expect(fr['form.heading']).toBe('Diagnostic solaire — 60 secondes');
    expect(fr['form.step1.legend']).toBe('Votre étude commence ici');
    expect(fr['form.bill.label']).toBe("Facture d'électricité mensuelle *");
    expect(fr['form.roof.label']).toBe('Type de toiture *');
    expect(fr['form.step3.legend']).toBe('Recevez votre étude sur WhatsApp');
    expect(fr['form.consent.link']).toBe('Politique de confidentialité');
    expect(fr['form.waOptIn']).toBe('Je préfère être contacté(e) par WhatsApp');
    // Tranches & toitures : les libellés visibles FR = la source BILL_RANGES /
    // ROOF_TYPES (1:1) — seules les VALUES (ids) sont soumises, jamais traduites.
    expect(fr['bill.1000-1500']).toBe('1 000 – 1 500 MAD');
    expect(fr['bill.lt800']).toBe('Moins de 800 MAD');
    expect(fr['roof.villa']).toBe('Villa');
    expect(fr['roof.hangar']).toBe('Hangar industriel');
  });

  it('chiffres & mentions légales conservés EXACTEMENT en EN et AR', () => {
    // Aucun chiffre/claim n'est inventé ni altéré entre les langues : la ligne
    // légale (RC/ICE) et les seuils MAD restent identiques.
    for (const loc of LOCALES) {
      const d = ui[loc] as Record<string, string>;
      expect(d['footer.legalLine']).toBe(
        'TAQINOR Solutions SARLAU — RC 691213 (Casablanca) — ICE 003799642000067',
      );
      // Le seuil et les paliers MAD restent en chiffres latins partout.
      expect(d['bill.gt10000']).toMatch(/10[\s,]?000/);
    }
    // La loi 82-21 garde son numéro exact dans le ruban, toutes langues.
    for (const loc of LOCALES) {
      expect((ui[loc] as Record<string, string>)['ribbon.badge']).toContain('82-21');
    }
  });
});

describe("registre de disponibilité & alternates (anti-lien-mort)", () => {
  it("le FR est toujours disponible ; une page non traduite renvoie ['fr']", () => {
    expect(localesForPath('/contact')).toContain('fr');
    expect(localesForPath('/page-inexistante')).toEqual(['fr']);
    expect(hasLocale('/contact', 'fr')).toBe(true);
  });

  it("localizeNavHref préfixe seulement si la cible existe, sinon repli FR (jamais de lien mort)", () => {
    // FR : jamais de préfixe.
    expect(localizeNavHref('/contact', 'fr')).toBe('/contact');
    // EN/AR : préfixe seulement si la page est traduite.
    if (hasLocale('/contact', 'en')) {
      expect(localizeNavHref('/contact', 'en')).toBe('/en/contact');
    }
    // W67 lot 2 : /guides et les pages ville SONT désormais traduits → préfixés.
    expect(localizeNavHref('/guides', 'en')).toBe('/en/guides');
    expect(localizeNavHref('/installation-solaire-casablanca', 'ar')).toBe('/ar/installation-solaire-casablanca');
    expect(localizeNavHref('/realisations/el-jadida-17-kwc', 'en')).toBe('/en/realisations/el-jadida-17-kwc');
    // Un chemin SANS traduction retombe sur le FR (cible qui existe toujours).
    expect(localizeNavHref('/page-inexistante', 'en')).toBe('/page-inexistante');
  });

  it('toute page listée traduite a réellement ses routes /en/ et /ar/ construites', () => {
    // Garde anti-lien-mort au niveau source : chaque chemin RACINE déclaré
    // traduit doit avoir son fichier de page EN et AR (les routes dynamiques
    // sont couvertes par leur gabarit [city] / [slug]).
    const srcExists = (root: string, locale: 'en' | 'ar'): boolean => {
      const base = root === '/' ? 'index' : root.replace(/^\//, '');
      const candidates = [
        `../src/pages/${locale}/${base}.astro`,
        `../src/pages/${locale}/${base}/index.astro`,
      ];
      if (/^installation-solaire-.+/.test(base)) {
        candidates.push(`../src/pages/${locale}/installation-solaire-[city].astro`);
      }
      if (/^realisations\/.+/.test(base)) {
        candidates.push(`../src/pages/${locale}/realisations/[slug].astro`);
      }
      return candidates.some((f) => {
        try {
          read(f);
          return true;
        } catch {
          return false;
        }
      });
    };
    for (const root of TRANSLATED_PATHS) {
      // Chaque page n'affirme QUE les locales qu'elle déclare (W348 :
      // PARTIAL_TRANSLATED permet une page FR+AR sans EN — ne jamais exiger
      // un mirror EN qu'elle n'annonce pas, sinon lien mort/incohérence).
      for (const loc of localesForPath(root)) {
        if (loc === 'fr') continue; // FR = la page source elle-même
        expect(srcExists(root, loc), `source ${loc.toUpperCase()} manquante pour ${root}`).toBe(true);
      }
    }
  });
});

describe('formulaire de lead — flux de données IDENTIQUE dans toutes les langues', () => {
  // Le composant partagé DiagnosticForm est rendu dans toutes les locales :
  // sa charge utile, ses noms de champs, l'endpoint, le seuil et le deeplink
  // ne dépendent JAMAIS de la locale. On l'affirme sur la SOURCE (une seule
  // source pour toutes les langues) + les libellés d'options gardent l'id.
  const form = read('../src/components/DiagnosticForm.astro');

  it('noms de champs soumis inchangés (charge utile identique)', () => {
    for (const name of ['fullName', 'phone', 'whatsappOptIn', 'city', 'roofType', 'billRange', 'consent',
      'fbclid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']) {
      expect(form, name).toContain(`name="${name}"`);
    }
  });

  it('endpoint unique /api/simulate — jamais dépendant de la locale', () => {
    const fetches = [...form.matchAll(/fetch\(\s*['"]([^'"]+)['"]/g)].map((m) => m[1]);
    expect(fetches).toContain('/api/simulate');
    for (const url of fetches) expect(url.startsWith('/api/')).toBe(true);
  });

  it('le seuil 1 000 MAD et le deeplink WhatsApp restent hors du formulaire (serveur)', () => {
    // Le formulaire ne fixe ni seuil ni numéro WhatsApp : ils vivent côté
    // serveur (lead.ts / billRange.ts / whatsappLink) — inchangés par locale.
    expect(form).not.toContain('1000');
    expect(form).not.toMatch(/wa\.me\//);
    // Le deeplink renvoyé par le serveur est posé tel quel (data.whatsappUrl).
    expect(form).toContain('waEl.href = data.whatsappUrl');
  });

  it("les VALUES des options restent l'id (jamais traduites) ; seul le libellé change", () => {
    // value={r.id} pour les tranches et les toitures → la charge utile soumise
    // est identique quelle que soit la langue d'affichage.
    expect(form).toContain('value={r.id}');
    expect(form).toContain('billLabel(r.id)');
    expect(form).toContain('roofLabel(r.id)');
  });
});

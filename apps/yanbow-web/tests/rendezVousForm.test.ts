/**
 * YBW55 — composant « Prendre rendez-vous », sur le HTML RENDU (FR et EN).
 * (Débordement 320/375/768 px et cibles ≥ 44 px : gardes navigateur YBW15 sur
 * la page sonde qui porte le formulaire, `tests-e2e/overflow.spec.ts`.)
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { experimental_AstroContainer as AstroContainer } from 'astro/container';
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import Formulaire from '../src/components/RendezVousForm.astro';
import { CHAMPS, CLES_CHAMPS, POT_DE_MIEL } from '../src/lib/rdv/champs';
import { lienWhatsApp, WHATSAPP } from '../src/lib/whatsapp';
import { DIST_CLIENT, pageRendue } from './builtHtml';

async function rendre(props: Record<string, unknown>): Promise<Document> {
  const container = await AstroContainer.create();
  return new JSDOM(await container.renderToString(Formulaire, { props })).window.document;
}

/** Texte visible + attributs lisibles (aria-label, placeholder, data-texte-*, libellés JSON). */
function texteLisible(doc: Document): string {
  const morceaux = [doc.body.textContent ?? ''];
  for (const el of doc.querySelectorAll('*')) {
    for (const a of Array.from(el.attributes)) {
      if (/^(aria-label|placeholder|title|alt|data-texte-.*|data-libelles)$/.test(a.name)) morceaux.push(a.value);
    }
  }
  return morceaux.join(' ');
}

const MOTS_FRANCAIS = /\b(Envoyer|demande|Société|facultatif|obligatoire|Choisir|Merci|J.accepte|Vérifiez|Écrire|Nom et prénom|Ne pas remplir|Développement|aucune donnée|Réessayez|Confidentialité)\b/i;

describe('YBW55 — formulaire rendu', () => {
  it('FR : champs du registre, noValidate, POST, consentement non coché, aucun pixel', async () => {
    const doc = await rendre({ locale: 'fr' });
    const form = doc.querySelector('form[data-rendez-vous]')!;
    expect(form.hasAttribute('novalidate')).toBe(true);
    expect(form.getAttribute('method')).toBe('post');
    expect(form.getAttribute('data-langue')).toBe('fr');
    // Champs saisis = ceux du registre marqués `saisi`, et rien d'autre (hors pot de miel).
    const saisis = CLES_CHAMPS.filter((k) => CHAMPS[k].saisi);
    const noms = [...form.querySelectorAll('input, select, textarea')].map((e) => e.getAttribute('name'));
    expect(noms.filter((n) => n !== POT_DE_MIEL).sort()).toEqual([...saisis].sort());
    for (const n of noms) expect(n === POT_DE_MIEL || (CLES_CHAMPS as string[]).includes(n!)).toBe(true);
    // Longueurs maximales = registre.
    for (const k of saisis) {
      const max = (CHAMPS[k] as { max?: number }).max;
      if (max) expect(form.querySelector(`[name="${k}"]`)!.getAttribute('maxlength')).toBe(String(max));
    }
    const consentement = form.querySelector<HTMLInputElement>('input[name="consentement"]')!;
    expect(consentement.type).toBe('checkbox');
    expect(consentement.hasAttribute('checked')).toBe(false);
    // Produit : les valeurs du contrat, dans la langue.
    expect([...form.querySelectorAll('select[name="produit"] option')].map((o) => o.getAttribute('value'))).toEqual(['', ...CHAMPS.produit.valeurs]);
    expect(doc.body.textContent).toContain('Développement sur mesure');
    // Aide « aucune donnée sensible » sous le message.
    expect(doc.querySelector('[data-aide-message]')!.textContent).toMatch(/aucune donnée sensible/);
    // Aucun pixel, iframe ni script tiers ; aucune donnée en champ caché.
    expect(doc.querySelectorAll('img, iframe, input[type="hidden"]').length).toBe(0);
    expect(texteLisible(doc)).not.toMatch(/undefined|null/);
  });

  it('chaque champ a son message d’erreur SOUS lui, lié par aria-describedby, et un bandeau', async () => {
    const doc = await rendre({ locale: 'fr' });
    for (const k of ['nom', 'societe', 'email', 'telephone', 'produit', 'message', 'consentement']) {
      const el = doc.querySelector(`[name="${k}"]`)!;
      const erreur = doc.querySelector(`[data-erreur-pour="${k}"]`)!;
      expect(el.getAttribute('aria-describedby')!.split(' ')).toContain(erreur.id);
      expect(erreur.closest('[data-champ]')).toBe(el.closest('[data-champ]'));
      // Le message suit le champ dans le document (sous lui).
      expect(el.compareDocumentPosition(erreur) & 4).toBe(4);
      const label = doc.querySelector(`label[for="${el.id}"]`);
      expect(label?.textContent?.trim()).toBeTruthy();
    }
    const bandeau = doc.querySelector('[data-bandeau]')!;
    expect(bandeau.getAttribute('role')).toBe('alert');
  });

  it('pot de miel : motif CLIP, hors tabulation, jamais left:-9999px (CSS du BUILD)', async () => {
    const doc = await rendre({ locale: 'fr' });
    const pot = doc.querySelector<HTMLInputElement>(`input[name="${POT_DE_MIEL}"]`)!;
    expect(pot.getAttribute('tabindex')).toBe('-1');
    expect(pot.closest('.rdv-pot')!.getAttribute('aria-hidden')).toBe('true');
    // La page Rendez-vous CONSTRUITE (YBW66) porte le formulaire : on lit les feuilles de style qu'elle sert.
    const page = pageRendue('/rendez-vous/');
    expect(page.document.querySelector('form[data-rendez-vous]')).not.toBeNull();
    const feuilles = [...page.document.querySelectorAll('link[rel="stylesheet"]')].map((l) =>
      readFileSync(join(DIST_CLIENT, l.getAttribute('href')!.replace(/^\//, '')), 'utf-8'),
    );
    const css = [...feuilles, ...[...page.document.querySelectorAll('style')].map((s) => s.textContent ?? '')].join('\n').replace(/\s+/g, '');
    const regle = /\.rdv-pot(\[[^\]]+\])?\{[^}]*\}/.exec(css)?.[0] ?? '';
    expect(regle).toMatch(/clip-path:inset\(50%\)/);
    expect(css).not.toMatch(/-9999px/);
    // Scripts servis : même origine seulement.
    for (const s of page.document.querySelectorAll('script[src]')) expect(s.getAttribute('src')!.startsWith('/')).toBe(true);
  });

  it('EN : même composant, aucun mot français ni « undefined »', async () => {
    const doc = await rendre({ locale: 'en', whatsapp: '33600000000' });
    expect(doc.querySelector('form')!.getAttribute('data-langue')).toBe('en');
    const texte = texteLisible(doc);
    expect(texte).not.toMatch(/undefined/);
    expect(texte).not.toMatch(MOTS_FRANCAIS);
    expect(texte).toContain('Custom software');
    expect(texte).toContain('Send the request');
    expect(doc.querySelector('[data-aide-message]')!.textContent).toMatch(/sensitive data/);
  });

  it('WhatsApp : absent tant que le numéro n’est pas fourni ; présent (wa.me) sinon', async () => {
    expect(WHATSAPP).toBeNull();
    expect((await rendre({ locale: 'fr' })).querySelector('[data-whatsapp]')).toBeNull();
    const avec = await rendre({ locale: 'fr', whatsapp: '+33 6 00 00 00 00' });
    expect(avec.querySelector('[data-succes] [data-whatsapp]')!.getAttribute('href')).toBe('https://wa.me/33600000000');
    expect(lienWhatsApp('abc')).toBeNull();
  });

  it('consentement lié à la page Confidentialité seulement quand elle est publiable', async () => {
    const ferme = await rendre({ locale: 'fr', completes: [] });
    expect(ferme.querySelector('[data-champ="consentement"] a')).toBeNull();
    const ouvert = await rendre({ locale: 'fr', completes: ['/confidentialite'] });
    expect(ouvert.querySelector('[data-champ="consentement"] a[data-page="confidentialite"]')!.getAttribute('href')).toBe('/confidentialite/');
  });

  it('aucune promesse de délai de réponse', async () => {
    for (const locale of ['fr', 'en']) {
      const texte = (await rendre({ locale, whatsapp: '33600000000' })).body.textContent ?? '';
      expect(texte).not.toMatch(/\d+\s*(h|heures?|hours?|min|jours?|days?)\b|sous\s+\d|within|rapidement|quickly|immédiatement|immediately/i);
    }
  });
});

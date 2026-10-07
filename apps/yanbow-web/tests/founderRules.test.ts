/**
 * YBW17 — règles fondateur (RULES.md) vérifiées sur le HTML RENDU, FR et EN.
 * Chaque règle a une fixture qui la viole (le test qui rougit la nomme) ; le
 * site réel (toutes les pages construites) doit être à zéro violation.
 */
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import { pagesRendues } from './builtHtml';

type Regle = {
  id: string;
  /** Motifs interdits dans le texte public (visible + méta + alt + JSON-LD). */
  motifs?: RegExp[];
  /** Contrôle sur le document quand un motif ne suffit pas. */
  controle?: (doc: Document, texte: string) => string[];
};

/** Phrases (découpées sur . ! ? et les fins de bloc) de chaque bloc de texte. */
function phrases(doc: Document): string[] {
  const blocs = doc.querySelectorAll('p, li, h1, h2, h3, h4, h5, h6, td, th, figcaption, blockquote, dd, dt, a, button, span, div');
  const out: string[] = [];
  for (const b of Array.from(blocs)) {
    // Texte propre au bloc (sans ses blocs enfants, déjà visités).
    const propre = Array.from(b.childNodes)
      .map((n) => (n.nodeType === 3 ? n.textContent ?? '' : ['SPAN', 'EM', 'STRONG', 'B', 'I', 'A'].includes((n as Element).tagName) ? n.textContent ?? '' : ' | '))
      .join('');
    for (const p of propre.split(/[.!?|]+/)) if (p.trim()) out.push(p.trim());
  }
  return out;
}

export const REGLES: Regle[] = [
  { id: 'R1-PRIX', motifs: [/€/, /\bEUR\b/, /\bMAD\b/, /\bDHS?\b/, /\btarifs?\b/i, /\bpricing\b/i, /\bprices?\b/i] },
  {
    id: 'R2-CHIFFRES',
    motifs: [
      /\d[\d\s.,]*\+?\s*(clients?|customers?|installations?|installateurs?|installers?|utilisateurs?|users?|projets?|projects?|entreprises?|companies|sociétés)\b/i,
      /\d[\d\s.,]*\+?\s*(ans|années|years?)\b/i,
    ],
  },
  {
    id: 'R3-PREUVE-SOCIALE',
    motifs: [
      /avis (clients?|vérifiés)/i,
      /t[ée]moignages?/i,
      /\btestimonials?\b/i,
      /\breviews?\b/i,
      /[★⭐]/,
      /\b[ée]toiles\b/i,
      /\bstars?\b/i,
      /aggregateRating/,
      /compte à rebours/i,
      /\bcountdown\b/i,
      /offre limitée/i,
      /limited[- ](time|offer)/i,
    ],
  },
  {
    id: 'R4-COMPTE',
    motifs: [/essai gratuit/i, /\binscri(ption|vez|re)\b/i, /cr[ée]er un compte/i, /free trial/i, /sign[- ]?up/i, /create an account/i, /\bregister\b/i],
  },
  { id: 'R5-ANCRETO', motifs: [/ancreto/i] },
  { id: 'R6-MARQUE', motifs: [/®/, /marque déposée/i, /registered trademark/i, /\bOMPIC\b/i] },
  { id: 'R7-EMPLOI', motifs: [/rempla(cer|ce|cez)\s+(un|vos|des|votre)\s+(employ|salari)/i, /replac(e|es|ing)\s+(an?|your)\s+(employee|staff|worker)/i] },
  { id: 'R8-SCRAPING', motifs: [/scraping/i, /[ée]tats[- ]unis/i, /\bUSA\b/, /united states/i, /australi[ae]/i] },
  {
    id: 'R9-VEILLE',
    motifs: [/\bveille\b/i, /ad library/i, /biblioth[èe]que (publicitaire|des publicités)/i, /competitor ads?/i, /ad intelligence/i],
  },
  { id: 'R10-FRANCE', motifs: [/pr[êe]t pour la france/i, /ready for france/i] },
  {
    id: 'R11-IDENTIFIANTS',
    motifs: [/691213/, /003799642000067/, /212661850410/, /d[ée]claration CNDP en cours/i, /reda kasri/i],
  },
  { id: 'R12-NOM-ENTREPRISE', motifs: [/taqinor/i] },
  {
    id: 'R13-MARKETINGBOW',
    controle: (doc) =>
      phrases(doc)
        .filter((p) => /marketingbow/i.test(p) && /(en service|en production|in use|in production|\blive\b)/i.test(p))
        .map((p) => p.slice(0, 120)),
  },
  {
    id: 'R14-PERSONNES',
    controle: (doc) =>
      Array.from(doc.querySelectorAll('img, picture source, [style*="background-image"]'))
        .map((el) => `${el.getAttribute('src') ?? ''} ${el.getAttribute('srcset') ?? ''} ${el.getAttribute('alt') ?? ''} ${el.getAttribute('style') ?? ''}`)
        .filter((s) => /(portrait|team|[ée]quipe|fondateur|founder|person|visage|face|headshot|avatar|selfie|people|gens)/i.test(s))
        .map((s) => s.trim().slice(0, 120)),
  },
];

/** Texte public d'une page : visible + titre + méta + alt/title/aria-label + JSON-LD. */
export function textePublic(doc: Document): string {
  const parties: string[] = [];
  const corps = doc.body?.cloneNode(true) as HTMLElement | undefined;
  if (corps) {
    corps.querySelectorAll('script:not([type="application/ld+json"]), style, noscript template').forEach((n) => n.remove());
    parties.push(corps.textContent ?? '');
  }
  parties.push(doc.title);
  doc.querySelectorAll('meta[content]').forEach((m) => parties.push(m.getAttribute('content') ?? ''));
  doc.querySelectorAll('[alt], [title], [aria-label], [placeholder]').forEach((el) => {
    for (const a of ['alt', 'title', 'aria-label', 'placeholder']) parties.push(el.getAttribute(a) ?? '');
  });
  doc.querySelectorAll('script[type="application/ld+json"]').forEach((s) => parties.push(s.textContent ?? ''));
  return parties.join('\n');
}

/** Violations de toutes les règles sur un document : `[{ id, extrait }]`. */
export function violations(doc: Document): { id: string; extrait: string }[] {
  const texte = textePublic(doc);
  const out: { id: string; extrait: string }[] = [];
  for (const r of REGLES) {
    for (const m of r.motifs ?? []) {
      const hit = texte.match(m);
      if (hit) out.push({ id: r.id, extrait: hit[0] });
    }
    for (const e of r.controle?.(doc, texte) ?? []) out.push({ id: r.id, extrait: e });
  }
  return out;
}

const doc = (corps: string, lang = 'fr') =>
  new JSDOM(`<!doctype html><html lang="${lang}"><head><title>t</title></head><body><main>${corps}</main></body></html>`).window.document;

/** Une fixture FR et une EN qui violent CHAQUE règle. */
const FIXTURES: Record<string, [string, string]> = {
  'R1-PRIX': ['<p>À partir de 990 € par mois</p>', '<p>Pricing on request</p>'],
  'R2-CHIFFRES': ['<p>Plus de 120 clients satisfaits</p>', '<p>10 years of experience</p>'],
  'R3-PREUVE-SOCIALE': ['<p>Lisez nos témoignages</p>', '<p>★★★★★ customer reviews</p>'],
  'R4-COMPTE': ['<a href="/x">Essai gratuit</a>', '<a href="/x">Sign up now</a>'],
  'R5-ANCRETO': ['<p>Ancreto, notre ERP</p>', '<p>Ancreto ERP</p>'],
  'R6-MARQUE': ['<p>SolarBow®</p>', '<p>a registered trademark</p>'],
  'R7-EMPLOI': ['<p>Remplacer un employé par un logiciel</p>', '<p>Replace an employee</p>'],
  'R8-SCRAPING': ['<p>Couverture États-Unis</p>', '<p>Ad scraping in Australia</p>'],
  'R9-VEILLE': ['<p>La veille des publicités concurrentes</p>', '<p>Powered by the Meta Ad Library</p>'],
  'R10-FRANCE': ['<p>SolarBow est prêt pour la France</p>', '<p>Ready for France</p>'],
  'R11-IDENTIFIANTS': ['<p>RC 691213</p>', '<p>Contact: M. Reda Kasri</p>'],
  'R12-NOM-ENTREPRISE': ['<p>Construit chez TAQINOR</p>', '<p>Built at Taqinor</p>'],
  'R13-MARKETINGBOW': ['<p>MarketingBow est en service chez nos clients.</p>', '<p>MarketingBow is in use today.</p>'],
  'R14-PERSONNES': ['<img src="/img/equipe.webp" alt="Notre équipe">', '<img src="/img/founder-portrait.webp" alt="Founder">'],
};

describe('YBW17 — chaque règle rougit sur une fixture qui la viole (FR et EN)', () => {
  for (const r of REGLES) {
    const [fr, en] = FIXTURES[r.id] ?? ['', ''];
    it(`${r.id} — fixture FR`, () => {
      expect(violations(doc(fr)).map((v) => v.id)).toContain(r.id);
    });
    it(`${r.id} — fixture EN`, () => {
      expect(violations(doc(en, 'en')).map((v) => v.id)).toContain(r.id);
    });
  }

  it('chaque règle de RULES.md a sa fixture', () => {
    expect(Object.keys(FIXTURES).sort()).toEqual(REGLES.map((r) => r.id).sort());
  });

  it('un texte conforme ne déclenche rien', () => {
    const ok = doc('<h1>Des logiciels métier</h1><p>MarketingBow crée les campagnes en pause. Prenez rendez-vous.</p>');
    expect(violations(ok)).toEqual([]);
  });

  it('le JSON-LD et les méta-descriptions sont contrôlés aussi', () => {
    const d = new JSDOM(
      '<!doctype html><html lang="fr"><head><title>t</title><meta name="description" content="Prix : 10 MAD"></head><body><script type="application/ld+json">{"aggregateRating":{}}</script></body></html>',
    ).window.document;
    const ids = violations(d).map((v) => v.id);
    expect(ids).toContain('R1-PRIX');
    expect(ids).toContain('R3-PREUVE-SOCIALE');
  });
});

describe('YBW17 — le site réel respecte toutes les règles', () => {
  const pages = pagesRendues();
  it('au moins une page construite est contrôlée', () => expect(pages.length).toBeGreaterThan(0));
  for (const p of pages) {
    it(`${p.url} (${p.langueUrl}) : 0 violation`, () => {
      expect(violations(p.document)).toEqual([]);
    });
  }
});

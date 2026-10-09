/**
 * YBW67 — fiche de relecture FR générée depuis le RENDU (`scripts/review-sheet.mjs`).
 * Rougit si la fiche committée ne reflète plus les pages construites (une
 * affirmation rendue absente de la fiche, une page manquante).
 */
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';
import { describe, expect, it } from 'vitest';
import { executer } from '../scripts/check-claims.mjs';
import { pagesFr, phrasesPubliques } from '../scripts/review-sheet.mjs';
import { PAGES } from '../src/i18n/pages';
import { pagesRendues } from './builtHtml';

const FICHE = readFileSync(fileURLToPath(new URL('../REVIEW_FR.md', import.meta.url)), 'utf-8');

describe('YBW67 — phrasesPubliques', () => {
  it('une affirmation (même portée par un enfant du titre) est liée à son identifiant ; le reste est « interface »', () => {
    const doc = new JSDOM(
      '<main><h1><span data-affirmation="A1">Titre affirmé</span></h1><p data-affirmation="A2">Fait.</p><ul><li><a href="/x/">Lien</a></li></ul><p class="rdv-pot">Piège</p></main>',
    ).window.document;
    expect(phrasesPubliques(doc).map((p: { texte: string; affirmation: string | null }) => [p.texte, p.affirmation])).toEqual([
      ['Titre affirmé', 'A1'],
      ['Fait.', 'A2'],
      ['Lien', null],
    ]);
  });
});

describe('YBW67 — REVIEW_FR.md à jour avec le rendu', () => {
  it('une section par page française construite', () => {
    const pages = pagesFr();
    expect(pages.length).toBe(6);
    for (const p of pages) expect(FICHE, p.url).toContain(`\`${p.url}\``);
  });

  for (const p of pagesRendues().filter((x) => Object.values(PAGES).some((c) => c.fr === x.url))) {
    it(`${p.url} : chaque affirmation rendue figure dans la fiche avec son identifiant et sa phrase`, () => {
      for (const el of p.document.querySelectorAll('[data-affirmation]')) {
        const ligne = FICHE.split('\n').find((l) => l.includes(`\`${el.getAttribute('data-affirmation')}\``) && l.includes((el.textContent ?? '').replace(/\s+/g, ' ').trim()));
        expect(ligne, el.getAttribute('data-affirmation')!).toBeDefined();
      }
    });
  }

  // `--stale` n'est PAS asserté ici : toute coche du plan (preuve de plusieurs affirmations) le
  // rouvrirait en CI. La fiche en consigne l'état ; la porte de lancement (YBW85) le bloque.
  it('check-claims sans erreur', async () => {
    expect((await executer()).erreurs).toEqual([]);
  });
});

// Architecture de l'information — lot W27–W31 : en-tête à déroulants
// (Solutions / Ressources), pied de page à vrais liens, hub Nos solutions,
// section accueil, pedigree fondateur. Garde-fous purement source (les
// composants Astro ne sont pas rendus ici).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { ui } from '../src/i18n/ui';

const uiFr = ui.fr as Record<string, string>;

const read = (rel: string) => readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');

const header = read('../src/components/Header.astro');
const footer = read('../src/components/Footer.astro');
const index = read('../src/pages/index.astro');
const hub = read('../src/pages/nos-solutions.astro');
const apropos = read('../src/pages/à-propos.astro');
const pourquoi = read('../src/pages/pourquoi-taqinor.astro');

// Les 6 solutions, dans l'ordre canonique (W28/W29/W30/W31).
const SOLUTIONS = [
  '/résidentiel',
  '/professionnel',
  '/pompage-solaire',
  '/batteries-stockage',
  '/maintenance-monitoring',
  '/regularization-article-33',
];
const RESSOURCES = ['/guides', '/faq', '/loi-82-21', '/pourquoi-taqinor', '/financement', '/marocains-du-monde'];

describe('W28 — en-tête : nav primaire + déroulants accessibles', () => {
  it('les deux déclencheurs sont de vrais liens vers leur hub (repli sans-JS)', () => {
    // W67 — les href sont localisés via L('/x') (FR = chemin inchangé) ; on
    // vérifie donc le chemin racine référencé, pas la forme href littérale.
    expect(header).toContain("L('/nos-solutions')"); // Solutions → hub
    expect(header).toContain("L('/guides')"); // Ressources → hub guides
    expect(header).toContain('data-dropdown');
    expect(header).toContain('aria-haspopup="true"');
  });

  it('le menu Solutions liste les 6 solutions dans l’ordre', () => {
    for (const h of SOLUTIONS) expect(header, h).toContain(`href: '${h}'`);
  });

  it('le menu Ressources liste Guides, FAQ, Loi 82-21 expliquée, Pourquoi, Financement, MRE', () => {
    for (const h of RESSOURCES) expect(header, h).toContain(`href: '${h}'`);
  });

  it('À propos reste en nav primaire', () => {
    // W67 — lien localisé via L('/à-propos') (FR = '/à-propos' inchangé).
    expect(header).toContain("L('/à-propos')");
  });

  it('accessibilité : révélation au focus (sans JS) + Échap referme (JS)', () => {
    expect(header).toContain('group-focus-within:');
    expect(header).toContain("'Escape'");
    expect(header).toContain('role="menu"');
    expect(header).toContain('role="menuitem"');
  });

  it('l’explainer Loi 82-21 sort de la nav de 1er niveau (plus de lien primaire « Loi 82-21 »)', () => {
    // Présent — mais uniquement comme item Ressources « Loi 82-21 expliquée ».
    // W67 — le libellé vient désormais du dictionnaire (clé nav.law), dont la
    // valeur FR reste « Loi 82-21 expliquée ».
    expect(header).toContain('/loi-82-21');
    expect(header).toContain("t('nav.law')");
    expect(uiFr['nav.law']).toBe('Loi 82-21 expliquée');
    // L’ancien lien primaire dont le libellé rendu était « Loi 82-21 » n’existe plus.
    expect(header).not.toMatch(/>Loi 82-21</);
  });
});

describe('W29 — pied de page : Solutions/Ressources en VRAIS liens', () => {
  it('colonne Solutions : les 6 services liés', () => {
    for (const h of SOLUTIONS) expect(footer, h).toContain(`href: '${h}'`);
  });

  it('colonne Ressources : réalisations, guides, faq, loi-82-21, pourquoi, financement, MRE, à-propos', () => {
    for (const h of ['/realisations', '/guides', '/faq', '/loi-82-21', '/pourquoi-taqinor', '/financement', '/marocains-du-monde', '/à-propos']) {
      expect(footer, h).toContain(`href: '${h}'`);
    }
  });

  it('le hub solutions et les villes sont liés', () => {
    // W67 — lien hub localisé via L('/nos-solutions') (FR inchangé).
    expect(footer).toContain("L('/nos-solutions')");
    expect(footer).toContain('installation-solaire-');
  });

  it('ne rend plus la liste « Services » en texte non cliquable (NAP.services)', () => {
    expect(footer).not.toContain('NAP.services');
  });
});

describe('W30 — hub « Nos solutions »', () => {
  it('liste les 6 solutions et émet un CollectionPage', () => {
    for (const h of SOLUTIONS) expect(hub, h).toContain(`href: '${h}'`);
    expect(hub).toContain("'@type': 'CollectionPage'");
  });
});

describe('W31 — section « Nos solutions » sur l’accueil', () => {
  it('l’accueil rend une section solutions liée aux 6 pages + au hub', () => {
    for (const h of SOLUTIONS) expect(index, h).toContain(`href: '${h}'`);
    expect(index).toContain('href="/nos-solutions"');
    expect(index).toContain('Nos solutions');
  });
});

describe('W27 — À propos : pedigree fondateur approuvé + réconciliation Pourquoi', () => {
  it('nomme les trois employeurs approuvés', () => {
    for (const e of ['Huawei', 'Ericsson', 'STMicroelectronics']) expect(apropos, e).toContain(e);
  });

  it('À propos et Pourquoi Taqinor sont croisées dans les deux sens', () => {
    expect(apropos).toContain('href="/pourquoi-taqinor"');
    expect(pourquoi).toContain('href="/à-propos"');
  });
});

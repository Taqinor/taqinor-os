// Audit item 66 (revue Fable finale) — la contre-signature Taqinor.
//
// Le PDF (apps/ventes/quote_engine/residential/trust.py) affiche DEUX cases
// de signature côte à côte : « Bon pour accord — le client » (nom + zone de
// tracé + « Nom, date, mention « Bon pour accord » & signature ») ET
// « Pour {brand} / Cachet et signature » (+ « Le devis fait foi dès
// réception de l'acompte »). La page /proposition/[token] ne portait QUE la
// première (le canvas manuscrit du client, section #signer) — le client
// signait seul, sans jamais voir sur l'écran l'engagement RÉCIPROQUE que le
// PDF lui montre pourtant. Ce test pin le panneau additif qui comble l'écart :
// DISPLAY ONLY (aucun canvas, aucun nouvel endpoint), sous le bloc de
// signature existant, jamais un layout qui dérange le formulaire au-dessus.
//
// Même convention que propositionFoldWJ114.test.ts : lecture SOURCE en texte
// (un montage DOM complet d'un .astro n'est pas praticable ici).
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const root = (rel: string) => fileURLToPath(new URL(rel, import.meta.url));
const read = (rel: string) => readFileSync(root(rel), 'utf-8');
const PROPOSITION = read('../src/pages/proposition/[...token].astro');

// Le panneau doit vivre ENTRE la fin du formulaire de signature du client
// (#sign-form) et le bloc « quelle version télécharger » qui suit — jamais
// À L'INTÉRIEUR du <form>, jamais avant le canvas client.
const formEnd = PROPOSITION.indexOf('</form>', PROPOSITION.indexOf('id="sign-form"'));
const panelStart = PROPOSITION.indexOf('id="prop-contre-signature"');
const pdfVariantStart = PROPOSITION.indexOf('L-VAR · QUELLE VERSION TÉLÉCHARGER');
const panel = PROPOSITION.slice(panelStart, pdfVariantStart);

describe('Audit item 66 — panneau de contre-signature Taqinor', () => {
  it('existe et est monté APRÈS le formulaire de signature client, avant le bloc PDF', () => {
    expect(formEnd).toBeGreaterThan(0);
    expect(panelStart).toBeGreaterThan(formEnd);
    expect(pdfVariantStart).toBeGreaterThan(panelStart);
  });

  it('reste dans la section #signer (montage additif, pas une nouvelle section)', () => {
    const signerStart = PROPOSITION.indexOf('id="signer"');
    const signerEnd = PROPOSITION.indexOf('</section>', panelStart);
    expect(panelStart).toBeGreaterThan(signerStart);
    expect(panelStart).toBeLessThan(signerEnd);
  });

  it('porte un data-testid stable', () => {
    expect(panel).toContain('data-testid="contre-signature-marque"');
  });

  it('DISPLAY ONLY : aucun <canvas>, aucun <form>, aucun nouvel appel réseau/endpoint', () => {
    expect(panel).not.toContain('<canvas');
    expect(panel).not.toContain('<form');
    expect(panel).not.toContain('fetch(');
    expect(panel).not.toMatch(/api\//);
  });

  it('reprend le cadrage EXACT du PDF : « Pour {brand} — signature et cachet »', () => {
    expect(panel).toContain('Pour ${brand} — signature et cachet');
  });

  it('mirroire la ligne d\'engagement du PDF (trust.py : « Le devis fait foi dès réception de l\'acompte »)', () => {
    expect(panel).toContain('Le devis fait foi dès réception de l’acompte.');
  });

  it('les TROIS langues sont posées via data-i18n (data-fr/data-en/data-ar), jamais un texte figé seul', () => {
    // Le libellé « Pour {brand} » : 3 langues + le nœud FR par défaut (tri-node).
    expect(panel).toContain('data-i18n');
    expect((panel.match(/data-fr=/g) ?? []).length).toBeGreaterThanOrEqual(2);
    expect((panel.match(/data-en=/g) ?? []).length).toBeGreaterThanOrEqual(2);
    expect((panel.match(/data-ar=/g) ?? []).length).toBeGreaterThanOrEqual(2);
  });

  it('utilise les tokens de thème existants de la page (nuit/lune/brass), jamais une couleur codée en dur', () => {
    expect(panel).toContain('text-lune');
    expect(panel).not.toMatch(/#[0-9a-fA-F]{3,6}/);
    expect(panel).not.toContain('rgb(');
  });

  it('le nom du signataire est CONDITIONNÉ à seller?.name — jamais un nom fabriqué quand le backend ne le fournit pas', () => {
    expect(panel).toContain('{seller?.name && (');
    expect(panel).toContain('{seller.name}');
  });

  it('const brand est un littéral simple (site public Taqinor, jamais multi-tenant) — pas une valeur dérivée du payload', () => {
    expect(PROPOSITION).toContain("const brand = 'Taqinor';");
  });
});

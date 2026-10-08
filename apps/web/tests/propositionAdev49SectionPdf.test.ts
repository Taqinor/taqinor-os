/**
 * ADEV49 (C-ADEV-016) — case « PDF » décochée : le serveur sert
 * `pdf_disponible: false` et la page ne rend AUCUN des trois liens
 * « Télécharger le devis (PDF) » (héros, succès post-signature, bas de page) —
 * jamais un lien vers le 404 « lien expiré » de `/proposal` (sonde VA p9).
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { pdfDisponible, type ProposalResponse } from '../src/lib/proposition';

const read = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), 'utf-8');
const CONTRAT = JSON.parse(read('../src/contract_samples/proposal_data.json')) as Record<string, unknown>;
const EXEMPLE = CONTRAT.exemple as unknown as ProposalResponse;
const PAGE = read('../src/pages/proposition/[...token].astro');

/** Les liens PDF du gabarit : `href={pdfUrl}` ou sa variante `?variante=`. */
const LIEN_PDF = /href=\{(?:showPdfVariants \? `\$\{pdfUrl\}\?variante=\$\{pdfVariantDefault\}` : )?pdfUrl\}/g;

describe('ADEV49 — `pdf_disponible: false` ⇒ aucun lien « Télécharger »', () => {
  it('le contrat sert le drapeau et la page le lit', () => {
    expect(EXEMPLE.pdf_disponible).toBe(true);
    expect(pdfDisponible(EXEMPLE)).toBe(true);
    expect(pdfDisponible({ ...EXEMPLE, pdf_disponible: false })).toBe(false);
    expect(pdfDisponible(null)).toBe(false);
  });

  it('les TROIS liens vers `pdfUrl` sont gardés par `avecPdf`', () => {
    expect(PAGE).toContain('const avecPdf = ok && pdfDisponible(data!);');
    // Chaque `href` vers le PDF du gabarit est dans un bloc `{avecPdf && (…)}`.
    const hrefs = [...PAGE.matchAll(LIEN_PDF)];
    expect(hrefs.length).toBe(3);
    for (const m of hrefs) {
      const avant = PAGE.slice(0, m.index);
      const garde = avant.lastIndexOf('{avecPdf && (');
      expect(garde, `lien PDF non gardé à l’index ${m.index}`).toBeGreaterThan(-1);
      // Aucun bloc gardé ne s'est refermé entre la garde et ce lien.
      expect(avant.slice(garde)).not.toMatch(/<\/(?:a|p|div)>\)\}/);
    }
  });
});

// L-VAR (ordre fondateur, 24/08/2026) — le choix avec/sans batterie n'engage
// QUE la signature : le client doit toujours pouvoir télécharger le devis
// COMPLET, et choisir la version téléchargée depuis un petit sélecteur placé
// au-dessus du bouton « Télécharger le devis (PDF) ».
//
// Épingle SOURCE (même convention que perceivedPerfWJ34.test.ts) : le
// sélecteur et le paramètre `?variante=` sont du câblage DOM qu'on ne monte pas
// sous vitest — on prouve le câblage et ses invariants de sûreté.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const PROPOSITION = readFileSync(
  fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
  'utf-8',
);

describe('L-VAR — sélecteur de variante au-dessus du bouton PDF', () => {
  it('les trois choix existent, en FR/EN/AR', () => {
    expect(PROPOSITION).toContain('id="pdf-variante"');
    for (const v of ['data-pdf-variante="sans"', 'data-pdf-variante="avec"', 'data-pdf-variante="les_deux"']) {
      expect(PROPOSITION).toContain(v);
    }
    // Le libellé du groupe et les trois étiquettes portent les 3 langues.
    expect(PROPOSITION).toContain('data-fr="Quelle version télécharger ?"');
    expect(PROPOSITION).toContain('data-en="Which version would you like?"');
    expect(PROPOSITION).toContain('data-ar="أي نسخة تريدون تحميلها؟"');
    expect(PROPOSITION).toContain('data-en="Both options"');
  });

  it('le défaut est la composition du COMMERCIAL, lue dans la donnée (quote.scenario) — jamais une déduction', () => {
    expect(PROPOSITION).toContain('const pdfVariantDefault');
    expect(PROPOSITION).toContain("q?.scenario === 'Sans batterie' ? 'sans'");
    expect(PROPOSITION).toContain("q?.scenario === 'Avec batterie' ? 'avec'");
    expect(PROPOSITION).toContain(": 'les_deux'");
  });

  it('le sélecteur ne s\'affiche que sur un devis à deux options', () => {
    const bloc = PROPOSITION.slice(
      PROPOSITION.indexOf('L-VAR · QUELLE VERSION TÉLÉCHARGER'),
      PROPOSITION.indexOf('id="pdf-download"'),
    );
    expect(bloc).toContain('{twoOptions && (');
  });

  it('le clic ne change QUE le paramètre ?variante= du lien PDF existant (pas de second chemin PDF)', () => {
    expect(PROPOSITION).toContain('pdfLink.href = `${variantBase}?variante=${value}`');
    // Le lien de départ porte déjà le défaut sur un devis à deux options.
    expect(PROPOSITION).toContain('href={twoOptions ? `${pdfUrl}?variante=${pdfVariantDefault}` : pdfUrl}');
    // Une seule fabrique d'URL PDF : proposalPdfEndpoint (aucun endpoint parallèle).
    expect(PROPOSITION.match(/proposalPdfEndpoint\(/g) ?? []).toHaveLength(1);
  });

  it('le script whiteliste les valeurs côté page aussi (défense en profondeur)', () => {
    expect(PROPOSITION).toContain(
      "if (value !== 'sans' && value !== 'avec' && value !== 'les_deux') return;");
  });

  it('la signature reste inchangée : le formulaire garde son propre choix d\'option', () => {
    expect(PROPOSITION).toContain('input[name="option"]:checked');
  });
});

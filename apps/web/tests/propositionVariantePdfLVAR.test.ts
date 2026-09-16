// L-VAR — quelle version du devis se télécharge.
//
// RECALIBRÉ — décision fondateur du 16/09/2026 : « réduire au minimum prouvé ».
// L-VAR (24/08) posait TROIS boutons « Sans / Avec / Les deux » au-dessus du
// lien PDF, dans l'étape de signature. Aucun des flux étudiés (r8/r9
// sign_flows) ne fait choisir un FORMAT DE DOCUMENT dans l'écran d'acceptation
// — et Baymard rappelle que tout ce qui n'est pas nécessaire à l'engagement
// éloigne le bouton. Le sélecteur part ; le lien UNIQUE « Télécharger le devis
// (PDF) » suit désormais l'option cochée dans le formulaire.
//
// L'INTENTION de L-VAR est conservée intégralement : le choix de SIGNATURE
// n'engage que la signature, le devis reste téléchargeable, et il n'existe
// qu'UN SEUL chemin PDF (même endpoint, même token, même liste blanche).
//
// Épingle SOURCE (même convention que perceivedPerfWJ34.test.ts) : le câblage
// `?variante=` est du DOM qu'on ne monte pas sous vitest — on prouve le câblage
// et ses invariants de sûreté.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const PROPOSITION = readFileSync(
  fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
  'utf-8',
);

describe('L-VAR — un seul lien PDF, qui suit l’option cochée', () => {
  it('le sélecteur à trois boutons a quitté l’étape de signature', () => {
    expect(PROPOSITION).not.toContain('id="pdf-variante"');
    expect(PROPOSITION).not.toContain('data-pdf-variante=');
    expect(PROPOSITION).not.toContain('data-fr="Quelle version télécharger ?"');
  });

  it('le lien unique existe, en FR/EN/AR, et reste le seul chemin PDF', () => {
    expect(PROPOSITION).toContain('id="pdf-download"');
    expect(PROPOSITION).toContain('data-fr="Télécharger le devis (PDF)"');
    expect(PROPOSITION).toContain('data-en="Download the quote (PDF)"');
    expect(PROPOSITION).toContain('data-ar="تحميل العرض (PDF)"');
    // Une seule fabrique d'URL PDF : proposalPdfEndpoint (aucun endpoint parallèle).
    expect(PROPOSITION.match(/proposalPdfEndpoint\(/g) ?? []).toHaveLength(1);
  });

  it('le href de départ est inchangé : complet (« les_deux ») quand les deux côtés sont servables', () => {
    expect(PROPOSITION).toContain("const pdfVariantDefault: 'sans' | 'avec' | 'les_deux' = 'les_deux';");
    expect(PROPOSITION).toContain('href={showPdfVariants ? `${pdfUrl}?variante=${pdfVariantDefault}` : pdfUrl}');
    // L'ancien défaut suivait la composition du commercial (`quote.scenario`) et
    // livrait donc un document AMPUTÉ à un client qui n'avait rien demandé.
    expect(PROPOSITION).not.toContain("q?.scenario === 'Sans batterie'");
    expect(PROPOSITION).not.toContain("q?.scenario === 'Avec batterie'");
    // Découplé de `twoOptions` : un devis rétréci côté backend (nb_options
    // retombé à 1, incident DEV-202608-0023) garde un équipement capable de
    // servir les deux côtés.
    expect(PROPOSITION).toContain('const showPdfVariants = ok ? showVariantSelector(data!) : false;');
  });

  it('le lien SUIT le radio d’option — et ne touche à rien quand aucune variante n’est servable', () => {
    expect(PROPOSITION).toContain('const portaitUneVariante = pdfLink.href.includes(\'?variante=\');');
    expect(PROPOSITION).toContain('if (!portaitUneVariante) return;');
    expect(PROPOSITION).toContain('sans_batterie: \'sans\',');
    expect(PROPOSITION).toContain('avec_batterie: \'avec\',');
    expect(PROPOSITION).toContain('pdfLink.href = `${variantBase}?variante=${value}`');
  });

  it('la liste blanche des valeurs reste posée côté page (défense en profondeur)', () => {
    expect(PROPOSITION).toContain(
      "if (value !== 'sans' && value !== 'avec' && value !== 'les_deux') return;");
  });

  it('la signature reste inchangée : le formulaire garde son propre choix d\'option', () => {
    expect(PROPOSITION).toContain('input[name="option"]:checked');
  });
});

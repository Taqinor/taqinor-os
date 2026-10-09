/**
 * Neutral English dictionary of the design round (YBW42) — same keys as the
 * French one. Placeholder copy only (describes each slot), never final text:
 * the real English is translated from the approved French (YBW70).
 * Deleted with the `/_design/*` routes by YBW44.
 */
import type { DictEn } from '../config';
import type { fr } from './design.fr';

export const en: DictEn<typeof fr> = {
  meta: {
    titre: 'Design round — candidate homepage (private page)',
    description: 'Private page comparing the design candidates. Neutral placeholder copy, not final.',
  },
  candidats: {
    a: 'Candidate A — Ink and paper',
    b: 'Candidate B — Night',
    c: 'Candidate C — Deck continuity',
  },
  ruban: 'Private comparison page. Neutral placeholder copy, not final.',
  nav: {
    aria: 'Main navigation',
    ariaMobile: 'Navigation (mobile)',
    menu: 'Menu',
    surMesure: 'Custom software',
    societe: 'Company',
    rdv: 'Book a meeting',
    langue: 'Français',
  },
  hero: {
    surtitre: 'Short homepage eyebrow',
    titre: 'Main homepage headline, one strong sentence over two lines',
    intro:
      'Introduction paragraph: what the company builds, for whom, and the action offered. Two or three lines, never more. Final copy is written once the design is chosen.',
    cta: 'Book a meeting',
    secondaire: 'See the products',
  },
  capture: {
    attente: 'Product screenshot placeholder',
    note: 'Real screen, fictional company, cropped to the useful area.',
  },
  produits: {
    surtitre: 'Products',
    titre: 'Products section headline, on one line',
    intro: 'One sentence introducing the products built, with no figure and no promise.',
  },
  produit: {
    surtitre: 'Product',
    description: 'Short product description: who it is for and what it does, in two or three lines of plain text.',
    point1: 'First product capability, described in one line',
    point2: 'Second capability, with a more precise word',
    point3: 'Third capability, the most concrete of the three',
    lien: 'Talk about this product',
  },
  surMesure: {
    surtitre: 'Custom software',
    titre: 'Custom block headline: what the company builds for a business',
    texte: 'Paragraph on the approach: start from the real need, show something working quickly, then run it together.',
    etape1: 'First step of the approach',
    etape2: 'Second step',
    etape3: 'Third step',
    etape4: 'Fourth step',
    detail: 'One line that details this step.',
  },
  societe: {
    surtitre: 'Company',
    titre: 'Company block: what the name means, rooted in Morocco and France',
    texte: 'Two sentences about the company, with no date, no figure and no portrait. The sentence about the installation business goes here.',
  },
  rdv: {
    titre: 'Final call: book a meeting',
    texte: 'One sentence on what happens after the request: a reply from a person.',
    bouton: 'Book a meeting',
  },
  pied: {
    note: 'Footer. Legal links appear as soon as their pages are complete.',
    aria: 'Footer',
  },
};

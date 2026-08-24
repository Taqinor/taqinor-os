// L-VAR — « quelle version télécharger ? » ne dépend plus du nombre d'options
// PRÉSENTÉES par le devis.
//
// Incident DEV-202608-0023 : un devis à deux options rétréci côté backend
// (`option_totals.nb_options` retombé à 1) faisait disparaître D'UN COUP, via le
// seul drapeau `twoOptions`, la case de signature sans/avec, le sélecteur de
// variante PDF et le `?variante=` du lien de téléchargement — alors que
// l'équipement du devis servait toujours les DEUX côtés.
//
// Ces tests épinglent la séparation ordonnée par le fondateur (24/08/2026) :
//   (1) le téléchargement lit `variantes_servables` (clé RACINE du contrat
//       backend), lue DÉFENSIVEMENT — valeurs inconnues ignorées ;
//   (2) clé absente ⇒ REPLI sur le signal historique : rendu strictement
//       inchangé sur tous les payloads d'avant le contrat ;
//   (3) le défaut du téléchargement est « les_deux », TOUJOURS ;
//   (4) la case de SIGNATURE reste, elle, sur `twoOptions` — c'est voulu.
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  hasTwoOptions,
  showVariantSelector,
  variantesServables,
  type ProposalResponse,
} from '../src/lib/proposition';

const PAGE = readFileSync(
  fileURLToPath(new URL('../src/pages/proposition/[...token].astro', import.meta.url)),
  'utf-8',
);

/** Surcharge de scénario : le `quote` peut n'être fourni que partiellement. */
type ProposalOverride = Partial<Omit<ProposalResponse, 'quote'>> & {
  quote?: Partial<ProposalResponse['quote']>;
};

/** Devis à DEUX options (les deux blocs de totaux, nb_options = 2). */
function makeProposal(over: ProposalOverride = {}): ProposalResponse {
  const base: ProposalResponse = {
    reference: 'DEV-202608-0023',
    date: '24/08/2026',
    client_name: 'Reda Kasri',
    statut: 'envoye',
    quote: {
      ref: 'DEV-202608-0023',
      date: '24/08/2026',
      client_name: 'Reda Kasri',
      inst_type: 'residentiel',
      totaux_sans: { ht_brut: 50000, remise: 0, ht_net: 50000, tva: 10000, ttc: 60000 },
      totaux_avec: { ht_brut: 80000, remise: 0, ht_net: 80000, tva: 16000, ttc: 96000 },
      nb_options: 2,
    },
    roof_image_url: null,
    option_totals: { sans_batterie: 60000, avec_batterie: 96000, display_total: 96000, nb_options: 2 },
    accepted: false,
  };
  return { ...base, ...over, quote: { ...base.quote, ...(over.quote ?? {}) } };
}

/** Le devis rétréci de l'incident : les DEUX totaux sont là, nb_options dit 1. */
function makeShrunk(over: ProposalOverride = {}): ProposalResponse {
  const p = makeProposal(over);
  return {
    ...p,
    quote: { ...p.quote, nb_options: 1 },
    option_totals: { ...p.option_totals, nb_options: 1 },
  };
}

// ════════════════════════════════════════════════════════════════════════════
describe('L-VAR — `variantes_servables` : lecture défensive de la clé servie', () => {
  it('["sans","avec"] → les deux côtés, donc le sélecteur', () => {
    const p = makeProposal({ variantes_servables: ['sans', 'avec'] });
    expect(variantesServables(p)).toEqual(['sans', 'avec']);
    expect(showVariantSelector(p)).toBe(true);
  });

  it('un devis MONO ne sert qu’un côté, et le sélecteur disparaît', () => {
    const avec = makeProposal({ variantes_servables: ['avec'] });
    expect(variantesServables(avec)).toEqual(['avec']);
    expect(showVariantSelector(avec)).toBe(false);
    const sans = makeProposal({ variantes_servables: ['sans'] });
    expect(variantesServables(sans)).toEqual(['sans']);
    expect(showVariantSelector(sans)).toBe(false);
  });

  it('l’ordre rendu est CANONIQUE, pas celui (arbitraire) du payload', () => {
    expect(variantesServables(makeProposal({ variantes_servables: ['avec', 'sans'] })))
      .toEqual(['sans', 'avec']);
  });

  it('les valeurs inconnues sont ignorées, jamais propagées', () => {
    expect(variantesServables(makeProposal({ variantes_servables: ['avec', 'hybride', ''] })))
      .toEqual(['avec']);
    // Une liste 100 % inconnue ne « sert » rien : on retombe sur le signal
    // historique plutôt que de rendre une page vide de tout choix.
    expect(variantesServables(makeProposal({ variantes_servables: ['hybride'] })))
      .toEqual(['sans', 'avec']);
  });

  it('un type inattendu ne fait JAMAIS tomber la page (repli, pas d’exception)', () => {
    const bizarre = { variantes_servables: 'sans,avec' } as unknown as ProposalOverride;
    expect(() => variantesServables(makeProposal(bizarre))).not.toThrow();
    expect(variantesServables(makeProposal(bizarre))).toEqual(['sans', 'avec']);
    expect(variantesServables(makeProposal({ variantes_servables: [] }))).toEqual(['sans', 'avec']);
    expect(variantesServables(makeProposal({ variantes_servables: null }))).toEqual(['sans', 'avec']);
    expect(variantesServables(null)).toEqual([]);
    expect(showVariantSelector(null)).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('L-VAR — clé ABSENTE : rétro-compatibilité stricte (backend d’avant)', () => {
  it('deux options présentées → les deux côtés (comportement d’aujourd’hui)', () => {
    const p = makeProposal();
    expect(p.variantes_servables).toBeUndefined();
    expect(hasTwoOptions(p)).toBe(true);
    expect(variantesServables(p)).toEqual(['sans', 'avec']);
    expect(showVariantSelector(p)).toBe(true);
  });

  it('devis « avec batterie » seul → un seul côté, sélecteur masqué', () => {
    const p = makeProposal({
      quote: { totaux_sans: undefined, nb_options: 1 },
      option_totals: { sans_batterie: 0, avec_batterie: 96000, display_total: 96000, nb_options: 1 },
    });
    expect(variantesServables(p)).toEqual(['avec']);
    expect(showVariantSelector(p)).toBe(false);
  });

  it('devis « sans batterie » seul → un seul côté, sélecteur masqué', () => {
    const p = makeProposal({
      quote: { totaux_avec: undefined, nb_options: 1 },
      option_totals: { sans_batterie: 60000, avec_batterie: 0, display_total: 60000, nb_options: 1 },
    });
    expect(variantesServables(p)).toEqual(['sans']);
    expect(showVariantSelector(p)).toBe(false);
  });
});

// ════════════════════════════════════════════════════════════════════════════
describe('L-VAR — le devis RÉTRÉCI de l’incident DEV-202608-0023', () => {
  it('sans la clé servie, il perd le sélecteur (l’état d’avant, reproduit)', () => {
    const p = makeShrunk();
    expect(hasTwoOptions(p)).toBe(false);
    expect(showVariantSelector(p)).toBe(false);
  });

  it('avec la clé servie, le sélecteur REVIENT bien que nb_options dise 1', () => {
    const p = makeShrunk({ variantes_servables: ['sans', 'avec'] });
    // La signature, elle, ne bouge pas : le document ne PRÉSENTE qu'une option.
    expect(hasTwoOptions(p)).toBe(false);
    expect(showVariantSelector(p)).toBe(true);
  });
});

// ════════════════════════════════════════════════════════════════════════════
// (Le câblage de la page — gâteau `showPdfVariants`, défaut « les_deux »,
//  `?variante=` — est épinglé dans propositionVariantePdfLVAR.test.ts.)
describe('L-VAR — la SIGNATURE, elle, reste sur `twoOptions`', () => {
  it('le choix sans/avec du formulaire suit ce que le devis PRÉSENTE', () => {
    // Voulu : un devis qui ne présente qu'une option n'a rien à faire choisir
    // au signataire, même quand son équipement sert les deux côtés.
    expect(PAGE).toContain('const twoOptions = ok ? hasTwoOptions(data!) : false;');
    expect(PAGE).toContain('{twoOptions && (');
  });
});

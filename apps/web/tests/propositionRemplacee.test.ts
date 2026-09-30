/**
 * QJR536 (Groupe QJR5, contrat QJR501) — le lien public d'une version
 * REMPLACÉE s'affiche « remplacée », sans signature, et mène à la version en
 * vigueur si elle a été envoyée.
 *
 * Les cas viennent de l'échantillon COMMITTÉ `proposal_data.json` (fragments
 * `exemple_remplace_par_envoye` / `exemple_remplace_par_brouillon`) — jamais
 * un mock écrit à la main (PACT10).
 */
import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import {
  isOfferDead,
  resolveOfferState,
  resolveRemplacement,
  type ProposalResponse,
} from '../src/lib/proposition';

const CONTRAT = JSON.parse(readFileSync(
  fileURLToPath(new URL('../src/contract_samples/proposal_data.json', import.meta.url)),
  'utf-8',
)) as Record<string, Record<string, unknown>>;

const ENVOYE = CONTRAT.exemple_remplace_par_envoye!.remplace_par as ProposalResponse['remplace_par'];
const BROUILLON = CONTRAT.exemple_remplace_par_brouillon!.remplace_par as ProposalResponse['remplace_par'];
const EXEMPLE = CONTRAT.exemple as unknown as ProposalResponse;

describe('QJR536 — une version remplacée n’est plus signable', () => {
  it('statut « envoye » + remplace_par ⇒ withdrawn', () => {
    expect(resolveOfferState({ statut: 'envoye', remplace_par: ENVOYE } as never)).toBe('withdrawn');
    expect(isOfferDead(resolveOfferState({ statut: 'envoye', remplace_par: ENVOYE } as never))).toBe(true);
  });

  it('successeur encore brouillon : toujours withdrawn, mais aucun lien', () => {
    expect(resolveOfferState({ statut: 'envoye', remplace_par: BROUILLON } as never)).toBe('withdrawn');
    expect(resolveRemplacement({ remplace_par: BROUILLON })).toEqual({
      reference: 'DEV-202609-0012', url: null,
    });
  });

  it('successeur envoyé : la référence ET le chemin public', () => {
    expect(resolveRemplacement({ remplace_par: ENVOYE })).toEqual({
      reference: 'DEV-202609-0012', url: '/proposition/<slug>/<token>',
    });
  });

  it('l’exemple du contrat (remplace_par: null) n’est pas « retiré »', () => {
    expect(EXEMPLE.remplace_par).toBeNull();
    expect(resolveRemplacement(EXEMPLE)).toBeNull();
    expect(resolveOfferState(EXEMPLE)).not.toBe('withdrawn');
    expect(resolveOfferState({ statut: 'envoye', remplace_par: null } as never)).toBe('live');
  });

  it('défensif : une URL externe ou une référence vide n’est jamais servie', () => {
    expect(resolveRemplacement({ remplace_par: { reference: 'DEV-1', url: 'https://evil.test/x' } }))
      .toEqual({ reference: 'DEV-1', url: null });
    expect(resolveRemplacement({ remplace_par: { reference: '  ', url: '/proposition/a/b' } })).toBeNull();
    expect(resolveRemplacement({})).toBeNull();
  });
});

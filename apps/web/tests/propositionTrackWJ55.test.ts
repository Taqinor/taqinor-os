/**
 * WJ55 — buildProposalTrackPayload : télémétrie de vue/engagement, garde-fou
 * anti-pollution CRM (aucun envoi sans téléphone client exploitable).
 */
import { describe, expect, it } from 'vitest';
import { buildProposalTrackPayload } from '../src/lib/proposition';

describe('WJ55 — buildProposalTrackPayload', () => {
  it('renvoie null sans téléphone client (jamais de lead fantôme)', () => {
    expect(buildProposalTrackPayload({ reference: 'DV-001', token: 'tok1' }, 'proposal_first_view')).toBeNull();
    expect(
      buildProposalTrackPayload({ reference: 'DV-001', token: 'tok1', clientPhone: '' }, 'proposal_first_view'),
    ).toBeNull();
    expect(
      buildProposalTrackPayload({ reference: 'DV-001', token: 'tok1', clientPhone: '   ' }, 'proposal_first_view'),
    ).toBeNull();
  });

  it('construit un payload qualified:false corrélable par téléphone quand disponible', () => {
    const payload = buildProposalTrackPayload(
      { reference: 'DV-042', token: 'tok42', clientPhone: '+212600000000' },
      'proposal_scrolled_financing',
    );
    expect(payload).toEqual({
      qualified: false,
      event_type: 'proposal_scrolled_financing',
      phoneE164: '+212600000000',
      utm: { utm_source: 'proposal_engagement', utm_campaign: 'DV-042', utm_content: 'proposal_scrolled_financing' },
      page: '/proposition/tok42',
    });
  });

  it('retombe sur le token comme utm_campaign quand la référence est absente', () => {
    const payload = buildProposalTrackPayload(
      { reference: '', token: 'tok99', clientPhone: '0600000000' },
      'proposal_first_view',
    );
    expect(payload?.utm.utm_campaign).toBe('tok99');
  });
});

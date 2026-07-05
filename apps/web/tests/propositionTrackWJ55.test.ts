/**
 * WJ55/WJ109 — buildProposalTrackPayload : télémétrie PURE de vue/engagement.
 *
 * WJ109 — [régression de corruption CRM] Ce payload transitait auparavant vers
 * le webhook de CAPTURE DE LEAD (`LEAD_WEBHOOK_URL`) sous une forme
 * `{ qualified, phoneE164, utm, ... }` qui ressemblait à un lead — recevant ce
 * ping, le backend écrasait le nom réel du lead par « Lead site web ». Ce
 * garde-fou vérifie que le payload n'a PLUS jamais cette forme (aucun champ
 * `qualified`/`phoneE164`/`utm`, jamais de téléphone) et route désormais vers
 * le canal télémétrie/funnel dédié (`FUNNEL_WEBHOOK_URL`, voir
 * `pages/api/proposition-track.ts`), jamais le webhook de lead.
 */
import { describe, expect, it } from 'vitest';
import { buildProposalTrackPayload } from '../src/lib/proposition';

describe('WJ55/WJ109 — buildProposalTrackPayload', () => {
  it('renvoie null sans référence ni token (rien de corrélable)', () => {
    expect(buildProposalTrackPayload({ reference: '', token: '' }, 'proposal_first_view')).toBeNull();
    expect(
      buildProposalTrackPayload({ reference: '   ', token: '  ', clientPhone: '+212600000000' }, 'proposal_first_view'),
    ).toBeNull();
  });

  it('construit un payload de télémétrie PURE — jamais lead-shaped (WJ109)', () => {
    const payload = buildProposalTrackPayload(
      { reference: 'DV-042', token: 'tok42', clientPhone: '+212600000000' },
      'proposal_scrolled_financing',
    );
    expect(payload).toEqual({
      event_type: 'proposal_scrolled_financing',
      reference: 'DV-042',
      token: 'tok42',
      page: '/proposition/tok42',
    });
    // WJ109 — garde-fou explicite : jamais un champ qui ressemble à un lead.
    expect(payload).not.toHaveProperty('qualified');
    expect(payload).not.toHaveProperty('phoneE164');
    expect(payload).not.toHaveProperty('utm');
  });

  it('reste corrélable par référence seule quand le token est absent', () => {
    const payload = buildProposalTrackPayload({ reference: 'DV-099', token: '' }, 'proposal_first_view');
    expect(payload?.reference).toBe('DV-099');
  });

  it('reste corrélable par token seul quand la référence est absente', () => {
    const payload = buildProposalTrackPayload(
      { reference: '', token: 'tok99', clientPhone: '0600000000' },
      'proposal_first_view',
    );
    expect(payload?.token).toBe('tok99');
  });
});

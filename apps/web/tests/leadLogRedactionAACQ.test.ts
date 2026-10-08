// AACQ43 — la ligne de log d'un lead ne contient plus d'empreinte du téléphone.
import { describe, expect, it } from 'vitest';
import { buildLeadRecord, leadLogId, redactLeadForLog, validateLead } from '../src/lib/lead';

const band = { kwcMin: 5, kwcMax: 9, kwcLabel: '5 à 9 kWc', paybackLabel: '4 à 6 ans', source: 'local' as const };
const v = validateLead({
  fullName: 'Reda K.',
  phone: '+212612345678',
  city: 'Casablanca',
  roofType: 'villa',
  billRange: '1500-3000',
  consent: true,
});
if (!v.ok) throw new Error('fixture invalide');
const lead = v.lead;
const mk = (extra: Record<string, unknown> = {}) => ({
  ...buildLeadRecord(lead, band, new Date()),
  ...extra,
});

/** Toutes les valeurs de la ligne, aplaties en chaînes. */
function values(o: Record<string, unknown>): string[] {
  return Object.values(o).map((v) => JSON.stringify(v));
}

describe('AACQ43 — redactLeadForLog', () => {
  it('aucune empreinte du téléphone dans la ligne', () => {
    const record = mk({ idempotencyKey: 'abcdefgh12345678' });
    const line = redactLeadForLog(record);
    expect(line).not.toHaveProperty('id');
    const empreinte = leadLogId(record.phoneE164);
    expect(JSON.stringify(line)).not.toContain(empreinte);
    // énumération bornée : aucun candidat autour du numéro ne reproduit une valeur de la ligne
    const lineValues = new Set(values(line).map((v) => v.replace(/"/g, '')));
    const base = 212612345600;
    let retrouve: string | null = null;
    for (let n = base; n < base + 100; n++) {
      if (lineValues.has(leadLogId(`+${n}`))) retrouve = `+${n}`;
    }
    expect(retrouve).toBeNull();
  });

  it('corrélation par idempotencyKey (ou rien si absente)', () => {
    expect(redactLeadForLog(mk({ idempotencyKey: 'abcdefgh12345678' })).idempotencyKey).toBe('abcdefgh12345678');
    const sans = mk();
    delete (sans as { idempotencyKey?: string }).idempotencyKey;
    expect(redactLeadForLog(sans)).not.toHaveProperty('idempotencyKey');
  });

  it('les autres champs rédigés sont inchangés', () => {
    const line = redactLeadForLog(mk({ idempotencyKey: 'abcdefgh12345678' }));
    expect(line.qualified).toBe(true);
    expect(line.billRange).toBe('1500-3000');
    expect(line).toHaveProperty('utmKeys');
    expect(line).toHaveProperty('page');
    expect(line).toHaveProperty('kwcLabel');
  });
});

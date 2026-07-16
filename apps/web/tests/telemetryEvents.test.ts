import { describe, expect, it } from 'vitest';
import {
  TELEMETRY_EVENT_PROPS,
  TELEMETRY_EVENTS,
  TELEMETRY_FORBIDDEN_KEYS,
  TELEMETRY_LOCALES,
  TELEMETRY_MODES,
  TELEMETRY_STEP_IDS,
  buildTelemetryEvent,
  isTelemetryEventName,
  toFunnelWire,
} from '../src/lib/telemetryEvents';

describe('telemetryEvents — vocabulaire fermé (WJ91)', () => {
  it('les 4 step_id correspondent EXACTEMENT aux vraies étapes de /devis/mon-toit', () => {
    expect(TELEMETRY_STEP_IDS).toEqual(['toit', 'facture', 'estimation', 'contact']);
  });

  it('les modes correspondent EXACTEMENT à LEAD_MODES (lib/lead.ts)', () => {
    // WJ121 — 4 modes émis (residentiel/industriel/commercial/agricole) +
    // l'alias hérité 'professionnel' (accepté, plus jamais émis par le site).
    expect(TELEMETRY_MODES).toEqual(['residentiel', 'professionnel', 'industriel', 'commercial', 'agricole']);
  });

  it('couvre les événements attendus (journey_step_*, estimate_rendered, whatsapp_clicked, proposal_*)', () => {
    for (const name of [
      'journey_step_viewed',
      'journey_step_completed',
      'journey_step_abandoned',
      'estimate_rendered',
      'whatsapp_clicked',
      'proposal_viewed',
      'proposal_scrolled_to_financing',
      'proposal_signed',
    ]) {
      expect(TELEMETRY_EVENTS).toContain(name);
    }
  });

  // WJ104 — delta d'instrumentation RÉELLEMENT câblé (voir toFunnelWire ci-dessous).
  it('WJ104 — couvre les nouveaux événements delta (estimate_viewed, callback_requested)', () => {
    expect(TELEMETRY_EVENTS).toContain('estimate_viewed');
    expect(TELEMETRY_EVENTS).toContain('callback_requested');
  });

  it('isTelemetryEventName rejette un nom hors vocabulaire', () => {
    expect(isTelemetryEventName('proposal_signed')).toBe(true);
    expect(isTelemetryEventName('random_event')).toBe(false);
    expect(isTelemetryEventName(42)).toBe(false);
  });
});

// WJ104 — traduction vers le beacon step-level existant (WJ59 funnelBeacon.ts).
describe('toFunnelWire — WJ104 : pont vers le beacon {step, action} existant', () => {
  it('traduit les 4 événements delta vers leur couple {step, action}', () => {
    expect(toFunnelWire('estimate_viewed')).toEqual({ step: 'estimation', action: 'viewed' });
    expect(toFunnelWire('callback_requested')).toEqual({ step: 'contact', action: 'callback_requested' });
    expect(toFunnelWire('proposal_viewed')).toEqual({ step: 'proposal', action: 'viewed' });
    expect(toFunnelWire('proposal_signed')).toEqual({ step: 'proposal', action: 'signed' });
  });

  it('renvoie null pour un événement non câblé (statut d\'adoption inchangé)', () => {
    expect(toFunnelWire('journey_step_viewed')).toBeNull();
    expect(toFunnelWire('estimate_rendered')).toBeNull();
    expect(toFunnelWire('whatsapp_clicked')).toBeNull();
    expect(toFunnelWire('proposal_scrolled_to_financing')).toBeNull();
  });
});

describe('buildTelemetryEvent — CONTRAT DE VIE PRIVÉE : jamais de PII (WJ91)', () => {
  it('un événement construit avec des props légitimes les conserve', () => {
    const evt = buildTelemetryEvent('journey_step_viewed', {
      step_id: 'facture',
      mode: 'professionnel',
      locale: 'ar',
      page: '/devis/mon-toit',
    });
    expect(evt.event).toBe('journey_step_viewed');
    expect(evt.props).toEqual({
      step_id: 'facture',
      mode: 'professionnel',
      locale: 'ar',
      page: '/devis/mon-toit',
    });
  });

  it('AUCUNE clé interdite (PII) ne survit jamais, même injectée explicitement', () => {
    const attack: Record<string, unknown> = {
      step_id: 'toit',
      fullName: 'Karim Benali',
      phone: '0612345678',
      phoneE164: '+212612345678',
      email: 'karim@example.com',
      address: 'Maârif, Casablanca',
      adresse: 'Maârif, Casablanca',
      city: 'Casablanca',
      gps: { lat: 33.5, lng: -7.6 },
      gpsLat: 33.5,
      gpsLng: -7.6,
      roofPoint: { lat: 33.5, lng: -7.6 },
      roofOutline: [[33.5, -7.6], [33.5, -7.6], [33.5, -7.6]],
    };
    const evt = buildTelemetryEvent('estimate_rendered', attack);
    const serialized = JSON.stringify(evt);
    for (const forbidden of TELEMETRY_FORBIDDEN_KEYS) {
      expect(evt.props).not.toHaveProperty(forbidden);
      expect(serialized).not.toContain('Karim Benali');
    }
    expect(serialized).not.toContain('0612345678');
    expect(serialized).not.toContain('612345678');
    expect(serialized).not.toContain('karim@example.com');
    expect(serialized).not.toContain('Casablanca');
    expect(serialized).not.toContain('Maârif');
    // Seule la propriété légitime (step_id) est retenue.
    expect(evt.props).toEqual({ step_id: 'toit' });
  });

  it('les propriétés de l\'allowlist restent exactement step_id/mode/locale/page', () => {
    expect(TELEMETRY_EVENT_PROPS).toEqual(['step_id', 'mode', 'locale', 'page']);
  });

  it('une valeur malformée (hors vocabulaire) est écartée SANS lever ni bloquer', () => {
    const evt = buildTelemetryEvent('whatsapp_clicked', {
      step_id: 'un_id_invente',
      mode: 'startup', // pas dans TELEMETRY_MODES (WJ121 : 'industriel' est désormais un vrai mode)
      locale: 'es',
      page: 'javascript:alert(1)', // ne commence pas par "/"
    });
    expect(evt.props).toEqual({});
  });

  it('un chemin avec query string est tronqué avant le "?" (jamais un fbclid/UTM ici)', () => {
    const evt = buildTelemetryEvent('journey_step_completed', {
      page: '/devis/mon-toit?fbclid=abc&utm_source=fb',
    });
    expect(evt.props.page).toBe('/devis/mon-toit');
  });
});

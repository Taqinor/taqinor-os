import { describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { JSDOM } from 'jsdom';
import { validateBeaconEvent } from '../src/lib/funnelBeacon';
import {
  TELEMETRY_EVENT_PROPS,
  TELEMETRY_EVENTS,
  TELEMETRY_FORBIDDEN_KEYS,
  TELEMETRY_LOCALES,
  TELEMETRY_MODES,
  TELEMETRY_STEP_IDS,
  buildTelemetryEvent,
  installerMesureContact,
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

describe('WAUD7 — mesure des clics WhatsApp et téléphone', () => {
  function monter(html: string, consentement: string | null = null) {
    const dom = new JSDOM(`<!doctype html><body>${html}</body>`, { url: 'https://taqinor.ma/contact/' });
    const win = dom.window as unknown as Window & typeof globalThis & { tqPixelTrack: ReturnType<typeof vi.fn> };
    win.tqPixelTrack = vi.fn();
    const sendBeacon = vi.fn(() => true);
    Object.defineProperty(win.navigator, 'sendBeacon', { value: sendBeacon });
    if (consentement) win.localStorage.setItem('tq_consent', consentement);
    Object.defineProperty(win, 'crypto', { value: { randomUUID: () => 'aaaa-bbbb-cccc' } });
    installerMesureContact(win.document, win);
    const cliquer = (s: string) => {
      const a = win.document.querySelector(s)!;
      a.addEventListener('click', (e) => e.preventDefault());
      a.dispatchEvent(new win.MouseEvent('click', { bubbles: true, cancelable: true }));
    };
    return { win, sendBeacon, cliquer };
  }

  it('wa.me : Contact + whatsapp_clicked (step, action, jeton, chemin), aucune donnée de contact', async () => {
    const { win, sendBeacon, cliquer } = monter('<footer><a id="a" href="https://wa.me/212600000000?text=x"><b id="b">WA</b></a></footer>');
    cliquer('#b');
    expect(win.tqPixelTrack).toHaveBeenCalledWith('Contact', { content_name: '/contact/', placement: 'footer' });
    expect(sendBeacon).toHaveBeenCalledTimes(1);
    const corps = JSON.parse(await (sendBeacon.mock.calls[0] as unknown as [string, Blob])[1].text());
    expect(validateBeaconEvent(corps).ok).toBe(true);
    expect(corps).toEqual({ step: 'contact', action: 'whatsapp_clicked', sessionToken: 'aaaabbbbcccc', path: '/contact/' });
  });

  it('tel: : Contact seulement', () => {
    const { win, sendBeacon, cliquer } = monter('<main><a id="t" href="tel:+212600000000">Appeler</a></main>');
    cliquer('#t');
    expect(win.tqPixelTrack).toHaveBeenCalledWith('Contact', { content_name: '/contact/', placement: 'main' });
    expect(sendBeacon).not.toHaveBeenCalled();
  });

  it('refus explicite : aucun beacon ; un autre lien : rien du tout', () => {
    const a = monter('<a id="a" href="https://wa.me/212600000000">WA</a><a id="z" href="/faq/">FAQ</a>', 'denied');
    a.cliquer('#a');
    expect(a.sendBeacon).not.toHaveBeenCalled();
    const b = monter('<a id="z" href="/faq/">FAQ</a>');
    b.cliquer('#z');
    expect(b.win.tqPixelTrack).not.toHaveBeenCalled();
    expect(b.sendBeacon).not.toHaveBeenCalled();
  });

  it('un seul écouteur délégué, branché par Layout', () => {
    const layout = readFileSync(fileURLToPath(new URL('../src/layouts/Layout.astro', import.meta.url)), 'utf-8');
    expect(layout).toContain('installerMesureContact(document, window)');
  });
});

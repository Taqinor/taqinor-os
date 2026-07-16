/**
 * WJ91 — VOCABULAIRE FERMÉ des événements de télémétrie privacy-light du
 * parcours /devis/mon-toit et de /proposition/[token].
 *
 * PROBLÈME résolu : chaque point d'instrumentation (le beacon d'étape WJ59
 * `funnelBeacon.ts`, le suivi d'engagement de proposition WJ55
 * `proposition.ts`) définissait ses NOMS D'ÉVÉNEMENT et ses ÉTAPES en ligne,
 * séparément. Sur un trimestre, ces vocabulaires DÉRIVENT (un nom renommé
 * d'un côté, oublié de l'autre) et il devient impossible de recouper les
 * événements entre eux de façon fiable. Ce module est la source UNIQUE des
 * noms d'événement, des noms de propriété et des identifiants d'étape — tout
 * futur call-site doit importer d'ICI plutôt que redéclarer un littéral.
 *
 * CONTRAT DE VIE PRIVÉE (jamais relâché, prouvé par le test compagnon
 * `tests/telemetryEvents.test.ts`) : un événement de télémétrie ne porte
 * JAMAIS de PII — ni nom, ni téléphone, ni e-mail, ni adresse, ni GPS, ni
 * contour de toit. C'est la même discipline que `redactLeadForLog` (lib/lead.ts)
 * et l'ALLOWLIST de `funnelBeacon.ts` (WJ59) : les seules propriétés admises
 * ci-dessous (`TELEMETRY_EVENT_PROPS`) sont des identifiants d'étape/mode/
 * locale/page — jamais un champ de contact.
 *
 * STATUT D'ADOPTION : `funnelBeacon.ts` (WJ59) et `proposition.ts` (WJ55)
 * définissent AUJOURD'HUI leurs propres identifiants d'étape/événement en
 * ligne (`FUNNEL_STEP_IDS`, `ProposalEngagementEvent`) — ces deux fichiers
 * sont HORS PÉRIMÈTRE de cette tâche (@files de WJ91 = uniquement ce module
 * neuf). Ce dictionnaire est construit pour que ces call-sites REPOINTENT
 * vers lui sans changement de forme : les identifiants d'étape ci-dessous
 * (`TELEMETRY_STEP_IDS`) reprennent EXACTEMENT les 4 valeurs de
 * `FUNNEL_STEP_IDS` (toit/facture/estimation/contact), et les noms
 * d'événement de proposition (`proposal_viewed`,
 * `proposal_scrolled_to_financing`) correspondent sémantiquement à
 * `proposal_first_view`/`proposal_scrolled_financing` de `proposition.ts` —
 * un futur repointage est donc un simple remplacement de littéral, jamais un
 * changement de forme de payload.
 *
 * WJ104 — DELTA branché : `estimate_viewed`, `callback_requested`,
 * `proposal_viewed`, `proposal_signed` sont désormais RÉELLEMENT envoyés,
 * via le canal beacon existant (WJ59 `pages/api/funnel-beacon.ts` →
 * `FUNNEL_WEBHOOK_URL`, log-only sinon) — jamais un second canal. `toFunnelWire`
 * ci-dessous traduit un nom d'événement de ce vocabulaire vers le couple
 * {step, action} qu'attend `funnelBeacon.ts` (désormais élargi, WJ104, avec
 * l'étape `proposal` et les actions `viewed`/`callback_requested`/`signed`).
 */

/**
 * Identifiants d'étape du parcours /devis/mon-toit — MIROIR exact de
 * `FUNNEL_STEP_IDS` (lib/funnelBeacon.ts, WJ59) : les 4 VRAIES étapes de
 * l'assistant (Votre toit → Votre facture → Votre estimation → contact/porte
 * de conversion). Ne JAMAIS ajouter un id ici qui ne correspond à aucune
 * étape réelle de l'assistant.
 */
export const TELEMETRY_STEP_IDS = ['toit', 'facture', 'estimation', 'contact'] as const;
export type TelemetryStepId = (typeof TELEMETRY_STEP_IDS)[number];

/**
 * Modes de parcours — MIROIR exact de `LEAD_MODES` (lib/lead.ts, WJ6/WJ30) :
 * résidentiel / industriel / commercial / agricole, plus l'alias hérité
 * professionnel (WJ121 — accepté, plus jamais émis par le site). Jamais un
 * mode inventé ici qui n'existe pas dans LEAD_MODES.
 */
export const TELEMETRY_MODES = ['residentiel', 'professionnel', 'industriel', 'commercial', 'agricole'] as const;
export type TelemetryMode = (typeof TELEMETRY_MODES)[number];

/** Langues actives suivies — MIROIR de `LEAD_LANGS` (lib/lead.ts). */
export const TELEMETRY_LOCALES = ['fr', 'ar', 'en'] as const;
export type TelemetryLocale = (typeof TELEMETRY_LOCALES)[number];

/**
 * VOCABULAIRE FERMÉ des noms d'événement. Chaque entrée documente la sémantique
 * ET le call-site (existant ou visé) pour qu'un nouvel appelant sache lequel
 * choisir sans deviner :
 *  - `journey_step_viewed` / `_completed` / `_abandoned` — cycle de vie d'une
 *    étape de l'assistant /devis/mon-toit (repoint visé : WJ59 funnelBeacon.ts,
 *    qui utilise aujourd'hui reached/abandoned — _completed est l'extension
 *    honnête d'un « reached » qui a mené à l'étape suivante).
 *  - `estimate_rendered` — l'estimation instantanée (billEstimate) vient de
 *    s'afficher à l'écran (étape "estimation" atteinte AVEC un résultat rendu,
 *    distinct d'un simple `journey_step_viewed('estimation')` qui ne dit rien
 *    du succès du calcul).
 *  - `whatsapp_clicked` — le CTA WhatsApp (deeplink pré-rempli, WJ3) a été activé.
 *  - `proposal_viewed` / `proposal_scrolled_to_financing` / `proposal_signed`
 *    — cycle de vie de /proposition/[token] (repoint visé : WJ55 proposition.ts,
 *    qui utilise aujourd'hui proposal_first_view/proposal_scrolled_financing ;
 *    proposal_signed est NOUVEAU, pour le moment de signature électronique).
 *  - `estimate_viewed` (WJ104) — l'estimation instantanée (billEstimate) vient
 *    d'être RENDUE À L'ÉCRAN sur /devis/mon-toit — synonyme intentionnel
 *    d'`estimate_rendered` (même moment), nommé pour matcher le vocabulaire
 *    demandé par le suivi de funnel WJ104 ; branché sur le beacon WJ59 via
 *    `toFunnelWire` ci-dessous (step `estimation`, action `viewed`).
 *  - `callback_requested` (WJ104) — une demande de rappel EXPLICITE (WJ97,
 *    /contact « on vous rappelle » ou l'équivalent sur mon-toit), DISTINCTE
 *    d'un simple opt-in WhatsApp (`whatsapp_clicked`) — branché sur (step
 *    `contact`, action `callback_requested`).
 */
export const TELEMETRY_EVENTS = [
  'journey_step_viewed',
  'journey_step_completed',
  'journey_step_abandoned',
  'estimate_rendered',
  'estimate_viewed',
  'whatsapp_clicked',
  'callback_requested',
  'proposal_viewed',
  'proposal_scrolled_to_financing',
  'proposal_signed',
] as const;
export type TelemetryEventName = (typeof TELEMETRY_EVENTS)[number];

/**
 * ALLOWLIST des propriétés qu'un événement peut porter — la garantie
 * anti-PII. `step_id` est borné à TELEMETRY_STEP_IDS, `mode` à
 * TELEMETRY_MODES, `locale` à TELEMETRY_LOCALES ; `page` reste un chemin
 * (jamais une query string — même discipline que `cleanPath` dans
 * funnelBeacon.ts). AUCUNE autre clé n'est un événement de télémétrie valide.
 */
export const TELEMETRY_EVENT_PROPS = ['step_id', 'mode', 'locale', 'page'] as const;
export type TelemetryEventProp = (typeof TELEMETRY_EVENT_PROPS)[number];

export interface TelemetryEventProps {
  step_id?: TelemetryStepId;
  mode?: TelemetryMode;
  locale?: TelemetryLocale;
  /** Chemin de page (ex. "/devis/mon-toit"), jamais une URL complète/query string. */
  page?: string;
}

export interface TelemetryEvent {
  event: TelemetryEventName;
  props: TelemetryEventProps;
}

/** Clés STRICTEMENT interdites dans un événement de télémétrie — la liste
 *  noire explicite qui documente l'intention (en plus de l'allowlist
 *  positive ci-dessus) : un slip qui ajouterait l'une de ces clés à
 *  TELEMETRY_EVENT_PROPS romprait le contrat de vie privée. Le test compagnon
 *  vérifie qu'AUCUNE de ces clés n'apparaît jamais dans un événement construit
 *  par `buildTelemetryEvent`. */
export const TELEMETRY_FORBIDDEN_KEYS = [
  'name',
  'fullName',
  'phone',
  'phoneE164',
  'email',
  'address',
  'adresse',
  'city',
  'gps',
  'gpsLat',
  'gpsLng',
  'roofPoint',
  'roofOutline',
] as const;

function isEnum<T extends string>(v: unknown, allowed: readonly T[]): v is T {
  return typeof v === 'string' && (allowed as readonly string[]).includes(v);
}

/** Chemin sûr : commence par "/", jamais de query string ni de fragment. */
function cleanPage(v: unknown): string | undefined {
  if (typeof v !== 'string') return undefined;
  const raw = v.trim().slice(0, 200);
  if (!raw.startsWith('/')) return undefined;
  return raw.split('?')[0].split('#')[0] || undefined;
}

/**
 * Construit un événement de télémétrie VALIDÉ : le nom doit appartenir à
 * TELEMETRY_EVENTS, et SEULES les propriétés de l'allowlist sont retenues
 * (chacune validée individuellement, une valeur malformée est simplement
 * omise — jamais bloquant, jamais une exception levée). C'est le point de
 * passage unique recommandé pour tout futur appelant : construire l'objet à
 * la main risque d'oublier le filtrage anti-PII que cette fonction garantit.
 */
export function buildTelemetryEvent(
  event: TelemetryEventName,
  props: Record<string, unknown> = {},
): TelemetryEvent {
  const cleaned: TelemetryEventProps = {};
  if (isEnum(props.step_id, TELEMETRY_STEP_IDS)) cleaned.step_id = props.step_id;
  if (isEnum(props.mode, TELEMETRY_MODES)) cleaned.mode = props.mode;
  if (isEnum(props.locale, TELEMETRY_LOCALES)) cleaned.locale = props.locale;
  const page = cleanPage(props.page);
  if (page) cleaned.page = page;
  return { event, props: cleaned };
}

/** `true` ssi `name` est un nom d'événement du vocabulaire fermé. */
export function isTelemetryEventName(name: unknown): name is TelemetryEventName {
  return isEnum(name, TELEMETRY_EVENTS);
}

// ── WJ104 · Pont vers le beacon step-level existant (WJ59 funnelBeacon.ts) ──
//
// `funnel-beacon.ts` (le SEUL transport câblé aujourd'hui, `FUNNEL_WEBHOOK_URL`)
// attend un couple fermé {step, action} — pas un nom d'événement libre. Plutôt
// qu'un second canal/endpoint pour ce vocabulaire de plus haut niveau, ce
// module se contente de TRADUIRE les 4 événements DELTA de WJ104 vers ce
// couple ; `journey_step_*`/`estimate_rendered`/`whatsapp_clicked` restent des
// noms DÉCLARÉS mais NON câblés (statut d'adoption inchangé, cf. l'en-tête).

/** Couple {step, action} au format attendu par `validateBeaconEvent` (funnelBeacon.ts). */
export interface FunnelWireEvent {
  step: 'toit' | 'facture' | 'estimation' | 'contact' | 'proposal';
  action: 'reached' | 'abandoned' | 'viewed' | 'callback_requested' | 'signed';
}

/**
 * WJ104 — Traduit un événement du vocabulaire DELTA (`estimate_viewed`,
 * `callback_requested`, `proposal_viewed`, `proposal_signed`) vers le couple
 * {step, action} du beacon WJ59. Renvoie `null` pour tout autre nom
 * (`journey_step_*`/`estimate_rendered`/`whatsapp_clicked`/
 * `proposal_scrolled_to_financing`) — non câblés aujourd'hui, jamais un envoi
 * silencieusement mal formé.
 */
export function toFunnelWire(event: TelemetryEventName): FunnelWireEvent | null {
  switch (event) {
    case 'estimate_viewed':
      return { step: 'estimation', action: 'viewed' };
    case 'callback_requested':
      return { step: 'contact', action: 'callback_requested' };
    case 'proposal_viewed':
      return { step: 'proposal', action: 'viewed' };
    case 'proposal_signed':
      return { step: 'proposal', action: 'signed' };
    default:
      return null;
  }
}

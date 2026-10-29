// RWEB17-M1 — SECTION « PERSISTANCE » du tunnel « mon-toit » (FR/EN/AR).
//
// Extrait À L'IDENTIQUE de la page FR (code vérifié identique sur les trois
// locales, aux commentaires près) : jeton de funnel et balises, bandeau
// hors ligne, instantané `mt-wizard-v1`, garde `beforeunload`, jetons de
// dédoublonnage, réhydratation, persistance à la saisie, référence client et
// clés de suivi. Possède `restoring`, `hasEnteredData`, `dedupIdempotencyKey`,
// `dedupEventId`, `clientRef` (de `ctx.etat`). Aucune page ne l'importe encore
// (M11 les câble).
//
// CROCHETS REQUIS (inscrits par d'autres sections, appelés tard) :
// `syncCityRequirement` et `syncCallbackSla` (parcours, M2),
// `syncEquipDetails` (sélections, M3). CROCHETS INSCRITS ICI : `saveWizardState`,
// `markDataEntered`, `sendFunnelBeacon`, `hasReachedConsentStep`,
// `getOrCreateDedupTokens`, `getOrCreateClientRef`, `readTrackingParams`,
// `clearWizardState`.

import { buildClientRef } from '../lead';
import { newDedupToken, type WizardSnapshot } from './etat';
import type { ContexteTunnel } from './contexte';

export const FUNNEL_TOKEN_KEY = 'mt-funnel-token-v1';
export const WIZARD_STORAGE_KEY = 'mt-wizard-v1';

export const PERSISTED_TEXT_FIELDS = [
  'mt-name', 'mt-phone', 'mt-city', 'mt-email', 'mt-facture-hiver',
  'mt-bill', 'mt-fallback-address',
  'rp9-address',
  'mt-raison-sociale',
  'mt-pro-bill', 'mt-surface-m2',
  'mt-cc-bill',
  'mt-profondeur', 'mt-hmt', 'mt-water-need', 'mt-heures-pompage',
  'mt-culture', 'mt-surface-ha', 'mt-fuel-spend',
  'mt-equip-ve-km', 'mt-equip-clim-pieces', 'mt-equip-piscine-kw',
  'mt-equip-chauffe-eau-kw', 'mt-equip-chauffe-eau-creneau',
  'mt-equip-ve-kw', 'mt-equip-ve-creneau',
  'mt-equip-clim-kw', 'mt-equip-clim-creneau',
  'mt-equip-piscine-heures', 'mt-equip-piscine-creneau',
];
export const PERSISTED_CHECK_FIELDS = [
  'mt-contact-whatsapp', 'mt-contact-phone', 'mt-consent',
  'mt-equip-chauffe-eau', 'mt-equip-ve', 'mt-equip-clim', 'mt-equip-piscine',
];
export const PERSIST_ON_INPUT_IDS = [...PERSISTED_TEXT_FIELDS, ...PERSISTED_CHECK_FIELDS];

export const TRACK_KEYS = ['fbclid', 'gclid', 'gbraid', 'wbraid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'] as const;

export type EtapeFunnel = 'toit' | 'facture' | 'estimation' | 'contact';
export type ActionFunnel = 'reached' | 'abandoned' | 'viewed' | 'callback_requested';

/** Relit l'instantané (ou `null`) — fonction pure, appelée AVANT `creerEtat`. */
export function loadWizardState(): WizardSnapshot | null {
  try {
    const raw = sessionStorage.getItem(WIZARD_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as WizardSnapshot) : null;
  } catch {
    return null;
  }
}

export function clearWizardState() {
  try { sessionStorage.removeItem(WIZARD_STORAGE_KEY); } catch { /* confort seulement */ }
}

/** Clés de suivi (fbclid, gclid, UTM…) reprises du `sessionStorage`. */
export function readTrackingParams(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const k of TRACK_KEYS) {
    try {
      const v = sessionStorage.getItem('tq_' + k);
      if (v) out[k] = v;
    } catch {}
  }
  return out;
}

function getFunnelToken(): string {
  try {
    let t = sessionStorage.getItem(FUNNEL_TOKEN_KEY);
    if (!t) {
      t = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(FUNNEL_TOKEN_KEY, t);
    }
    return t;
  } catch {
    // sessionStorage indisponible : jeton éphémère, jamais un blocage.
    return Math.random().toString(36).slice(2);
  }
}

export interface Persistance {
  saveWizardState: () => void;
  markDataEntered: () => void;
  hasReachedConsentStep: () => boolean;
  sendFunnelBeacon: (step: EtapeFunnel, action: ActionFunnel) => void;
  getOrCreateDedupTokens: () => { idempotencyKey: string; eventId: string };
  getOrCreateClientRef: () => string;
  /** WJ61 — peuple champs, repère et contour depuis l'instantané. */
  rehydrater: () => void;
  /** WJ61 — persiste sur toute frappe/changement des champs listés. */
  brancherPersistanceSurSaisie: () => void;
}

/** Installe la section : jeton de funnel, bandeau hors ligne, `beforeunload`,
 *  crochets. `savedWizard` = `loadWizardState()` déjà lu pour `creerEtat`.
 *  `rehydrater` et `brancherPersistanceSurSaisie` sont appelés par la page à
 *  leur place d'origine (après les sections dont ils dépendent). */
export function installerPersistance(ctx: ContexteTunnel, savedWizard: WizardSnapshot | null): Persistance {
  const { etat, dom } = ctx;
  const { $, val } = dom;

  // ——— WJ59 : beacon de funnel étape par étape (privacy-light, aucune PII) ———
  const funnelToken = getFunnelToken();
  const funnelStepReached = new Set<string>(); // évite les doublons « reached » sur re-render.

  function hasReachedConsentStep(): boolean {
    return etat.step >= 1 && etat.revealed;
  }

  function sendFunnelBeacon(step: EtapeFunnel, action: ActionFunnel) {
    if (action === 'reached' || action === 'viewed' || action === 'callback_requested') {
      const key = `${step}:${action}`;
      if (funnelStepReached.has(key)) return;
      funnelStepReached.add(key);
    }
    try {
      const payload = JSON.stringify({ step, action, sessionToken: funnelToken, path: location.pathname });
      if (navigator.sendBeacon) {
        const blob = new Blob([payload], { type: 'application/json' });
        navigator.sendBeacon('/api/funnel-beacon', blob);
      } else {
        void fetch('/api/funnel-beacon', { method: 'POST', headers: { 'content-type': 'application/json' }, body: payload, keepalive: true }).catch(() => {});
      }
    } catch {
      // Mesure best-effort seulement — ne doit jamais perturber le parcours.
    }
  }

  // ——— WJ45 : bandeau hors-ligne (navigator.onLine + online/offline) ———
  const offlineBanner = $('mt-offline-banner');
  function syncOfflineBanner() {
    if (offlineBanner) offlineBanner.hidden = navigator.onLine;
  }
  syncOfflineBanner();
  window.addEventListener('online', syncOfflineBanner);
  window.addEventListener('offline', syncOfflineBanner);

  // ——— WJ61 : l'état de l'assistant survit à un rafraîchissement/retour ———
  function saveWizardState() {
    if (etat.restoring) return;
    try {
      const fields: Record<string, string> = {};
      for (const id of PERSISTED_TEXT_FIELDS) {
        const v = val(id);
        if (v) fields[id] = v;
      }
      const checks: Record<string, boolean> = {};
      for (const id of PERSISTED_CHECK_FIELDS) {
        const el = $(id) as HTMLInputElement | null;
        if (el) checks[id] = el.checked;
      }
      const snapshot: WizardSnapshot = {
        step: etat.step, revealed: etat.revealed, mode: etat.mode,
        visitWindowPart: etat.visitWindowPart, visitWindowWeek: etat.visitWindowWeek,
        sel: {
          proUnit: etat.proUnit, tension: etat.tension, activity: etat.activity,
          tensionTouched: etat.tensionTouched ? '1' : '', activityTouched: etat.activityTouched ? '1' : '',
          surfaceType: etat.surfaceType, waterSource: etat.waterSource, waterUnit: etat.waterUnit,
          commercialCategory: etat.commercialCategory, ccUnit: etat.ccUnit, equipes: etat.equipes,
          regionAgricole: etat.regionAgricole, roofInputMode: etat.roofInputMode, occupationJour: etat.occupationJour,
        },
        capturePin: etat.capturePin, captureOutline: etat.captureOutline, capturePans: etat.capturePans, captureLayout: etat.captureLayout,
        fields, checks,
        idempotencyKey: etat.dedupIdempotencyKey, eventId: etat.dedupEventId,
      };
      sessionStorage.setItem(WIZARD_STORAGE_KEY, JSON.stringify(snapshot));
    } catch {
      // sessionStorage indisponible : la persistance est un CONFORT.
    }
  }

  // WJ61 — garde-fou de sortie : invite native une fois des données saisies.
  function markDataEntered() { etat.hasEnteredData = true; }
  window.addEventListener('beforeunload', (e) => {
    if (!etat.hasEnteredData || etat.submitted) return;
    e.preventDefault();
    e.returnValue = '';
  });

  // ——— Jetons de DÉDOUBLONNAGE technique (CRM + Meta CAPI) ———
  function getOrCreateDedupTokens(): { idempotencyKey: string; eventId: string } {
    if (!etat.dedupIdempotencyKey) etat.dedupIdempotencyKey = newDedupToken();
    if (!etat.dedupEventId) etat.dedupEventId = newDedupToken();
    return { idempotencyKey: etat.dedupIdempotencyKey, eventId: etat.dedupEventId };
  }

  // ——— WJ52 : référence client courte, générée UNE FOIS côté navigateur ———
  function getOrCreateClientRef(): string {
    if (!etat.clientRef) etat.clientRef = buildClientRef();
    return etat.clientRef;
  }

  function rehydrater() {
    if (!savedWizard) return;
    etat.restoring = true;
    for (const [id, v] of Object.entries(savedWizard.fields ?? {})) {
      const el = $(id) as HTMLInputElement | HTMLSelectElement | null;
      if (el) el.value = v;
    }
    for (const [id, v] of Object.entries(savedWizard.checks ?? {})) {
      const el = $(id) as HTMLInputElement | null;
      if (el) el.checked = v;
    }
    // Une ville restaurée compte comme « déjà touchée ».
    if (savedWizard.fields?.['mt-city']) etat.cityTouched = true;
    // AGW403 — un curseur « heures de pompage » restauré à une valeur ≠ 7 a été touché.
    {
      const hp = $('mt-heures-pompage') as HTMLInputElement | null;
      const savedHp = savedWizard.fields?.['mt-heures-pompage'];
      if (hp && savedHp && savedHp !== '7') hp.dataset.touche = '1';
    }
    ctx.crochets.appeler('syncCallbackSla');
    ctx.crochets.appeler('syncEquipDetails');
    if (savedWizard.capturePin) etat.capturePin = savedWizard.capturePin;
    if (savedWizard.captureOutline?.length) etat.captureOutline = savedWizard.captureOutline;
    if (savedWizard.capturePans?.length) etat.capturePans = savedWizard.capturePans;
    if (savedWizard.captureLayout) etat.captureLayout = savedWizard.captureLayout;
    ctx.crochets.appeler('syncCityRequirement');
    if (Object.keys(savedWizard.fields ?? {}).length > 0 || savedWizard.capturePin) markDataEntered();
    etat.restoring = false;
  }

  function brancherPersistanceSurSaisie() {
    for (const id of PERSIST_ON_INPUT_IDS) {
      const el = $(id);
      el?.addEventListener('input', () => { markDataEntered(); saveWizardState(); });
      el?.addEventListener('change', () => { markDataEntered(); saveWizardState(); });
    }
  }

  const section: Persistance = {
    saveWizardState, markDataEntered, hasReachedConsentStep, sendFunnelBeacon,
    getOrCreateDedupTokens, getOrCreateClientRef, rehydrater, brancherPersistanceSurSaisie,
  };
  const { crochets } = ctx;
  crochets.installer('saveWizardState', saveWizardState);
  crochets.installer('markDataEntered', markDataEntered);
  crochets.installer('hasReachedConsentStep', hasReachedConsentStep);
  crochets.installer('sendFunnelBeacon', sendFunnelBeacon);
  crochets.installer('getOrCreateDedupTokens', getOrCreateDedupTokens);
  crochets.installer('getOrCreateClientRef', getOrCreateClientRef);
  crochets.installer('readTrackingParams', readTrackingParams);
  crochets.installer('clearWizardState', clearWizardState);
  return section;
}

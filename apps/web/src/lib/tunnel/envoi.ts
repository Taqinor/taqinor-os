// RWEB17-M8 — SECTION « ENVOI ET SORTIE » du tunnel « mon-toit ».
//
// Reprend le lien WhatsApp (`buildWaUrl`), la relève de la référence serveur
// (`pollServerClientRef`), l'étape « Affiner » (`setupAffiner`), la soumission
// vers /api/capture-lead (`submit`, `setSubmitPending`, messages d'erreur), la
// modale de sortie (piège de focus, lien WhatsApp d'abandon) et l'init finale.
// Les messages suivent la langue AFFICHÉE (`langueActive`) en FR et AR, et sont
// constants en EN : une seule table par langue.
//
// DÉCISION FONDATEUR D-RWEB17-WA-REF (29/10/2026) : le message WhatsApp du lien
// de succès porte « Ma référence : <code> » dans les TROIS locales (les pages EN
// et AR l'omettaient). C'est le SEUL changement de comportement de cette
// section ; `captureWhatsappText` n'a pas de gestion de locale (le message est
// en français sur les trois pages), la ligne reste donc dans sa forme existante.
//
// La section ne possède que `submitted`, `exitShown`, `exitTriggerEl`,
// `funnelAbandonSent` ; elle lit/écrit le reste via `ctx.etat` et appelle les
// autres sections par `ctx.crochets` (voir `CROCHETS_REQUIS`). Non câblée avant M18.

import { WHATSAPP_LEADS } from '../nap';
import { brancherAffiner } from '../../scripts/tunnel/affiner';
import { captureWhatsappText, whatsappLink } from '../whatsapp';
import type { ContexteTunnel } from './contexte';

/** Crochets que cette section APPELLE (installés par les autres sections). */
export const CROCHETS_REQUIS = [
  'langueActive', // M2
  'corpsDuLead', // M7
  'showInlineErrors', // M7
  'traduireErreur', // M7 (EN : messages de validateLead traduits ; sinon identité)
  'getOrCreateClientRef', // M1
  'getOrCreateDedupTokens', // M1
  'clearWizardState', // M1
  'syncOfflineBanner', // M1
  'sendFunnelBeacon', // M1
  'hasReachedConsentStep', // M1
  'resolveMonthlyBill', // M3
  'syncBillRangeFromExact', // M3
  'computeEstimate', // M6
] as const;

type Langue = 'fr' | 'ar' | 'en';

interface MessagesEnvoi {
  serverError: string;
  offline: string;
  fieldsHighlighted: string;
  missingField: string;
  exitPhone: string;
}

const MESSAGES: Record<Langue, MessagesEnvoi> = {
  fr: {
    serverError: 'Un problème technique de notre côté — réessayez.',
    offline: 'Pas de connexion — vos réponses sont conservées, on réessaie dès le retour du réseau.',
    fieldsHighlighted: 'Vérifiez les champs surlignés ci-dessus.',
    missingField: 'Un champ est manquant ou invalide. Vérifiez vos informations.',
    exitPhone: "Indiquez un numéro pour qu'on vous réponde.",
  },
  ar: {
    serverError: 'مشكلة تقنية من جانبنا — يرجى إعادة المحاولة.',
    offline: 'لا يوجد اتصال — إجاباتكم محفوظة، سنعيد المحاولة فور عودة الشبكة.',
    fieldsHighlighted: 'يرجى مراجعة الحقول المُبرزة أعلاه.',
    missingField: 'حقل ناقص أو غير صالح. يرجى مراجعة معلوماتكم.',
    exitPhone: 'يرجى إدخال رقم للرد عليكم.',
  },
  en: {
    serverError: 'A technical problem on our side — please try again.',
    offline: "No connection — your answers are kept, we'll retry as soon as the network is back.",
    fieldsHighlighted: 'Please check the highlighted fields above.',
    missingField: 'A field is missing or invalid. Please check your information.',
    exitPhone: 'Please enter a number so we can reply to you.',
  },
};

/** Élément qui reprend le focus à la fermeture de la modale sans déclencheur. */
const ANCRE_FOCUS: Record<'fr' | 'en' | 'ar', string> = { fr: 'mt-lang-fr', en: 'mt-next-0', ar: 'mt-lang-fr' };

const LEAD_REF_LOOKUP_WAITS_MS = [1000, 1500, 2000];
const LEAD_REF_LOOKUP_TIMEOUT_MS = 1500;
// WJ60 — 15 s laisse le temps à une connexion lente de répondre.
const SUBMIT_TIMEOUT_MS = 15_000;

export interface SectionLienWhatsapp {
  buildWaUrl(): string;
  pollServerClientRef(idempotencyKey: string): void;
  setupAffiner(idempotencyKey: string): void;
}
export interface SectionSoumission {
  setSubmitPending(pending: boolean): void;
}
export interface SectionSortie {
  buildExitWaHref(): string;
  showWhatsappOffer(triggerEl?: HTMLElement | null): void;
  maybeShowExit(triggerEl?: HTMLElement | null): void;
  closeExit(): void;
}

const appelerCrochet = (ctx: ContexteTunnel, nom: string, ...args: unknown[]) => ctx.crochets.appeler(nom, ...args);
const inscrire = (ctx: ContexteTunnel, section: object) => {
  for (const [nom, fn] of Object.entries(section)) ctx.crochets.installer(nom, fn as (...a: any[]) => any);
};

/** Les quatre installeurs, dans l'ordre de la page. */
export function installerEnvoi(ctx: ContexteTunnel, doc: Document) {
  const lien = installerLienWhatsapp(ctx, doc);
  const soumission = installerSoumission(ctx, doc);
  const sortie = installerSortie(ctx, doc);
  initialiserEnvoi(ctx);
  return { ...lien, ...soumission, ...sortie };
}

/** Lien WhatsApp, relève de la référence serveur, « Affiner » (FR l. 4588-4650). */
export function installerLienWhatsapp(ctx: ContexteTunnel, doc: Document): SectionLienWhatsapp {
  const { $, val } = ctx.dom;
  const appeler = (nom: string, ...args: unknown[]) => appelerCrochet(ctx, nom, ...args);

  function buildWaUrl(): string {
    const addressEl = $('rp9-address') as HTMLInputElement | null;
    const text = captureWhatsappText({
      fullName: val('mt-name'),
      city: (val('mt-city') || addressEl?.value || '').trim(),
      kwcLabel: ctx.etat.lastKwcLabel || undefined,
      savingsLabel: ctx.etat.lastSavingsLabel || undefined,
      // WREF + D-RWEB17-WA-REF — le code promis par l'écran de succès voyage dans
      // le message, quelle que soit la locale.
      clientRef: appeler('getOrCreateClientRef'),
    });
    return whatsappLink(WHATSAPP_LEADS, text);
  }

  // WREF2-L3 — relève de la vraie référence serveur « NOM-N » APRÈS l'envoi
  // fire-and-forget ; silencieuse en échec (le code provisoire reste affiché).
  function pollServerClientRef(idempotencyKey: string) {
    if (!idempotencyKey) return;
    void (async () => {
      for (const waitMs of LEAD_REF_LOOKUP_WAITS_MS) {
        await new Promise((resolve) => setTimeout(resolve, waitMs));
        try {
          const res = await fetch(`/api/lead-ref-lookup?key=${encodeURIComponent(idempotencyKey)}`, {
            signal: AbortSignal.timeout(LEAD_REF_LOOKUP_TIMEOUT_MS),
          });
          const data = (await res.json().catch(() => null)) as { ok?: boolean; client_ref?: string } | null;
          if (data?.ok && data.client_ref) {
            ctx.etat.clientRef = data.client_ref; // getOrCreateClientRef() renvoie désormais la vraie référence.
            const refEl = $('mt-client-ref');
            if (refEl) refEl.textContent = ctx.etat.clientRef;
            const waLink = $('mt-success-wa') as HTMLAnchorElement | null;
            if (waLink) waLink.href = buildWaUrl();
            return;
          }
        } catch {
          // silencieux — on retente.
        }
      }
    })();
  }

  // CIW405 (D-CIQ-8) — étape « Affiner », réservée aux profils commercial / industriel.
  function setupAffiner(idempotencyKey: string) {
    if (ctx.etat.mode !== 'commercial' && ctx.etat.mode !== 'industriel') return;
    brancherAffiner($('mt-affiner') as HTMLButtonElement | null, idempotencyKey);
  }

  void doc;
  const section: SectionLienWhatsapp = { buildWaUrl, pollServerClientRef, setupAffiner };
  inscrire(ctx, section);
  return section;
}

/** Soumission vers /api/capture-lead (FR l. 4651-4837). */
export function installerSoumission(ctx: ContexteTunnel, doc: Document): SectionSoumission {
  const { $ } = ctx.dom;
  const appeler = (nom: string, ...args: unknown[]) => appelerCrochet(ctx, nom, ...args);
  const win = doc.defaultView as Window & typeof globalThis;
  const reducedMotion = win.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const msgs = (): MessagesEnvoi => MESSAGES[appeler('langueActive') as Langue];

  const form = $('mt-form') as HTMLFormElement | null;
  const errEl = $('mt-error');
  const okEl = $('mt-success');
  const belowEl = $('mt-belowthreshold');
  const submitBtn = $('mt-submit') as HTMLButtonElement | null;
  const submitLabelEl = $('mt-submit-label');
  const submitPendingEl = $('mt-submit-pending');

  // WJ60 — bascule le CTA sur « Envoi en cours… » pendant l'attente réseau.
  function setSubmitPending(pending: boolean) {
    if (submitBtn) submitBtn.disabled = pending;
    if (submitLabelEl) submitLabelEl.hidden = pending;
    if (submitPendingEl) submitPendingEl.hidden = !pending;
  }

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (errEl) errEl.hidden = true;
    const { body, errors } = appeler('corpsDuLead') as { body: Record<string, unknown>; errors: Record<string, string> };
    if (Object.keys(errors).length > 0) {
      appeler('showInlineErrors', errors);
      if (errEl) {
        errEl.textContent = msgs().fieldsHighlighted;
        errEl.hidden = false;
      }
      // amène l'utilisateur au premier champ en erreur.
      const firstId = ['mt-name', 'mt-phone', 'mt-city', 'mt-bill']
        .find((id) => $(id)?.getAttribute('aria-invalid') === 'true');
      if (firstId) ($(firstId) as HTMLElement | null)?.focus();
      return;
    }
    appeler('showInlineErrors', {});

    setSubmitPending(true);
    try {
      const res = await fetch('/api/capture-lead', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(SUBMIT_TIMEOUT_MS),
      });
      // WJ60/WJ63 — une réponse JSON malformée est une panne serveur.
      let malformed = false;
      const data = (await res.json().catch(() => {
        malformed = true;
        return {};
      })) as { ok?: boolean; qualified?: boolean; errors?: Record<string, string> };
      if (res.ok && !malformed && data.ok) {
        ctx.etat.submitted = true;
        ctx.etat.hasEnteredData = false; // WJ61 — plus besoin du garde-fou beforeunload.
        appeler('clearWizardState'); // WJ61 — l'instantané n'a plus lieu d'être.
        // WJ104 — « rappel demandé » : seulement si « on m'appelle » est choisi.
        if (($('mt-contact-phone') as HTMLInputElement | null)?.checked === true) {
          appeler('sendFunnelBeacon', 'contact', 'callback_requested');
        }
        const waUrl = appeler('buildWaUrl') as string;
        // WJ5 — réponse HONNÊTE selon le seuil 1 000 MAD (qualified renvoyé par le serveur).
        if (data.qualified) {
          // WB33 — événement « Lead » avec le MÊME event_id que le relais CAPI.
          (win as unknown as { tqPixelTrack?: (e: string, p?: object, id?: string) => void })
            .tqPixelTrack?.('Lead', {}, appeler('getOrCreateDedupTokens').eventId);
          (win as unknown as { tqGoogleTrack?: (id?: string) => void })
            .tqGoogleTrack?.(appeler('getOrCreateDedupTokens').eventId);
          if (okEl) okEl.hidden = false;
          // WJ52 — la référence incluse dans le body, relue (jamais régénérée).
          const refEl = $('mt-client-ref');
          if (refEl) refEl.textContent = appeler('getOrCreateClientRef');
          const waLink = $('mt-success-wa') as HTMLAnchorElement | null;
          if (waLink) waLink.href = waUrl;
          // WREF2-L3 — relève best-effort de la vraie référence serveur.
          appeler('pollServerClientRef', appeler('getOrCreateDedupTokens').idempotencyKey);
          appeler('setupAffiner', appeler('getOrCreateDedupTokens').idempotencyKey); // CIW405
          // WJ3/WJ51 — sur mobile, WhatsApp s'ouvre si la préférence est « Uniquement sur WhatsApp ».
          const wantsWa = ($('mt-contact-phone') as HTMLInputElement | null)?.checked !== true;
          if (wantsWa && /Mobi|Android|iPhone/i.test(win.navigator.userAgent) && !reducedMotion) {
            setTimeout(() => { win.location.href = waUrl; }, 900);
          }
        } else {
          // sous le seuil : PAS de faux « enregistré » — message adapté + WhatsApp.
          const mode = ctx.etat.mode;
          if (mode === 'commercial' || mode === 'industriel') {
            // CIW409 — message neutre pour un pro.
            const neutreEl = $('mt-belowthreshold-pro');
            if (neutreEl) neutreEl.hidden = false;
            const neutreWa = $('mt-belowthreshold-pro-wa') as HTMLAnchorElement | null;
            if (neutreWa) neutreWa.href = waUrl;
          } else {
            if (belowEl) belowEl.hidden = false;
            const belowWa = $('mt-belowthreshold-wa') as HTMLAnchorElement | null;
            if (belowWa) belowWa.href = waUrl;
          }
        }
        // désactive les champs après envoi (sauf les liens WhatsApp).
        Array.from(form.elements).forEach((el) => ((el as HTMLInputElement).disabled = true));
        return;
      }
      // WJ60/WJ63 — ≥500 ou JSON malformé : panne CÔTÉ SERVEUR, jamais un message
      // qui blâme les champs ; `errors.rate` (429) ne remplace pas notre copie.
      const isServerError = malformed || res.status >= 500 || (!!data.errors && 'rate' in data.errors);
      if (!isServerError && data.errors) appeler('showInlineErrors', data.errors);
      const firstFieldErr = !isServerError && data.errors ? Object.values(data.errors)[0] : null;
      if (errEl) {
        errEl.textContent = isServerError
          ? msgs().serverError
          : ((firstFieldErr && appeler('traduireErreur', firstFieldErr)) || msgs().missingField);
        errEl.hidden = false;
      }
      setSubmitPending(false);
    } catch {
      // WJ60 — englobe le timeout et toute coupure réseau ; WJ45 — hors-ligne dit explicitement.
      appeler('syncOfflineBanner');
      if (errEl) {
        errEl.textContent = win.navigator.onLine ? msgs().serverError : msgs().offline;
        errEl.hidden = false;
      }
      setSubmitPending(false);
    }
  });

  const section: SectionSoumission = { setSubmitPending };
  inscrire(ctx, section);
  return section;
}

/** Modale de sortie : exit-intent, pic d'intérêt, piège de focus (FR l. 4838-4975). */
export function installerSortie(ctx: ContexteTunnel, doc: Document): SectionSortie {
  const { $, val } = ctx.dom;
  const appeler = (nom: string, ...args: unknown[]) => appelerCrochet(ctx, nom, ...args);
  const win = doc.defaultView as Window & typeof globalThis;
  const exitModal = $('mt-exit') as HTMLElement | null;
  const exitPhoneInput = $('mt-exit-phone') as HTMLInputElement | null;
  const exitWaLink = $('mt-exit-wa') as HTMLAnchorElement | null;

  /** WJ33 — construit (ou reconstruit) le lien WhatsApp d'abandon depuis l'état actuel. */
  function buildExitWaHref(): string {
    const phone = exitPhoneInput?.value.trim() || '';
    const addressEl = $('rp9-address') as HTMLInputElement | null;
    const text = captureWhatsappText({
      fullName: '',
      city: (val('mt-city') || addressEl?.value || '').trim(),
      kwcLabel: ctx.etat.lastKwcLabel || undefined,
      savingsLabel: ctx.etat.lastSavingsLabel || undefined,
    }) + (phone.length >= 6 ? ` Mon numéro : ${phone}.` : '');
    return whatsappLink(WHATSAPP_LEADS, text);
  }

  // WJ102 — le RESTE du document devient inatteignable (`inert`) pendant la modale.
  const inertedSiblings: HTMLElement[] = [];
  function setBackgroundInert(on: boolean): void {
    if (on) {
      inertedSiblings.length = 0;
      for (const child of Array.from(doc.body.children)) {
        if (!(child instanceof win.HTMLElement)) continue;
        if (child.contains(exitModal)) continue; // ne jamais rendre la modale elle-même inerte
        if (child.hasAttribute('inert')) continue; // déjà inerte pour une autre raison
        child.setAttribute('inert', '');
        inertedSiblings.push(child);
      }
    } else {
      for (const el of inertedSiblings) el.removeAttribute('inert');
      inertedSiblings.length = 0;
    }
  }

  /** WJ46 — affiche l'offre WhatsApp (exit-intent OU pic d'intérêt), une fois par visite. */
  function showWhatsappOffer(triggerEl: HTMLElement | null = null) {
    if (ctx.etat.exitShown || ctx.etat.submitted) return;
    ctx.etat.exitShown = true;
    ctx.etat.exitTriggerEl = triggerEl ?? (doc.activeElement as HTMLElement | null);
    if (exitWaLink) exitWaLink.href = buildExitWaHref();
    if (exitModal) {
      exitModal.hidden = false;
      setBackgroundInert(true);
      exitPhoneInput?.focus(); // WJ33 — focus initial DANS la modale
    }
  }
  function maybeShowExit(triggerEl: HTMLElement | null = null) {
    const e = ctx.etat;
    // ne déranger que si l'utilisateur a au moins commencé (mode/facture ou step > 0)
    const started2 = e.step > 0 || appeler('resolveMonthlyBill') != null || e.capturePin != null;
    if (!started2) return;
    // WB30 — pas de beacon « abandonné » avant l'étape de consentement.
    if (!e.submitted && !e.funnelAbandonSent && appeler('hasReachedConsentStep')) {
      e.funnelAbandonSent = true;
      // COUPE FONDATEUR 21/08 — même projection que renderStep(). Vocabulaire figé.
      const currentStep = e.step === 0
        ? 'toit'
        : !e.revealed
          ? 'facture'
          : (e.lastKwc != null ? 'contact' : 'estimation');
      appeler('sendFunnelBeacon', currentStep, 'abandoned');
    }
    showWhatsappOffer(triggerEl);
  }
  function closeExit() {
    if (!exitModal || exitModal.hidden) return;
    exitModal.hidden = true;
    // WJ102 — restaure l'accessibilité AVANT de rendre le focus.
    setBackgroundInert(false);
    const trigger = ctx.etat.exitTriggerEl;
    (trigger && doc.contains(trigger) ? trigger : $(ANCRE_FOCUS[ctx.locale]))?.focus();
    ctx.etat.exitTriggerEl = null;
  }
  // desktop : la souris quitte par le haut
  doc.addEventListener('mouseout', (e) => {
    if (!e.relatedTarget && (e as MouseEvent).clientY <= 0) maybeShowExit();
  });
  // mobile : l'onglet passe en arrière-plan
  doc.addEventListener('visibilitychange', () => {
    if (doc.visibilityState === 'hidden') maybeShowExit();
  });
  $('mt-exit-close')?.addEventListener('click', () => closeExit());
  exitModal?.addEventListener('click', (e) => { if (e.target === exitModal) closeExit(); });

  // WJ33 — clavier : Esc ferme + focus trap (Tab/Shift+Tab restent DANS la modale).
  exitModal?.addEventListener('keydown', (e) => {
    const ke = e as KeyboardEvent;
    if (ke.key === 'Escape') { closeExit(); return; }
    if (ke.key !== 'Tab' || !exitModal) return;
    const focusable = Array.from(
      exitModal.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'),
    ).filter((el) => el.offsetParent !== null || el === doc.activeElement);
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = doc.activeElement as HTMLElement | null;
    if (ke.shiftKey && active === first) {
      ke.preventDefault();
      last.focus();
    } else if (!ke.shiftKey && active === last) {
      ke.preventDefault();
      first.focus();
    }
  });

  // WJ33 — le lien d'abandon est reconstruit à CHAQUE saisie.
  exitPhoneInput?.addEventListener('input', () => {
    const err = $('mt-exit-err');
    if (err) err.hidden = true;
    if (exitWaLink) exitWaLink.href = buildExitWaHref();
  });
  exitWaLink?.addEventListener('click', (e) => {
    const phone = exitPhoneInput?.value.trim() || '';
    const err = $('mt-exit-err');
    if (phone.length < 6) {
      e.preventDefault();
      // WJ63 — suit la langue affichée (bascule FR/عربي en direct).
      if (err) {
        err.textContent = MESSAGES[appeler('langueActive') as Langue].exitPhone;
        err.hidden = false;
      }
      return;
    }
    if (err) err.hidden = true;
  });

  const section: SectionSortie = { buildExitWaHref, showWhatsappOffer, maybeShowExit, closeExit };
  inscrire(ctx, section);
  return section;
}

/** Init finale après réhydratation complète (FR l. 4976-4999). */
export function initialiserEnvoi(ctx: ContexteTunnel): void {
  // Tranche dérivée d'un montant exact restauré (fix « tranche redondante »).
  appelerCrochet(ctx, 'syncBillRangeFromExact');
  // Parcours restauré avec l'estimation DÉJÀ révélée : recalcule le document.
  if (ctx.etat.step === 1 && ctx.etat.revealed) appelerCrochet(ctx, 'computeEstimate');
}

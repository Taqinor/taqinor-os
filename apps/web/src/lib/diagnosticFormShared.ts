/**
 * ENF19 — briques DOM partagées par DiagnosticForm.astro et DiagnosticFormEnriched.astro
 * (une seule copie : jetons de dédoublonnage, marquage aria-invalid, consentement
 * publicitaire, reprise fbclid/UTM, état du wizard, charge utile commune).
 * Aucun libellé ni endpoint ici : chaque composant garde les siens.
 */
import type { DiagnosticState } from './diagnostic';
import { buildClientRef, buildIdempotencyKey } from './lead';

// QJW15 (a) — JETONS DE DÉDOUBLONNAGE, persistés pour la session de saisie.
// `submitBtn.disabled` protège du double-clic, mais PAS d'une resoumission
// après rechargement de page : le CRM se retrouvait alors avec deux lignes et
// aucun signal pour les fusionner. Générés une seule fois puis relus en
// sessionStorage — un rechargement renvoie donc le MÊME couple, exactement
// comme le tunnel /devis/mon-toit. Jamais une clé d'unicité serveur : un
// simple signal de dédoublonnage, borné par les regex de validateOptionalFields.
export function jetonPersistant(cle: string, generer: () => string): string {
  try {
    const existant = sessionStorage.getItem(cle);
    if (existant) return existant;
    const neuf = generer();
    sessionStorage.setItem(cle, neuf);
    return neuf;
  } catch {
    // Stockage indisponible (navigation privée) : un jeton non persistant
    // vaut mieux que pas de jeton du tout — jamais bloquant.
    return generer();
  }
}

// QJW15 (b) — `input[aria-invalid="true"]` était du CSS MORT : le script ne
// posait jamais l'attribut, donc ni bordure d'erreur ni annonce au lecteur
// d'écran. Les clés d'erreur de `validateStep` (et celles du serveur) sont
// exactement les NAMES des champs : on retrouve le contrôle fautif sans table
// de correspondance à maintenir.
const CHAMPS_MARQUABLES = ['billRange', 'roofType', 'city', 'fullName', 'phone', 'consent'];

export function creerMarqueurs(form: HTMLFormElement | null) {
  function marquerChamp(nom: string, invalide: boolean) {
    const el = form?.elements.namedItem(nom);
    if (!(el instanceof HTMLElement)) return;
    if (invalide) el.setAttribute('aria-invalid', 'true');
    else el.removeAttribute('aria-invalid');
  }
  function effacerMarques() {
    for (const nom of CHAMPS_MARQUABLES) marquerChamp(nom, false);
  }
  // La marque tombe dès que le visiteur corrige le champ — jamais une bordure
  // rouge qui reste après la correction.
  for (const evt of ['input', 'change'] as const) {
    form?.addEventListener(evt, (e) => {
      const cible = e.target;
      if (cible instanceof HTMLElement && cible.hasAttribute('aria-invalid')) {
        cible.removeAttribute('aria-invalid');
      }
    });
  }
  return { marquerChamp, effacerMarques };
}

// QJW14 — signal de consentement publicitaire posé par ConsentBanner.astro
// (`tq_consent` ∈ {granted, denied}, absent tant que le visiteur n'a pas
// répondu). Transmis TEL QUEL au serveur, qui ne gate que le beacon Meta
// CAPI : la capture du lead et son envoi au CRM ne dépendent JAMAIS de lui.
// Lecture défensive (mode privé, storage bloqué) → null = « pas de signal ».
export function readAdsConsent(): 'granted' | 'denied' | null {
  try {
    const v = localStorage.getItem('tq_consent');
    return v === 'granted' || v === 'denied' ? v : null;
  } catch {
    return null;
  }
}

// Reprise fbclid + UTM depuis sessionStorage (capture first-touch du Layout)
const TRACK_KEYS = ['fbclid', 'gclid', 'gbraid', 'wbraid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];

/** WAUD30 — fbclid/gclid/utm_* déjà captés (sessionStorage), sans champ DOM :
 *  pour le rappel de /contact, qui n'a pas de formulaire diagnostic. Lecture
 *  défensive ; seules les clés présentes sont rendues. */
export function lireTrackingCapte(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const k of [...TRACK_KEYS, 'landingPath', 'referrerHost']) {
    try {
      const v = sessionStorage.getItem('tq_' + k);
      if (v) out[k] = v;
    } catch {}
  }
  return out;
}

/** WAUD30 — corps du rappel rapide de /contact (une seule source, testée) :
 *  tracking + eventId (dédoublonnage Lead pixel ↔ CAPI) + adsConsent seulement
 *  s'ils existent — jamais un champ fabriqué. */
export function corpsRappel(
  saisie: { fullName: string; phone: string; consent: boolean; websiteUrl: string },
  adsConsent: 'granted' | 'denied' | null,
  tracking: Record<string, string>,
  eventId: string,
  langue?: string,
): Record<string, unknown> {
  return {
    fullName: saisie.fullName,
    phone: saisie.phone,
    consent: saisie.consent,
    website_url: saisie.websiteUrl,
    whatsappOptIn: false,
    quickCallback: true,
    contactPreference: 'phone_ok',
    ...tracking,
    eventId,
    ...(adsConsent ? { adsConsent } : {}),
    // WAUD81 — le rappel EN/AR dit sa langue ; le FR n'envoie rien (inchangé).
    ...(langue ? { langue_preferee: langue } : {}),
  };
}

export function reprendreTracking(form: HTMLFormElement | null) {
  for (const k of TRACK_KEYS) {
    const input = form?.elements.namedItem(k) as HTMLInputElement | null;
    if (input) {
      try {
        input.value = sessionStorage.getItem('tq_' + k) ?? '';
      } catch {}
    }
  }
}

export function lireEtat(form: HTMLFormElement): DiagnosticState {
  const fd = new FormData(form);
  return {
    billRange: String(fd.get('billRange') ?? ''),
    roofType: String(fd.get('roofType') ?? ''),
    city: String(fd.get('city') ?? ''),
    fullName: String(fd.get('fullName') ?? ''),
    phone: String(fd.get('phone') ?? ''),
    consent: fd.get('consent') === 'on',
  };
}

/** Charge utile commune (champs de base, tracking, consentement pub, jetons, honeypot). */
export function chargeUtileCommune(fd: FormData): Record<string, unknown> {
  const payload: Record<string, unknown> = {
    fullName: fd.get('fullName'),
    phone: fd.get('phone'),
    whatsappOptIn: fd.get('whatsappOptIn') === 'on',
    city: fd.get('city'),
    roofType: fd.get('roofType'),
    billRange: fd.get('billRange'),
    consent: fd.get('consent') === 'on',
  };
  for (const k of TRACK_KEYS) {
    const v = String(fd.get(k) ?? '');
    if (v) payload[k] = v;
  }
  // QJW14 — joint uniquement si le visiteur a RÉPONDU à la bannière ; sans
  // réponse, aucun champ n'est fabriqué et le serveur garde son comportement.
  const adsConsent = readAdsConsent();
  if (adsConsent) payload.adsConsent = adsConsent;
  // QJW15 (a) — jetons de dédoublonnage (stables sur toute la session de
  // saisie, donc identiques après un rechargement + resoumission).
  payload.idempotencyKey = jetonPersistant('tq_diag_idempotency', buildIdempotencyKey);
  payload.clientRef = jetonPersistant('tq_diag_client_ref', buildClientRef);
  // QJW15 (c) — le honeypot part TEL QUEL (vide pour un humain) : c'est ce
  // que `isHoneypotTripped` juge côté serveur.
  payload.website_url = String(fd.get('website_url') ?? '');
  return payload;
}

/** Éléments DOM communs des deux variantes du formulaire diagnostic. */
export function lireElements() {
  const el = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T | null;
  return {
    form: el<HTMLFormElement>('lead-form'),
    success: el('lf-success')!,
    kwcEl: el('lf-kwc')!,
    roiEl: el('lf-roi')!,
    waEl: el<HTMLAnchorElement>('lf-wa')!,
    errEl: el('lf-err')!,
    phoneErr: el('lf-phone-err')!,
    submitBtn: el<HTMLButtonElement>('lf-submit')!,
    nextBtn: el<HTMLButtonElement>('diag-next')!,
    backBtn: el<HTMLButtonElement>('diag-back')!,
    progressEl: el('diag-progress')!,
    sunEl: el('diag-sun')!,
    // W191 — spinner (null-safe)
    spinnerEl: el('lf-spinner'),
    submitLabelEl: el('lf-submit-label'),
  };
}

/** Affiche le fieldset de l'étape courante et allume les segments <= étape. */
export function afficherEtape(form: HTMLFormElement, step: number, segOn: string, segOff: string) {
  for (const fs of form.querySelectorAll<HTMLFieldSetElement>('fieldset[data-step]')) {
    const visible = Number(fs.dataset.step) === step;
    fs.classList.toggle('hidden', !visible);
    fs.classList.toggle('flex', visible);
  }
  document.querySelectorAll<HTMLElement>('[data-seg]').forEach((seg) => {
    const on = Number(seg.dataset.seg) <= step;
    seg.classList.toggle(segOn, on);
    seg.classList.toggle(segOff, !on);
  });
}

/** Boutons de navigation, message d'erreur et focus pour l'étape courante. */
export function majNavigation(
  form: HTMLFormElement,
  step: number,
  els: { backBtn: HTMLElement; nextBtn: HTMLElement; submitBtn: HTMLElement; errEl: HTMLElement },
  focusActive: boolean,
) {
  els.backBtn.classList.toggle('invisible', step === 1);
  els.nextBtn.classList.toggle('hidden', step === 3);
  els.submitBtn.classList.toggle('hidden', step !== 3);
  els.errEl.classList.add('hidden');
  if (focusActive) {
    form
      .querySelector<HTMLElement>(`fieldset[data-step="${step}"] select, fieldset[data-step="${step}"] input`)
      ?.focus();
  }
}

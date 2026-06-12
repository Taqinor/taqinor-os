/**
 * Logique du « Diagnostic solaire » en 3 étapes — pur restaging UI du
 * formulaire de lead : la validation serveur, la capture fbclid/UTM, le
 * seuil 1 000 MAD et la simulation restent dans lead.ts / billRange.ts,
 * strictement inchangés. Ce module ne gère QUE la progression côté client,
 * testée unitairement (y compris abandon en cours de parcours).
 */
import { isBillRangeId } from './billRange';
import { ROOF_TYPES } from './lead';
import { normalizeMoroccanPhone } from './phone';

export const DIAGNOSTIC_STEPS = 3 as const;

export interface DiagnosticState {
  billRange: string;
  roofType: string;
  city: string;
  fullName: string;
  phone: string;
  consent: boolean;
}

export type StepResult = { ok: true } | { ok: false; errors: Record<string, string> };

/** Validation d'une étape — mêmes règles que la validation serveur. */
export function validateStep(step: 1 | 2 | 3, s: DiagnosticState): StepResult {
  const errors: Record<string, string> = {};
  if (step === 1) {
    if (!isBillRangeId(s.billRange)) errors.billRange = 'Choisissez votre tranche de facture';
    if (!ROOF_TYPES.some((r) => r.id === s.roofType)) errors.roofType = 'Choisissez votre type de toiture';
  } else if (step === 2) {
    if (s.city.trim().length < 2) errors.city = 'Indiquez votre ville ou commune';
  } else {
    if (s.fullName.trim().length < 2) errors.fullName = 'Indiquez votre nom complet';
    if (!normalizeMoroccanPhone(s.phone).ok) errors.phone = 'Numéro de téléphone marocain invalide';
    if (s.consent !== true) errors.consent = 'Le consentement est requis pour recevoir votre étude';
  }
  return Object.keys(errors).length ? { ok: false, errors } : { ok: true };
}

/** Soumission possible uniquement si les 3 étapes sont valides —
 * un parcours abandonné (état partiel) ne soumet jamais rien. */
export function canSubmit(s: DiagnosticState): boolean {
  return ([1, 2, 3] as const).every((step) => validateStep(step, s).ok);
}

/** Étape suivante atteignable (ne saute jamais une étape invalide). */
export function nextStep(current: 1 | 2 | 3, s: DiagnosticState): 1 | 2 | 3 {
  if (current < 3 && validateStep(current, s).ok) return (current + 1) as 2 | 3;
  return current;
}

export function progressLabel(step: 1 | 2 | 3): string {
  return `Étape ${step} sur ${DIAGNOSTIC_STEPS}`;
}

/**
 * Signal préliminaire en direct à l'étape 2 — ordre de grandeur
 * d'ensoleillement, jamais une promesse de production. Le Maroc reçoit
 * globalement 2 800 à 3 400 h de soleil par an.
 */
const SUN_TIERS: Array<{ cities: string[]; label: string }> = [
  {
    cities: ['ouarzazate', 'errachidia', 'agadir', 'marrakech', 'laayoune', 'laâyoune', 'dakhla', 'guelmim'],
    label: 'Ensoleillement exceptionnel — parmi les plus élevés du Maroc (≈ 3 200 h/an)',
  },
  {
    cities: ['casablanca', 'rabat', 'sale', 'salé', 'tanger', 'tetouan', 'tétouan', 'kenitra', 'kénitra', 'mohammedia', 'el jadida'],
    label: 'Ensoleillement excellent — littoral atlantique (≈ 3 000 h/an)',
  },
];

export function sunshineSignal(city: string): string {
  const c = city
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
  if (c.length < 2) return '';
  for (const tier of SUN_TIERS) {
    if (tier.cities.some((t) => c.includes(t.normalize('NFD').replace(/[̀-ͯ]/g, '')))) {
      return tier.label;
    }
  }
  return 'Ensoleillement excellent — le Maroc reçoit 2 800 à 3 400 h de soleil par an';
}

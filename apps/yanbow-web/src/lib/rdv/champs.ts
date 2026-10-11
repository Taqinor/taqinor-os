/**
 * Registre des champs du formulaire « Prendre rendez-vous » (YBW53) — SOURCE
 * UNIQUE côté site.
 *
 * Il reproduit, clé pour clé, le contrat partagé avec l'ERP
 * (`src/contract_samples/demande_rdv_site.json`, jumeau JSON-égal de
 * `backend/django_core/apps/crm/contract_samples/demande_rdv_site.json`,
 * YBW50) : mêmes clés, types, longueurs maximales, caractère obligatoire et
 * valeurs permises (`tests/rdvContrat.test.ts`). Le formulaire (YBW55), la
 * validation du proxy (YBW54) et la page Confidentialité (YBW27, « données
 * collectées ») lisent CE registre — jamais une liste écrite ailleurs.
 *
 * Aucun champ sensible : jamais de numéro d'identité (CIN), de santé ni
 * d'opinion ; une aide sous le message le rappelle au visiteur. Aucune IP ni
 * agent utilisateur n'est collecté (contrat : `jamais_transmis`).
 */
import type { Locale } from '../../i18n/config';
import { VALEURS_PRODUIT } from '../brand';

export type TypeChamp = 'uuid' | 'texte' | 'email' | 'enum' | 'booleen' | 'date-heure' | 'chemin';

/** Texte dans les deux langues — une langue manquante = `npm run check` rouge. */
export type Texte = Record<Locale, string>;

export interface Champ {
  type: TypeChamp;
  obligatoire: boolean;
  /** Longueur maximale (caractères), si le contrat en fixe une. */
  max?: number;
  /** Valeurs permises (champ `enum`). */
  valeurs?: readonly string[];
  /**
   * `true` = saisi par le visiteur dans le formulaire ; `false` = posé par le
   * site lui-même (clé d'idempotence, langue de la page, date du
   * consentement, page, paramètres de campagne de l'adresse).
   */
  saisi: boolean;
  /** Ce que la donnée est (page Confidentialité). */
  donnee: Texte;
  /** Pourquoi elle est collectée (page Confidentialité). */
  finalite: Texte;
}

const UTM_FINALITE: Texte = {
  fr: "Savoir quelle campagne ou quel lien vous a amené, seulement si l’adresse de la page en contient.",
  en: 'Know which campaign or link brought you here, only if the page address contains one.',
};

function utm(nom: string): Champ {
  return {
    type: 'texte',
    obligatoire: false,
    max: 300,
    saisi: false,
    donnee: { fr: `Paramètre de campagne « ${nom} »`, en: `Campaign parameter “${nom}”` },
    finalite: UTM_FINALITE,
  };
}

/** Les champs du contrat, dans l'ordre du contrat. */
export const CHAMPS = {
  idempotency_key: {
    type: 'uuid',
    obligatoire: true,
    max: 36,
    saisi: false,
    donnee: { fr: 'Identifiant technique aléatoire de la demande', en: 'Random technical identifier of the request' },
    finalite: {
      fr: "Éviter qu’une même demande soit enregistrée deux fois.",
      en: 'Avoid recording the same request twice.',
    },
  },
  nom: {
    type: 'texte',
    obligatoire: true,
    max: 120,
    saisi: true,
    donnee: { fr: 'Nom', en: 'Name' },
    finalite: { fr: 'Savoir à qui répondre.', en: 'Know whom to answer.' },
  },
  societe: {
    type: 'texte',
    obligatoire: true,
    max: 160,
    saisi: true,
    donnee: { fr: 'Société', en: 'Company' },
    finalite: {
      fr: 'Préparer le rendez-vous avec le contexte de votre entreprise.',
      en: "Prepare the meeting with your company's context.",
    },
  },
  email: {
    type: 'email',
    obligatoire: true,
    max: 254,
    saisi: true,
    donnee: { fr: 'Adresse e-mail', en: 'Email address' },
    finalite: { fr: 'Vous répondre.', en: 'Answer you.' },
  },
  telephone: {
    type: 'texte',
    obligatoire: false,
    max: 30,
    saisi: true,
    donnee: { fr: 'Téléphone (facultatif)', en: 'Phone (optional)' },
    finalite: { fr: 'Vous rappeler, si vous le souhaitez.', en: 'Call you back, if you wish.' },
  },
  produit: {
    type: 'enum',
    obligatoire: true,
    valeurs: VALEURS_PRODUIT,
    saisi: true,
    donnee: { fr: 'Sujet du rendez-vous', en: 'Meeting topic' },
    finalite: {
      fr: 'Orienter la demande vers la bonne personne.',
      en: 'Route the request to the right person.',
    },
  },
  message: {
    type: 'texte',
    obligatoire: false,
    max: 2000,
    saisi: true,
    donnee: { fr: 'Message (facultatif)', en: 'Message (optional)' },
    finalite: { fr: 'Comprendre votre besoin avant le rendez-vous.', en: 'Understand your need before the meeting.' },
  },
  langue: {
    type: 'enum',
    obligatoire: true,
    valeurs: ['fr', 'en'],
    saisi: false,
    donnee: { fr: 'Langue de la page', en: 'Page language' },
    finalite: { fr: 'Vous répondre dans votre langue.', en: 'Answer you in your language.' },
  },
  consentement: {
    type: 'booleen',
    obligatoire: true,
    saisi: true,
    donnee: { fr: 'Votre accord', en: 'Your consent' },
    finalite: {
      fr: "Garder la preuve que vous avez accepté l’envoi de votre demande.",
      en: 'Keep proof that you agreed to send your request.',
    },
  },
  consentement_le: {
    type: 'date-heure',
    obligatoire: true,
    saisi: false,
    donnee: { fr: 'Date et heure de votre accord', en: 'Date and time of your consent' },
    finalite: { fr: 'Dater cette preuve.', en: 'Date that proof.' },
  },
  page: {
    type: 'chemin',
    obligatoire: false,
    max: 200,
    saisi: false,
    donnee: { fr: 'Page du site depuis laquelle la demande est envoyée', en: 'Site page the request is sent from' },
    finalite: { fr: 'Savoir quelle page vous a conduit à la demande.', en: 'Know which page led you to the request.' },
  },
  utm_source: utm('utm_source'),
  utm_medium: utm('utm_medium'),
  utm_campaign: utm('utm_campaign'),
  utm_term: utm('utm_term'),
  utm_content: utm('utm_content'),
} as const satisfies Record<string, Champ>;

export type CleChamp = keyof typeof CHAMPS;

export const CLES_CHAMPS = Object.keys(CHAMPS) as CleChamp[];

/** Clés que le site n'envoie JAMAIS (l'ERP les refuse : 400). */
export const CLES_REFUSEES = ['company', 'company_id', 'societe_id'] as const;

/**
 * Pot de miel : champ invisible (motif CLIP) qu'un humain laisse vide. Il
 * n'appartient PAS au contrat et n'est jamais transmis à l'ERP.
 */
export const POT_DE_MIEL = 'site_internet';

/** Aide affichée sous le message (aucune donnée sensible). */
export const AIDE_MESSAGE: Texte = {
  fr: "N’indiquez aucune donnée sensible (santé, opinions, numéro d’identité…).",
  en: 'Do not include any sensitive data (health, opinions, identity number…).',
};

// ── Normalisation + validation (YBW54 côté serveur, YBW55 côté navigateur) ──

/** Codes d'erreur par champ (jamais la valeur reçue). */
export type CodeErreur = 'obligatoire' | 'trop_long' | 'format' | 'valeur';

/** Messages d'erreur, dans la langue de la page. */
export const MESSAGES_ERREUR: Record<Locale, Record<CodeErreur, string> & { consentement: string }> = {
  fr: {
    obligatoire: 'Ce champ est obligatoire.',
    trop_long: 'Ce texte est trop long.',
    format: "Cette adresse e-mail n’est pas complète (exemple : nom@entreprise.fr).",
    valeur: 'Choisissez une option de la liste.',
    consentement: "Cochez la case pour accepter l’envoi de votre demande.",
  },
  en: {
    obligatoire: 'This field is required.',
    trop_long: 'This text is too long.',
    format: 'This email address is incomplete (example: name@company.com).',
    valeur: 'Choose an option from the list.',
    consentement: 'Tick the box to agree to send your request.',
  },
};

/** Message d'un code pour un champ (le consentement a le sien). */
export function messageErreur(cle: CleChamp, code: CodeErreur, locale: Locale): string {
  const m = MESSAGES_ERREUR[locale];
  return cle === 'consentement' ? m.consentement : m[code];
}

/** Corps transmis à l'ERP : SEULES les clés du registre. */
export type CorpsDemande = Partial<Record<CleChamp, string | boolean>>;

export interface ResultatValidation {
  langue: Locale;
  corps: CorpsDemande;
  erreurs: Partial<Record<CleChamp, CodeErreur>>;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
// Proche de `django.core.validators.EmailValidator` (partie locale « dot-atom »,
// domaine en étiquettes, extension d'au moins deux caractères).
const LOCAL = /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$/;
const DOMAINE = /^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z0-9-]{2,63}$/;

/** Vrai si `email` passera la validation de l'ERP (forme, pas existence). */
export function emailValide(email: string): boolean {
  const at = email.lastIndexOf('@');
  if (at <= 0) return false;
  const domaine = email.slice(at + 1);
  return LOCAL.test(email.slice(0, at)) && DOMAINE.test(domaine) && !domaine.endsWith('-');
}

const ligne = (v: unknown) => (typeof v === 'string' ? v.normalize('NFC').replace(/\s+/g, ' ').trim() : '');
const bloc = (v: unknown) =>
  typeof v === 'string' ? v.normalize('NFC').replace(/\r\n?/g, '\n').replace(/\n{3,}/g, '\n\n').trim() : '';

/** Chemin seul (sans origine, requête ni fragment), borné. */
function chemin(v: unknown, max: number): string {
  if (typeof v !== 'string' || !v.startsWith('/')) return '';
  try {
    return new URL(v, 'https://x.invalid').pathname.slice(0, max);
  } catch {
    return '';
  }
}

/** Date ISO 8601 UTC à la seconde (`2026-10-07T09:00:00Z`). */
export function isoSeconde(d: Date): string {
  return d.toISOString().replace(/\.\d{3}Z$/, 'Z');
}

/**
 * Normalise puis valide une demande brute. Les valeurs sont NORMALISÉES
 * (espaces, casse de l'e-mail), jamais refusées pour leur mise en forme ; seuls
 * un champ obligatoire vide, un texte trop long, un e-mail incomplet, une
 * option hors liste ou un consentement non coché produisent une erreur. Les
 * champs posés par le site (langue, page, campagne) sont bornés, jamais
 * refusés. `consentement_le` est posé ICI (heure du serveur), jamais repris du
 * navigateur. Aucune clé hors registre ne passe.
 */
export function normaliserDemande(brut: Record<string, unknown>, maintenant: Date, nouvelleCle: () => string): ResultatValidation {
  const erreurs: ResultatValidation['erreurs'] = {};
  const langue: Locale = brut.langue === 'en' ? 'en' : 'fr';
  const corps: CorpsDemande = {};

  const idem = ligne(brut.idempotency_key).toLowerCase();
  corps.idempotency_key = UUID.test(idem) ? idem : nouvelleCle();

  const saisi = (cle: 'nom' | 'societe' | 'email' | 'telephone' | 'message', valeur: string) => {
    const c: Champ = CHAMPS[cle];
    if (!valeur) {
      if (c.obligatoire) erreurs[cle] = 'obligatoire';
      return;
    }
    if (c.max !== undefined && valeur.length > c.max) {
      erreurs[cle] = 'trop_long';
      return;
    }
    corps[cle] = valeur;
  };
  saisi('nom', ligne(brut.nom));
  saisi('societe', ligne(brut.societe));
  const email = ligne(brut.email).replace(/\s+/g, '').toLowerCase();
  saisi('email', email);
  if (corps.email !== undefined && !emailValide(email)) {
    delete corps.email;
    erreurs.email = 'format';
  }
  saisi('telephone', ligne(brut.telephone));

  if (typeof brut.produit === 'string' && (CHAMPS.produit.valeurs as readonly string[]).includes(brut.produit)) {
    corps.produit = brut.produit;
  } else {
    erreurs.produit = brut.produit === undefined || brut.produit === '' ? 'obligatoire' : 'valeur';
  }

  saisi('message', bloc(brut.message));
  corps.langue = langue;

  if (brut.consentement === true) {
    corps.consentement = true;
    corps.consentement_le = isoSeconde(maintenant);
  } else {
    erreurs.consentement = 'obligatoire';
  }

  const page = chemin(brut.page, CHAMPS.page.max);
  if (page) corps.page = page;
  for (const cle of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'] as const) {
    const v = ligne(brut[cle]).slice(0, CHAMPS[cle].max);
    if (v) corps[cle] = v;
  }

  // Ordre du registre (= ordre du contrat) : corps déterministe, signé tel quel.
  const ordonne: CorpsDemande = {};
  for (const cle of CLES_CHAMPS) if (corps[cle] !== undefined) ordonne[cle] = corps[cle];
  return { langue, corps: ordonne, erreurs };
}

/** Champs collectés, dans l'ordre, pour la page Confidentialité. */
export function donneesCollectees(locale: Locale): { cle: CleChamp; donnee: string; finalite: string; obligatoire: boolean }[] {
  return CLES_CHAMPS.map((cle) => {
    const c: Champ = CHAMPS[cle];
    return { cle, donnee: c.donnee[locale], finalite: c.finalite[locale], obligatoire: c.obligatoire };
  });
}

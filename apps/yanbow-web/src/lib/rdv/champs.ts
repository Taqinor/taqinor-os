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
  fr: "Savoir quelle campagne ou quel lien vous a amené, seulement si l'adresse de la page en contient.",
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
      fr: "Éviter qu'une même demande soit enregistrée deux fois.",
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
      fr: "Garder la preuve que vous avez accepté l'envoi de votre demande.",
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
  fr: "N'indiquez aucune donnée sensible (santé, opinions, numéro d'identité…).",
  en: 'Do not include any sensitive data (health, opinions, identity number…).',
};

/** Champs collectés, dans l'ordre, pour la page Confidentialité. */
export function donneesCollectees(locale: Locale): { cle: CleChamp; donnee: string; finalite: string; obligatoire: boolean }[] {
  return CLES_CHAMPS.map((cle) => {
    const c: Champ = CHAMPS[cle];
    return { cle, donnee: c.donnee[locale], finalite: c.finalite[locale], obligatoire: c.obligatoire };
  });
}

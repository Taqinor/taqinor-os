/**
 * Registre des sous-traitants et hôtes tiers (YBW11, rempli par YBW26).
 *
 * La Content-Security-Policy du Worker (worker/headers.mjs) est CONSTRUITE à
 * partir de ce registre : un hôte tiers n'est autorisé par la CSP que s'il y a
 * une entrée ici. Registre VIDE au départ = CSP `'self'` seulement.
 */

/** Directives CSP qu'un sous-traitant peut ouvrir. */
export type DirectiveCsp = 'connect-src' | 'img-src' | 'script-src' | 'frame-src' | 'form-action' | 'font-src' | 'style-src';

export interface SousTraitant {
  /** Identifiant stable (ex. « cloudflare »). */
  id: string;
  /** Nom affiché sur la page Confidentialité. */
  nom: string;
  /** Rôle / finalité, en français. */
  role: string;
  /** Rôle / finalité, en anglais (page Confidentialité EN). */
  roleEn?: string;
  /** Pays où les données sont traitées (codes ISO 3166-1 alpha-2), si connu. */
  pays?: string[];
  /** Quand des données du visiteur lui parviennent, en français / anglais. */
  quand?: { fr: string; en: string };
  /** Données concernées (en clair : « journaux techniques », « formulaire de rendez-vous »). */
  donnees?: string[];
  /** Durée de conservation en jours, si ce sous-traitant STOCKE des données du formulaire. */
  dureeJours?: number | null;
  /** Hôtes (origines https://…) ouverts dans la CSP, par directive. */
  csp: Partial<Record<DirectiveCsp, string[]>>;
}

/**
 * Stockage de reprise KV des demandes non livrées (YBW54) : il n'existe QUE si
 * Reda crée l'espace KV (YBWM3). Tant qu'il n'existe pas, `null` : aucune
 * entrée au registre, rien n'est stocké. S'il est créé, poser ici sa durée.
 */
export const KV_REPRISE_DUREE_JOURS: number | null = null;

/** Entrée KV, ajoutée au registre seulement si l'espace existe. */
function entreeKv(dureeJours: number): SousTraitant {
  return {
    id: 'cloudflare-kv',
    nom: 'Cloudflare KV',
    role: "Reprise des demandes de rendez-vous non livrées à l'ERP.",
    roleEn: 'Retry storage for meeting requests not yet delivered to the ERP.',
    quand: { fr: "Seulement si l'ERP ne répond pas à l'envoi.", en: 'Only if the ERP does not answer on submission.' },
    donnees: ['formulaire de rendez-vous'],
    dureeJours,
    csp: {},
  };
}

/**
 * Registre RÉEL (YBW26 — faits du plan du 06/10/2026, `docs/DATA_FLOWS.md`).
 * Aucun de ces sous-traitants n'ouvre d'hôte tiers dans la CSP : le site est
 * servi par le Worker (même origine), le formulaire est relayé côté SERVEUR par
 * le Worker vers l'ERP (le navigateur ne le contacte jamais), et le lien
 * WhatsApp est une simple navigation au clic (aucune requête avant).
 */
export const SOUS_TRAITANTS: SousTraitant[] = [
  {
    id: 'cloudflare',
    nom: 'Cloudflare',
    role: 'Hébergement du site, exécution du Worker (relais du formulaire) et journaux techniques.',
    roleEn: 'Website hosting, Worker execution (form relay) and technical logs.',
    quand: { fr: 'À chaque visite.', en: 'On every visit.' },
    donnees: ['journaux techniques'],
    dureeJours: null,
    csp: {},
  },
  {
    id: 'serveur-erp',
    nom: "Serveur de l'ERP",
    role: "Réception et traitement de la demande de rendez-vous dans l'ERP de la société.",
    roleEn: "Receipt and handling of the meeting request in the company's ERP.",
    pays: ['DE'],
    quand: { fr: "À l'envoi du formulaire de rendez-vous.", en: 'When the meeting form is submitted.' },
    donnees: ['formulaire de rendez-vous'],
    dureeJours: null,
    csp: {},
  },
  {
    id: 'whatsapp',
    nom: 'WhatsApp (Meta)',
    role: 'Conversation WhatsApp, seulement si le visiteur clique sur le lien WhatsApp.',
    roleEn: 'WhatsApp conversation, only if the visitor clicks the WhatsApp link.',
    quand: { fr: 'Seulement au clic sur le lien WhatsApp (aucune donnée avant).', en: 'Only when the WhatsApp link is clicked (no data before).' },
    donnees: [],
    dureeJours: null,
    csp: {},
  },
  ...(KV_REPRISE_DUREE_JOURS === null ? [] : [entreeKv(KV_REPRISE_DUREE_JOURS)]),
];

/** Valeurs CSP qui ne sont pas des hôtes tiers. */
const MOTS_CLES_CSP = new Set(["'self'", "'none'", "'unsafe-inline'", 'data:', 'blob:']);

/**
 * Hôtes présents dans une CSP (valeur d'en-tête) mais ABSENTS du registre :
 * doit toujours être vide (garde YBW26).
 */
export function hotesHorsRegistre(csp: string, registre: readonly SousTraitant[] = SOUS_TRAITANTS): string[] {
  const connus = new Set(Object.values(sourcesCsp(registre)).flatMap((l) => l ?? []));
  const out: string[] = [];
  for (const directive of csp.split(';')) {
    const valeurs = directive.trim().split(/\s+/).slice(1);
    for (const v of valeurs) if (v && !MOTS_CLES_CSP.has(v) && !connus.has(v) && !out.includes(v)) out.push(v);
  }
  return out;
}

/** Hôtes à ajouter à chaque directive CSP, dédoublonnés, dans l'ordre du registre. */
export function sourcesCsp(registre: readonly SousTraitant[] = SOUS_TRAITANTS): Partial<Record<DirectiveCsp, string[]>> {
  const out: Partial<Record<DirectiveCsp, string[]>> = {};
  for (const st of registre) {
    for (const [directive, hotes] of Object.entries(st.csp) as [DirectiveCsp, string[]][]) {
      const liste = (out[directive] ??= []);
      for (const h of hotes) if (!liste.includes(h)) liste.push(h);
    }
  }
  return out;
}

/**
 * Identités légales du site (YBW25) — SOURCE UNIQUE, DEUX entités.
 *
 * - `editeur` : la société britannique (Ltd, À CRÉER — YBWM5) qui publie le site.
 * - `maroc` : la SARLAU marocaine (nom à choisir — YBWM6) qui signe et facture
 *   les clients marocains.
 *
 * RÈGLE : chaque champ reste `null` tant que Reda ne l'a pas fourni. Rien n'est
 * affiché pour une entité qui n'existe pas : un bloc n'est rendu que s'il est
 * COMPLET (tous ses champs requis non nuls). Avant l'immatriculation, aucune
 * page ne doit dire ni laisser croire que la société existe (« Ltd »,
 * « SARL », numéro) — Companies Act 2006 s.51. Règles et sources :
 * `LEGAL_RULES.md`. Jamais de valeur inventée, jamais de valeur reprise de
 * l'entreprise d'installation.
 */
import type { Locale } from '../i18n/config';
import { MARQUE } from './brand';

/** Partie du Royaume-Uni où la société est immatriculée (Regs 2015 reg. 25). */
export type PartieRoyaumeUni = 'angleterre_galles' | 'ecosse' | 'irlande_du_nord';

export interface EditeurUk {
  /** Nom EXACT tel qu'immatriculé (ex. « … Ltd »). */
  nomExact: string | null;
  partie: PartieRoyaumeUni | null;
  /** Numéro d'immatriculation (Companies House). */
  numero: string | null;
  /** Adresse du siège (registered office). */
  siege: string | null;
  /** Numéro de TVA — seulement s'il existe (facultatif pour la complétude). */
  tva: string | null;
}

export interface SocieteMaroc {
  denomination: string | null;
  /** Capital social, tel que rédigé dans les statuts (texte, aucune devise ajoutée par le code). */
  capital: string | null;
  siege: string | null;
  rc: string | null;
  ice: string | null;
  identifiantFiscal: string | null;
  gerant: string | null;
}

/** Valeur relevée à la main, avec sa source (jamais téléchargée au build). */
export interface ValeurSourcee<T> {
  valeur: T | null;
  urlSource: string | null;
  /** Date de lecture, AAAA-MM-JJ. */
  dateLecture: string | null;
}

export interface Hebergeur {
  nom: string;
  adresse: string;
  telephone: string;
}

/** Entité responsable du traitement du formulaire (YBWM8). */
export type Responsable = 'editeur' | 'maroc';

export interface Commun {
  email: string | null;
  telephone: string | null;
  directeurPublication: string | null;
  /** Relevé sur la page légale de Cloudflare et confirmé par Reda (YBWM8). */
  hebergeur: ValeurSourcee<Hebergeur>;
  /** Récépissés de déclaration CNDP (numéros) — vide/null tant qu'aucun. */
  recepissesCndp: string[] | null;
  /** Représentant UE (RGPD art. 27) — seulement s'il est désigné. */
  representantUe: string | null;
  responsableTraitement: Responsable | null;
}

export interface Legal {
  editeur: EditeurUk;
  maroc: SocieteMaroc;
  commun: Commun;
}

/** Mention obligatoire de forme pour la SARLAU (loi 5-96). */
export const FORME_SARLAU: Record<Locale, string> = {
  fr: "SARL d'associé unique",
  en: "SARL d'associé unique (single-member limited liability company)",
};

const PARTIES: Record<PartieRoyaumeUni, Record<Locale, string>> = {
  angleterre_galles: { fr: 'Angleterre et pays de Galles', en: 'England and Wales' },
  ecosse: { fr: 'Écosse', en: 'Scotland' },
  irlande_du_nord: { fr: 'Irlande du Nord', en: 'Northern Ireland' },
};

/** État RÉEL au 07/10/2026 : aucune entité n'existe, rien n'est fourni. */
export const LEGAL: Legal = {
  editeur: { nomExact: null, partie: null, numero: null, siege: null, tva: null },
  maroc: { denomination: null, capital: null, siege: null, rc: null, ice: null, identifiantFiscal: null, gerant: null },
  commun: {
    email: null,
    telephone: null,
    directeurPublication: null,
    hebergeur: { valeur: null, urlSource: null, dateLecture: null },
    recepissesCndp: null,
    representantUe: null,
    responsableTraitement: null,
  },
};

const plein = (v: string | null | undefined): v is string => typeof v === 'string' && v.trim() !== '';

/** Le bloc éditeur est complet (TVA facultative : seulement si elle existe). */
export function editeurComplet(l: Legal = LEGAL): boolean {
  const e = l.editeur;
  return plein(e.nomExact) && e.partie !== null && plein(e.numero) && plein(e.siege);
}

/** Le bloc SARLAU est complet. */
export function marocComplet(l: Legal = LEGAL): boolean {
  const m = l.maroc;
  return [m.denomination, m.capital, m.siege, m.rc, m.ice, m.identifiantFiscal, m.gerant].every(plein);
}

/** L'hébergeur est relevé ET sourcé ET daté. */
export function hebergeurComplet(l: Legal = LEGAL): boolean {
  const h = l.commun.hebergeur;
  return h.valeur !== null && plein(h.valeur.nom) && plein(h.valeur.adresse) && plein(h.valeur.telephone) && plein(h.urlSource) && plein(h.dateLecture);
}

export interface LigneLegale {
  /** Clé stable (le libellé vient du dictionnaire de la page). */
  cle: string;
  valeur: string;
}

/**
 * Lignes du bloc éditeur à afficher : `[]` tant que le bloc n'est pas complet
 * (jamais un bloc partiel qui laisserait croire que la société existe).
 */
export function lignesEditeur(l: Legal = LEGAL, locale: Locale = 'fr'): LigneLegale[] {
  if (!editeurComplet(l)) return [];
  const e = l.editeur;
  const out: LigneLegale[] = [
    { cle: 'nom', valeur: e.nomExact as string },
    { cle: 'partie', valeur: PARTIES[e.partie as PartieRoyaumeUni][locale] },
    { cle: 'numero', valeur: e.numero as string },
    { cle: 'siege', valeur: e.siege as string },
  ];
  if (plein(e.tva)) out.push({ cle: 'tva', valeur: e.tva });
  return out;
}

/** Lignes du bloc SARLAU : `[]` tant que le bloc n'est pas complet. */
export function lignesMaroc(l: Legal = LEGAL, locale: Locale = 'fr'): LigneLegale[] {
  if (!marocComplet(l)) return [];
  const m = l.maroc;
  return [
    { cle: 'denomination', valeur: m.denomination as string },
    { cle: 'forme', valeur: FORME_SARLAU[locale] },
    { cle: 'capital', valeur: m.capital as string },
    { cle: 'siege', valeur: m.siege as string },
    { cle: 'rc', valeur: m.rc as string },
    { cle: 'ice', valeur: m.ice as string },
    { cle: 'if', valeur: m.identifiantFiscal as string },
    { cle: 'gerant', valeur: m.gerant as string },
  ];
}

/** Lignes communes (LCEN) : seulement les champs fournis. */
export function lignesCommunes(l: Legal = LEGAL): LigneLegale[] {
  const c = l.commun;
  const out: LigneLegale[] = [];
  if (plein(c.email)) out.push({ cle: 'email', valeur: c.email });
  if (plein(c.telephone)) out.push({ cle: 'telephone', valeur: c.telephone });
  if (plein(c.directeurPublication)) out.push({ cle: 'directeurPublication', valeur: c.directeurPublication });
  if (hebergeurComplet(l)) {
    const h = c.hebergeur.valeur as Hebergeur;
    out.push({ cle: 'hebergeur', valeur: `${h.nom}, ${h.adresse}, ${h.telephone}` });
  }
  if (c.recepissesCndp && c.recepissesCndp.some(plein)) out.push({ cle: 'cndp', valeur: c.recepissesCndp.filter(plein).join(', ') });
  if (plein(c.representantUe)) out.push({ cle: 'representantUe', valeur: c.representantUe });
  return out;
}

/**
 * Page Mentions légales publiable (YBW28) : bloc éditeur complet + éléments
 * LCEN (e-mail, directeur de la publication, hébergeur sourcé). Sinon la route
 * n'existe pas (retirée du build, 404 au Worker — porte YBW12).
 */
export function mentionsLegalesCompletes(l: Legal = LEGAL): boolean {
  return editeurComplet(l) && plein(l.commun.email) && plein(l.commun.directeurPublication) && hebergeurComplet(l);
}

/** Routes juridiques déclarées complètes (lues par le build → Worker, YBW12). */
export function routesJuridiquesCompletes(l: Legal = LEGAL): string[] {
  return mentionsLegalesCompletes(l) ? ['/mentions-legales', '/en/legal'] : [];
}

/**
 * Nom du responsable du traitement à afficher : le nom exact de l'entité
 * désignée SI son bloc est complet ; sinon la marque seule (jamais une forme
 * juridique pour une entité qui n'existe pas) ; `null` si non désigné.
 */
export function nomResponsable(l: Legal = LEGAL): string | null {
  const r = l.commun.responsableTraitement;
  if (r === 'editeur' && editeurComplet(l)) return l.editeur.nomExact;
  if (r === 'maroc' && marocComplet(l)) return l.maroc.denomination;
  return r === null ? null : MARQUE;
}

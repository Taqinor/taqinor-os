// RWEB17-M0 — CONTEXTE PARTAGÉ DU TUNNEL « mon-toit » : tout ce qu'une section
// extraite reçoit en un seul argument. Voir l'en-tête de `etat.ts` pour la table
// des sections et l'ordre d'installation.

import type { Dom } from './dom';
import type { EtatPage, LocaleTunnel } from './etat';

/** Configuration propre à une locale ; chaque section la complète de ses
 *  propres tables de locale. */
export interface ConfigLocale {
  locale: LocaleTunnel;
  /** Vrai sur FR et AR (bascule de la langue affichée), faux sur EN. */
  langueBasculable: boolean;
  /** Formatage des nombres : `fr-FR` pour FR et AR, `en-GB` pour EN. */
  formatNombre: (n: number) => string;
}

type Crochet = (...args: any[]) => any;

/** Registre à liaison tardive : une section inscrit ses fonctions appelées par
 *  une AUTRE section ; appeler un crochet absent lève une erreur claire au lieu
 *  d'un `undefined is not a function` (ou d'un TDZ). */
export interface RegistreCrochets {
  /** Inscrit (ou remplace) le crochet `nom`. */
  installer(nom: string, fn: Crochet): void;
  /** Appelle le crochet `nom` ; lève `Crochet non installé : <nom>` s'il manque. */
  appeler(nom: string, ...args: any[]): any;
  /** Vrai si le crochet est installé. */
  a(nom: string): boolean;
}

export function creerCrochets(): RegistreCrochets {
  const table = new Map<string, Crochet>();
  return {
    installer(nom, fn) {
      table.set(nom, fn);
    },
    appeler(nom, ...args) {
      const fn = table.get(nom);
      if (!fn) throw new Error(`Crochet non installé : ${nom}`);
      return fn(...args);
    },
    a(nom) {
      return table.has(nom);
    },
  };
}

export interface ContexteTunnel {
  locale: LocaleTunnel;
  etat: EtatPage;
  dom: Dom;
  crochets: RegistreCrochets;
  config: ConfigLocale;
}

export function creerContexte(dom: Dom, etat: EtatPage, config: ConfigLocale): ContexteTunnel {
  return { locale: config.locale, etat, dom, crochets: creerCrochets(), config };
}

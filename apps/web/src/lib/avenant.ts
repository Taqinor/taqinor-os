/**
 * VNT72 — L'AVENANT sur la page publique /proposition.
 *
 * Une négociation de prix (Groupe VNT) produit une V2 : un AVENANT à la
 * proposition d'origine. Quand l'avenant est accepté en interne, le client le
 * signe par son lien (VNT61) ; `proposal_data` porte alors la clé ADDITIVE
 * `avenant` {a_signer, remplace{reference}, signe_le} — ABSENTE (jamais `null`)
 * sur une proposition qui n'est pas un avenant (contrat
 * `src/contract_samples/proposal_data.json`, VNT2).
 *
 * MODULE PUR, sans DOM, sans dépendance de la page : `lib/proposition.ts` (6 607 l.)
 * n'en reçoit qu'un import + un appel (`lireProposal`), le composant
 * `components/proposition/BandeauAvenant.astro` n'en reçoit que du texte. La page
 * ne calcule RIEN : elle dit ce que le serveur a servi (omission héritée, jamais
 * comblée — pas de référence servie ⇒ le titre n'en invente pas).
 */

/** Un texte servi en trois langues, comme les `data-fr/en/ar` de la page. */
export interface TexteTrilingue {
  fr: string;
  en: string;
  ar: string;
}

/** L'avenant tel que SERVI (`avenant` de `proposal_data`). */
export interface Avenant {
  /** Vrai tant que le client n'a pas signé cet avenant. */
  aSigner: boolean;
  /** Référence de la version que l'avenant remplace (V1), ou `null`. */
  remplaceReference: string | null;
  /** Horodatage ISO de la signature client, `null` tant que non signé. */
  signeLe: string | null;
}

export interface AvenantVue {
  etat: 'a_signer' | 'signe';
  titre: TexteTrilingue;
  corps: TexteTrilingue;
  /** Ce que la page affiche une fois l'avenant signé en direct (sans recharger). */
  confirmation: { titre: TexteTrilingue; corps: TexteTrilingue };
}

function texteOuNull(v: unknown): string | null {
  return typeof v === 'string' && v.trim() !== '' ? v.trim() : null;
}

/**
 * Lit le bloc `avenant` de la charge utile (la valeur de la clé, pas le
 * document). Clé absente ou illisible ⇒ `null` : aucune proposition-avenant.
 */
export function lireAvenant(brut: unknown): Avenant | null {
  if (!brut || typeof brut !== 'object' || Array.isArray(brut)) return null;
  const a = brut as Record<string, unknown>;
  const remplace = a.remplace && typeof a.remplace === 'object' && !Array.isArray(a.remplace)
    ? (a.remplace as Record<string, unknown>)
    : null;
  return {
    aSigner: a.a_signer === true,
    remplaceReference: texteOuNull(remplace?.reference),
    signeLe: texteOuNull(a.signe_le),
  };
}

const LOCALES = { fr: 'fr-FR', en: 'en-GB', ar: 'ar-MA-u-nu-latn' } as const;

/** « 12 octobre 2026 » dans la langue demandée, ou `null` si la date est illisible. */
function dateLongue(iso: string | null, lang: keyof typeof LOCALES): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  try {
    return new Intl.DateTimeFormat(LOCALES[lang], {
      day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Africa/Casablanca',
    }).format(d);
  } catch {
    return null;
  }
}

function confirmation(ref: string | null, signeLe: string | null) {
  const f = dateLongue(signeLe, 'fr');
  const e = dateLongue(signeLe, 'en');
  const r = dateLongue(signeLe, 'ar');
  const suite = {
    fr: 'Merci de votre confiance — votre conseiller Taqinor revient vers vous.',
    en: 'Thank you for your trust — your Taqinor advisor will be in touch.',
    ar: 'شكراً على ثقتكم — سيتواصل معكم مستشار تاقينور قريباً.',
  };
  return {
    titre: { fr: 'Avenant signé ✓', en: 'Amendment signed ✓', ar: 'تم توقيع الملحق ✓' },
    corps: {
      fr: `${ref ? `L’avenant à ${ref}` : 'Cet avenant'} a été signé${f ? ` le ${f}` : ''}. ${suite.fr}`,
      en: `${ref ? `The amendment to ${ref}` : 'This amendment'} was signed${e ? ` on ${e}` : ''}. ${suite.en}`,
      ar: `${ref ? `الملحق الخاص بالعرض ${ref}` : 'هذا الملحق'} تم توقيعه${r ? ` بتاريخ ${r}` : ''}. ${suite.ar}`,
    },
  };
}

/**
 * Le texte du bandeau, ou `null` quand il n'y a rien à dire (avenant ni à
 * signer ni signé — jamais un bloc vide).
 */
export function avenantVue(av: Avenant | null): AvenantVue | null {
  if (!av) return null;
  const ref = av.remplaceReference;
  const conf = confirmation(ref, av.signeLe);
  if (av.aSigner) {
    return {
      etat: 'a_signer',
      titre: {
        fr: ref ? `Avenant à ${ref} — nouveau prix` : 'Avenant — nouveau prix',
        en: ref ? `Amendment to ${ref} — new price` : 'Amendment — new price',
        ar: ref ? `ملحق للعرض ${ref} — سعر جديد` : 'ملحق — سعر جديد',
      },
      corps: {
        fr: 'Ce document reprend le nouveau prix convenu avec votre conseiller Taqinor. Relisez-le puis signez cet avenant ci-dessous pour le confirmer.',
        en: 'This document reflects the new price agreed with your Taqinor advisor. Please review it, then sign this amendment below to confirm it.',
        ar: 'تتضمن هذه الوثيقة السعر الجديد المتفق عليه مع مستشاركم في تاقينور. اطلعوا عليها ثم وقّعوا هذا الملحق أدناه لتأكيده.',
      },
      confirmation: conf,
    };
  }
  if (av.signeLe) {
    return { etat: 'signe', titre: conf.titre, corps: conf.corps, confirmation: conf };
  }
  return null;
}

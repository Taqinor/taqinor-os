// CIQ324 — l'identité d'ENTREPRISE à l'acceptation d'un devis commercial ou
// industriel saisie dans l'ERP (contrat partagé `acceptation_entreprise.json`,
// `exemple_erp`). Facultative ici : D-CIQ-11 ne la rend obligatoire qu'en ligne.
// Fonctions PURES (node --test), sans React ni réseau.

/** Un devis commercial ou industriel porte-t-il une identité d'entreprise ? */
export const estDevisCi = (devis) => ['commercial', 'industriel'].includes(devis?.mode_installation)

export const ENTREPRISE_VIDE = Object.freeze({ raison_sociale: '', signataire_qualite: '', ice: '' })

/**
 * Le corps d'acceptation : celui d'aujourd'hui, plus le bloc `entreprise` pour
 * un C&I seulement (résidentiel / agricole : corps INCHANGÉ, aucune clé en plus).
 */
export function corpsAcceptation(base, devis, entreprise) {
  if (!estDevisCi(devis)) return base
  const e = entreprise || ENTREPRISE_VIDE
  return {
    ...base,
    entreprise: {
      raison_sociale: String(e.raison_sociale ?? '').trim(),
      signataire_qualite: String(e.signataire_qualite ?? '').trim(),
      ice: String(e.ice ?? '').trim(),
    },
  }
}

/** La raison sociale connue du client servie avec le devis, sinon vide (jamais inventée). */
export const raisonSocialeConnue = (devis) => String(devis?.client_raison_sociale ?? '')

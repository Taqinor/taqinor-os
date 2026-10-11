// ENF22 — helpers extraits de Provenance.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/** Les CINQ origines admises. Toute autre valeur = provenance non déclarée. */
export const ORIGINES = {
  fiche: {
    libelle: 'fiche technique',
    explication: 'valeur lue sur la fiche technique du produit retenu',
  },
  pvgis: {
    libelle: 'PVGIS',
    explication: 'donnée renvoyée par PVGIS pour ce site',
  },
  societe: {
    libelle: 'réglage société',
    explication: 'paramètre enregistré dans les réglages de la société',
  },
  saisie: {
    libelle: 'saisie',
    explication: 'valeur saisie pour ce calepinage',
  },
  hypothese: {
    libelle: 'hypothèse',
    explication: 'hypothèse assumée, à confirmer avant de l’opposer à un tiers',
  },
}

/** Vrai si `origine` est l'une des cinq origines fermées ci-dessus. */
export function estOrigineDeclaree(origine) {
  return typeof origine === 'string'
    && Object.prototype.hasOwnProperty.call(ORIGINES, origine)
}

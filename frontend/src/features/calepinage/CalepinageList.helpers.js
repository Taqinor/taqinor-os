// ENF22 — helpers extraits de CalepinageList.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/* ACAL197 — LES STATUTS SERVIS (contrat `calepinage_liste.json`,
   `statuts_publies`) : le filtre les propose TOUJOURS, pas seulement ceux de la
   page courante. Gardée par un vitest contre l'échantillon de contrat. */
export const STATUTS_CALEPINAGE = [
  ['brouillon', 'Brouillon'],
  ['valide', 'Validé'],
  ['perime', 'Périmé'],
  ['refuse', 'Refusé'], // ACON28 — dernière décision d'approbation : un refus
]

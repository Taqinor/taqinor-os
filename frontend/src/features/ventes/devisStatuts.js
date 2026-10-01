// QJR532 (Groupe QJR5, D-QJR5-1 / D-QJR5-2) — UNE seule lecture des droits de
// geste d'un devis. L'écran ne redérive jamais la règle du statut : il LIT les
// champs servis par le backend (QJR516, contrat `devis_modifiabilite.json`).
// Jamais une clé de STAGES.py ici : ce sont les statuts de DOCUMENT.

// Miroir Installation.Statut ordonné (apps/installations/models_installation.py)
// — un chantier potentiellement engagé sur le terrain. Déménagé de
// DevisList.jsx (QJR532) : une seule copie.
export const CHANTIER_EN_COURS_STATUTS = [
  'signe', 'materiel_commande', 'planifie', 'en_cours', 'installe',
  // Statuts hérités équivalents (LEGACY_STATUT_MAP backend).
  'a_planifier', 'pose_en_cours', 'pose', 'raccordement_onee', 'mise_en_service',
]

export const chantierEnCours = (chantier) =>
  !!chantier && CHANTIER_EN_COURS_STATUTS.includes(chantier.statut)

/** Un devis s'ouvre en Édition complète ssi le serveur le dit modifiable. */
export const peutEditerDevis = (d) =>
  !!d && d.modifiable === true && d.is_active !== false

/** « Réviser » (nouvelle version) ssi le serveur le dit révisable. */
export const peutReviserDevis = (d) =>
  !!d && d.revision_possible === true && d.is_active !== false

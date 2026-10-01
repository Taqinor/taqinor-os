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

// ── QJR654 — LA table des statuts DOCUMENT d'un devis (couche règle #4) ─────
// Ordre, libellés et options de filtre, importés par tous les écrans qui les
// recopiaient (liste, board, cockpit lead, signature, tableau de bord, fiche
// produit, visite). Jamais une clé de STAGES.py (règle #2) : le funnel CRM et
// les statuts de document ne se mélangent pas.
export const DEVIS_STATUTS = ['brouillon', 'envoye', 'accepte', 'refuse', 'expire']

export const STATUT_DEVIS_LABELS = Object.freeze({
  brouillon: 'Brouillon',
  envoye: 'Envoyé',
  accepte: 'Accepté',
  refuse: 'Refusé',
  expire: 'Expiré',
})

/** Libellé d'un statut de devis ; repli sur la valeur brute (jamais un vide). */
export const libelleStatutDevis = (statut) => STATUT_DEVIS_LABELS[statut] ?? statut

/** Filtres segmentés : « Tous » + les cinq statuts, dans l'ordre. */
export const STATUT_DEVIS_FILTRES = [
  { value: 'tous', label: 'Tous' },
  ...DEVIS_STATUTS.map(value => ({ value, label: STATUT_DEVIS_LABELS[value] })),
]

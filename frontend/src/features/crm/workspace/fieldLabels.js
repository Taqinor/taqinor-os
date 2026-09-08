// RÈGLE FONDATEUR 08/09/2026 — « all the errors should point at the field
// creating this error and even say what is exactly the error so it is easy
// to solve ». Incident déclencheur : un échec d'autosauvegarde affichait
// « Non enregistré — Réessayer » + un toast « Assurez-vous qu'il n'y a pas
// plus de 3 chiffres avant la virgule » SANS dire quel champ était en cause
// (equip_clim_kw). Cette carte associe chaque clé de champ du lead (celle que
// `setField`/une erreur serveur DRF utilisent) à : son libellé humain (celui
// posé sur le `FormField` correspondant), l'id de section du registre
// SectionsPane (pour déplier la bonne section) et l'id DOM du contrôle (pour
// y focaliser directement — `jumpToField`).
//
// Consommée par :
//   - LeadWorkspace.jsx  (SaveChip : nomme le champ fautif + navigue dessus) ;
//   - useLeadDraft.js    (message de FLUSH_ERROR : « Non enregistré —
//                          « <Label> » : <message serveur> ») ;
//   - fieldLabels.test.jsx (garde-fou anti-dérive : chaque htmlFor rencontré
//                            dans les sections a une entrée ici, et vice versa).
//
// NE PAS laisser dériver : un champ ajouté à une section (nouveau
// `<FormField htmlFor="lf-...">`) doit gagner son entrée ici, sinon
// `fieldLabels.test.jsx` échoue.
const fieldLabels = {
  // ── Contact ────────────────────────────────────────────────────────────
  nom: { label: 'Nom', section: 'contact', inputId: 'lf-nom' },
  prenom: { label: 'Prénom', section: 'contact', inputId: 'lf-prenom' },
  telephone: { label: 'Téléphone', section: 'contact', inputId: 'lf-telephone' },
  whatsapp: { label: 'WhatsApp', section: 'contact', inputId: 'lf-whatsapp' },
  ville: { label: 'Ville / quartier', section: 'contact', inputId: 'lf-ville' },
  email: { label: 'Email', section: 'contact', inputId: 'lf-email' },
  societe: { label: 'Société', section: 'contact', inputId: 'lf-societe' },
  adresse: { label: 'Adresse', section: 'contact', inputId: 'lf-adresse' },
  gps_lat: { label: 'GPS lat.', section: 'contact', inputId: 'lf-gps-lat' },
  gps_lng: { label: 'GPS long.', section: 'contact', inputId: 'lf-gps-lng' },
  lien_maps: { label: 'Lien Google Maps (envoyé par le client)', section: 'contact', inputId: 'lf-lien-maps' },

  // ── Suivi commercial (pipeline) ───────────────────────────────────────
  type_installation: { label: "Type d'installation", section: 'pipeline', inputId: 'lf-type-installation' },
  relance_date: { label: 'Relance le', section: 'pipeline', inputId: 'lf-relance-date' },
  montant_estime: { label: 'Montant estimé (MAD)', section: 'pipeline', inputId: 'lf-montant-estime' },
  date_cloture_prevue: { label: 'Clôture prévue le', section: 'pipeline', inputId: 'lf-date-cloture' },
  priorite: { label: 'Priorité', section: 'pipeline', inputId: 'lf-priorite' },
  canal: { label: 'Canal', section: 'pipeline', inputId: 'lf-canal' },
  langue_preferee: { label: 'Langue préférée', section: 'pipeline', inputId: 'lf-langue-preferee' },
  tags: { label: 'Tags (séparés par des virgules)', section: 'pipeline', inputId: 'lf-tags' },
  motif_perte: { label: 'Motif de perte', section: 'pipeline', inputId: 'lf-motif-perte' },

  // ── Profil énergétique (energie) ──────────────────────────────────────
  facture_hiver: { label: 'Facture mensuelle (MAD/mois)', section: 'energie', inputId: 'lf-facture-hiver' },
  facture_ete: { label: 'Facture Été (MAD/mois)', section: 'energie', inputId: 'lf-facture-ete' },
  conso_mensuelle_kwh: { label: 'Conso mensuelle (kWh)', section: 'energie', inputId: 'lf-conso-mensuelle' },
  tranche_onee: { label: 'Tarif / tranche ONEE', section: 'energie', inputId: 'lf-tranche-onee' },
  raccordement: { label: 'Raccordement', section: 'energie', inputId: 'lf-raccordement' },

  // ── Questionnaire d'appel (equipements) ───────────────────────────────
  occupation_jour: {
    label: "Y a-t-il quelqu'un à la maison en journée ?", section: 'equipements', inputId: 'lf-occupation-jour',
  },
  equip_piscine: { label: 'Avez-vous une piscine ?', section: 'equipements', inputId: 'lf-equip-piscine' },
  equip_piscine_pompe_kw: {
    label: 'Puissance de la pompe de filtration (kW)', section: 'equipements', inputId: 'lf-equip-piscine-kw',
  },
  equip_piscine_heures_jour: {
    label: 'Heures de filtration par jour', section: 'equipements', inputId: 'lf-equip-piscine-heures',
  },
  equip_piscine_creneau: {
    label: 'Quand la pompe tourne-t-elle le plus ?', section: 'equipements', inputId: 'lf-equip-piscine-creneau',
  },
  equip_voiture_electrique: {
    label: 'Avez-vous ou prévoyez-vous un véhicule électrique ?', section: 'equipements', inputId: 'lf-equip-ve',
  },
  equip_ve_km_semaine: {
    label: 'Combien de km par semaine avec ce véhicule ?', section: 'equipements', inputId: 'lf-equip-ve-km',
  },
  equip_ve_chargeur_kw: {
    label: 'Puissance du chargeur/borne (kW)', section: 'equipements', inputId: 'lf-equip-ve-chargeur-kw',
  },
  equip_ve_creneau: {
    label: 'Quand rechargez-vous le plus souvent ?', section: 'equipements', inputId: 'lf-equip-ve-creneau',
  },
  equip_clim: { label: 'Avez-vous la climatisation ?', section: 'equipements', inputId: 'lf-equip-clim' },
  equip_clim_pieces: {
    label: 'Combien de pièces/unités climatisées ?', section: 'equipements', inputId: 'lf-equip-clim-pieces',
  },
  // Incident déclencheur (08/09/2026) : la contrainte serveur (max 3 chiffres
  // avant la virgule) portait sur CE champ, sans que l'écran le nomme jamais.
  equip_clim_kw: {
    label: 'Puissance totale climatisation (kW)', section: 'equipements', inputId: 'lf-equip-clim-kw',
  },
  equip_clim_creneau: {
    label: 'Quand la clim tourne-t-elle le plus ?', section: 'equipements', inputId: 'lf-equip-clim-creneau',
  },
  equip_chauffe_eau_electrique: {
    label: 'Votre chauffe-eau est-il électrique ?', section: 'equipements', inputId: 'lf-equip-chauffe-eau',
  },
  equip_chauffe_eau_kw: {
    label: 'Puissance chauffe-eau (kW)', section: 'equipements', inputId: 'lf-equip-chauffe-eau-kw',
  },
  equip_chauffe_eau_creneau: {
    label: 'Créneau de chauffe principal', section: 'equipements', inputId: 'lf-equip-chauffe-eau-creneau',
  },

  // ── Pompage (agricole) ────────────────────────────────────────────────
  pompe_cv: { label: 'Pompe (CV)', section: 'pompage', inputId: 'lf-pompe-cv' },
  pompe_hmt_m: { label: 'HMT (m)', section: 'pompage', inputId: 'lf-pompe-hmt' },
  pompe_debit_m3h: { label: 'Débit souhaité (m³/h)', section: 'pompage', inputId: 'lf-pompe-debit' },

  // ── Toiture & site ─────────────────────────────────────────────────────
  type_toiture: { label: 'Type de toiture', section: 'toiture', inputId: 'lf-type-toiture' },
  surface_toiture_m2: { label: 'Surface (m²)', section: 'toiture', inputId: 'lf-surface-toiture' },
  taille_souhaitee_kwc: { label: 'Taille souhaitée (kWc)', section: 'toiture', inputId: 'lf-taille-souhaitee' },
  batterie_souhaitee: { label: 'Batterie', section: 'toiture', inputId: 'lf-batterie' },
  orientation: { label: 'Orientation', section: 'toiture', inputId: 'lf-orientation' },
  inclinaison_deg: { label: 'Inclinaison / pente (°)', section: 'toiture', inputId: 'lf-inclinaison' },
  ombrage: { label: 'Ombrage', section: 'toiture', inputId: 'lf-ombrage' },
  ombrage_notes: { label: 'Notes ombrage', section: 'toiture', inputId: 'lf-ombrage-notes' },
  structure_pref: { label: 'Structure', section: 'toiture', inputId: 'lf-structure' },
  nb_etages: { label: 'Étages / hauteur', section: 'toiture', inputId: 'lf-nb-etages' },

  // ── Visite technique ───────────────────────────────────────────────────
  visite_prevue_le: { label: 'Visite prévue le', section: 'visite', inputId: 'lf-visite-prevue' },
  visite_notes: { label: 'Notes de visite', section: 'visite', inputId: 'lf-visite-notes' },

  // ── Compléments ────────────────────────────────────────────────────────
  note: { label: 'Note générale', section: 'divers', inputId: 'lf-note' },
}

export default fieldLabels

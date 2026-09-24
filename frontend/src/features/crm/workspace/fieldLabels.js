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

  // ── Vague 1 du script d'appel guidé (CAD149/CAD174) ───────────────────
  // Libellé = EXACTEMENT le `verbose_name` du champ côté serveur
  // (`apps/crm/models.py`) — garde-fou de la tâche : l'écran et le
  // `help_text` (la question orale) doivent dire la MÊME chose. `pending`
  // = ces champs sont saisis par `PanneauScriptAppel.jsx` (CAD152/153, hors
  // périmètre de cette lane), pas encore par un `<FormField htmlFor>` des
  // six sections classiques — `inputId` est le nom RÉSERVÉ que cet écran
  // futur doit reprendre tel quel. Un champ marqué `pending` est EXEMPTÉ de
  // la garde « pas de fantôme » de `fieldLabels.test.jsx` ; retirer `pending`
  // dès que son `<FormField>` existe quelque part dans les six sections.
  type_bien: {
    label: 'Type de bien', section: 'toiture', inputId: 'lf-type-bien',
    pending: 'PanneauScriptAppel (CAD152/153)',
  },
  objectif_projet: {
    label: 'Objectif du projet', section: 'pipeline', inputId: 'lf-objectif-projet',
    pending: 'PanneauScriptAppel (CAD152/153)',
  },
  decideur: {
    label: 'Qui décide', section: 'pipeline', inputId: 'lf-decideur',
    pending: 'PanneauScriptAppel (CAD152/153)',
  },
  devis_concurrents: {
    label: 'Autres devis en cours', section: 'pipeline', inputId: 'lf-devis-concurrents',
    pending: 'PanneauScriptAppel (CAD152/153)',
  },
  equip_ve_statut: {
    label: 'Véhicule électrique — déjà là ou prévu ?', section: 'equipements',
    inputId: 'lf-equip-ve-statut', pending: 'PanneauScriptAppel (CAD152/153)',
  },
  pompage_heures_jour: {
    label: 'Pompage — heures par jour', section: 'pompage',
    inputId: 'lf-pompage-heures-jour', pending: 'PanneauScriptAppel (CAD152/153)',
  },
  pompe_alim_actuelle: {
    label: 'Pompe actuelle — alimentation', section: 'pompage',
    inputId: 'lf-pompe-alim-actuelle', pending: 'PanneauScriptAppel (CAD152/153)',
  },
  carburant_litres_mois: {
    label: 'Carburant consommé (litres/mois)', section: 'pompage',
    inputId: 'lf-carburant-litres-mois', pending: 'PanneauScriptAppel (CAD152/153)',
  },

  // CAD153 — la garde « tout champ écrit par le panneau d'appel, et tout
  // champ neuf du script guidé, a son entrée ». Deux familles, même règle
  // `pending` que ci-dessus (libellé = `verbose_name` serveur) :
  //   · les deux colonnes ANCIENNES que le panneau écrit sans qu'aucun
  //     `<FormField htmlFor>` ne les porte (la case « été différent » de
  //     SectionEnergie n'a pas d'id ; le statut d'occupation n'est affiché
  //     qu'en lecture dans SectionDivers) ;
  //   · la VAGUE 2 (CAD154) : six colonnes posées au serveur dont la moitié
  //     écran n'avait jamais été déclarée (le même geste que CAD174).
  ete_differente: {
    label: 'L’été est différent de l’hiver ?', section: 'energie',
    inputId: 'lf-ete-differente', pending: 'PanneauScriptAppel (CAD152/153)',
  },
  ownership: {
    label: "Statut d'occupation", section: 'toiture',
    inputId: 'lf-ownership', pending: 'PanneauScriptAppel (CAD152/153)',
  },
  nb_personnes_foyer: {
    label: 'Nombre de personnes au foyer', section: 'equipements',
    inputId: 'lf-nb-personnes-foyer', pending: 'vague 2 (CAD154)',
  },
  budget_client_mad: {
    label: 'Budget annoncé par le client (MAD)', section: 'pipeline',
    inputId: 'lf-budget-client-mad', pending: 'vague 2 (CAD154)',
  },
  frein_principal: {
    label: 'Frein principal', section: 'pipeline',
    inputId: 'lf-frein-principal', pending: 'vague 2 (CAD154)',
  },
  declencheur: {
    label: 'Ce qui a accroché', section: 'pipeline',
    inputId: 'lf-declencheur', pending: 'vague 2 (CAD154)',
  },
  compteur_puissance_kva: {
    label: 'Puissance souscrite du compteur (kVA)', section: 'energie',
    inputId: 'lf-compteur-puissance-kva', pending: 'vague 2 (CAD154)',
  },
  chauffage_electrique_hiver: {
    label: 'Chauffage électrique en hiver', section: 'equipements',
    inputId: 'lf-chauffage-electrique-hiver', pending: 'vague 2 (CAD154)',
  },
}

export default fieldLabels

/**
 * NAP canonique (Name / Address / Phone) — source unique de vérité.
 * Toute mention du nom, du téléphone, de l'email ou de l'URL sur le site
 * DOIT passer par cette constante (cohérence Google Business Profile).
 *
 * Valeurs réelles confirmées par Reda (2026-06-12) — phoneDisplay reste
 * caractère pour caractère identique à l'affichage GBP : « 0661850410 ».
 */
export const NAP = {
  name: 'Taqinor', // pas de suffixe SARL — aligné GBP
  url: 'https://taqinor.ma',
  phone: '+212661850410', // NAP_PHONE : JSON-LD, liens tel: — PERMANENT (GBP), jamais reformaté
  phoneDisplay: '0661850410', // format GBP exact (pages contact / mentions légales) — ne pas reformater
  phoneDisplayIntl: '+212 6 61 85 04 10', // affichage lisible en-tête + pied de page (W10) ; même numéro, lien tel: inchangé
  email: 'contact@taqinor.com', // adresse GBP confirmée par le propriétaire (2026-06-13)
  // Zone de service (pas d'adresse postale physique — mode service-area)
  serviceArea: ['Casablanca', 'Rabat', 'Marrakech', 'Tanger', 'Agadir', 'Maroc'],
  // Liste de services — doit correspondre EXACTEMENT au Google Business Profile
  services: [
    'Installation solaire résidentielle',
    'Installation solaire industrielle',
    'Batteries de stockage',
    'Étude et dimensionnement',
    'Monitoring',
    'Régularisation Loi 82-21 — Article 33',
  ],
} as const;

/**
 * Cible des deeplinks wa.me et de la remise d'étude du diagnostic —
 * DISTINCTE du téléphone NAP : aujourd'hui le même numéro, demain la
 * ligne de Meryem. Chiffres uniquement, avec indicatif pays.
 * (Surchargable au déploiement via l'env WHATSAPP_NUMBER du Worker.)
 */
export const WHATSAPP_LEADS = '212661850410';

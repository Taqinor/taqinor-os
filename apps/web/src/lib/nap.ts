/**
 * NAP canonique (Name / Address / Phone) — source unique de vérité.
 * Toute mention du nom, du téléphone, de l'email ou de l'URL sur le site
 * DOIT passer par cette constante (cohérence Google Business Profile).
 *
 * PLACEHOLDER(REDA): phone, whatsapp et email sont des valeurs provisoires —
 * à remplacer par les coordonnées exactes du Google Business Profile.
 */
export const NAP = {
  name: 'Taqinor', // pas de suffixe SARL — aligné GBP
  url: 'https://taqinor.ma',
  phone: '+212600000000', // PLACEHOLDER(REDA): numéro GBP exact
  phoneDisplay: '+212 6 00 00 00 00', // PLACEHOLDER(REDA)
  whatsapp: '212600000000', // PLACEHOLDER(REDA): WhatsApp Meryem, chiffres uniquement
  email: 'contact@taqinor.ma', // PLACEHOLDER(REDA): email GBP exact
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

/**
 * WJ122 — Étude COMMERCIALE par catégorie (parcours public /devis/mon-toit,
 * mode « commercial »). Module PUR : aucun DOM, aucune dépendance.
 *
 * Chaque marché commercial a une signature de consommation DIURNE distincte : un
 * bureau consomme le jour (autoconsommation élevée), un hôtel/restaurant a un pic
 * du soir. Le « day-share » (part de la conso pendant les heures solaires)
 * remplace l'unique DAY_USAGE_DEFAULTS['Commerciale']=80 par une table par
 * catégorie — hôtel ≠ bureau à facture égale.
 *
 * SOURCE: frontend/src/features/ventes/solar.js:87-186 (QX44). Les trois
 * structures ci-dessous (COMMERCIAL_CATEGORIES, COMMERCIAL_DAY_SHARE +
 * commercialDayShare, COMMERCIAL_CATEGORY_QUESTIONS) sont un PORT VERBATIM de ce
 * fichier — un test de parité (commercialCategoriesWJ122.test.ts) échoue si l'une
 * diverge. SOURCE = archétype de charge documenté ; EST. = estimation marché à
 * vérifier fondateur (QXG6 durcira ces valeurs). Pictos : miroir informatif de
 * backend .../quote_engine/commercial/categories.py METADATA.
 */

export interface CommercialCategory {
  value: string;
  label: string;
  /** Emoji picto (parité backend categories.py METADATA — informatif). */
  icon: string;
}

// SOURCE: frontend/src/features/ventes/solar.js:87-98 (COMMERCIAL_CATEGORIES).
// Emojis alignés sur quote_engine/commercial/categories.py METADATA.
export const COMMERCIAL_CATEGORIES: readonly CommercialCategory[] = [
  { value: 'hotel', label: 'Hôtel / Riad', icon: '🏨' },
  { value: 'restaurant', label: 'Restaurant / Café', icon: '🍽️' },
  { value: 'commerce', label: 'Commerce / Supermarché', icon: '🛒' },
  { value: 'bureau', label: 'Bureau / Siège', icon: '🏢' },
  { value: 'sante', label: 'Santé (clinique / cabinet)', icon: '🏥' },
  { value: 'ecole', label: 'École privée', icon: '🎓' },
  { value: 'hammam', label: 'Hammam / Spa / Gym', icon: '🧖' },
  { value: 'boulangerie', label: 'Boulangerie', icon: '🥖' },
  { value: 'froid', label: 'Entrepôt froid', icon: '❄️' },
  { value: 'autre', label: 'Autre commerce', icon: '🏪' },
] as const;

/** Liste fermée des identifiants de catégorie (liste blanche lead.ts + webhook). */
export const COMMERCIAL_CATEGORY_IDS = COMMERCIAL_CATEGORIES.map((c) => c.value) as readonly string[];

// SOURCE: frontend/src/features/ventes/solar.js:100-113 (COMMERCIAL_DAY_SHARE).
// Day-share (%) par catégorie — part de la consommation consommée en journée.
export const COMMERCIAL_DAY_SHARE: Record<string, number> = {
  bureau: 80, // SOURCE archétype bureau : conso ~9h-18h alignée au solaire
  ecole: 85, // SOURCE école (période scolaire) : forte conso diurne
  commerce: 75, // EST. supermarché : froid + éclairage jour, pic soir modéré
  sante: 70, // EST. clinique : diurne dominant, garde de nuit résiduelle
  restaurant: 70, // EST. restaurant : services midi + soir → part solaire moyenne
  hammam: 65, // EST. hammam/spa/gym : chauffe jour + soirée
  hotel: 55, // EST. hôtel : occupation soir/nuit, base diurne (clim/piscine)
  froid: 50, // EST. entrepôt froid : base 24 h, part solaire ≈ heures de jour
  boulangerie: 45, // EST. boulangerie : cuisson souvent nocturne → faible part solaire
  autre: 80, // repli = ancien défaut Commerciale
};
export const COMMERCIAL_DAY_SHARE_DEFAUT = 80;

/**
 * Day-share effectif d'une catégorie (override société optionnel, borné 10-100).
 * SOURCE: frontend/src/features/ventes/solar.js:116-122 (commercialDayShare).
 */
export function commercialDayShare(
  category: string,
  { override }: { override?: Record<string, number | string> } = {},
): number {
  if (override && typeof override === 'object' && override[category] != null) {
    const v = parseFloat(String(override[category]));
    if (Number.isFinite(v) && v > 0) return Math.min(100, Math.max(10, v));
  }
  return COMMERCIAL_DAY_SHARE[category] ?? COMMERCIAL_DAY_SHARE_DEFAUT;
}

export interface CommercialQuestion {
  key: string;
  label: string;
  type: 'number' | 'bool' | 'select';
  options?: { value: string; label: string }[];
}

// SOURCE: frontend/src/features/ventes/solar.js:127-186 (COMMERCIAL_CATEGORY_QUESTIONS).
// Questions 2-4 par catégorie (recherche 2026-07-16). key = clé snake_case
// stockée dans etude_params (et acceptée par le webhook QX51). type =
// 'number' | 'bool' | 'select' (+ options).
export const COMMERCIAL_CATEGORY_QUESTIONS: Record<string, CommercialQuestion[]> = {
  hotel: [
    { key: 'chambres', label: 'Nombre de chambres', type: 'number' },
    { key: 'occupation_pct', label: "Taux d'occupation annuel (%)", type: 'number' },
    { key: 'piscine', label: 'Piscine chauffée', type: 'bool' },
  ],
  restaurant: [
    { key: 'chambres_froides', label: 'Chambres froides', type: 'number' },
    {
      key: 'horaires', label: 'Horaires', type: 'select', options: [
        { value: 'midi', label: 'Midi' }, { value: 'soir', label: 'Soir' },
        { value: 'continu', label: 'Continu' },
      ],
    },
    {
      key: 'cuisson', label: 'Cuisson', type: 'select', options: [
        { value: 'electrique', label: 'Électrique' }, { value: 'gaz', label: 'Gaz' },
      ],
    },
  ],
  commerce: [
    { key: 'surface_vente_m2', label: 'Surface de vente (m²)', type: 'number' },
    { key: 'chambres_froides', label: 'Meubles / chambres froids', type: 'number' },
  ],
  bureau: [
    { key: 'effectif', label: 'Effectif (postes)', type: 'number' },
    { key: 'clim', label: 'Climatisation centralisée', type: 'bool' },
  ],
  sante: [
    { key: 'lits', label: 'Nombre de lits', type: 'number' },
    { key: 'garde_nuit', label: 'Garde de nuit', type: 'bool' },
  ],
  ecole: [
    { key: 'effectif', label: 'Effectif (élèves)', type: 'number' },
    { key: 'internat', label: 'Internat', type: 'bool' },
    { key: 'fermeture_estivale', label: 'Fermeture estivale', type: 'bool' },
  ],
  hammam: [
    { key: 'surface_m2', label: 'Surface (m²)', type: 'number' },
    {
      key: 'chauffe', label: 'Chauffe eau', type: 'select', options: [
        { value: 'electrique', label: 'Électrique' }, { value: 'gaz', label: 'Gaz' },
      ],
    },
  ],
  boulangerie: [
    {
      key: 'four', label: 'Four', type: 'select', options: [
        { value: 'electrique', label: 'Électrique' }, { value: 'gaz', label: 'Gaz' },
      ],
    },
    { key: 'cuisson_nocturne', label: 'Cuisson nocturne', type: 'bool' },
  ],
  froid: [
    { key: 'temperature_consigne', label: 'Température de consigne (°C)', type: 'number' },
    { key: 'volume_m3', label: 'Volume froid (m³)', type: 'number' },
    { key: 'saisonnalite_recolte', label: 'Pic saisonnier (récolte)', type: 'bool' },
  ],
  autre: [],
};

/**
 * WJ122 — mapping clé de question snake_case → clé webhook camelCase (QX51,
 * SOURCE: backend/django_core/apps/crm/webhooks.py `_extract_web_questionnaire`).
 * Seules les clés ici présentes sont envoyées au webhook (lead.ts les whiteliste
 * aussi) ; `surface_m2` (hammam) n'a PAS de destination webhook dédiée — il n'est
 * donc jamais transmis (jamais mappé sur le `surfaceM2` PRO, sémantique différente).
 */
export const COMMERCIAL_QUESTION_WEBHOOK_KEY: Record<string, string> = {
  chambres: 'chambres',
  occupation_pct: 'occupationPct',
  piscine: 'piscine',
  chambres_froides: 'chambresFroides',
  horaires: 'horaires',
  cuisson: 'cuisson',
  surface_vente_m2: 'surfaceVenteM2',
  effectif: 'effectif',
  clim: 'clim',
  lits: 'lits',
  garde_nuit: 'gardeNuit',
  internat: 'internat',
  fermeture_estivale: 'fermetureEstivale',
  chauffe: 'chauffe',
  four: 'four',
  cuisson_nocturne: 'cuissonNocturne',
  temperature_consigne: 'temperatureConsigne',
  volume_m3: 'volumeM3',
  saisonnalite_recolte: 'saisonnaliteRecolte',
  // surface_m2 : volontairement ABSENT (pas de clé webhook — jamais transmis).
};

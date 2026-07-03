/**
 * W380 — facts.ts : UNE seule surface machine-lisible agrégeant les faits
 * canoniques déjà publiés et déjà committés ailleurs sur le site. Toute
 * couche de "grounding" future (llms.txt, une page méthodologie type W359,
 * un futur assistant IA) doit citer CET artifact plutôt que re-dériver les
 * mêmes faits à la main dans un cinquième endroit.
 *
 * RÈGLE D'INTÉGRITÉ : ce fichier n'INVENTE ni ne RESTATE aucune valeur — il
 * IMPORTE et ré-expose les constantes déjà canoniques :
 *   - `nap.ts`       → identité, coordonnées, zone de service, services GBP.
 *   - `billRange.ts` → tranches de facture, fourchettes kWc/payback indicatives.
 *   - `fiches.ts`    → garanties structurées PAR PRODUIT (panneaux, onduleurs,
 *                      batteries, supervision) — c'est la SEULE source « garanties »
 *                      du repo qui soit un module `.ts` réellement importable
 *                      (le tableau de `/garanties` et les Q/R de `/faq` vivent
 *                      dans le frontmatter de pages `.astro`, qui n'exporte
 *                      rien et n'est donc pas important tel quel — voir la
 *                      note `faqTopics` ci-dessous).
 *
 * La FAQ publique (`/faq`) n'est PAS dupliquée ici question par question :
 * son contenu vit dans le frontmatter de `src/pages/faq.astro`, qui n'exporte
 * aucune constante (une page Astro n'est pas un module JS important ailleurs).
 * Dupliquer les 19 paires Q/R à la main dans ce fichier créerait exactement
 * le problème que W380 doit éviter — une deuxième copie qui diverge de la
 * source. `faqTopics` référence donc la page comme la source vivante, avec un
 * compte de questions à titre indicatif (à re-vérifier si `/faq` change), et
 * un sujet par thème réellement traité — sans inventer une seule réponse.
 */
import { NAP, WHATSAPP_LEADS } from './nap';
import { BILL_RANGES, LOCAL_PAYBACK_BY_KWC, type BillRangeId } from './billRange';
import { FICHES, FICHE_CATEGORIES, type Fiche } from './fiches';

/** Date de génération de cet agrégat — à avancer quand une source change. */
export const FACTS_GENERATED_AT = '2026-07-03';

/** Identité, coordonnées et zone de service — ré-export direct de `nap.ts`. */
export const identity = {
  name: NAP.name,
  url: NAP.url,
  phone: NAP.phone,
  phoneDisplay: NAP.phoneDisplay,
  phoneDisplayIntl: NAP.phoneDisplayIntl,
  email: NAP.email,
  serviceArea: NAP.serviceArea,
  services: NAP.services,
  whatsappLeads: WHATSAPP_LEADS,
} as const;

/** Tranches de facture mensuelle + éligibilité CRM — ré-export de `billRange.ts`. */
export const billing = {
  ranges: BILL_RANGES,
  paybackByKwc: LOCAL_PAYBACK_BY_KWC,
} as const;

export function billRangeById(id: BillRangeId) {
  return BILL_RANGES.find((r) => r.id === id);
}

/**
 * Garanties par produit — dérivées de `fiches.ts` (une ligne par fiche
 * technique publiée), groupées par catégorie. `years`/`note` viennent du
 * champ `warranty` déjà structuré dans `fiches.ts` — rien de recalculé.
 */
export interface WarrantyFact {
  categorie: Fiche['categorie'];
  marque: string;
  modele: string;
  years: number;
  note?: string;
}

export const warranties: WarrantyFact[] = FICHES.map((f) => ({
  categorie: f.categorie,
  marque: f.marque,
  modele: f.modele,
  years: f.warranty.years,
  note: f.warranty.note,
}));

/** Durée de garantie la plus longue et la plus courte réellement publiées (produits fiches.ts). */
export const warrantyYearsRange = {
  min: Math.min(...FICHES.map((f) => f.warranty.years)),
  max: Math.max(...FICHES.map((f) => f.warranty.years)),
} as const;

export const ficheCategories = FICHE_CATEGORIES;

/**
 * FAQ publique — pointeur vers la source vivante, PAS une copie des réponses.
 * `questionCount` reflète le nombre de paires Q/R dans `src/pages/faq.astro`
 * au moment de `FACTS_GENERATED_AT` (à recompter si la page change) ; `topics`
 * liste les thèmes réellement traités sur la page, dans l'ordre où ils y
 * apparaissent — aucune formulation de réponse n'est reproduite ici.
 */
export const faqSource = {
  path: '/faq',
  questionCount: 19,
  topics: [
    'Prix & ordres de grandeur',
    'Fonctionnement des panneaux',
    'Loi 82-21',
    'Article 33 — régularisation',
    'Batteries / autoconsommation',
    'Garanties',
    'Véhicule électrique',
    'Délais & process',
    'Monitoring / SAV',
  ],
} as const;

/**
 * Garanties écrites (page `/garanties`) — pointeur vers la source vivante,
 * pour la partie du tableau (structure, main-d'œuvre) qui n'est pas une
 * "fiche produit" et vit donc uniquement dans le frontmatter de la page.
 * Les garanties PRODUIT (panneaux/onduleurs/batteries/supervision) sont,
 * elles, réellement importées ci-dessus via `warranties`.
 */
export const warrantyPageSource = {
  path: '/garanties',
  /** Éléments couverts par la page mais absents de `fiches.ts` (non un "produit" catalogue). */
  additionalCoverage: [
    { item: 'Structure acier galvanisé', years: 20 },
    { item: 'Installation et main-d’œuvre Taqinor', years: 2 },
  ],
} as const;

/** L'artifact complet — un seul objet à citer/sérialiser par tout consommateur. */
export const FACTS = {
  generatedAt: FACTS_GENERATED_AT,
  identity,
  billing,
  warranties,
  warrantyYearsRange,
  ficheCategories,
  faqSource,
  warrantyPageSource,
} as const;

export default FACTS;

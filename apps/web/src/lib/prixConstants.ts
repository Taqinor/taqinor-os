/**
 * WAUD68 — constante de prix UNIQUE du site public (D-WAUD-5 = a, 03/11/2026).
 *
 * Règle « chiffres vérifiés » : un chiffre d'argent ne s'affiche qu'avec sa source PRIMAIRE et sa
 * date. D-WAUD-5 les fait dériver de l'export ERP des devis résidentiels signés 2026 (prix TTC réel au
 * kWc) et de l'article du CGI 2026 lu (TVA des panneaux nus) — donnée pas encore fournie au 04/11/2026
 * (WAUD68-b, data-gated). D'ici là chaque valeur est `null` et les pages qui la consomment (/prix,
 * billet prix 2026, /résidentiel ×3 langues, réponse courte WAUD77) OMETTENT le chiffre.
 *
 * Chiffres retirés le 04/11/2026 en attendant D-WAUD-5 (reviennent d'ici seulement, datés) :
 *  - prix au kWc 10 000 – 12 500 DH (colonne « investissement » de /résidentiel) et 10 000 – 14 000 DH/kWc (/prix) ;
 *  - fourchettes 3 / 5 / 10 kWc : 28 000 – 42 000, 45 000 – 65 000, 85 000 – 120 000 DH ;
 *  - surcoûts toiture tuiles/tôle +6 000 – 12 000 DH, forte pente +4 000 – 8 000 DH ;
 *  - batterie LFP 5 – 15 kWh +22 000 – 60 000 DH et « retour allongé de 1 à 3 ans » ;
 *  - « 4 700 DH/kWc » (kit seul) ; panneaux ~1,0 – 1,5 DH/Wc ; onduleur Huawei ~12 500 DH ;
 *  - droits de douane des onduleurs 17,5 % → 2,5 % ; TVA « 20 % clé-en-main », « panneaux nus exonérés ».
 */
export interface ChiffreSource<T> {
  valeur: T | null;
  /** URL ou référence primaire (export ERP daté, article du CGI, loi de finances). */
  source: string | null;
  /** Date de lecture de la source (ISO). */
  date: string | null;
}

/** Prix TTC clé-en-main au kWc des devis résidentiels signés (D-WAUD-5). */
export const PRIX_KWC_TTC: ChiffreSource<{ bas: number; haut: number }> = { valeur: null, source: null, date: null };

/**
 * La SEULE phrase TVA du site sur le prix d'une installation : celle de la source AGW305
 * (CGI 2026, art. 91-I-C-6° — pompes à eau solaires à usage agricole), sans taux pour le reste.
 */
export const PHRASE_TVA = {
  fr: 'Seules les pompes à eau solaires à usage agricole sont exonérées de TVA (art. 91 du CGI) ; le taux de chaque autre élément figure ligne par ligne sur votre devis.',
  en: 'Only solar water pumps for agricultural use are VAT-exempt (art. 91 of the CGI); the rate for every other item appears line by line on your quote.',
  ar: 'وحدها مضخّات الماء الشمسية ذات الاستعمال الفلاحي معفاة من الضريبة على القيمة المضافة (المادة 91 من المدونة العامة للضرائب)؛ ويظهر سعر الضريبة لكل عنصر آخر سطراً بسطر في عرض السعر.',
} as const;

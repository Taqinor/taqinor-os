/**
 * PERTES SYSTÈME — SOURCE UNIQUE DU SITE (ordre fondateur, 18/08).
 *
 * « We introduce a system loss of 20% total. » Un seul chiffre de pertes pour
 * tout le groupe : la page marketing, le tunnel d'estimation et le devis ERP
 * doivent annoncer la MÊME production centrale pour la même ville et la même
 * puissance.
 *
 * Ce module ne dépend de RIEN (aucun import) : c'est ce qui lui permet d'être
 * importé aussi bien par `roof.ts` que par `estimatorBrainV2.ts` (qui importe
 * `roof.ts`) sans créer de dépendance circulaire. Ne jamais y ajouter d'import.
 *
 * DEUX BASES COEXISTENT, ne pas les confondre :
 *  • les appels PVGIS LIVE (`roofEstimate.ts`) demandent directement
 *    `loss=20` → leur résultat est DÉJÀ sur la base du fondateur, aucun
 *    facteur à appliquer ;
 *  • la table committée `yieldTable.ts` a été générée à `loss=14` (donnée
 *    figée, cf. apps/web/scripts/generate-yield-table.mjs) → il faut lui
 *    appliquer le COMPLÉMENT `PRODUCTION_NET_FACTOR`, ce que fait
 *    `specificYield()` et lui seul.
 * Appliquer les deux à la même valeur donnerait ~31 % de pertes cumulées.
 *
 * MIROIR ERP (les trois DOIVENT rester alignés — verrouillé par
 * apps/web/tests/systemLoss20pct.test.ts) :
 *  • frontend/src/features/ventes/solar.js  → SYSTEM_LOSS_TOTAL / PVGIS_BUILTIN_LOSS
 *                                             / PRODUCTIBLE_NET_FACTOR
 *  • backend/django_core/apps/ventes/quote_engine/pricing.py → PRODUCTION_DERATE
 */

/** Pertes système TOTALES retenues (ordre fondateur 18/08). */
export const SYSTEM_LOSS_TOTAL = 0.2;

/** Pertes déjà incluses dans la table PVGIS committée (`loss=14`). */
export const PVGIS_BUILTIN_LOSS = 0.14;

/**
 * Complément à appliquer à un productible EXPRIMÉ EN BASE 14 % pour le ramener
 * à la base 20 % : (1 − 0,20)/(1 − 0,14) = 0,8/0,86 ≈ 0,9302.
 * À n'appliquer QU'UNE FOIS, et uniquement à une valeur en base 14 %.
 */
export const PRODUCTION_NET_FACTOR = (1 - SYSTEM_LOSS_TOTAL) / (1 - PVGIS_BUILTIN_LOSS);

/** Pertes système (%) à demander à PVGIS en LIVE — la base du fondateur. */
export const PVGIS_LIVE_LOSS_PCT = SYSTEM_LOSS_TOTAL * 100;

/**
 * L-WEBT TASK2 — « Une journée type » (production PV vs consommation, quatre
 * mois représentatifs) pour /devis/mon-toit.
 *
 * SOURCE UNIQUE DE VÉRITÉ : `apps.ventes.etude_horaire.jours_types_annee`
 * (backend/django_core/apps/ventes/etude_horaire.py) — ce module ne calcule
 * RIEN ; il porte seulement la FORME du jeu de données que le composant
 * consomme, et le jeu réel doit venir de ce moteur.
 *
 * RÈGLE « ZÉRO CHIFFRE INVENTÉ » (CLAUDE.md) : cette lane (apps/web
 * uniquement, aucun accès au moteur Django depuis ce worktree) ne peut pas
 * appeler `jours_types_annee` elle-même. Les quatre mois ci-dessous sont donc
 * VOLONTAIREMENT `null` — aucune valeur fabriquée. Le composant qui lit ce
 * module (mon-toit.astro, section « Une journée type ») se MASQUE ENTIÈREMENT
 * tant que `hasJourTypeData()` est faux : jamais une courbe dessinée sur des
 * zéros inventés.
 *
 * [HANDOFF] — un futur run avec accès au backend régénère ce fichier :
 *   from apps.ventes.etude_horaire import jours_types_annee
 *   jours, _, _ = jours_types_annee(
 *       kwc=<kWc représentatif d'un foyer résidentiel type, ex. 3>,
 *       conso_kwh_mensuelles=<12 valeurs mensuelles d'un profil résidentiel
 *                             représentatif — factures réelles agrégées,
 *                             jamais une série inventée>,
 *       ville='Casablanca', occupation='presence_partielle')
 *   # puis pour chaque mois cible (1/4/7/11) :
 *   #   prodKw   = [v / 1 for v in jour['prod_24h']]   # déjà en kWh/heure ≈ kW moyen
 *   #   consoKw  = jour['conso_24h']
 *   #   autoconsommeKwh = sum(min(c, p) for c, p in zip(consoKw, prodKw))
 *   #   surplusKwh = jour['prod_jour_kwh'] - autoconsommeKwh
 * Coller le résultat dans JOUR_TYPE_DATA ci-dessous et rien d'autre — la
 * fonction `hasJourTypeData()` et le composant n'ont besoin d'aucun autre
 * changement.
 */

export type JourTypeMonthId = 1 | 4 | 7 | 11; // janvier / avril / juillet / novembre

export interface JourTypeMonth {
  /** 24 valeurs — puissance PRODUITE moyenne de chaque heure du jour moyen (kW). */
  prodKw: number[];
  /** 24 valeurs — puissance CONSOMMÉE moyenne de chaque heure du jour moyen (kW). */
  consoKw: number[];
  /** kWh consommés le jour moyen du mois (sous-titre). */
  consoJourKwh: number;
  /** kWh produits le jour moyen du mois (sous-titre). */
  prodJourKwh: number;
  /** kWh autoconsommés le jour moyen (min(conso,prod) heure par heure, sommé). */
  autoconsommeKwh: number;
  /** kWh de surplus le jour moyen (prod − autoconsommé). */
  surplusKwh: number;
}

export const JOUR_TYPE_MONTH_IDS: readonly JourTypeMonthId[] = [1, 4, 7, 11];

export const JOUR_TYPE_MONTH_LABELS: Record<JourTypeMonthId, { fr: string; ar: string }> = {
  1: { fr: 'Janvier', ar: 'يناير' },
  4: { fr: 'Avril', ar: 'أبريل' },
  7: { fr: 'Juillet', ar: 'يوليوز' },
  11: { fr: 'Novembre', ar: 'نونبر' },
};

/**
 * Jeu de données — VIDE par construction (voir [HANDOFF] ci-dessus). Ne
 * jamais remplacer un `null` par une estimation « pour faire joli » : un
 * composant masqué est toujours préférable à un graphe qui ment.
 */
export const JOUR_TYPE_DATA: Record<JourTypeMonthId, JourTypeMonth | null> = {
  1: null,
  4: null,
  7: null,
  11: null,
};

function isValidHourlyShape(a: unknown): a is number[] {
  return Array.isArray(a) && a.length === 24 && a.every((v) => typeof v === 'number' && Number.isFinite(v) && v >= 0);
}

/**
 * Vrai seulement si LES QUATRE mois portent une courbe valide (24 nombres
 * finis ≥ 0 pour prod ET conso). Un jeu partiel serait plus trompeur qu'utile
 * — les quatre petits multiples sont conçus pour se comparer entre eux.
 */
export function hasJourTypeData(): boolean {
  return JOUR_TYPE_MONTH_IDS.every((m) => {
    const d = JOUR_TYPE_DATA[m];
    return !!d && isValidHourlyShape(d.prodKw) && isValidHourlyShape(d.consoKw);
  });
}

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
 * Jeu de données — GÉNÉRÉ le 2026-08-24 par l'orchestrateur du run, en
 * exécutant réellement `apps.ventes.etude_horaire.jours_types_annee(
 *   kwc=7.10, conso_kwh_mensuelles=[2070.5]*12, ville='Casablanca',
 *   occupation='presence_jour')` sur le moteur calibré lot 4 (commit
 * aed87896 de main) — les paramètres EXACTS du graphe validé fondateur du
 * 24/08 (villa 10 panneaux, 3 500 DH/mois). Aucune valeur inventée : chaque
 * nombre sort du moteur ; pour changer de profil, régénérer via le même
 * appel et coller le résultat ici.
 */
export const JOUR_TYPE_DATA: Record<JourTypeMonthId, JourTypeMonth | null> = {
  1: {
    consoKw: [1.16, 1.16, 1.16, 1.16, 1.16, 1.16, 1.45, 2.32, 2.9, 2.9, 3.19, 3.19, 3.91, 3.91, 3.91, 2.9, 2.9, 2.9, 3.48, 4.35, 5.22, 4.93, 3.48, 2.03],
    prodKw: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.71, 1.9, 2.93, 3.69, 3.98, 3.88, 3.59, 2.93, 2.01, 0.74, 0.0, 0.0, 0.0, 0.0, 0.0],
    consoJourKwh: 66.8,
    prodJourKwh: 26.4,
    autoconsommeKwh: 25.6,
    surplusKwh: 0.79,
  },
  4: {
    consoKw: [1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.5, 2.4, 2.99, 2.99, 3.29, 3.29, 4.04, 4.04, 4.04, 2.99, 2.99, 2.99, 3.59, 4.49, 5.39, 5.09, 3.59, 2.1],
    prodKw: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.03, 0.64, 1.63, 2.61, 3.49, 4.21, 4.61, 4.58, 4.21, 3.53, 2.51, 1.42, 0.41, 0.0, 0.0, 0.0, 0.0],
    consoJourKwh: 69.0,
    prodJourKwh: 33.9,
    autoconsommeKwh: 30.6,
    surplusKwh: 3.24,
  },
  7: {
    consoKw: [1.16, 1.16, 1.16, 1.16, 1.16, 1.16, 1.45, 2.32, 2.9, 2.9, 3.19, 3.19, 3.91, 3.91, 3.91, 2.9, 2.9, 2.9, 3.48, 4.35, 5.22, 4.93, 3.48, 2.03],
    prodKw: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.18, 0.71, 1.62, 2.64, 3.56, 4.3, 4.69, 4.65, 4.3, 3.63, 2.64, 1.59, 0.63, 0.14, 0.0, 0.0, 0.0],
    consoJourKwh: 66.8,
    prodJourKwh: 35.3,
    autoconsommeKwh: 30.9,
    surplusKwh: 4.41,
  },
  11: {
    consoKw: [1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.5, 2.4, 2.99, 2.99, 3.29, 3.29, 4.04, 4.04, 4.04, 2.99, 2.99, 2.99, 3.59, 4.49, 5.39, 5.09, 3.59, 2.1],
    prodKw: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.03, 0.5, 1.25, 2.01, 2.69, 3.24, 3.55, 3.52, 3.24, 2.71, 1.93, 1.1, 0.31, 0.0, 0.0, 0.0, 0.0],
    consoJourKwh: 69.0,
    prodJourKwh: 26.1,
    autoconsommeKwh: 25.8,
    surplusKwh: 0.25,
  },
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

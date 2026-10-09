/**
 * Page SolarBow (YBW62) — titres et textes d'interface. Les faits viennent du
 * registre (`src/lib/claims.ts`) : parties prêtes pour la France seulement
 * (D-YBW-8), jamais d'euros, d'économies ni de tarifs, jamais « prêt pour la
 * France » ; aucune mention de signature électronique, Factur-X, paiement en
 * ligne, suivi de production, agent de requêtes, sécurité ou hébergement.
 */
export const fr = {
  titre: 'SolarBow — le logiciel des installateurs solaires',
  description: 'SolarBow : prospects et relances, calepinage, dossiers déclaration préalable, Enedis et Consuel, devis et proposition commerciale.',
  surtitre: 'Pour les installateurs solaires',
  cta: 'Prendre rendez-vous',
  secondaire: 'Voir ce que fait SolarBow',
  modules: {
    surtitre: 'Ce que fait SolarBow',
    titre: 'Du premier contact à la proposition',
    prospects: 'Prospects et relances',
    calepinage: 'Calepinage',
    dossiers: 'Dossiers déclaration préalable, Enedis et Consuel',
    devis: 'Devis et proposition',
  },
  appel: {
    titre: 'Voyons SolarBow sur vos projets',
    bouton: 'Prendre rendez-vous',
  },
} as const;

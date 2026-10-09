/**
 * Accueil (YBW61) — titres et textes d'interface. Les faits viennent du
 * registre (`src/lib/claims.ts`) : YB-METIER, YB-POSITIONNEMENT, les
 * affirmations des deux produits, SM-OFFRE, YB-NOM-SOURCE, YB-REPONSE-HUMAINE.
 * Aucune statistique, aucun logo client, aucune personne.
 */
export const fr = {
  titre: 'YanBow — logiciels métier',
  description:
    'YanBow construit des logiciels métier : SolarBow pour les installateurs solaires, MarketingBow pour les campagnes publicitaires, et du développement sur mesure.',
  surtitre: 'Studio logiciel',
  cta: 'Prendre rendez-vous',
  secondaire: 'Découvrir les produits',
  produits: {
    surtitre: 'Produits',
    titre: 'Deux produits construits',
    solarbow: { surtitre: 'Pour les installateurs solaires', lien: 'Découvrir SolarBow' },
    marketingbow: { surtitre: 'Pour les campagnes publicitaires', lien: 'Découvrir MarketingBow' },
  },
  surMesure: {
    surtitre: 'Sur-mesure',
    titre: 'Et pour le reste, du sur-mesure',
    besoin: 'Le besoin',
    prototype: 'Le prototype',
    service: 'La mise en service',
    exploitation: 'L’exploitation',
    lien: 'La démarche sur mesure',
  },
  societe: {
    surtitre: 'Société',
    titre: 'Pourquoi YanBow',
    lien: 'Qui nous sommes',
  },
  appel: {
    titre: 'Parlons de votre projet',
    bouton: 'Prendre rendez-vous',
  },
} as const;

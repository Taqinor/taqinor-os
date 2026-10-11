/**
 * Page Sur mesure (YBW64) — textes d'interface et titres. Les phrases qui
 * affirment un fait viennent du registre (`src/lib/claims.ts`) : SM-OFFRE,
 * SM-DEMARCHE, YB-DEUX-PRODUITS, YB-REPONSE-HUMAINE. Aucun client, aucun délai,
 * aucun prix, aucune technologie à la mode en titre (STYLE.md).
 */
export const fr = {
  titre: 'Logiciel sur mesure — YanBow',
  description: 'YanBow construit des logiciels sur mesure pour les entreprises : besoin, prototype, mise en service, exploitation.',
  surtitre: 'Sur-mesure',
  h1: 'Le logiciel dont votre entreprise a besoin',
  cta: 'Prendre rendez-vous',
  demarche: {
    surtitre: 'La démarche',
    titre: 'Quatre temps, dans cet ordre',
    besoin: { titre: 'Le besoin', detail: 'On part de votre façon de travailler et de ce qui coince aujourd’hui.' },
    prototype: { titre: 'Le prototype', detail: 'Un premier logiciel qui fonctionne, à essayer avant d’aller plus loin.' },
    service: { titre: 'La mise en service', detail: 'Le logiciel est installé et utilisé par vos équipes.' },
    exploitation: { titre: 'L’exploitation', detail: 'On le maintient et on le fait évoluer avec vous.' },
  },
  preuve: {
    surtitre: 'La preuve',
    titre: 'Deux produits construits',
    solarbow: 'Découvrir SolarBow',
    marketingbow: 'Découvrir MarketingBow',
  },
  appel: {
    titre: 'Parlons de votre besoin',
    bouton: 'Prendre rendez-vous',
  },
} as const;

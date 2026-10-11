/**
 * Page Société (YBW65) — texte seulement : aucun portrait, aucune photo
 * d'équipe, aucune date de création, aucun chiffre. Les faits viennent du
 * registre (`src/lib/claims.ts`) : YB-METIER, YB-NOM-SOURCE, YB-NOM-YAN,
 * YB-SLOGAN, SB-ENTREPRISE-REELLE, YB-REPONSE-HUMAINE. Les phrases sur les
 * sociétés ne s'affichent que lorsque `src/lib/legal.ts` est rempli (rien ne
 * laisse croire qu'une société existe avant son immatriculation).
 * `{nom}`, `{partie}`, `{numero}`, `{forme}` sont remplacés depuis legal.ts.
 */
export const fr = {
  titre: 'La société — YanBow',
  description: 'YanBow construit des logiciels métier pour les entreprises : SolarBow, MarketingBow et du développement sur mesure.',
  surtitre: 'Société',
  h1: 'Qui nous sommes',
  nom: {
    surtitre: 'Le nom',
    titre: 'Pourquoi YanBow',
  },
  entites: {
    titre: 'Les sociétés',
    editeur: 'Ce site est publié par {nom}, société immatriculée en {partie} sous le numéro {numero}.',
    maroc: 'Au Maroc, les clients signent avec {nom}, {forme}.',
  },
  origine: {
    surtitre: 'D’où vient SolarBow',
    titre: 'SolarBow',
  },
  offre: {
    surtitre: 'Ce que nous faisons',
    titre: 'Deux produits et du sur-mesure',
    surMesure: 'Sur-mesure',
  },
  appel: {
    titre: 'Parlons de votre projet',
    bouton: 'Prendre rendez-vous',
  },
} as const;

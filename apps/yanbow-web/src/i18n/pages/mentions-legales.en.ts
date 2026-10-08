/** English dictionary of the Legal notice page (YBW28) — same keys as the FR. */
import type { DictEn } from '../config';
import type { fr } from './mentions-legales.fr';

export const en: DictEn<typeof fr> = {
  titre: 'Legal notice',
  description: 'Legal notice of the website: publisher, Moroccan company, contact, publication and hosting.',
  h1: 'Legal notice',
  langue: 'Language',
  editeur: {
    titre: 'Website publisher',
    nom: 'Company name',
    partie: 'Registered in',
    numero: 'Company number',
    siege: 'Registered office',
    tva: 'VAT number',
  },
  maroc: {
    titre: 'Company in Morocco',
    denomination: 'Company name',
    forme: 'Legal form',
    capital: 'Share capital',
    siege: 'Registered office',
    rc: 'Trade register (RC)',
    ice: 'Common company identifier (ICE)',
    if: 'Tax identifier (IF)',
    gerant: 'Manager',
  },
  commun: {
    titre: 'Contact, publication and hosting',
    email: 'Email',
    telephone: 'Phone',
    directeurPublication: 'Publication director',
    hebergeur: 'Hosting provider',
    cndp: 'CNDP declaration receipts',
    representantUe: 'Representative in the European Union',
  },
  foi: 'The French version of this page prevails.',
};

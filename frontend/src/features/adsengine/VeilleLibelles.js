/* PLAN_VEILLE — libellés FR d'AFFICHAGE partagés par les onglets de la veille.
   Les codes (pays ISO, statuts) viennent toujours du serveur ; ce fichier ne
   fait que les traduire pour l'écran. */

export const NOMS_PAYS = {
  AT: 'Autriche', BE: 'Belgique', BG: 'Bulgarie', HR: 'Croatie', CY: 'Chypre',
  CZ: 'Tchéquie', DK: 'Danemark', EE: 'Estonie', FI: 'Finlande', FR: 'France',
  DE: 'Allemagne', GR: 'Grèce', HU: 'Hongrie', IE: 'Irlande', IT: 'Italie',
  LV: 'Lettonie', LT: 'Lituanie', LU: 'Luxembourg', MT: 'Malte',
  NL: 'Pays-Bas', PL: 'Pologne', PT: 'Portugal', RO: 'Roumanie',
  SK: 'Slovaquie', SI: 'Slovénie', ES: 'Espagne', SE: 'Suède',
  GB: 'Royaume-Uni',
}

export const nomPays = (code) => NOMS_PAYS[code] || code

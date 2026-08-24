import fr from './catalogs/fr.json'
import en from './catalogs/en.json'
import ar from './catalogs/ar.json'

// N93 — le SEUL fichier qui importe les catalogues JSON statiques (isolé de
// `resolve.js` pour que ce dernier reste chargeable par `node --test` sans
// l'attribut d'import `with { type: 'json' }`).
export const CATALOGS = { fr, en, ar }

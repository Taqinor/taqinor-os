// N91/F21/EZ8 — la persistance IndexedDB des files a DÉMÉNAGÉ (NTMOB1) vers
// `src/lib/offlineStore.js` : elle sert désormais tous les modules, pas
// seulement la capture terrain. Réexportation pure — une seule base, un seul
// magasin, jamais deux implémentations.
// Extension EXPLICITE : `node --test` charge ce fichier sans bundler.
export * from '../../../lib/offlineStore.js'

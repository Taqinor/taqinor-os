// N91/F21/EZ8 — le moteur d'outbox a DÉMÉNAGÉ (NTMOB1).
//
// Il n'est plus propre à la capture terrain : la même file sert désormais tous
// les modules (crm, ventes, stock, installations, sav) et vit dans
// `src/lib/offlineOutbox.js`. Ce fichier n'est PAS une seconde implémentation —
// c'est une simple réexportation, pour que les imports terrain existants
// (`fieldOutbox.js`, les tests N91/EZ8) continuent de pointer vers l'UNIQUE
// moteur (décision VX105 : un seul outbox, un seul badge).
// Extension EXPLICITE : `node --test` charge ce fichier sans bundler.
export * from '../../../lib/offlineOutbox.js'

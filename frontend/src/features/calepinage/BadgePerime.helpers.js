// ENF22 — helpers extraits de BadgePerime.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/**
 * `true` UNIQUEMENT si le serveur a AFFIRMÉ la péremption — jamais sur
 * `null`/`undefined`/toute autre valeur que le booléen `true` strict.
 */
export function estPerime(layoutStale) {
  return layoutStale === true
}

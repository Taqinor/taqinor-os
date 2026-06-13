/**
 * Redirections de chemin : anciennes URL et variantes sans accent →
 * équivalent canonique actuel. Module pur (aucun import), testé par
 * tests/redirect.test.ts et copié dans dist/server/ au build (voir
 * astro.config.mjs). Exécuté par le Worker AVANT l'app Astro
 * (run_worker_first sur les routes HTML) — donc avant tout 404, ce qu'un
 * fichier public/_redirects ne garantirait pas avec ce wrapper Worker.
 */

// Chemin exact → { to, status }. Les slugs canoniques du site sont accentués
// (/résidentiel, /équipement) : toute variante sans accent est un 404 réel.
// Les autres entrées couvrent les alias d'atterrissage usuels (best-effort —
// la liste exhaustive viendra des URLs réellement indexées dans Search Console).
const EXACT = {
  '/residentiel': { to: '/résidentiel', status: 301 },
  '/equipement': { to: '/équipement', status: 301 },
  '/home': { to: '/', status: 301 },
  '/accueil': { to: '/', status: 301 },
  '/index.html': { to: '/', status: 301 },
  '/regularisation': { to: '/regularization-article-33', status: 301 },
  '/regularization': { to: '/regularization-article-33', status: 301 },
  '/article-33': { to: '/regularization-article-33', status: 301 },
  '/mentions': { to: '/mentions-legales', status: 301 },
  '/confidentialite': { to: '/politique-de-confidentialite', status: 301 },
  '/privacy': { to: '/politique-de-confidentialite', status: 301 },
};

/**
 * Cible de redirection { target, status } pour une requête, sinon null
 * (la requête continue vers l'app Astro).
 *
 * TEMPORAIRE : l'ancien outil de devis /simulator est réhébergé sur
 * https://simulateur.taqinor.ma, mais ce sous-domaine n'a pas encore de
 * certificat HTTPS valide — on replie donc /simulator* vers /contact en 302.
 * Bascule prévue (one-liner) une fois le certificat en place :
 *   if (path === '/simulator' || path.startsWith('/simulator/'))
 *     return { target: 'https://simulateur.taqinor.ma/' + url.search, status: 301 };
 */
export function pathRedirect(requestUrl) {
  const url = new URL(requestUrl);
  let path = url.pathname;
  if (path.length > 1 && path.endsWith('/')) path = path.slice(0, -1); // tolère la barre finale

  if (path === '/simulator' || path.startsWith('/simulator/')) {
    return { target: url.origin + '/contact' + url.search, status: 302 };
  }

  const hit = EXACT[path];
  if (hit) return { target: url.origin + encodeURI(hit.to) + url.search, status: hit.status };

  return null;
}

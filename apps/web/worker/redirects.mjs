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
 * /simulator : l'ancien outil de devis est réhébergé sur
 * https://simulateur.taqinor.ma (HTTPS valide depuis 2026-06-13, app servie
 * sous /simulator/). On redirige en 301 permanent en PRÉSERVANT le chemin —
 * /simulator/login → https://simulateur.taqinor.ma/simulator/login.
 */
export function pathRedirect(requestUrl) {
  const url = new URL(requestUrl);
  let path = url.pathname;
  if (path.length > 1 && path.endsWith('/')) path = path.slice(0, -1); // tolère la barre finale

  if (path === '/simulator' || path.startsWith('/simulator/')) {
    // chemin original conservé (url.pathname, pas la version sans barre finale)
    return { target: 'https://simulateur.taqinor.ma' + url.pathname + url.search, status: 301 };
  }

  const hit = EXACT[path];
  if (hit) return { target: url.origin + encodeURI(hit.to) + url.search, status: hit.status };

  return null;
}

/**
 * Canonicalisation de la barre finale : forme canonique = AVEC barre finale
 * (les <link rel="canonical"> et le sitemap émettent déjà cette forme). On 301 la
 * forme sans barre → avec barre, pour les pages HTML uniquement.
 *
 * EXEMPTÉ (jamais de barre ajoutée) : requêtes non-GET/HEAD (POST de formulaire),
 * la racine `/`, les chemins DÉJÀ terminés par `/`, les routes d'API `/api/*` (le
 * script et le formulaire live appellent fetch('/api/…') sans barre — y toucher
 * casserait le lead flow), et tout fichier à extension (sitemap.xml, robots.txt,
 * favicon.svg, assets). N'altère AUCUN contenu : routage seul.
 */
export function trailingSlashRedirect(requestUrl, method = 'GET') {
  if (method !== 'GET' && method !== 'HEAD') return null;
  const url = new URL(requestUrl);
  const p = url.pathname;
  if (p === '/' || p.endsWith('/')) return null;
  if (p === '/api' || p.startsWith('/api/')) return null;
  const lastSegment = p.slice(p.lastIndexOf('/') + 1);
  if (lastSegment.includes('.')) return null; // fichier à extension → pas de barre
  return { target: url.origin + p + '/' + url.search, status: 301 };
}

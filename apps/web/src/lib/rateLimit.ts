/**
 * Limiteur de débit léger pour les endpoints de lead (ERR112).
 *
 * But : empêcher le spam scriptable (POST en boucle vers /api/simulate et
 * /api/preview-lead → injection dans le CRM / la CAPI / WhatsApp) SANS
 * nouvelle dépendance, NI nouveau secret, NI CAPTCHA.
 *
 * Stratégie : fenêtre glissante par IP, comptage en MÉMOIRE (Map au niveau du
 * module). Aucune liaison KV/Durable Object n'existe dans ce Worker
 * (wrangler.jsonc), donc le store durable n'est pas disponible — on fait du
 * « best-effort ».
 *
 * LIMITATION ASSUMÉE (documentée) : le compteur vit dans l'isolat Worker
 * courant. Cloudflare peut router des requêtes vers plusieurs isolats et
 * recycler les isolats (cold start), donc ce limiteur n'est PAS un quota global
 * strict : il écrête le spam à fort volume depuis une même IP frappant le même
 * isolat, mais ne garantit pas un plafond global. C'est un garde-fou non
 * cassant, pas une protection anti-DDoS (Cloudflare s'en charge en amont). Le
 * remplacer par un quota durable nécessiterait une liaison KV/DO (= nouveau
 * binding, suivi séparé) — volontairement hors périmètre ici.
 *
 * Le module est pur et testable : l'horloge est injectable (`now`) et le store
 * est réinitialisable (`resetRateLimit`) pour les tests.
 */

export interface RateLimitOptions {
  /** Nombre de requêtes autorisées par fenêtre et par clé. */
  limit?: number;
  /** Durée de la fenêtre en millisecondes. */
  windowMs?: number;
  /** Horloge injectable (tests). Par défaut Date.now(). */
  now?: () => number;
}

export interface RateLimitResult {
  allowed: boolean;
  /** Requêtes restantes dans la fenêtre courante (≥ 0). */
  remaining: number;
  /** Nombre de secondes avant réouverture (pour l'en-tête Retry-After). */
  retryAfterSec: number;
}

// Valeurs par défaut : généreuses pour un humain, serrées pour un script.
export const DEFAULT_RATE_LIMIT = 8;
export const DEFAULT_WINDOW_MS = 60_000; // 1 minute

interface Bucket {
  count: number;
  resetAt: number; // timestamp (ms) de fin de la fenêtre courante
}

const store = new Map<string, Bucket>();

/** Vide le store (tests uniquement). */
export function resetRateLimit(): void {
  store.clear();
}

/**
 * Enregistre une requête pour `key` et indique si elle est autorisée. Effet de
 * bord borné : on purge paresseusement les buckets expirés à chaque appel et on
 * plafonne la taille du store pour éviter une croissance non bornée en mémoire.
 */
export function rateLimit(key: string, opts: RateLimitOptions = {}): RateLimitResult {
  const limit = opts.limit ?? DEFAULT_RATE_LIMIT;
  const windowMs = opts.windowMs ?? DEFAULT_WINDOW_MS;
  const now = (opts.now ?? Date.now)();

  // Purge paresseuse + garde-fou mémoire (best-effort, pas de timer).
  if (store.size > 5000) {
    for (const [k, b] of store) if (b.resetAt <= now) store.delete(k);
  }

  let bucket = store.get(key);
  if (!bucket || bucket.resetAt <= now) {
    bucket = { count: 0, resetAt: now + windowMs };
    store.set(key, bucket);
  }

  bucket.count += 1;
  const retryAfterSec = Math.max(0, Math.ceil((bucket.resetAt - now) / 1000));
  if (bucket.count > limit) {
    return { allowed: false, remaining: 0, retryAfterSec };
  }
  return { allowed: true, remaining: Math.max(0, limit - bucket.count), retryAfterSec };
}

/**
 * Extrait une IP cliente d'une requête Cloudflare. `CF-Connecting-IP` est posée
 * par Cloudflare et n'est pas falsifiable par le client (contrairement à
 * `X-Forwarded-For` que l'on n'utilise qu'en dernier recours, dev local). Sans
 * IP identifiable on retombe sur une clé partagée 'unknown' : tous les clients
 * anonymes partagent alors un seul bucket (fail-safe : on préfère écrêter un peu
 * plus large plutôt que laisser passer un flot illimité).
 */
export function clientIpFromRequest(request: Request): string {
  const cf = request.headers.get('cf-connecting-ip');
  if (cf) return cf.trim();
  const xff = request.headers.get('x-forwarded-for');
  if (xff) return xff.split(',')[0].trim();
  return 'unknown';
}

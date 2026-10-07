/**
 * Logique du rapport d'erreurs du navigateur (YBW20), testable seule.
 * Route : src/pages/api/client-error.ts ; émetteur : src/scripts/client-error.ts.
 *
 * AUCUNE donnée personnelle : pas d'IP, pas d'agent, pas de requête d'URL ;
 * e-mails et longues suites de chiffres masqués dans le message. Taille
 * maximale du corps ; limite par isolat (compteur en mémoire, par minute).
 */

export const TAILLE_MAX = 2048;
export const LIMITE_PAR_MINUTE = 30;

const etat = { fenetre: -1, compte: 0 };

/** Réinitialise le compteur (tests). */
export function reinitialiserLimite(): void {
  etat.fenetre = -1;
  etat.compte = 0;
}

/** Compte un rapport ; vrai si la limite de l'isolat est dépassée. */
export function limiteAtteinte(maintenant: number): boolean {
  const fenetre = Math.floor(maintenant / 60_000);
  if (fenetre !== etat.fenetre) {
    etat.fenetre = fenetre;
    etat.compte = 0;
  }
  etat.compte += 1;
  return etat.compte > LIMITE_PAR_MINUTE;
}

/** Masque ce qui pourrait identifier quelqu'un dans un texte libre, borné. */
export function masquer(texte: string): string {
  return texte
    .replace(/[^\s@]+@[^\s@]+/g, '[masqué]')
    .replace(/\+?\d[\d\s.-]{5,}\d/g, '[masqué]')
    .slice(0, 300);
}

/** Chemin seul (sans origine, requête ni fragment), borné. */
export function cheminSeul(valeur: unknown): string {
  if (typeof valeur !== 'string' || !valeur) return '';
  try {
    return new URL(valeur, 'https://x.invalid').pathname.slice(0, 200);
  } catch {
    return '';
  }
}

function entier(valeur: unknown): number | null {
  return typeof valeur === 'number' && Number.isInteger(valeur) && valeur >= 0 && valeur < 1e7 ? valeur : null;
}

export interface Rapport {
  type: 'error' | 'rejection';
  message: string;
  fichier: string;
  ligne: number | null;
  colonne: number | null;
  page: string;
}

/** Ne garde QUE les champs connus, nettoyés. */
export function nettoyer(corps: Record<string, unknown>): Rapport {
  return {
    type: corps.type === 'rejection' ? 'rejection' : 'error',
    message: masquer(typeof corps.message === 'string' ? corps.message : ''),
    fichier: cheminSeul(corps.fichier),
    ligne: entier(corps.ligne),
    colonne: entier(corps.colonne),
    page: cheminSeul(corps.page),
  };
}

const vide = (status: number) => new Response(null, { status, headers: { 'cache-control': 'no-store' } });

/**
 * Traite `POST /api/client-error` : même origine, taille, limite, JSON ; écrit
 * le rapport nettoyé dans le journal (`journal`, console.warn par défaut).
 */
export async function traiterRapport(
  request: Request,
  journal: (ligne: string) => void = (l) => console.warn('[client-error]', l),
  maintenant: number = Date.now(),
): Promise<Response> {
  if (request.method !== 'POST') return new Response(null, { status: 405, headers: { allow: 'POST' } });
  const site = request.headers.get('sec-fetch-site');
  const origine = request.headers.get('origin');
  const memeOrigine = site ? site === 'same-origin' : origine === null || origine === new URL(request.url).origin;
  if (!memeOrigine) return vide(403);

  if (Number(request.headers.get('content-length') ?? '0') > TAILLE_MAX) return vide(413);
  if (limiteAtteinte(maintenant)) return vide(429);

  const brut = await request.text();
  if (brut.length > TAILLE_MAX) return vide(413);
  let v: unknown;
  try {
    v = JSON.parse(brut);
  } catch {
    return vide(400);
  }
  if (!v || typeof v !== 'object' || Array.isArray(v)) return vide(400);
  journal(JSON.stringify(nettoyer(v as Record<string, unknown>)));
  return vide(204);
}

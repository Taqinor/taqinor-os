/**
 * ENF19 — logique serveur PARTAGÉE par les pages à jeton (/proposition, /questionnaire, /suivi) :
 * une seule copie (garde ACAL345, scripts/check_duplicats_litteraux.py).
 */

/** Statut HTTP de la page quand la lecture a échoué : un jeton invalide/expiré rend 404 (propre pour les bots comme pour les humains). */
export function appliquerStatutToken(reponse: { status?: number }, data: unknown, httpStatus: number): void {
  if (!data && (httpStatus === 404 || httpStatus === 200)) {
    reponse.status = httpStatus === 200 ? 404 : httpStatus;
  } else if (!data) {
    reponse.status = httpStatus;
  }
}

/** Champ `detail` (chaîne) du corps JSON d'un refus de l'API, '' si le corps est illisible. */
export async function detailRefus(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    return typeof body?.detail === 'string' ? body.detail : '';
  } catch {
    return '';
  }
}

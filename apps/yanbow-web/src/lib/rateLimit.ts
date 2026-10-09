/**
 * Limiteur par ISOLAT (YBW54) — compteur en mémoire sur une fenêtre fixe.
 *
 * Jamais par IP : aucune adresse du visiteur n'est lue ni gardée. C'est un
 * frein anti-rafale best-effort (un isolat Worker peut être recyclé à tout
 * moment) ; la limite qui fait foi côté ERP est comptée PAR CLÉ (YBW51).
 */

export interface Limiteur {
  /** Compte une tentative à `maintenant` (ms) ; `ok` faux au-delà de la limite. */
  tenter(maintenant: number): { ok: boolean; retryAfterSec: number };
  /** Remet le compteur à zéro (tests). */
  reinitialiser(): void;
}

export function creerLimiteur(limite: number, fenetreMs: number): Limiteur {
  let fenetre = -1;
  let compte = 0;
  return {
    tenter(maintenant) {
      const f = Math.floor(maintenant / fenetreMs);
      if (f !== fenetre) {
        fenetre = f;
        compte = 0;
      }
      compte += 1;
      const ok = compte <= limite;
      const retryAfterSec = ok ? 0 : Math.max(1, Math.ceil(((f + 1) * fenetreMs - maintenant) / 1000));
      return { ok, retryAfterSec };
    },
    reinitialiser() {
      fenetre = -1;
      compte = 0;
    },
  };
}

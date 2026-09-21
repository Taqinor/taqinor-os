/* ============================================================================
   Paie — logique PURE (statuts + gating de l'assistant de run), sans DOM/JSX.
   ----------------------------------------------------------------------------
   Isolée ici pour être testable sans rendu. Reflète 1:1 le cycle serveur
   (apps/paie/models.py) : la période avance
   brouillon → calculee → validee → cloturee (STRICTEMENT progressif) ; un
   bulletin est brouillon → valide (fige le snapshot). L'assistant UX10
   n'autorise une étape que si la précédente est satisfaite.
   ========================================================================== */

// ── Statuts de PÉRIODE (miroir de PeriodePaie.ORDRE_STATUTS) ──
export const PERIODE_STATUTS = {
  BROUILLON: 'brouillon',
  CALCULEE: 'calculee',
  VALIDEE: 'validee',
  CLOTUREE: 'cloturee',
}
export const PERIODE_ORDRE = [
  PERIODE_STATUTS.BROUILLON,
  PERIODE_STATUTS.CALCULEE,
  PERIODE_STATUTS.VALIDEE,
  PERIODE_STATUTS.CLOTUREE,
]

// ── Statuts de BULLETIN ──
export const BULLETIN_STATUTS = {
  BROUILLON: 'brouillon',
  VALIDE: 'valide',
}

// ── Statuts d'ORDRE DE VIREMENT ──
export const ORDRE_STATUTS = {
  BROUILLON: 'brouillon',
  EMIS: 'emis',
}

// Rang d'un statut de période dans le cycle (−1 si inconnu).
export function periodeRang(statut) {
  return PERIODE_ORDRE.indexOf(statut)
}

// Une période ne peut qu'AVANCER (jamais reculer, jamais sauter en arrière).
export function peutAvancerPeriode(actuel, cible) {
  const a = periodeRang(actuel)
  const c = periodeRang(cible)
  return a >= 0 && c >= 0 && c > a
}

// Le statut immédiatement suivant du cycle (null si déjà clôturée / inconnu).
export function statutSuivant(statut) {
  const r = periodeRang(statut)
  if (r < 0 || r >= PERIODE_ORDRE.length - 1) return null
  return PERIODE_ORDRE[r + 1]
}

// ── Étapes de l'assistant de run (UX10) ──
export const RUN_STEPS = ['periode', 'generer', 'revue', 'valider', 'cloturer']

/* Gating d'étape de l'assistant. Une étape est ACCESSIBLE quand le contexte
   minimal est réuni ; sinon elle est verrouillée avec un motif. `ctx` :
     { periode, bulletins }  (periode : objet|null ; bulletins : tableau)
   Retour : { step -> { unlocked, done, reason } }. */
export function runStepState(ctx = {}) {
  const periode = ctx.periode || null
  const bulletins = Array.isArray(ctx.bulletins) ? ctx.bulletins : []
  const statut = periode?.statut ?? null
  const rang = periodeRang(statut)

  const aBulletins = bulletins.length > 0
  const tousValides = aBulletins &&
    bulletins.every((b) => b.statut === BULLETIN_STATUTS.VALIDE)
  const auMoinsUnValide = bulletins.some(
    (b) => b.statut === BULLETIN_STATUTS.VALIDE,
  )
  const cloturee = statut === PERIODE_STATUTS.CLOTUREE

  return {
    // 1) Créer / ouvrir la période.
    periode: {
      unlocked: true,
      done: !!periode,
      reason: periode ? '' : 'Créez ou sélectionnez une période.',
    },
    // 2) Générer les bulletins (période ouverte, non clôturée).
    generer: {
      unlocked: !!periode && !cloturee,
      done: aBulletins,
      reason: !periode
        ? 'Ouvrez d’abord une période.'
        : cloturee
          ? 'Période clôturée : plus aucun bulletin ne peut être généré.'
          : '',
    },
    // 3) Revue des bruts/nets/écarts (dès qu'il y a des bulletins).
    revue: {
      unlocked: aBulletins,
      done: aBulletins && rang >= periodeRang(PERIODE_STATUTS.CALCULEE),
      reason: aBulletins ? '' : 'Générez d’abord des bulletins à réviser.',
    },
    // 4) Valider (tous les bulletins validés → période validée).
    valider: {
      unlocked: aBulletins && auMoinsUnValide === auMoinsUnValide,
      done: tousValides &&
        rang >= periodeRang(PERIODE_STATUTS.VALIDEE),
      reason: aBulletins
        ? ''
        : 'Aucun bulletin à valider.',
    },
    // 5) Clôturer (verrou) — seulement une période validée.
    cloturer: {
      unlocked: !!periode && rang >= periodeRang(PERIODE_STATUTS.VALIDEE),
      done: cloturee,
      reason: !periode
        ? 'Aucune période.'
        : rang < periodeRang(PERIODE_STATUTS.VALIDEE)
          ? 'Validez la période avant de la clôturer.'
          : '',
    },
  }
}

// Détecte les écarts/anomalies d'un bulletin pour la table de REVUE (UX10 §3).
// Retour : tableau de libellés d'anomalie (vide si RAS).
export function anomaliesBulletin(b = {}) {
  const flags = []
  const brut = num(b.brut)
  const net = num(b.net_a_payer)
  const netImposable = num(b.net_imposable)
  if (brut <= 0) flags.push('Brut nul ou négatif')
  if (net <= 0) flags.push('Net à payer nul ou négatif')
  if (net > brut && brut > 0) flags.push('Net supérieur au brut')
  if (netImposable > brut && brut > 0) {
    flags.push('Net imposable supérieur au brut')
  }
  return flags
}

// Vrai si le run comporte au moins une anomalie à signaler (bloque implicitement
// la sérénité de la validation — l'UI l'affiche, ne l'empêche pas).
export function runAAnomalies(bulletins = []) {
  return (Array.isArray(bulletins) ? bulletins : [])
    .some((b) => anomaliesBulletin(b).length > 0)
}

function num(v) {
  const n = typeof v === 'number' ? v : parseFloat(v)
  return Number.isFinite(n) ? n : 0
}

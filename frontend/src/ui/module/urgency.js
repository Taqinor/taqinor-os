/* ============================================================================
   UX1 — Logique d'échéance / urgence (PURE, sans JSX).
   ----------------------------------------------------------------------------
   Base partagée par tous les modules ERP (contrats, SAV, flotte, QHSE…) pour
   afficher « J-N / En retard » de façon COHÉRENTE et pour trier les échéances
   les plus urgentes en premier. Aucune dépendance React : testable au node.
   ========================================================================== */

const MS_PER_DAY = 24 * 60 * 60 * 1000

/** Nombre de jours (entier) d'aujourd'hui vers `dateInput` (négatif = passé).
    Accepte un Date ou une chaîne ISO ; renvoie null si vide/invalide. On
    calcule sur des jours calendaires (minuit local) pour éviter qu'une échéance
    « demain à 1 h » compte 0 jour à cause des heures. */
export function daysUntil(dateInput, now = new Date()) {
  if (!dateInput) return null
  const target = dateInput instanceof Date ? dateInput : new Date(dateInput)
  if (Number.isNaN(target.getTime())) return null
  const base = now instanceof Date ? now : new Date(now)
  if (Number.isNaN(base.getTime())) return null
  const a = Date.UTC(target.getFullYear(), target.getMonth(), target.getDate())
  const b = Date.UTC(base.getFullYear(), base.getMonth(), base.getDate())
  return Math.round((a - b) / MS_PER_DAY)
}

/** Niveau d'urgence à partir du nombre de jours restants. */
export function urgencyLevel(daysLeft) {
  if (daysLeft === null || daysLeft === undefined || Number.isNaN(daysLeft)) return 'none'
  if (daysLeft < 0) return 'overdue'
  if (daysLeft <= 7) return 'urgent'
  if (daysLeft <= 30) return 'soon'
  return 'ok'
}

/** Ton (StatusPill / Badge) associé à un niveau d'urgence. */
export function urgencyTone(level) {
  switch (level) {
    case 'overdue':
      return 'danger'
    case 'urgent':
      return 'danger'
    case 'soon':
      return 'warning'
    case 'ok':
      return 'success'
    default:
      return 'neutral'
  }
}

/** Libellé français court : « En retard (J+N) » · « Aujourd'hui » · « J-N » · « — ». */
export function urgencyLabel(daysLeft) {
  if (daysLeft === null || daysLeft === undefined || Number.isNaN(daysLeft)) return '—'
  if (daysLeft < 0) return `En retard (J+${Math.abs(daysLeft)})`
  if (daysLeft === 0) return "Aujourd'hui"
  return `J-${daysLeft}`
}

/** Extrait le nombre de jours restants d'un objet {daysLeft} OU d'un nombre brut. */
function daysOf(x) {
  if (typeof x === 'number') return x
  if (x && typeof x === 'object') return x.daysLeft
  return null
}

/** Comparateur pour `.sort` : jours restants croissants (les plus urgents en
    premier), valeurs nulles/absentes en dernier. Accepte des objets {daysLeft}
    ou des nombres bruts. */
export function compareUrgency(a, b) {
  const da = daysOf(a)
  const db = daysOf(b)
  const na = da === null || da === undefined || Number.isNaN(da)
  const nb = db === null || db === undefined || Number.isNaN(db)
  if (na && nb) return 0
  if (na) return 1 // nulls en dernier
  if (nb) return -1
  return da - db
}

export default {
  daysUntil,
  urgencyLevel,
  urgencyTone,
  urgencyLabel,
  compareUrgency,
}

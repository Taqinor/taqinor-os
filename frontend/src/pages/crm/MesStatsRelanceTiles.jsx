// CKP4 (fondateur 2026-09-10) — 3 tuiles PERSO du commercial, en tête du
// Cockpit : à faire maintenant / mon à-l'heure 7 j / série sans retard.
// JAMAIS comparatives (un rep voit SES chiffres, pas un classement — même
// esprit que HBR anti-surveillance cité au Groupe CKP) ; mêmes données
// visibles par le manager (décision transparence, MRY29/KpiRelancesPanel
// reste le panneau d'ÉQUIPE, distinct de celui-ci). Dénominateur nul → « pas
// encore de données », jamais un 0 % inventé.
import { useEffect, useState } from 'react'
import crmApi from '../../api/crmApi'
import { Spinner } from '../../ui'

const AUCUNE_DONNEE = 'pas encore de données'

// `null`/`undefined` (dénominateur 0 côté serveur) → texte honnête ; un 0
// réel (série de 0 jour, 0 % réel) reste affiché TEL QUEL, jamais confondu.
const valeur = (v) => (v === null || v === undefined ? AUCUNE_DONNEE : String(v))
const pourcentage = (v) => (v === null || v === undefined ? AUCUNE_DONNEE : `${v} %`)

function Tuile({ label, value }) {
  const vide = value === AUCUNE_DONNEE
  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <span className="block text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className={vide
        ? 'text-sm text-muted-foreground'
        : 'font-display text-xl font-semibold tabular-nums'}
      >
        {value}
      </span>
    </div>
  )
}

export default function MesStatsRelanceTiles() {
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [stats, setStats] = useState(null)

  useEffect(() => {
    let active = true
    queueMicrotask(() => { if (active) { setLoading(true); setErreur(false) } })
    crmApi.getMesStatsRelance()
      .then((r) => { if (active) setStats(r.data) })
      .catch(() => { if (active) setErreur(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  if (loading) return <Spinner />
  if (erreur) {
    return <p className="text-sm text-muted-foreground">Indisponible pour le moment.</p>
  }

  return (
    <div
      className="grid grid-cols-1 gap-3 sm:grid-cols-3"
      data-testid="mes-stats-relance-tuiles"
    >
      <Tuile label="À faire maintenant" value={valeur(stats?.a_faire_maintenant)} />
      <Tuile label="Mon à-l'heure (7 j)" value={pourcentage(stats?.a_lheure_7j_pct)} />
      <Tuile label="Série sans retard" value={valeur(stats?.serie_jours_sans_retard)} />
    </div>
  )
}

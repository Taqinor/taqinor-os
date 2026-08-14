import { useEffect, useState } from 'react'
import marketingApi from '../../../api/marketingApi'

/* NTMKT18/19 — badge chaud/tiède/froid + sparkline du score de MATURITÉ
   marketing d'un lead (distinct du score de QUALITÉ QJ6, déjà affiché
   ailleurs sur la fiche — jamais mélangé ici).

   Rien n'est affiché si le module est désactivé pour la société
   (`actif=false`, comportement par défaut — `ParametresMarketing
   .score_maturite_actif`) : jamais un badge à 0 trompeur. Défensif comme
   `SalleVenteAnalyticsBadge` : un mock partiel de `marketingApi` (courant
   dans les tests existants) ne doit jamais faire planter la fiche. */
function niveauMaturite(valeur) {
  if (valeur >= 70) return { label: 'Chaud', className: 'lw-maturite-chaud' }
  if (valeur >= 30) return { label: 'Tiède', className: 'lw-maturite-tiede' }
  return { label: 'Froid', className: 'lw-maturite-froid' }
}

// Sparkline SVG minimaliste maison (aucune dépendance) : les dernières
// valeurs de l'historique, du plus ancien au plus récent.
function sparklinePath(points, largeur, hauteur) {
  if (points.length < 2) return ''
  return points
    .map((v, i) => {
      const x = (i / (points.length - 1)) * largeur
      const y = hauteur - (Math.max(0, Math.min(100, v)) / 100) * hauteur
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

export default function LeadMaturiteBadge({ leadId }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    let active = true
    // setState différé au prochain microtask (jamais synchrone dans l'effet).
    queueMicrotask(() => {
      if (!active) return
      if (!leadId || typeof marketingApi?.scoreMaturite?.get !== 'function') {
        setData(null)
        return
      }
      marketingApi.scoreMaturite.get(leadId)
        .then((r) => { if (active) setData(r.data ?? null) })
        .catch(() => { if (active) setData(null) })
    })
    return () => { active = false }
  }, [leadId])

  if (!data || !data.actif) return null

  const niveau = niveauMaturite(data.valeur)
  // L'API renvoie l'historique du plus RÉCENT au plus ANCIEN — la sparkline
  // se lit chronologiquement (ancien -> récent).
  const points = [...(data.historique || [])].reverse().map((v) => v.valeur_apres)
  const largeur = 60
  const hauteur = 18
  const path = sparklinePath(points, largeur, hauteur)

  return (
    <div
      className={`lw-maturite-badge ${niveau.className}`}
      data-testid="lead-maturite-badge"
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        borderRadius: 6, padding: '2px 8px', fontSize: 12,
        border: '1px solid #e2e8f0',
      }}
      title={`Score de maturité marketing : ${data.valeur}/100`}
    >
      <span>{niveau.label} · {data.valeur}</span>
      {path && (
        <svg width={largeur} height={hauteur} aria-hidden="true" role="presentation">
          <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
      )}
    </div>
  )
}

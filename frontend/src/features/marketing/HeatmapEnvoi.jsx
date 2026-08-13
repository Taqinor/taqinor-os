import { useEffect, useState } from 'react'
import marketingApi from '../../api/marketingApi'

/* ============================================================================
   NTMKT24 — Heatmap d'engagement hebdomadaire par heure d'envoi.
   ----------------------------------------------------------------------------
   Purement INFORMATIF pendant la planification d'une campagne : « vos contacts
   ouvrent le plus mardi 10h ». Ne bloque jamais l'envoi choisi et n'écrit
   rien — les données viennent du sélecteur serveur (historique réel
   `EnvoiCampagne` de la société). Société sans historique = état vide propre.
   ========================================================================== */

export const JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi',
  'Samedi', 'Dimanche']

/** Libellé de suggestion, ou '' si l'historique ne permet rien d'affirmer. */
export function libelleMeilleurCreneau(meilleur) {
  if (!meilleur || !meilleur.envois) return ''
  const jour = JOURS[meilleur.jour] || ''
  const pct = Math.round((meilleur.taux_ouverture || 0) * 100)
  return `Vos contacts ouvrent le plus ${jour.toLowerCase()} ${meilleur.heure}h (${pct} % d'ouverture)`
}

/** Intensité 0-1 d'une case, relative au meilleur taux observé. */
export function intensite(cellule, maxTaux) {
  if (!maxTaux) return 0
  return Math.min(1, (cellule?.taux_ouverture || 0) / maxTaux)
}

export default function HeatmapEnvoi() {
  const [donnees, setDonnees] = useState(null)
  const [chargement, setChargement] = useState(true)

  useEffect(() => {
    let vivant = true
    marketingApi.heatmapEngagement()
      .then(res => { if (vivant) setDonnees(res?.data || null) })
      .catch(() => { if (vivant) setDonnees(null) })
      .finally(() => { if (vivant) setChargement(false) })
    return () => { vivant = false }
  }, [])

  if (chargement) return <p>Chargement de l'historique d'ouverture…</p>
  const cellules = donnees?.cellules || []
  if (cellules.length === 0) {
    return (
      <p data-testid="heatmap-vide">
        Pas encore assez d'historique d'envoi pour suggérer un créneau.
      </p>
    )
  }
  const maxTaux = cellules.reduce(
    (m, c) => Math.max(m, c.taux_ouverture || 0), 0)
  const parCle = {}
  cellules.forEach(c => { parCle[`${c.jour}-${c.heure}`] = c })
  const heures = [...new Set(cellules.map(c => c.heure))].sort((a, b) => a - b)

  return (
    <div className="heatmap-envoi">
      <p data-testid="heatmap-suggestion">
        {libelleMeilleurCreneau(donnees?.meilleur)}
      </p>
      <table className="data-table" data-testid="heatmap-table">
        <thead>
          <tr>
            <th />
            {heures.map(h => <th key={h}>{h}h</th>)}
          </tr>
        </thead>
        <tbody>
          {JOURS.map((jour, index) => (
            <tr key={jour}>
              <th scope="row">{jour}</th>
              {heures.map(h => {
                const c = parCle[`${index}-${h}`]
                return (
                  <td key={h}
                    title={c ? `${c.ouvertures}/${c.envois} ouverts` : 'aucun envoi'}
                    style={{
                      background: c
                        ? `rgba(37, 99, 235, ${intensite(c, maxTaux)})`
                        : 'transparent',
                    }}>
                    {c ? `${Math.round((c.taux_ouverture || 0) * 100)}%` : '—'}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

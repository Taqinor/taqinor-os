import { useEffect, useState } from 'react'
import { Zap } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import { Card, EmptyState, Spinner } from '../../../ui'
import { formatDate } from '../../../lib/format'

/* ============================================================================
   ADOC140 (D-ADOC-1) — « Ma consommation » du portail client.
   ----------------------------------------------------------------------------
   Contrat `ma_consommation.json` : série de production (une entrée par jour
   AYANT un relevé), alertes de sous-performance OUVERTES, `provider_configure`.
   Chaque valeur est affichée TELLE QUE SERVIE (`energy_kwh` est un texte déjà
   quantifié) — aucun chiffre recalculé. Sans suivi raccordé
   (`provider_configure:false`) : un message, jamais un graphique vide.
   `?chantier=<id>` borne les alertes au site choisi (la série reste
   l'agrégat du client).
   ========================================================================== */

export default function PortailClientConsommation() {
  const [chantiers, setChantiers] = useState([])
  const [chantier, setChantier] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)

  useEffect(() => {
    portailApi.chantiers.liste()
      .then((r) => setChantiers(r.data?.results ?? []))
      .catch(() => setChantiers([]))
  }, [])

  useEffect(() => {
    let annule = false
    Promise.resolve().then(() => {
      if (annule) return null
      setLoading(true)
      return portailApi.consommation(chantier ? { chantier } : {})
    }).then((r) => { if (r && !annule) { setData(r.data); setErreur(false) } })
      .catch(() => { if (!annule) setErreur(true) })
      .finally(() => { if (!annule) setLoading(false) })
    return () => { annule = true }
  }, [chantier])

  if (loading && !data) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement de votre consommation…
      </div>
    )
  }

  if (erreur || !data) {
    return (
      <EmptyState
        title="Consommation indisponible"
        description="Vos données n’ont pas pu être chargées. Réessayez plus tard."
      />
    )
  }

  const alertes = data.alertes_ouvertes
  const points = data.points ?? []

  return (
    <>
      <div className="flex items-center gap-2">
        <Zap className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Ma consommation
        </h1>
      </div>

      {chantiers.length > 1 && (
        <label className="flex flex-col gap-1.5 text-sm">
          Site
          <select value={chantier} onChange={(e) => setChantier(e.target.value)}
                  className="h-9 rounded-md border border-border bg-background px-2">
            <option value="">Tous mes sites</option>
            {chantiers.map((c) => (
              <option key={c.id} value={c.id}>{c.reference}</option>
            ))}
          </select>
        </label>
      )}

      <p className="text-sm" data-testid="consommation-alertes">
        {alertes === 0
          ? 'Aucune alerte ouverte'
          : `${alertes} alerte${alertes > 1 ? 's' : ''} ouverte${alertes > 1 ? 's' : ''}`}
      </p>

      {!data.provider_configure ? (
        <EmptyState
          title="Suivi de production non raccordé"
          description="Le suivi de production de votre installation n’est pas encore raccordé."
        />
      ) : points.length === 0 ? (
        <EmptyState
          title="Aucun relevé"
          description={`Aucun relevé de production sur les ${data.window_days} derniers jours.`}
        />
      ) : (
        <Card className="p-4">
          <p className="mb-2 text-sm text-muted-foreground">
            Production des {data.window_days} derniers jours
          </p>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-muted-foreground">
                <th className="py-1 font-normal">Date</th>
                <th className="py-1 text-right font-normal">Production (kWh)</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.date}>
                  <td className="py-1">{formatDate(p.date)}</td>
                  <td className="py-1 text-right">{p.energy_kwh}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}

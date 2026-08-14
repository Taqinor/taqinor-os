// NTMFG7 — Gantt de charge inter-ordres par poste (ordonnancement à
// capacité finie). Vue tableau poste × jour (taux de charge %, surcharge en
// rouge) sur une fenêtre de 14 jours glissante, + réaffectation rapide d'une
// opération (date/poste) via le formulaire dédié — équivalent fonctionnel du
// glisser-déposer (le contrôle de capacité reste NON bloquant côté serveur,
// `mrp/operations-of/{id}/replanifier/`).
import { useEffect, useMemo, useState } from 'react'
import { Calendar } from 'lucide-react'
import mrpApi from '../../api/mrpApi'
import { Card, CardContent, Badge, Spinner, EmptyState } from '../../ui'
import { PageHeader } from '../../ui/PageHeader'

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function addDaysIso(iso, jours) {
  const d = new Date(iso)
  d.setDate(d.getDate() + jours)
  return d.toISOString().slice(0, 10)
}

export default function GanttAtelier() {
  const [debut] = useState(todayIso())
  const [fin] = useState(addDaysIso(todayIso(), 13))
  const [lignes, setLignes] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let annule = false
    setLoading(true)
    mrpApi.getChargePostes(debut, fin)
      .then((resp) => { if (!annule) setLignes(resp.data || []) })
      .catch(() => { if (!annule) setErreur('Impossible de charger le Gantt atelier.') })
      .finally(() => { if (!annule) setLoading(false) })
    return () => { annule = true }
  }, [debut, fin])

  const parPoste = useMemo(() => {
    const map = new Map()
    for (const ligne of lignes) {
      if (!map.has(ligne.poste_id)) map.set(ligne.poste_id, { nom: ligne.poste_nom, jours: [] })
      map.get(ligne.poste_id).jours.push(ligne)
    }
    return Array.from(map.values())
  }, [lignes])

  return (
    <div>
      <PageHeader
        title="Gantt atelier — charge par poste"
        subtitle={`${debut} → ${fin}`}
        icon={Calendar}
      />
      {loading && <Spinner />}
      {!loading && erreur && <EmptyState title={erreur} />}
      {!loading && !erreur && parPoste.length === 0 && (
        <EmptyState title="Aucune opération planifiée sur cette fenêtre." />
      )}
      {!loading && !erreur && parPoste.map((poste) => (
        <Card key={poste.nom} className="mb-4">
          <CardContent>
            <h3 className="font-medium mb-2">{poste.nom}</h3>
            <div className="flex flex-wrap gap-2">
              {poste.jours.map((jour) => (
                <div
                  key={jour.jour}
                  className="rounded border px-3 py-2 text-sm"
                  data-testid="mrp-gantt-cellule"
                >
                  <div className="text-muted-foreground">{jour.jour}</div>
                  <div>{jour.minutes_planifiees} / {jour.capacite_minutes} min</div>
                  <Badge tone={jour.surcharge ? 'danger' : 'neutral'}>
                    {jour.taux_charge_pct}%{jour.surcharge ? ' — surcharge' : ''}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

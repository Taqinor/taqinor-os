import { useEffect, useState } from 'react'
import { PieChart, Pie, Cell, Tooltip as RTooltip, ResponsiveContainer } from 'recharts'
import coreApi from '../../api/coreApi'
import { Button } from '../../ui'
import { toast } from '../../ui/confirm'
import { ChartEmpty, ChartTooltip, resolveColor } from '../../ui/charts'

/* NTI18N53 — widget « Répartition des clients par langue documentaire ».
   Se configure dans le `layout` d'un `core.Dashboard` existant (aucun nouveau
   modèle) : le bouton ajoute `{ type: 'repartition_langue_clients' }` à
   `layout.widgets` ; les comptes viennent de `GET /core/dashboards/{id}/donnees/`
   (company-scopé serveur, relus à chaque ouverture — aucun cache). */

// Miroir de core.dashboard_data.TYPE_REPARTITION_LANGUE (type de widget serveur).
export const TYPE_REPARTITION_LANGUE = 'repartition_langue_clients'
const TITRE = 'Répartition des clients par langue documentaire'
const LIBELLES = { fr: 'Français', ar: 'Arabe', en: 'Anglais' }
const TONS = { fr: 'primary', ar: 'success', en: 'warning' }

export default function RepartitionLangueWidget({ dashboardId, layout, onLayoutChange }) {
  const widgets = Array.isArray(layout?.widgets) ? layout.widgets : []
  const present = widgets.some((w) => w?.type === TYPE_REPARTITION_LANGUE)
  const [resultat, setResultat] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!present || !dashboardId) return undefined
    let active = true
    coreApi.dashboards.donnees(dashboardId)
      .then((r) => {
        if (!active) return
        const w = (r.data?.widgets || []).find((x) => x.type === TYPE_REPARTITION_LANGUE)
        setResultat(w || null)
      })
      .catch(() => { if (active) setResultat({ erreur: 'Données indisponibles.' }) })
    return () => { active = false }
  }, [present, dashboardId])

  const ajouter = async () => {
    const nextLayout = {
      ...(layout || {}),
      widgets: [...widgets, { id: 'repartition_langue', type: TYPE_REPARTITION_LANGUE, titre: TITRE }],
    }
    setSaving(true)
    try {
      await coreApi.dashboards.updateLayout(dashboardId, nextLayout)
      onLayoutChange?.(nextLayout)
      toast.success('Widget ajouté au tableau de bord.')
    } catch {
      toast.error('Le widget n’a pas pu être ajouté.')
    } finally {
      setSaving(false)
    }
  }

  if (!present) {
    return (
      <div>
        <Button variant="outline" size="sm" onClick={ajouter} loading={saving}>
          Ajouter le widget « {TITRE} »
        </Button>
      </div>
    )
  }

  const data = (resultat?.rows || [])
    .filter((r) => r.nombre > 0)
    .map((r) => ({ name: LIBELLES[r.langue] || r.langue, value: r.nombre, tone: TONS[r.langue] || 'muted' }))

  return (
    <div className="flex flex-col gap-2" data-testid="widget-repartition-langue">
      <span className="text-sm font-semibold">{resultat?.titre || TITRE}</span>
      {resultat?.erreur ? (
        <span className="text-sm text-destructive">{resultat.erreur}</span>
      ) : data.length === 0 ? (
        <ChartEmpty title="Aucun client" />
      ) : (
        <>
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" outerRadius={80} isAnimationActive={false}>
                {data.map((d) => <Cell key={d.name} fill={resolveColor(d.tone)} />)}
              </Pie>
              <RTooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap justify-center gap-3 text-xs text-muted-foreground">
            {(resultat?.rows || []).map((r) => (
              <span key={r.langue}>{`${LIBELLES[r.langue] || r.langue} : ${r.nombre}`}</span>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

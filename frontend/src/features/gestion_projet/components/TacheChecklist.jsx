import { useCallback, useEffect, useState } from 'react'
import { Check, Square, CheckSquare } from 'lucide-react'
import { Spinner } from '../../../ui'
import gestionProjetApi from '../../../api/gestionProjetApi'

/* XPRJ14 — Checklist d'une tâche : bascule `fait` via l'action serveur
   dédiée (`toggle`, qui pose fait_par/fait_le côté serveur). Composant
   autonome (fetch ses propres items), pensé pour s'insérer dans une carte
   kanban ou un panneau de détail sans logique dupliquée côté parent. */

export default function TacheChecklist({ tacheId }) {
  const [items, setItems] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(async () => {
    try {
      const res = await gestionProjetApi.getItemsChecklist({ tache: tacheId })
      setItems(Array.isArray(res.data) ? res.data : res.data?.results ?? [])
    } catch {
      setItems([])
    }
  }, [tacheId])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load() })()
    return () => { alive = false }
  }, [load])

  const toggle = async (item) => {
    setBusyId(item.id)
    const ancien = item.fait
    setItems((rows) => rows.map((r) => (r.id === item.id ? { ...r, fait: !ancien } : r)))
    try {
      const res = await gestionProjetApi.toggleItemChecklist(item.id)
      setItems((rows) => rows.map((r) => (r.id === item.id ? res.data : r)))
    } catch {
      setItems((rows) => rows.map((r) => (r.id === item.id ? { ...r, fait: ancien } : r)))
    } finally {
      setBusyId(null)
    }
  }

  if (items === null) return <div className="flex justify-center p-2"><Spinner /></div>
  if (items.length === 0) return null

  return (
    <ul className="mt-2 flex flex-col gap-1" aria-label="Checklist de la tâche">
      {items.map((item) => {
        const Icon = item.fait ? CheckSquare : Square
        return (
          <li key={item.id}>
            <button
              type="button"
              className="flex w-full items-center gap-1.5 text-left text-xs"
              disabled={busyId === item.id}
              onClick={() => toggle(item)}
            >
              <Icon className={`size-3.5 shrink-0 ${item.fait ? 'text-success' : 'text-muted-foreground'}`} aria-hidden="true" />
              <span className={item.fait ? 'text-muted-foreground line-through' : ''}>{item.libelle}</span>
              {item.fait && <Check className="ml-auto size-3 shrink-0 text-success" aria-hidden="true" />}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

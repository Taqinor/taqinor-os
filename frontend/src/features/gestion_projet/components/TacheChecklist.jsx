import { useCallback, useEffect, useState } from 'react'
import { Check, Square, CheckSquare, Trash2 } from 'lucide-react'
import { Spinner } from '../../../ui'
import gestionProjetApi from '../../../api/gestionProjetApi'

/* XPRJ14 — Checklist d'une tâche : bascule `fait` via l'action serveur
   dédiée (`toggle`, qui pose fait_par/fait_le côté serveur). Composant
   autonome (fetch ses propres items), pensé pour s'insérer dans une carte
   kanban ou un panneau de détail sans logique dupliquée côté parent.

   WIR246 — la checklist était morte en pratique : sur une tâche sans item le
   composant faisait `return null`, et AUCUN écran ne permettait d'en ajouter
   un — donc elle ne pouvait jamais sortir de l'état vide. La ligne « Ajouter
   un item » remplace ce `return null` ; la suppression est optimiste avec
   rollback, comme la bascule. `company`/`fait_par`/`fait_le` restent serveur. */

export default function TacheChecklist({ tacheId }) {
  const [items, setItems] = useState(null)
  const [busyId, setBusyId] = useState(null)
  // WIR246 — saisie d'un nouvel item.
  const [nouveau, setNouveau] = useState('')
  const [ajoutBusy, setAjoutBusy] = useState(false)

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

  // WIR246 — suppression d'un item : optimiste + rollback si le serveur refuse.
  const supprimer = async (item) => {
    setBusyId(item.id)
    const avant = items
    setItems((rows) => rows.filter((r) => r.id !== item.id))
    try {
      await gestionProjetApi.deleteItemChecklist(item.id)
    } catch {
      setItems(avant)
    } finally {
      setBusyId(null)
    }
  }

  const ajouter = async (e) => {
    e.preventDefault()
    const libelle = nouveau.trim()
    if (!libelle) return
    setAjoutBusy(true)
    try {
      const res = await gestionProjetApi.createItemChecklist({
        tache: tacheId, libelle,
      })
      setNouveau('')
      setItems((rows) => [...(rows ?? []), res.data])
    } catch {
      // Le serveur a refusé : on recharge pour ne jamais afficher un item
      // qui n'existe pas.
      await load()
    } finally {
      setAjoutBusy(false)
    }
  }

  if (items === null) return <div className="flex justify-center p-2"><Spinner /></div>

  return (
    <div className="mt-2 flex flex-col gap-1">
      <ul className="flex flex-col gap-1" aria-label="Checklist de la tâche">
      {items.map((item) => {
        const Icon = item.fait ? CheckSquare : Square
        return (
          <li key={item.id} className="flex items-center gap-1">
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
            <button
              type="button"
              className="shrink-0 text-muted-foreground hover:text-destructive"
              aria-label={`Supprimer « ${item.libelle} »`}
              disabled={busyId === item.id}
              onClick={() => supprimer(item)}
            >
              <Trash2 className="size-3.5" aria-hidden="true" />
            </button>
          </li>
        )
      })}
      </ul>
      <form onSubmit={ajouter} className="flex items-center gap-1">
        <input
          type="text"
          value={nouveau}
          onChange={(e) => setNouveau(e.target.value)}
          placeholder="Ajouter un item…"
          aria-label="Ajouter un item"
          className="h-7 w-full rounded-md border border-border bg-card px-2 text-xs"
        />
        <button
          type="submit"
          disabled={!nouveau.trim() || ajoutBusy}
          className="h-7 shrink-0 rounded-md border border-border px-2 text-xs"
        >
          {ajoutBusy ? '…' : 'Ajouter'}
        </button>
      </form>
    </div>
  )
}

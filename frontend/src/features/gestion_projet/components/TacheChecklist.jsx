import { useCallback, useEffect, useState } from 'react'
import { Check, Square, CheckSquare, Plus, Trash2 } from 'lucide-react'
import { Input, Spinner, toast } from '../../../ui'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage } from '../constants'

/* XPRJ14 — Checklist d'une tâche : bascule `fait` via l'action serveur
   dédiée (`toggle`, qui pose fait_par/fait_le côté serveur). Composant
   autonome (fetch ses propres items), pensé pour s'insérer dans une carte
   kanban ou un panneau de détail sans logique dupliquée côté parent.

   WIR246 — jusqu'ici morte en pratique : le composant se masquait
   entièrement (`return null`) dès qu'une tâche n'avait aucun item, sans
   aucun moyen d'en créer un. La ligne « Ajouter un item » (createItemChecklist)
   reste visible même à vide ; chaque item est supprimable (deleteItemChecklist,
   optimiste + rollback serveur en cas d'échec). */

export default function TacheChecklist({ tacheId }) {
  const [items, setItems] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [nouveauLibelle, setNouveauLibelle] = useState('')
  const [ajoutEnCours, setAjoutEnCours] = useState(false)

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

  const ajouter = async () => {
    const libelle = nouveauLibelle.trim()
    if (!libelle || ajoutEnCours) return
    setAjoutEnCours(true)
    try {
      const res = await gestionProjetApi.createItemChecklist({ tache: tacheId, libelle })
      setItems((rows) => [...(rows ?? []), res.data])
      setNouveauLibelle('')
    } catch (err) {
      toast.error(errMessage(err, "Impossible d'ajouter l'item."))
    } finally {
      setAjoutEnCours(false)
    }
  }

  const supprimer = async (item) => {
    const avant = items
    setItems((rows) => rows.filter((r) => r.id !== item.id))
    try {
      await gestionProjetApi.deleteItemChecklist(item.id)
    } catch (err) {
      setItems(avant)
      toast.error(errMessage(err, "Suppression impossible."))
    }
  }

  if (items === null) return <div className="flex justify-center p-2"><Spinner /></div>

  return (
    <div className="mt-2">
      {items.length > 0 && (
        <ul className="flex flex-col gap-1" aria-label="Checklist de la tâche">
          {items.map((item) => {
            const Icon = item.fait ? CheckSquare : Square
            return (
              <li key={item.id} className="flex items-center gap-1">
                <button
                  type="button"
                  className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-xs"
                  disabled={busyId === item.id}
                  onClick={() => toggle(item)}
                >
                  <Icon className={`size-3.5 shrink-0 ${item.fait ? 'text-success' : 'text-muted-foreground'}`} aria-hidden="true" />
                  <span className={`truncate ${item.fait ? 'text-muted-foreground line-through' : ''}`}>{item.libelle}</span>
                  {item.fait && <Check className="size-3 shrink-0 text-success" aria-hidden="true" />}
                </button>
                <button
                  type="button"
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                  aria-label={`Supprimer « ${item.libelle} »`}
                  onClick={() => supprimer(item)}
                >
                  <Trash2 className="size-3" aria-hidden="true" />
                </button>
              </li>
            )
          })}
        </ul>
      )}
      <div className="mt-1 flex items-center gap-1">
        <Input
          className="h-6 text-xs"
          placeholder="Ajouter un item…"
          aria-label="Nouvel item de checklist"
          value={nouveauLibelle}
          onChange={(e) => setNouveauLibelle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') { e.preventDefault(); ajouter() }
          }}
          disabled={ajoutEnCours}
        />
        <button
          type="button"
          className="shrink-0 text-muted-foreground hover:text-foreground disabled:opacity-50"
          aria-label="Ajouter un item"
          onClick={ajouter}
          disabled={ajoutEnCours || !nouveauLibelle.trim()}
        >
          <Plus className="size-3.5" aria-hidden="true" />
        </button>
      </div>
    </div>
  )
}

import { useDroppable } from '@dnd-kit/core'
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from './Select'
import { NO_TECH } from '../features/installations/statuses'

/* Éléments PARTAGÉS des kanbans Chantiers / Interventions : colonne de statut
   (zone de dépôt) et réaffectation rapide du technicien. */

/** Items « utilisateur » d'un Select (login, sinon nom, sinon #id). */
export function ItemsUtilisateurs({ users }) {
  return (users ?? []).map((u) => (
    <SelectItem key={u.id} value={String(u.id)}>
      {u.username ?? u.nom ?? `#${u.id}`}
    </SelectItem>
  ))
}

/** Colonne de statut : zone de dépôt dnd-kit ; `vide` = texte quand elle n'a aucune carte. */
export function ColonneStatut({ col, vide, children }) {
  const { setNodeRef, isOver } = useDroppable({ id: col.key })
  return (
    <section ref={setNodeRef} className={isOver ? 'kb-col kb-over' : 'kb-col'}
             style={{ '--kb-accent': col.color }}>
      <header className="kb-col-header">
        <div className="kb-col-title-row">
          <span className="kb-col-title">{col.label}</span>
          <span className="kb-col-count">{col.items.length}</span>
        </div>
      </header>
      <div className="kb-col-body">
        {col.items.length === 0 ? (
          <div className="kb-col-empty">{vide}</div>
        ) : children}
      </div>
    </section>
  )
}

/** Réaffectation rapide sous une carte : `valeur` = id courant (ou vide), `onChange(null | id)`. */
export function SelectReaffectation({ valeur, users, onChange, label }) {
  const techValue = valeur ? String(valeur) : NO_TECH
  return (
    <div className="kc-reassign"
         onPointerDown={(e) => e.stopPropagation()}
         onClick={(e) => e.stopPropagation()}>
      <Select value={techValue}
              onValueChange={(v) => onChange(v === NO_TECH ? null : v)}>
        <SelectTrigger className="h-8 text-xs" aria-label={label}>
          <SelectValue placeholder={label} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NO_TECH}>— {label} —</SelectItem>
          <ItemsUtilisateurs users={users} />
        </SelectContent>
      </Select>
    </div>
  )
}

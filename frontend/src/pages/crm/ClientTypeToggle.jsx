// L151 — bascule « en place » du type de client (Particulier ↔ Entreprise),
// le seul statut PERSISTÉ d'un client. Enregistrement OPTIMISTE avec rollback
// via useOptimisticSave (lecture immédiate, retour-arrière si le PATCH échoue),
// et libellé inline « Enregistrement… / Enregistré ». N'utilise que le thunk
// updateClient existant (aucune migration, aucun nouvel endpoint).
import { useState } from 'react'
import { StatusPill } from '../../ui'
import { toast } from '../../ui/confirm'
import { useOptimisticSave } from '../../hooks/useOptimisticSave'

// Un client est « entreprise » s'il porte ce type ou un identifiant légal B2B.
const isEntrepriseValue = (type, c) =>
  type === 'entreprise' || !!(c?.ice || c?.if_fiscal || c?.rc)

const LABEL = { entreprise: 'Entreprise', particulier: 'Particulier' }

export default function ClientTypeToggle({ client, onSave }) {
  // Valeur serveur normalisée : on déduit le type effectif (champ explicite ou
  // identifiants B2B) pour que la pastille reflète la réalité de la ligne.
  const serverType = isEntrepriseValue(client?.type_client, client)
    ? 'entreprise'
    : 'particulier'
  const { value, statusLabel, isSaving, save } = useOptimisticSave(serverType, {
    onError: () => toast.error('Type non enregistré — réessayez.'),
  })
  const [open, setOpen] = useState(false)

  const choose = async (next) => {
    setOpen(false)
    if (next === value) return
    const res = await save(next, (v) => onSave(v))
    if (res.ok) toast.success('Type mis à jour.')
  }

  const tone = value === 'entreprise' ? 'info' : 'neutral'

  // Affordance « en cours » + libellé inline (Enregistrement… / Enregistré).
  return (
    <span
      className="ct-type inline-flex items-center gap-1"
      aria-busy={isSaving}
      data-saving={isSaving}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        className="ct-type-btn appearance-none border-0 bg-transparent p-0"
        title="Changer le type de client"
        disabled={isSaving}
        onClick={() => setOpen((o) => !o)}
      >
        <StatusPill tone={tone} label={LABEL[value]} />
      </button>
      {statusLabel && (
        <span className="ct-type-status text-xs text-muted-foreground">
          {statusLabel}
        </span>
      )}
      {open && (
        <span className="ct-type-menu inline-flex items-center gap-1">
          {['particulier', 'entreprise'].map((opt) => (
            <button
              key={opt}
              type="button"
              className="ct-type-opt rounded border border-border px-1.5 py-0.5 text-xs hover:bg-muted"
              onClick={() => choose(opt)}
            >
              {LABEL[opt]}
            </button>
          ))}
        </span>
      )}
    </span>
  )
}

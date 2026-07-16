import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Send } from 'lucide-react'
import { Button, Input, Textarea, toast } from '../../ui'
import innovationApi from '../../api/innovationApi'

/* ============================================================================
   NTIDE8 — Formulaire « Proposer une idée » (route dédiée /innovation/
   proposer). Immédiat (pas de brouillon) : le submit crée l'Idee et
   redirige vers son détail avec un toast de confirmation.
   ========================================================================== */

export default function ProposerIdeeForm({ onCreated, onCancel, compact = false }) {
  const navigate = useNavigate()

  const [titre, setTitre] = useState('')
  const [description, setDescription] = useState('')
  const [contexte, setContexte] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    const t = titre.trim()
    if (!t) { toast.error('Le titre est obligatoire.'); return }
    setSubmitting(true)
    try {
      const payload = { titre: t, description: description.trim(), contexte: contexte.trim() }
      const res = await innovationApi.create(payload)
      toast.success("Merci ! L'équipe examinera votre idée.")
      setTitre(''); setDescription('')
      if (onCreated) onCreated(res.data)
      else navigate(`/innovation/idees/${res.data.id}`)
    } catch {
      toast.error('Impossible de proposer cette idée — réessayez.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <label htmlFor="idee-titre" className="text-sm font-medium">Titre</label>
        <Input
          id="idee-titre"
          value={titre}
          onChange={(e) => setTitre(e.target.value)}
          placeholder="En une phrase, quelle est votre idée ?"
          autoFocus={!compact}
          required
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="idee-description" className="text-sm font-medium">Description</label>
        <Textarea
          id="idee-description"
          rows={compact ? 3 : 5}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Décrivez le contexte, le problème résolu, l'impact attendu…"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="idee-contexte" className="text-sm font-medium">Contexte</label>
        <Input
          id="idee-contexte"
          value={contexte}
          onChange={(e) => setContexte(e.target.value)}
          placeholder="ex. SAV, Devis, Stock…"
        />
      </div>

      <div className="flex items-center justify-end gap-2 pt-1">
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
            Annuler
          </Button>
        )}
        <Button type="submit" disabled={submitting}>
          <Send /> Proposer l'idée
        </Button>
      </div>
    </form>
  )
}

import { useEffect, useId, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Send, Save } from 'lucide-react'
import { Button, Input, Textarea, Checkbox, toast } from '../../ui'
import innovationApi from '../../api/innovationApi'
import { contexteFromPath, linkedFromLocation } from './linkedContext'

/* ============================================================================
   NTIDE8/NTIDE9/NTIDE10/NTIDE11/NTIDE18 — Formulaire « Proposer une idée »,
   partagé entre la page dédiée (/innovation/proposer) et le CTA modal
   (Intercom-style, monté sur chaque écran). Contexte autodétecté depuis la
   route courante (NTIDE9, ex. leads → « CRM »), avec autocomplétion des 5
   contextes les plus fréquents (NTIDE10). Propose de lier l'idée au document
   ouvert quand un signal fiable existe dans l'URL (NTIDE11, ex. devis en
   édition). « Enregistrer en brouillon » (NTIDE18) : l'idée reste interne à
   l'auteur (invisible des autres) jusqu'à ce qu'il la publie depuis son
   détail (bouton « Publier »).
   ========================================================================== */

export default function ProposerIdeeForm({ onCreated, onCancel, compact = false }) {
  const location = useLocation()
  const navigate = useNavigate()
  const datalistId = useId()

  const [titre, setTitre] = useState('')
  const [description, setDescription] = useState('')
  const [contexte, setContexte] = useState(() => contexteFromPath(location.pathname))
  const [suggestions, setSuggestions] = useState([])
  const [submitting, setSubmitting] = useState(false)
  // NTIDE18 — brouillon (reste interne à l'auteur tant que non publié).
  const [draft, setDraft] = useState(false)

  const linked = linkedFromLocation(location.pathname, location.search)
  const [lierIdee, setLierIdee] = useState(!!linked)

  useEffect(() => {
    innovationApi.contextes()
      .then((res) => setSuggestions(res.data?.results || []))
      .catch(() => setSuggestions([]))
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    const t = titre.trim()
    if (!t) { toast.error('Le titre est obligatoire.'); return }
    setSubmitting(true)
    try {
      const payload = {
        titre: t, description: description.trim(), contexte: contexte.trim(), draft,
      }
      if (lierIdee && linked) {
        payload.linked_type = linked.type
        payload.linked_id = linked.id
      }
      const res = await innovationApi.create(payload)
      toast.success(draft
        ? 'Brouillon enregistré — visible uniquement par vous.'
        : "Merci ! L'équipe examinera votre idée.")
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
          list={datalistId}
          value={contexte}
          onChange={(e) => setContexte(e.target.value)}
          placeholder="ex. SAV, Devis, Stock…"
        />
        <datalist id={datalistId}>
          {suggestions.map((s) => <option key={s} value={s} />)}
        </datalist>
      </div>

      {linked && (
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <Checkbox checked={lierIdee} onCheckedChange={(v) => setLierIdee(!!v)} />
          Ajouter une idée liée à ce {linked.type === 'devis' ? 'devis' : linked.type} #{linked.id} ?
        </label>
      )}

      <label className="flex items-center gap-2 text-sm text-muted-foreground">
        <Checkbox checked={draft} onCheckedChange={(v) => setDraft(!!v)} />
        Enregistrer en brouillon (visible uniquement par vous, pour l'instant)
      </label>

      <div className="flex items-center justify-end gap-2 pt-1">
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel} disabled={submitting}>
            Annuler
          </Button>
        )}
        <Button type="submit" disabled={submitting}>
          {draft ? <><Save /> Enregistrer en brouillon</> : <><Send /> Proposer l'idée</>}
        </Button>
      </div>
    </form>
  )
}

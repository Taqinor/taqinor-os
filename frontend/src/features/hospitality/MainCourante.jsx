import { useEffect, useState } from 'react'
import { Card, Badge, Button, EmptyState, Spinner, Textarea, toast } from '../../ui'
import hospitalityApi from '../../api/hospitalityApi'

/* ============================================================================
   NTHOT12 — Main courante / passations d'équipe.
   ----------------------------------------------------------------------------
   Journal chronologique (widget flottant utilisable depuis n'importe quel
   écran hôtellerie) : saisie rapide d'une note + consultation par l'équipe
   suivante avec horodatage et auteur (posés côté serveur). Journal APPEND-ONLY
   (aucune édition/suppression exposée par l'API).
   ========================================================================== */

const CATEGORIES = [
  { value: 'consigne', label: 'Consigne' },
  { value: 'incident', label: 'Incident' },
  { value: 'reservation', label: 'Réservation' },
  { value: 'finance', label: 'Finance' },
  { value: 'autre', label: 'Autre' },
]

const CATEGORIE_TONE = {
  consigne: 'info',
  incident: 'danger',
  reservation: 'success',
  finance: 'warning',
  autre: 'neutral',
}

export default function MainCourante() {
  const [notes, setNotes] = useState(null)
  const [error, setError] = useState(null)
  const [categorie, setCategorie] = useState('consigne')
  const [texte, setTexte] = useState('')
  const [saving, setSaving] = useState(false)

  const load = () => {
    hospitalityApi
      .listMainCourante()
      .then((res) => setNotes(res.data?.results ?? res.data ?? []))
      .catch(() => setError('Main courante indisponible.'))
  }

  useEffect(() => {
    load()
  }, [])

  const submit = (e) => {
    e.preventDefault()
    if (!texte.trim()) return
    setSaving(true)
    hospitalityApi
      .createMainCourante({ categorie, texte: texte.trim() })
      .then((res) => {
        setNotes((prev) => [res.data, ...(prev || [])])
        setTexte('')
        toast.success('Note ajoutée à la main courante.')
      })
      .catch(() => toast.error("Impossible d'ajouter la note."))
      .finally(() => setSaving(false))
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4">
        <form onSubmit={submit} className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((c) => (
              <button
                key={c.value}
                type="button"
                onClick={() => setCategorie(c.value)}
                className={
                  'rounded-full border px-3 py-1 text-sm ' +
                  (categorie === c.value ? 'bg-primary/15 border-primary' : 'border-border')
                }
              >
                {c.label}
              </button>
            ))}
          </div>
          <Textarea
            aria-label="Nouvelle note"
            placeholder="Écrire une note pour l'équipe suivante…"
            value={texte}
            onChange={(e) => setTexte(e.target.value)}
            rows={3}
          />
          <Button type="submit" disabled={saving || !texte.trim()}>
            {saving ? <Spinner className="size-4" /> : 'Ajouter la note'}
          </Button>
        </form>
      </Card>

      {error && <EmptyState title="Main courante indisponible" description={error} />}
      {!error && !notes && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Spinner className="size-4" /> Chargement de la main courante…
        </div>
      )}
      {!error && notes && !notes.length && (
        <EmptyState
          title="Aucune note"
          description="Aucune passation enregistrée pour l'instant."
        />
      )}
      {!error && notes && notes.length > 0 && (
        <div className="flex flex-col gap-2">
          {notes.map((note) => (
            <Card key={note.id} className="flex flex-col gap-1 p-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Badge tone={CATEGORIE_TONE[note.categorie] || 'neutral'}>
                  {note.categorie_display || note.categorie}
                </Badge>
                <span>{note.auteur_nom || 'Auteur inconnu'}</span>
                <span>·</span>
                <span>{new Date(note.date_note).toLocaleString('fr-FR')}</span>
              </div>
              <p className="text-sm">{note.texte}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

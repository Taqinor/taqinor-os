import { useEffect, useState } from 'react'
import { Button, Textarea } from '../../ui'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   WIR262 — Chatter assurances (historique + composeur de note), PARTAGÉ entre
   PoliceDetail (noterPolice) et le détail sinistre de SinistresPage
   (noterSinistre) — même rendu, même comportement des deux côtés.
   ----------------------------------------------------------------------------
   Auparavant : la police avait DÉJÀ un onglet « Historique » en LECTURE seule
   (sans composeur — impossible de noter une police), et le sinistre n'avait
   AUCUN historique visible bien que `getSinistreHistorique`/`noterSinistre`
   existaient côté API. Le bouton « Publier » reste INACTIF tant que la note
   est vide (jamais un POST silencieux d'un corps vide).
   ========================================================================== */

function Empty({ label }) {
  return <p className="py-6 text-center text-sm text-muted-foreground">{label}</p>
}

export default function ChatterAssurance({ getHistorique, noter, subjectId, title = 'Historique' }) {
  const [entries, setEntries] = useState([])
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const reload = () => {
    getHistorique(subjectId)
      .then((res) => setEntries(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setEntries([]))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { reload() }, [subjectId])

  const peutPublier = note.trim().length > 0

  const publier = async () => {
    if (!peutPublier || saving) return
    setSaving(true)
    setError(null)
    try {
      await noter(subjectId, note.trim())
      setNote('')
      reload()
    } catch (err) {
      const data = err?.response?.data
      setError(data?.detail || (typeof data === 'string' ? data : 'Publication impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {entries.length === 0
        ? <Empty label="Aucune activité." />
        : (
          <ul className="flex flex-col gap-2">
            {entries.map((h) => (
              <li key={h.id} className="rounded-md border p-2 text-xs">
                <div className="flex items-center justify-between text-muted-foreground">
                  <span>{h.kind}</span>
                  <span>{formatDateTime(h.created_at)}</span>
                </div>
                {h.field
                  ? <p>{h.field_label || h.field} : {h.old_value} → {h.new_value}</p>
                  : <p>{h.body}</p>}
              </li>
            ))}
          </ul>
        )}
      <div className="mt-2 flex flex-col gap-2 border-t pt-2">
        <Textarea
          aria-label="Nouvelle note"
          placeholder="Ajouter une note…"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        {error && <p className="text-xs text-destructive" role="alert">{error}</p>}
        <div>
          <Button size="sm" disabled={!peutPublier || saving} onClick={publier}>
            {saving ? 'Publication…' : 'Publier'}
          </Button>
        </div>
      </div>
    </div>
  )
}

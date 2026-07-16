/**
 * QJ16 — DevisPresetPanel
 *
 * A small panel that lets the user:
 *   1. Save the current devis as a named preset ("Enregistrer comme modèle")
 *   2. Browse company presets and apply one to the current devis in one click
 *      ("Appliquer un modèle")
 *
 * Usage (inside DevisGenerator or DevisForm):
 *   <DevisPresetPanel
 *     devisId={devis.id}
 *     onApplied={(lignes) => handleLignesFromPreset(lignes)}
 *   />
 *
 * The backend endpoints used:
 *   GET  /ventes/presets/               — list company presets
 *   POST /ventes/devis/{id}/save-preset/ — snapshot current devis as preset
 *   POST /ventes/devis/{id}/apply-preset/ — apply preset lines to devis
 *   DEL  /ventes/presets/{id}/           — delete a preset
 *
 * Multi-tenancy: company scoping is 100 % server-side; this component never
 * sends a company field.  The server forces devis.company on save and
 * validates preset.company == devis.company on apply.
 *
 * RULE #4: this panel is CREATION-ONLY (lines are set up, status stays brouillon).
 * It never changes Devis.statut.
 */
import { useState, useEffect, useCallback } from 'react'
import { BookmarkPlus, BookOpen, Trash2, Check, ChevronDown, ChevronUp } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { Button, Input, Label, Badge } from '../../ui'

// ── Helpers ──────────────────────────────────────────────────────────────────

// VX18 — statut via le Badge du kit (tokens de thème) plutôt qu'un hex codé en
// dur : 'success' vert, sinon 'danger' rouge — cohérent avec le reste de l'UI.
function StatusBadge({ text, variant }) {
  return <Badge tone={variant === 'success' ? 'success' : 'danger'}>{text}</Badge>
}

// ── Sub-components ────────────────────────────────────────────────────────────

function SaveSection({ devisId, onSaved }) {
  const [nom, setNom] = useState('')
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState(null) // {ok, msg}

  const handleSave = async () => {
    const trimmed = nom.trim()
    if (!trimmed) {
      setStatus({ ok: false, msg: 'Le nom du modèle est obligatoire.' })
      return
    }
    setSaving(true)
    setStatus(null)
    try {
      await ventesApi.savePreset(devisId, { nom: trimmed })
      setStatus({ ok: true, msg: `Modèle "${trimmed}" enregistré.` })
      setNom('')
      if (onSaved) onSaved()
    } catch {
      setStatus({ ok: false, msg: 'Impossible d\'enregistrer le modèle.' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-2">
      <Label htmlFor="preset-nom" className="text-sm font-medium">
        Nom du modèle
      </Label>
      <div className="flex gap-2">
        <Input
          id="preset-nom"
          placeholder="Ex. Standard 6 kWc résidentiel"
          value={nom}
          onChange={e => setNom(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSave()}
          className="flex-1 text-sm"
          disabled={saving}
        />
        <Button
          size="sm"
          onClick={handleSave}
          disabled={saving || !nom.trim()}
          className="shrink-0"
        >
          <BookmarkPlus className="size-4 mr-1" aria-hidden="true" />
          {saving ? 'Enregistrement…' : 'Enregistrer'}
        </Button>
      </div>
      {status && (
        <StatusBadge
          text={status.msg}
          variant={status.ok ? 'success' : 'error'}
        />
      )}
    </div>
  )
}


function ApplySection({ devisId, onApplied }) {
  const [presets, setPresets] = useState([])
  const [loading, setLoading] = useState(true)
  const [applying, setApplying] = useState(null)  // preset id being applied
  const [deleting, setDeleting] = useState(null)  // preset id being deleted
  const [status, setStatus] = useState(null)

  const load = useCallback(() => {
    ventesApi.getPresets()
      .then(res => setPresets(res.data?.results ?? res.data ?? []))
      .catch(() => setPresets([]))
      .finally(() => setLoading(false))
  }, [])

  // Load once on mount
  useEffect(() => { load() }, [load])

  const handleApply = async (preset) => {
    setApplying(preset.id)
    setStatus(null)
    try {
      const res = await ventesApi.applyPreset(devisId, { preset_id: preset.id })
      setStatus({ ok: true, msg: `Modèle "${preset.nom}" appliqué.` })
      if (onApplied) onApplied(res.data)
    } catch {
      setStatus({ ok: false, msg: 'Impossible d\'appliquer le modèle.' })
    } finally {
      setApplying(null)
    }
  }

  const handleDelete = async (preset) => {
    setDeleting(preset.id)
    try {
      await ventesApi.deletePreset(preset.id)
      setPresets(prev => prev.filter(p => p.id !== preset.id))
    } catch {
      setStatus({ ok: false, msg: 'Impossible de supprimer le modèle.' })
    } finally {
      setDeleting(null)
    }
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">Chargement des modèles…</p>
  }

  if (!presets.length) {
    return (
      <p className="text-sm text-muted-foreground italic">
        Aucun modèle enregistré. Enregistrez ce devis comme modèle pour accélérer
        la création des suivants.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {status && (
        <StatusBadge
          text={status.msg}
          variant={status.ok ? 'success' : 'error'}
        />
      )}
      <ul className="divide-y divide-border rounded-md border border-border text-sm">
        {presets.map(preset => (
          <li key={preset.id}
              className="flex items-center gap-2 px-3 py-2 hover:bg-muted/40 transition-colors">
            <div className="flex-1 min-w-0">
              <span className="font-medium truncate block">{preset.nom}</span>
              {preset.mode_installation && (
                <span className="text-xs text-muted-foreground">
                  {preset.mode_installation}
                </span>
              )}
            </div>
            <Button
              size="xs"
              variant="outline"
              onClick={() => handleApply(preset)}
              disabled={applying === preset.id}
              title="Appliquer ce modèle au devis actuel"
            >
              {applying === preset.id
                ? <Check className="size-3 text-green-600" aria-hidden="true" />
                : 'Appliquer'}
            </Button>
            <button
              onClick={() => handleDelete(preset)}
              disabled={deleting === preset.id}
              className="p-1 rounded text-muted-foreground hover:text-destructive transition-colors disabled:opacity-40"
              title="Supprimer ce modèle"
              type="button"
            >
              <Trash2 className="size-3.5" aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}


// ── Main component ────────────────────────────────────────────────────────────

/**
 * DevisPresetPanel — collapsible panel with save + apply controls.
 *
 * @param {number}   devisId   - ID of the current Devis (required to call backend)
 * @param {function} onApplied - Called with the apply-response data after a
 *                               preset is applied so the parent can refresh lines
 */
export default function DevisPresetPanel({ devisId, onApplied }) {
  const [open, setOpen] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  // When a preset is saved, refresh the list
  const handleSaved = () => setRefreshKey(k => k + 1)

  if (!devisId) return null

  return (
    <div className="rounded-lg border border-border bg-card text-card-foreground shadow-sm">
      {/* Header — always visible */}
      <button
        type="button"
        className="flex w-full items-center gap-2 px-4 py-3 text-sm font-semibold
                   hover:bg-muted/30 transition-colors rounded-lg"
        onClick={() => setOpen(v => !v)}
        aria-expanded={open}
      >
        <BookOpen className="size-4 text-primary" aria-hidden="true" />
        <span>Modèles de devis</span>
        <span className="ml-auto text-muted-foreground">
          {open
            ? <ChevronUp className="size-4" aria-hidden="true" />
            : <ChevronDown className="size-4" aria-hidden="true" />}
        </span>
      </button>

      {/* Collapsible body */}
      {open && (
        <div className="px-4 pb-4 space-y-5 border-t border-border">
          {/* Save section */}
          <div className="pt-4">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Enregistrer comme modèle
            </h3>
            <SaveSection devisId={devisId} onSaved={handleSaved} />
          </div>

          {/* Apply section */}
          <div>
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Appliquer un modèle
            </h3>
            {/* key forces remount/reload when a preset is saved */}
            <ApplySection
              key={refreshKey}
              devisId={devisId}
              onApplied={onApplied}
            />
          </div>
        </div>
      )}
    </div>
  )
}

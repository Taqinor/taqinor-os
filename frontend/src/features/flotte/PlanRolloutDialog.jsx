import { useMemo, useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, MultiSelect, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'

/* ============================================================================
   XFLT22 — Duplique un plan d'entretien sur une sélection d'actifs.
   ----------------------------------------------------------------------------
   Un actif déjà couvert par un plan du même type d'entretien est SAUTÉ côté
   serveur (jamais de doublon) — les actifs ignorés sont réaffichés après
   soumission.
   ========================================================================== */

export default function PlanRolloutDialog({ plan, actifs = [], onClose, onSaved }) {
  const [selection, setSelection] = useState([])
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)
  const [resultat, setResultat] = useState(null)

  const options = useMemo(
    () => actifs.map((a) => ({ value: String(a.id), label: a.label || `#${a.id}` })),
    [actifs],
  )

  const peutEnregistrer = selection.length > 0
  // VX168 — garde de fermeture : dialogue de création, initial = sélection vide.
  const dirty = selection.length > 0
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer || !plan?.id) return
    setSaving(true)
    setServerError(null)
    setResultat(null)
    try {
      const res = await flotteApi.plansEntretien.rollout(plan.id, selection.map(Number))
      setResultat(res?.data || null)
      onSaved?.()
    } catch (err) {
      setServerError(err?.response?.data?.detail || 'Duplication impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Dupliquer le plan « {plan?.type_entretien || 'entretien'} »</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rollout-actifs">Actifs cibles</Label>
            <MultiSelect
              id="rollout-actifs"
              autoFocus
              options={options}
              value={selection}
              onChange={setSelection}
              placeholder="Choisir les véhicules / engins…"
            />
          </div>

          {resultat && (
            <div className="rounded-md border border-border p-3 text-sm">
              <p>{resultat.crees?.length || 0} plan(s) créé(s).</p>
              {resultat.ignores?.length > 0 && (
                <p className="text-muted-foreground">{resultat.ignores.length} actif(s) déjà couvert(s), ignoré(s).</p>
              )}
            </div>
          )}

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Fermer</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Duplication…' : 'Dupliquer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

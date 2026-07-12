import { useMemo, useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, Checkbox, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'

/* ============================================================================
   XFLT13 — Formulaire d'inspection périodique (check-list DVIR).
   ----------------------------------------------------------------------------
   Tout rôle peut réaliser une inspection (le conducteur l'exécute lui-même) —
   `company` ET `auteur` posés côté serveur. Un item coché « échec » crée
   automatiquement un signalement lié (XFLT5, géré côté serveur). E-signature
   loi 53-05 : nom saisi + horodatage serveur, pas de signature graphique.
   ========================================================================== */

export default function InspectionDialog({ actifs = [], modeles = [], onClose, onSaved }) {
  const [actifFlotte, setActifFlotte] = useState('')
  const [modeleId, setModeleId] = useState('')
  const [resultats, setResultats] = useState([])
  const [resultatsModeleId, setResultatsModeleId] = useState('')
  const [signatureNom, setSignatureNom] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const modele = useMemo(
    () => modeles.find((m) => String(m.id) === String(modeleId)) || null,
    [modeles, modeleId],
  )

  // Réinitialise la check-list au changement de modèle. Dérivé pendant le rendu
  // (plutôt qu'un effet) pour éviter un setState synchrone dans un effet.
  if (resultatsModeleId !== modeleId) {
    setResultatsModeleId(modeleId)
    const items = modele?.items || []
    setResultats(items.map((it) => ({ libelle: it.libelle, resultat: 'pass', bloquant: Boolean(it.bloquant) })))
  }

  const toggleItem = (index, ok) => {
    setResultats((prev) => prev.map((r, i) => (i === index ? { ...r, resultat: ok ? 'pass' : 'fail' } : r)))
  }

  const peutEnregistrer = Boolean(actifFlotte && modeleId && signatureNom.trim())
  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(actifFlotte || modeleId || signatureNom)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.inspections.create({
        actif_flotte: Number(actifFlotte),
        modele_inspection: Number(modeleId),
        resultats: resultats.map((r) => ({ libelle: r.libelle, resultat: r.resultat, photo: null })),
        signature_nom: signatureNom.trim(),
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'),
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvelle inspection</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="insp-actif">Véhicule / engin</Label>
            <select
              id="insp-actif"
              autoFocus
              value={actifFlotte}
              onChange={(e) => setActifFlotte(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {actifs.map((a) => (
                <option key={a.id} value={a.id}>{a.label || `#${a.id}`}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="insp-modele">Modèle de check-list</Label>
            <select
              id="insp-modele"
              value={modeleId}
              onChange={(e) => setModeleId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {modeles.map((m) => (
                <option key={m.id} value={m.id}>{m.nom}</option>
              ))}
            </select>
          </div>

          {resultats.length > 0 && (
            <div className="flex flex-col gap-2 rounded-md border border-border p-3">
              {resultats.map((r, i) => (
                <label key={r.libelle + i} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={r.resultat === 'pass'}
                    onCheckedChange={(v) => toggleItem(i, Boolean(v))}
                  />
                  {r.libelle}{r.bloquant ? ' *' : ''}
                </label>
              ))}
              <p className="text-xs text-muted-foreground">
                Décocher un item = échec (crée automatiquement un signalement).
              </p>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="insp-signature">Nom du signataire (e-signature)</Label>
            <Input id="insp-signature" value={signatureNom} onChange={(e) => setSignatureNom(e.target.value)} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Valider l’inspection'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, IconButton, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'

/* ============================================================================
   XFLT22 — Réaffectation conducteur en masse.
   ----------------------------------------------------------------------------
   Une ligne = un couple {véhicule, conducteur}. Le contrôle permis (FLOTTE9)
   par ligne est appliqué côté serveur — un échec est LISTÉ sans bloquer le
   lot (voir `echecs` dans la réponse, réaffiché après soumission).
   ========================================================================== */

export default function MasseAffectationDialog({ conducteurs = [], vehicules = [], onClose, onSaved }) {
  const [dateDebut, setDateDebut] = useState('')
  const [lignes, setLignes] = useState([{ vehicule: '', conducteur: '' }])
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)
  const [resultat, setResultat] = useState(null)

  const ajouterLigne = () => setLignes((ls) => [...ls, { vehicule: '', conducteur: '' }])
  const retirerLigne = (i) => setLignes((ls) => ls.filter((_, idx) => idx !== i))
  const majLigne = (i, champ, valeur) => setLignes((ls) => ls.map((l, idx) => (idx === i ? { ...l, [champ]: valeur } : l)))

  const lignesValides = lignes.filter((l) => l.vehicule && l.conducteur)
  const peutEnregistrer = Boolean(dateDebut && lignesValides.length > 0)
  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(dateDebut || lignes.some((l) => l.vehicule || l.conducteur))
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    setResultat(null)
    try {
      const res = await flotteApi.affectations.masse({
        date_debut: dateDebut,
        reaffectations: lignesValides.map((l) => ({
          vehicule_id: Number(l.vehicule), conducteur_id: Number(l.conducteur),
        })),
      })
      setResultat(res?.data || null)
      if (!res?.data?.echecs?.length) {
        onSaved?.()
      }
    } catch (err) {
      setServerError(err?.response?.data?.detail || 'Réaffectation impossible.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Réaffectation en masse</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="masse-date">Date de début (toutes les lignes)</Label>
            <Input id="masse-date" type="date" autoFocus value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
          </div>

          <div className="flex flex-col gap-2">
            {lignes.map((l, i) => (
              <div key={i} className="flex items-center gap-2">
                <select
                  aria-label={`Véhicule ligne ${i + 1}`}
                  value={l.vehicule}
                  onChange={(e) => majLigne(i, 'vehicule', e.target.value)}
                  className="h-9 flex-1 rounded-md border border-border bg-card px-3 text-sm"
                >
                  <option value="">— Véhicule —</option>
                  {vehicules.map((v) => (
                    <option key={v.id} value={v.id}>{v.immatriculation}</option>
                  ))}
                </select>
                <select
                  aria-label={`Conducteur ligne ${i + 1}`}
                  value={l.conducteur}
                  onChange={(e) => majLigne(i, 'conducteur', e.target.value)}
                  className="h-9 flex-1 rounded-md border border-border bg-card px-3 text-sm"
                >
                  <option value="">— Conducteur —</option>
                  {conducteurs.map((c) => (
                    <option key={c.id} value={c.id}>{c.nom}</option>
                  ))}
                </select>
                <IconButton label="Retirer la ligne" variant="ghost" onClick={() => retirerLigne(i)} disabled={lignes.length === 1}>
                  <Trash2 />
                </IconButton>
              </div>
            ))}
            <Button type="button" variant="outline" onClick={ajouterLigne}>
              <Plus /> Ajouter une ligne
            </Button>
          </div>

          {resultat && (
            <div className="rounded-md border border-border p-3 text-sm">
              <p>{resultat.reussies?.length || 0} réaffectation(s) réussie(s).</p>
              {resultat.echecs?.length > 0 && (
                <ul className="mt-1 list-disc pl-4 text-destructive">
                  {resultat.echecs.map((e, i) => (
                    <li key={i}>{e.message}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Fermer</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Réaffecter'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

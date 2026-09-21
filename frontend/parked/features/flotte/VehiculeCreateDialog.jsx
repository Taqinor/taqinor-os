import { useMemo, useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'
import { optionsFrom, ENERGIES } from './flotte'

/* ============================================================================
   XFLT12 — Formulaire de création véhicule avec pré-remplissage par modèle.
   ----------------------------------------------------------------------------
   À la sélection d'un ``modele_ref`` (catalogue), les champs encore VIDES du
   formulaire (énergie, puissance fiscale, valeur, valeur résiduelle, % charges
   non déductibles) sont pré-remplis côté client pour un retour immédiat — le
   serveur applique la MÊME règle (``services.prefill_depuis_modele``) et ne
   récrit jamais un champ déjà saisi, donc aucune divergence possible.
   ========================================================================== */

export default function VehiculeCreateDialog({ modeles = [], onClose, onSaved }) {
  const [immatriculation, setImmatriculation] = useState('')
  const [marque, setMarque] = useState('')
  const [modele, setModele] = useState('')
  const [modeleRefId, setModeleRefId] = useState('')
  const [energie, setEnergie] = useState('')
  const [puissanceFiscale, setPuissanceFiscale] = useState('')
  const [valeur, setValeur] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const modeleRef = useMemo(
    () => modeles.find((m) => String(m.id) === String(modeleRefId)) || null,
    [modeles, modeleRefId],
  )

  const appliquerModele = (id) => {
    setModeleRefId(id)
    const m = modeles.find((x) => String(x.id) === String(id))
    if (!m) return
    // Pré-remplit UNIQUEMENT les champs encore vides (miroir du serveur).
    if (!marque) setMarque(m.marque || '')
    if (!modele) setModele(m.modele || '')
    if (!energie && m.energie) setEnergie(m.energie)
    if (!puissanceFiscale && m.puissance_fiscale != null) setPuissanceFiscale(String(m.puissance_fiscale))
    if (!valeur && m.valeur_catalogue != null) setValeur(String(m.valeur_catalogue))
  }

  const peutEnregistrer = Boolean(immatriculation.trim())
  // VX168 — garde de fermeture : dialogue de création, initial = tout vide.
  const dirty = Boolean(
    immatriculation || marque || modele || modeleRefId || energie || puissanceFiscale || valeur,
  )
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.vehicules.create({
        immatriculation: immatriculation.trim(),
        marque,
        modele,
        modele_ref: modeleRefId ? Number(modeleRefId) : null,
        energie: energie || undefined,
        puissance_fiscale: puissanceFiscale === '' ? null : Number(puissanceFiscale),
        valeur: valeur === '' ? undefined : Number(valeur),
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.immatriculation
        || data?.detail
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
          <DialogTitle>Nouveau véhicule</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="veh-immat">Immatriculation</Label>
            <Input id="veh-immat" autoFocus value={immatriculation} onChange={(e) => setImmatriculation(e.target.value)} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="veh-modele-ref">Modèle de référence (catalogue)</Label>
            <select
              id="veh-modele-ref"
              value={modeleRefId}
              onChange={(e) => appliquerModele(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Saisie libre (aucun modèle) —</option>
              {modeles.map((m) => (
                <option key={m.id} value={m.id}>{m.marque} {m.modele}</option>
              ))}
            </select>
            {modeleRef && (
              <p className="text-xs text-muted-foreground">
                Pré-remplit les champs vides depuis le catalogue — une saisie déjà faite n’est jamais écrasée.
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="veh-marque">Marque</Label>
              <Input id="veh-marque" value={marque} onChange={(e) => setMarque(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="veh-modele">Modèle</Label>
              <Input id="veh-modele" value={modele} onChange={(e) => setModele(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="veh-energie">Énergie</Label>
              <select
                id="veh-energie"
                value={energie}
                onChange={(e) => setEnergie(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">—</option>
                {optionsFrom(ENERGIES).map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="veh-cv">Puissance fiscale (CV)</Label>
              <Input id="veh-cv" type="number" step="any" value={puissanceFiscale} onChange={(e) => setPuissanceFiscale(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="veh-valeur">Valeur (immobilisation, MAD)</Label>
            <Input id="veh-valeur" type="number" step="any" value={valeur} onChange={(e) => setValeur(e.target.value)} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Créer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

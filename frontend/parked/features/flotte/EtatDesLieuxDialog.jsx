import { useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, Textarea, confirmLeaveIfDirty,
} from '../../ui'
import flotteApi from '../../api/flotteApi'

/* ============================================================================
   WIR41(c) — Création d'un constat d'état des lieux (FLOTTE11), AVANT
   signature.
   ----------------------------------------------------------------------------
   `EtatsDesLieuxTab` ne permettait que de signer un constat déjà existant —
   il n'existait aucun chemin pour CRÉER le constat lui-même. Kilométrage,
   niveau de carburant et état général portent des valeurs par défaut côté
   modèle ; ce formulaire ne saisit que l'essentiel, les signatures restant un
   flux séparé (``SignatureDialog``).
   ========================================================================== */

const MOMENTS = [
  { value: 'depart', label: 'Départ' },
  { value: 'retour', label: 'Retour' },
]

const ETATS = [
  { value: 'bon', label: 'Bon' },
  { value: 'moyen', label: 'Moyen' },
  { value: 'mauvais', label: 'Mauvais' },
]

export default function EtatDesLieuxDialog({ vehicules = [], conducteurs = [], onClose, onSaved }) {
  const [vehiculeId, setVehiculeId] = useState('')
  const [conducteurId, setConducteurId] = useState('')
  const [moment, setMoment] = useState('depart')
  const [dateConstat, setDateConstat] = useState('')
  const [kilometrage, setKilometrage] = useState('')
  const [niveauCarburant, setNiveauCarburant] = useState('')
  const [etatGeneral, setEtatGeneral] = useState('bon')
  const [commentaire, setCommentaire] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const peutEnregistrer = Boolean(vehiculeId && dateConstat)
  const dirty = Boolean(
    vehiculeId || conducteurId || dateConstat || kilometrage
    || niveauCarburant || commentaire || moment !== 'depart' || etatGeneral !== 'bon',
  )
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await flotteApi.etatsDesLieux.create({
        vehicule: Number(vehiculeId),
        conducteur: conducteurId ? Number(conducteurId) : null,
        moment,
        date_constat: dateConstat,
        kilometrage: kilometrage === '' ? undefined : Number(kilometrage),
        niveau_carburant: niveauCarburant === '' ? undefined : Number(niveauCarburant),
        etat_general: etatGeneral,
        commentaire,
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
          <DialogTitle>Nouveau constat d’état des lieux</DialogTitle>
        </DialogHeader>

        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edl-vehicule">Véhicule</Label>
            <select
              id="edl-vehicule"
              autoFocus
              value={vehiculeId}
              onChange={(e) => setVehiculeId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {vehicules.map((v) => (
                <option key={v.id} value={v.id}>{v.immatriculation}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edl-conducteur">Conducteur (option.)</Label>
            <select
              id="edl-conducteur"
              value={conducteurId}
              onChange={(e) => setConducteurId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Non assigné —</option>
              {conducteurs.map((c) => (
                <option key={c.id} value={c.id}>{c.nom}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edl-moment">Moment</Label>
              <select
                id="edl-moment"
                value={moment}
                onChange={(e) => setMoment(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {MOMENTS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edl-date">Date du constat</Label>
              <Input id="edl-date" type="datetime-local" value={dateConstat} onChange={(e) => setDateConstat(e.target.value)} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edl-km">Kilométrage relevé</Label>
              <Input id="edl-km" type="number" step="any" value={kilometrage} onChange={(e) => setKilometrage(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="edl-carburant">Niveau de carburant (%)</Label>
              <Input id="edl-carburant" type="number" step="any" value={niveauCarburant} onChange={(e) => setNiveauCarburant(e.target.value)} />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edl-etat">État général</Label>
            <select
              id="edl-etat"
              value={etatGeneral}
              onChange={(e) => setEtatGeneral(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              {ETATS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edl-commentaire">Commentaire</Label>
            <Textarea id="edl-commentaire" value={commentaire} onChange={(e) => setCommentaire(e.target.value)} rows={3} />
          </div>

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Créer le constat'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

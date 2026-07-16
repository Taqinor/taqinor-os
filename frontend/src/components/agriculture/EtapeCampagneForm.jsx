import { useMemo, useState } from 'react'
import { AlertTriangle, ShieldCheck } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Label, Input, confirmLeaveIfDirty,
} from '../../ui'
import agricultureApi from '../../api/agricultureApi'

/* ============================================================================
   NTAGR8 — Formulaire d'ajout d'étape de campagne, avec alerte DAR EN DIRECT
   pour les traitements phyto (miroir client de `models.check_dar_guard` —
   même patron que `AffectationDialog.controlePermis` : retour immédiat côté
   client, re-vérifié côté serveur à l'enregistrement).
   ========================================================================== */

const TYPES_ETAPE = [
  ['semis', 'Semis'], ['traitement', 'Traitement'], ['irrigation', 'Irrigation'],
  ['desherbage', 'Désherbage'], ['fertilisation', 'Fertilisation'],
  ['recolte', 'Récolte'], ['autre', 'Autre'],
]

// Miroir de `apps.agriculture.models.check_dar_guard` : retourne
// `{ ok: true }` ou `{ ok: false, message }`. Ne bloque jamais si le type
// n'est pas « traitement », si l'intrant n'a pas de DAR défini, ou si la
// campagne n'a aucune date de récolte connue.
export function checkDarAlert({ typeEtape, date, intrant, campagne }) {
  if (typeEtape !== 'traitement') return { ok: true }
  if (!intrant || intrant.delai_avant_recolte_jours == null) return { ok: true }
  if (!date) return { ok: true }
  const candidates = [campagne?.date_recolte_prevue, campagne?.date_recolte_reelle]
    .filter(Boolean)
  if (candidates.length === 0) return { ok: true }
  const dateRecolteContraignante = candidates.sort()[0]
  // Arithmétique en UTC pur à partir des composants "YYYY-MM-DD" — évite
  // tout décalage de fuseau horaire local (Date.UTC gère nativement le
  // débordement de mois/année quand on ajoute les jours de DAR).
  const [y, m, d] = date.split('-').map(Number)
  const limiteIso = new Date(
    Date.UTC(y, m - 1, d + Number(intrant.delai_avant_recolte_jours)),
  ).toISOString().slice(0, 10)
  if (limiteIso > dateRecolteContraignante) {
    const produit = intrant.matiere_active || intrant.produit_nom || `intrant #${intrant.id}`
    return {
      ok: false,
      message: (
        `Délai avant récolte (DAR) de ${intrant.delai_avant_recolte_jours} jour(s) `
        + `pour « ${produit} » appliqué le ${date} : dépasse la date de récolte `
        + `du ${dateRecolteContraignante}.`
      ),
    }
  }
  return { ok: true }
}

export default function EtapeCampagneForm({ campagne, intrants = [], onClose, onSaved }) {
  const [typeEtape, setTypeEtape] = useState('traitement')
  const [date, setDate] = useState('')
  const [intrantId, setIntrantId] = useState('')
  const [description, setDescription] = useState('')
  const [coutMad, setCoutMad] = useState('')
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const intrant = useMemo(
    () => intrants.find((i) => String(i.id) === String(intrantId)) || null,
    [intrants, intrantId],
  )

  const darAlert = useMemo(
    () => checkDarAlert({ typeEtape, date, intrant, campagne }),
    [typeEtape, date, intrant, campagne],
  )

  const dirty = Boolean(date || intrantId || description || coutMad)
  const closeIfConfirmed = () => { if (confirmLeaveIfDirty(dirty)) onClose?.() }
  const peutEnregistrer = Boolean(date) && darAlert.ok

  const submit = async (e) => {
    e.preventDefault()
    if (!peutEnregistrer) return
    setSaving(true)
    setServerError(null)
    try {
      await agricultureApi.etapesCampagne.create({
        campagne: campagne.id, type_etape: typeEtape, date,
        intrant: intrantId || null, description,
        cout_mad: coutMad === '' ? null : coutMad,
      })
      onSaved?.()
    } catch (err) {
      const data = err?.response?.data
      setServerError(
        data?.date || data?.detail
        || (typeof data === 'string' ? data : 'Enregistrement impossible.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) closeIfConfirmed() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvelle étape — {campagne.culture}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="etape-type">Type d’étape</Label>
            <select
              id="etape-type" value={typeEtape}
              onChange={(e) => setTypeEtape(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              {TYPES_ETAPE.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          {typeEtape === 'traitement' && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="etape-intrant">Intrant appliqué</Label>
              <select
                id="etape-intrant" value={intrantId}
                onChange={(e) => setIntrantId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">— Choisir —</option>
                {intrants.map((i) => (
                  <option key={i.id} value={i.id}>
                    {i.matiere_active || i.produit_nom || `Intrant #${i.id}`}
                    {i.delai_avant_recolte_jours != null ? ` — DAR ${i.delai_avant_recolte_jours} j` : ''}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="etape-date">Date</Label>
            <Input id="etape-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="etape-description">Description</Label>
            <Input id="etape-description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optionnel" />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="etape-cout">Coût (MAD, option.)</Label>
            <Input id="etape-cout" type="number" step="any" value={coutMad} onChange={(e) => setCoutMad(e.target.value)} />
          </div>

          {/* Alerte DAR EN DIRECT (NTAGR8). */}
          {typeEtape === 'traitement' && intrant && date && (
            darAlert.ok ? (
              <div className="flex items-center gap-2 rounded-md border border-success/40 bg-success/10 px-3 py-2 text-sm text-success">
                <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
                Délai avant récolte respecté.
              </div>
            ) : (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive" role="alert">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <div>
                    <p className="font-medium">Traitement bloqué — délai avant récolte (DAR)</p>
                    <p className="mt-0.5">{darAlert.message}</p>
                  </div>
                </div>
              </div>
            )
          )}

          {serverError && (
            <p className="text-sm text-destructive" role="alert">{serverError}</p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={closeIfConfirmed}>Annuler</Button>
            <Button type="submit" disabled={!peutEnregistrer || saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

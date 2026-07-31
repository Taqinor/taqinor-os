import { useEffect, useMemo, useState } from 'react'
import { Card, Badge, Button, EmptyState, Spinner, Input, toast } from '../../ui'
import hospitalityApi from '../../api/hospitalityApi'
import { openPdfInGesture } from '../../utils/pdfBlob'

/* ============================================================================
   WIR146 — Check-in / check-out (NTHOT5/NTHOT6). Le backend expose déjà
   `check-in`/`check-out`/`fiche-police-pdf` (jamais consommés par aucun
   écran avant ce lot — `hospitalityApi.checkIn`/`checkOut` existaient déjà,
   morts). Le check-in bloque tant qu'une fiche de police par occupant n'est
   pas complète (nom/nationalité/pièce/date de naissance) — la garde vit
   côté serveur, ce formulaire relaie simplement l'erreur.
   ========================================================================== */

const STATUT_TONE = {
  confirmee: 'success', en_attente: 'warning', en_cours: 'info', terminee: 'neutral',
}

const FICHE_VIDE = () => ({
  nom_complet: '', nationalite: '', type_piece: 'cin', numero_piece: '', date_naissance: '',
})

function CheckInForm({ reservation, onDone }) {
  const [fiches, setFiches] = useState([FICHE_VIDE()])
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  const updateFiche = (idx, patch) => {
    setFiches((prev) => prev.map((f, i) => (i === idx ? { ...f, ...patch } : f)))
  }
  const ajouterFiche = () => setFiches((prev) => [...prev, FICHE_VIDE()])
  const retirerFiche = (idx) => setFiches((prev) => prev.filter((_, i) => i !== idx))

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    setServerError(null)
    hospitalityApi
      .checkIn(reservation.id, { fiches })
      .then(() => {
        toast.success('Check-in effectué.')
        onDone()
      })
      .catch((err) => {
        setServerError(err?.response?.data?.fiches || 'Impossible de faire le check-in.')
      })
      .finally(() => setSaving(false))
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      {fiches.map((fiche, idx) => (
        <div key={idx} className="flex flex-wrap items-end gap-2 border-b border-border pb-2">
          <Input
            aria-label={`Nom complet occupant ${idx + 1}`}
            placeholder="Nom complet"
            value={fiche.nom_complet}
            onChange={(e) => updateFiche(idx, { nom_complet: e.target.value })}
          />
          <Input
            aria-label={`Nationalité occupant ${idx + 1}`}
            placeholder="Nationalité"
            value={fiche.nationalite}
            onChange={(e) => updateFiche(idx, { nationalite: e.target.value })}
          />
          <select
            aria-label={`Type de pièce occupant ${idx + 1}`}
            value={fiche.type_piece}
            onChange={(e) => updateFiche(idx, { type_piece: e.target.value })}
            className="h-[var(--control-h)] rounded-md border border-input bg-card px-2 text-sm"
          >
            <option value="cin">CIN</option>
            <option value="passeport">Passeport</option>
          </select>
          <Input
            aria-label={`Numéro de pièce occupant ${idx + 1}`}
            placeholder="N° pièce"
            value={fiche.numero_piece}
            onChange={(e) => updateFiche(idx, { numero_piece: e.target.value })}
          />
          <Input
            type="date"
            aria-label={`Date de naissance occupant ${idx + 1}`}
            value={fiche.date_naissance}
            onChange={(e) => updateFiche(idx, { date_naissance: e.target.value })}
          />
          {fiches.length > 1 && (
            <Button type="button" variant="outline" onClick={() => retirerFiche(idx)}>
              Retirer
            </Button>
          )}
        </div>
      ))}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" onClick={ajouterFiche}>+ Occupant</Button>
        <Button type="submit" disabled={saving}>
          {saving ? <Spinner className="size-4" /> : 'Valider le check-in'}
        </Button>
      </div>
      {serverError && <p className="text-sm text-destructive" role="alert">{serverError}</p>}
    </form>
  )
}

export default function CheckInOut() {
  const [reservations, setReservations] = useState(null)
  const [error, setError] = useState(null)
  const [checkInOuverte, setCheckInOuverte] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    hospitalityApi
      .listReservations()
      .then((res) => setReservations(res.data?.results ?? res.data ?? []))
      .catch(() => setError('Réservations indisponibles.'))
  }

  useEffect(() => { load() }, [])

  const aFaireCheckIn = useMemo(
    () => (reservations || []).filter((r) => ['confirmee', 'en_attente'].includes(r.statut)),
    [reservations],
  )
  const aFaireCheckOut = useMemo(
    () => (reservations || []).filter((r) => r.statut === 'en_cours'),
    [reservations],
  )

  const checkOut = (reservation) => {
    setBusyId(reservation.id)
    hospitalityApi
      .checkOut(reservation.id)
      .then(() => {
        toast.success('Check-out effectué.')
        load()
      })
      .catch((err) => {
        toast.error(err?.response?.data?.detail || 'Impossible de faire le check-out.')
      })
      .finally(() => setBusyId(null))
  }

  const telechargerFichePolice = (reservation) => {
    // VX48 — window.open SYNCHRONE, avant tout await.
    const pending = openPdfInGesture()
    hospitalityApi
      .fichePolicePdf(reservation.id)
      .then((res) => {
        const blob = new Blob([res.data], { type: 'application/pdf' })
        if (!pending.deliver(blob, `fiche-police-${reservation.id}.pdf`)) {
          toast.error('Ouverture bloquée par le navigateur.')
        }
      })
      .catch(() => toast.error('Fiche de police indisponible (check-in non effectué ?).'))
  }

  if (error) return <EmptyState title="Check-in/out indisponible" description={error} />
  if (!reservations) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement des réservations…
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">Arrivées à checker-in</h2>
        {aFaireCheckIn.length === 0 && (
          <EmptyState title="Aucune arrivée" description="Aucune réservation en attente de check-in." />
        )}
        {aFaireCheckIn.map((r) => (
          <Card key={r.id} className="flex flex-col gap-2 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="font-medium">
                {r.client_nom || `Réservation #${r.id}`} — {r.date_arrivee} → {r.date_depart}
              </div>
              <Badge tone={STATUT_TONE[r.statut] || 'neutral'}>{r.statut_display || r.statut}</Badge>
              <Button
                variant={checkInOuverte === r.id ? 'outline' : 'default'}
                onClick={() => setCheckInOuverte(checkInOuverte === r.id ? null : r.id)}
              >
                {checkInOuverte === r.id ? 'Fermer' : 'Check-in'}
              </Button>
            </div>
            {checkInOuverte === r.id && (
              <CheckInForm
                reservation={r}
                onDone={() => { setCheckInOuverte(null); load() }}
              />
            )}
          </Card>
        ))}
      </div>

      <div className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">Séjours en cours (check-out)</h2>
        {aFaireCheckOut.length === 0 && (
          <EmptyState title="Aucun séjour en cours" description="Aucune réservation en cours." />
        )}
        {aFaireCheckOut.map((r) => (
          <Card key={r.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
            <div className="font-medium">
              {r.client_nom || `Réservation #${r.id}`} — départ {r.date_depart}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => telechargerFichePolice(r)}>
                Fiche de police (PDF)
              </Button>
              <Button disabled={busyId === r.id} onClick={() => checkOut(r)}>
                {busyId === r.id ? <Spinner className="size-4" /> : 'Check-out'}
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}

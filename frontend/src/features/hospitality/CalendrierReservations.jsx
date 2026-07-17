import { useEffect, useMemo, useState } from 'react'
import {
  Card, Badge, Button, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogFooter, EmptyState, Spinner, toast,
} from '../../ui'
import hospitalityApi from '../../api/hospitalityApi'

/* ============================================================================
   NTHOT21 — Calendrier réservations avec création par glisser-déposer.
   ----------------------------------------------------------------------------
   Grille planning hôtelier : une ligne par chambre, une colonne par jour
   (fenêtre glissante de ``NB_JOURS`` jours depuis aujourd'hui). Glisser depuis
   une case libre sélectionne une plage de dates ; un survol qui traverse une
   nuit déjà occupée (réservation ``confirmee``) est marqué en conflit — la
   création est BLOQUÉE (bouton désactivé) tant que le conflit n'est pas
   résolu, jamais une soumission qui laisserait le serveur trancher en
   silence (le serveur re-valide de toute façon, cf. NTHOT3).
   ========================================================================== */

const STATUT_TONE = {
  confirmee: 'success',
  en_attente: 'warning',
  annulee: 'danger',
  no_show: 'danger',
  en_cours: 'info',
  terminee: 'neutral',
}

const NB_JOURS = 14
const NON_BLOQUANTS = new Set(['annulee', 'no_show'])

function isoDate(date) {
  return date.toISOString().slice(0, 10)
}

function addDays(date, n) {
  const d = new Date(date)
  d.setDate(d.getDate() + n)
  return d
}

function buildJours() {
  const depart = new Date()
  depart.setHours(0, 0, 0, 0)
  return Array.from({ length: NB_JOURS }, (_, i) => addDays(depart, i))
}

function useReservationsData() {
  const [chambres, setChambres] = useState(null)
  const [reservations, setReservations] = useState(null)
  const [error, setError] = useState(null)

  const load = () => {
    Promise.all([hospitalityApi.listChambres(), hospitalityApi.listReservations()])
      .then(([resChambres, resReservations]) => {
        setChambres(resChambres.data?.results ?? resChambres.data ?? [])
        setReservations(resReservations.data?.results ?? resReservations.data ?? [])
      })
      .catch(() => setError('Calendrier des réservations indisponible.'))
  }

  return { chambres, reservations, error, load }
}

export default function CalendrierReservations() {
  const { chambres, reservations, error, load } = useReservationsData()
  const jours = useMemo(() => buildJours(), [])
  const [selection, setSelection] = useState(null) // { chambreId, startIdx, endIdx }
  const [dragging, setDragging] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [serverError, setServerError] = useState(null)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  if (error) {
    return <EmptyState title="Calendrier indisponible" description={error} />
  }
  if (!chambres || !reservations) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground">
        <Spinner className="size-4" /> Chargement du calendrier…
      </div>
    )
  }
  if (!chambres.length) {
    return (
      <EmptyState
        title="Aucune chambre"
        description="Créez des chambres pour afficher le calendrier des réservations."
      />
    )
  }

  const reservationsParChambre = (chambreId) =>
    reservations.filter(
      (r) => r.chambre === chambreId && !NON_BLOQUANTS.has(r.statut))

  const estOccupe = (chambreId, jour) => {
    const iso = isoDate(jour)
    return reservationsParChambre(chambreId).some(
      (r) => iso >= r.date_arrivee && iso < r.date_depart)
  }

  const range = () => {
    if (!selection) return null
    return {
      lo: Math.min(selection.startIdx, selection.endIdx),
      hi: Math.max(selection.startIdx, selection.endIdx),
    }
  }

  const inSelection = (chambreId, idx) => {
    if (!selection || selection.chambreId !== chambreId) return false
    const { lo, hi } = range()
    return idx >= lo && idx <= hi
  }

  const selectionConflict = () => {
    if (!selection) return false
    const { lo, hi } = range()
    for (let i = lo; i <= hi; i += 1) {
      if (estOccupe(selection.chambreId, jours[i])) return true
    }
    return false
  }

  const startDrag = (chambreId, idx) => {
    if (estOccupe(chambreId, jours[idx])) return
    setServerError(null)
    setDragging(true)
    setSelection({ chambreId, startIdx: idx, endIdx: idx })
  }

  const enterDrag = (chambreId, idx) => {
    if (!dragging || !selection || selection.chambreId !== chambreId) return
    setSelection((prev) => ({ ...prev, endIdx: idx }))
  }

  const endDrag = () => {
    if (dragging && selection) setConfirmOpen(true)
    setDragging(false)
  }

  const chambreEnCours = chambres.find((c) => c.id === selection?.chambreId)

  const confirmerCreation = () => {
    if (!selection || selectionConflict()) return
    const { lo, hi } = range()
    const dateArrivee = isoDate(jours[lo])
    const dateDepart = isoDate(addDays(jours[hi], 1))
    setSaving(true)
    setServerError(null)
    hospitalityApi
      .createReservation({
        chambre: selection.chambreId,
        date_arrivee: dateArrivee,
        date_depart: dateDepart,
      })
      .then(() => {
        toast.success('Réservation créée.')
        setConfirmOpen(false)
        setSelection(null)
        load()
      })
      .catch((err) => {
        setServerError(
          err?.response?.data?.chambre || 'Conflit de réservation.')
      })
      .finally(() => setSaving(false))
  }

  return (
    <div className="flex flex-col gap-3" onMouseUp={endDrag} onMouseLeave={endDrag}>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm select-none">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 min-w-[8rem] bg-card p-2 text-left">
                Chambre
              </th>
              {jours.map((jour) => (
                <th key={isoDate(jour)} className="min-w-[2.5rem] p-1 text-xs font-normal">
                  {jour.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {chambres.map((chambre) => (
              <tr key={chambre.id}>
                <td className="sticky left-0 z-10 bg-card p-2 font-medium">
                  {chambre.nom || chambre.numero}
                </td>
                {jours.map((jour, idx) => {
                  const occupe = estOccupe(chambre.id, jour)
                  const selected = inSelection(chambre.id, idx)
                  const conflit = selected && selectionConflict() && occupe
                  return (
                    <td
                      key={isoDate(jour)}
                      data-testid={`cell-${chambre.id}-${idx}`}
                      role="gridcell"
                      aria-label={
                        `${chambre.numero} ${isoDate(jour)}`
                        + (occupe ? ' occupée' : ' libre')
                      }
                      onMouseDown={() => startDrag(chambre.id, idx)}
                      onMouseEnter={() => enterDrag(chambre.id, idx)}
                      className={
                        'h-8 min-w-[2.5rem] cursor-pointer border border-border '
                        + (conflit
                          ? 'bg-destructive/40'
                          : selected
                            ? 'bg-primary/30'
                            : occupe
                              ? 'bg-muted'
                              : 'bg-transparent hover:bg-primary/10')
                      }
                    />
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-2">
        {chambres.map((chambre) => {
          const items = reservationsParChambre(chambre.id)
          if (!items.length) return null
          return (
            <Card key={chambre.id} className="flex flex-wrap items-center gap-3 p-3">
              <div className="w-28 shrink-0 font-semibold">
                {chambre.nom || chambre.numero}
              </div>
              {items.map((r) => (
                <Badge key={r.id} tone={STATUT_TONE[r.statut] || 'neutral'}>
                  {r.date_arrivee} → {r.date_depart}
                  {r.client_nom ? ` · ${r.client_nom}` : ''}
                </Badge>
              ))}
            </Card>
          )
        })}
      </div>

      {confirmOpen && selection && chambreEnCours && (
        <Dialog open onOpenChange={(o) => { if (!o) { setConfirmOpen(false); setSelection(null) } }}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>
                Nouvelle réservation — {chambreEnCours.nom || chambreEnCours.numero}
              </DialogTitle>
            </DialogHeader>
            <div className="flex flex-col gap-2 text-sm">
              <p>
                Du {isoDate(jours[range().lo])} au{' '}
                {isoDate(addDays(jours[range().hi], 1))}
              </p>
              {selectionConflict() && (
                <p className="text-destructive" role="alert">
                  Conflit : ces dates chevauchent une réservation existante sur
                  cette chambre.
                </p>
              )}
              {serverError && (
                <p className="text-destructive" role="alert">{serverError}</p>
              )}
            </div>
            <DialogFooter>
              <Button
                type="button" variant="outline"
                onClick={() => { setConfirmOpen(false); setSelection(null) }}
              >
                Annuler
              </Button>
              <Button
                type="button"
                disabled={selectionConflict() || saving}
                onClick={confirmerCreation}
              >
                {saving ? 'Création…' : 'Créer la réservation'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}

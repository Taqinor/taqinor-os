// LB15 — Flux « Marquer perdu » PARTAGÉ (fin de la triplication byte-à-byte
// entre LeadCard.jsx et ListView.jsx). Une seule popover : champ motif +
// datalist des motifs gérés (texte libre toléré), une seule requête via le
// callback stable `onMarkPerdu` (LB5) — JAMAIS d'écriture crmApi directe ici,
// JAMAIS de refetch. Les motifs de perte sont chargés PARESSEUSEMENT à la
// première ouverture (jamais à chaque montage — un kanban a des dizaines de
// cartes / une liste des dizaines de lignes).
import { useEffect, useState } from 'react'
import { Button, Popover, PopoverAnchor, PopoverContent, PopoverTrigger } from '../../../ui'
import crmApi from '../../../api/crmApi'

/**
 * PerduPopover — popover « Marquer perdu » réutilisable.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * CONTRAT D'EXPORT (référence pour lane LB3 / ListView, tâche LB21) :
 * ─────────────────────────────────────────────────────────────────────────────
 *  Props :
 *   - `lead` (obligatoire) : le lead à marquer perdu.
 *   - `onMarkPerdu(lead, motif)` (obligatoire) : callback STABLE de LeadsPage
 *     (LB5, blueprint I2). Il dispatch `updateLead({perdu:true, motif_perte})` —
 *     le store est la seule source de vérité, AUCUN refetch. Renvoie une
 *     Promise : sur REJET (échec réseau), le toast FR est déjà émis par
 *     onMarkPerdu et la popover RESTE ouverte pour retenter.
 *   - Mode AUTO-DÉCLENCHÉ : passer `trigger` (élément rendu en
 *     `PopoverTrigger asChild` — ex. le bouton ✗). L'état d'ouverture est
 *     interne.
 *   - Mode CONTRÔLÉ (ex. ouverture depuis un menu ••• DropdownMenu) : passer
 *     `open` + `onOpenChange`, et `anchor` (nœud rendu en `PopoverAnchor asChild`
 *     pour ancrer la popover puisqu'il n'y a pas de `trigger`).
 *   - `idPrefix` : préfixe d'`id` de la datalist (défaut 'perdu-motifs') — donner
 *     un préfixe distinct par surface évite toute collision d'id dans le DOM.
 *   - `align` : alignement de `PopoverContent` (défaut 'start').
 *
 *  Invariants garantis : chargement paresseux des motifs UNE fois, réinitialise
 *  le champ à la fermeture, jamais de mutation hors `onMarkPerdu`.
 */
export default function PerduPopover({
  lead,
  onMarkPerdu,
  trigger,
  anchor,
  open: openProp,
  onOpenChange: onOpenChangeProp,
  idPrefix = 'perdu-motifs',
  align = 'start',
}) {
  const controlled = openProp !== undefined
  const [openState, setOpenState] = useState(false)
  const open = controlled ? openProp : openState
  const [motif, setMotif] = useState('')
  const [busy, setBusy] = useState(false)
  const [motifs, setMotifs] = useState(null) // null = pas encore chargés

  const setOpen = (v) => {
    if (controlled) onOpenChangeProp?.(v)
    else setOpenState(v)
    if (!v) setMotif('')
  }

  useEffect(() => {
    if (!open || motifs !== null) return
    crmApi.getMotifsPerte()
      .then((r) => setMotifs(((r.data?.results ?? r.data) || []).filter((m) => !m.archived)))
      .catch(() => setMotifs([]))
  }, [open, motifs])

  const confirm = async () => {
    const m = motif.trim()
    if (!m || !onMarkPerdu) return
    setBusy(true)
    try {
      // LB5 — passe par le store (LeadsPage.onMarkPerdu) : la carte/ligne se
      // grise IMMÉDIATEMENT via Redux, aucun refetch. Toast d'échec déjà émis
      // par onMarkPerdu — on garde la popover ouverte pour retenter.
      await onMarkPerdu(lead, m)
      setOpen(false)
      setMotif('')
    } catch {
      // Échec réseau : toast déjà affiché en amont, popover reste ouverte.
    } finally {
      setBusy(false)
    }
  }

  const listId = `${idPrefix}-${lead?.id ?? 'x'}`

  return (
    <Popover open={open} onOpenChange={setOpen}>
      {trigger ? <PopoverTrigger asChild>{trigger}</PopoverTrigger> : null}
      {anchor ? <PopoverAnchor asChild>{anchor}</PopoverAnchor> : null}
      <PopoverContent
        align={align}
        onClick={(e) => e.stopPropagation()}
        onPointerDown={(e) => e.stopPropagation()}
      >
        <div className="kb-perdu-form">
          <p className="kb-perdu-title">Marquer perdu</p>
          <input
            className="form-control"
            list={listId}
            placeholder="Motif de perte"
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            autoFocus
          />
          <datalist id={listId}>
            {(motifs ?? []).map((m) => <option key={m.id} value={m.nom} />)}
          </datalist>
          <div className="kb-perdu-actions">
            <Button type="button" variant="outline" size="sm" onClick={() => setOpen(false)}>
              Annuler
            </Button>
            <Button
              type="button"
              size="sm"
              variant="destructive"
              disabled={!motif.trim() || busy}
              loading={busy}
              onClick={confirm}
            >
              Confirmer
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}

import { useEffect, useState } from 'react'
import { Download, Plus } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import { formatMAD } from '../../lib/format'
import {
  Button, Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle, Input, Label, toast,
} from '../../ui'

/* ============================================================================
   WIR103 — Note de débit (ZFAC4) depuis l'écran Facturation.
   ----------------------------------------------------------------------------
   Le serveur était complet et testé (création via
   `POST /ventes/factures/<id>/creer-note-debit/`, lecture
   `GET /ventes/notes-debit/?facture=<id>`, PDF
   `GET /ventes/notes-debit/<id>/telecharger-pdf/`) mais n'avait ZÉRO UI.

   Cette modale liste les notes de débit d'une facture et permet d'en créer une
   (motif libre ; sans lignes, le serveur recopie celles de la facture), puis
   de télécharger son PDF. Aucun prix d'achat ni marge n'est manipulé ici.
   ========================================================================== */

export default function NoteDebitDialog({ facture, open, onOpenChange }) {
  const [notes, setNotes] = useState([])
  const [loading, setLoading] = useState(false)
  const [motif, setMotif] = useState('')
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    if (!open || !facture?.id) return
    let active = true
    setLoading(true)
    ventesApi.getNotesDebit({ facture: facture.id })
      .then((r) => {
        if (!active) return
        const data = r.data
        setNotes(Array.isArray(data) ? data : (data?.results || []))
      })
      .catch(() => { if (active) setNotes([]) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [open, facture?.id])

  const creer = async () => {
    if (!facture?.id) return
    setCreating(true)
    try {
      const res = await ventesApi.creerNoteDebit(facture.id, { motif })
      setNotes((n) => [res.data, ...n])
      setMotif('')
      toast.success(`Note de débit ${res.data?.reference || ''} créée.`)
    } catch (e) {
      toast.error(
        e?.response?.data?.detail || 'Création de la note de débit impossible.')
    } finally {
      setCreating(false)
    }
  }

  const telecharger = async (note) => {
    try {
      const res = await ventesApi.telechargerNoteDebitPdf(note.id)
      openPdfBlob(res.data, `${note.reference || 'note-debit'}.pdf`)
    } catch {
      toast.error('PDF indisponible.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Notes de débit — {facture?.reference || '—'}</DialogTitle>
          <DialogDescription>
            Une note de débit majore une facture déjà émise (pendant de l&apos;avoir).
            Sans lignes personnalisées, elle reprend celles de la facture.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <p className="text-sm text-muted-foreground">Chargement…</p>
        ) : notes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucune note de débit sur cette facture.
          </p>
        ) : (
          <ul className="space-y-1">
            {notes.map((n) => (
              <li key={n.id} className="flex items-center justify-between gap-3 text-sm">
                <span>
                  <strong>{n.reference}</strong>
                  {n.total_ttc != null && ` · ${formatMAD(n.total_ttc)}`}
                </span>
                <Button size="sm" variant="ghost" onClick={() => telecharger(n)}>
                  <Download className="size-3.5" aria-hidden="true" />
                  PDF
                </Button>
              </li>
            ))}
          </ul>
        )}

        <div className="grid gap-1.5">
          <Label htmlFor="nd-motif">Motif</Label>
          <Input
            id="nd-motif"
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            placeholder="Ex. révision tarifaire, frais complémentaires…"
          />
        </div>

        <DialogFooter>
          <Button onClick={creer} disabled={creating}>
            <Plus className="size-3.5" aria-hidden="true" />
            Créer la note de débit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

import { useEffect, useState } from 'react'
import { Download, Plus } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import { formatMAD } from '../../lib/format'
import { useIsAdmin } from '../../hooks/useHasPermission'
import {
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader,
  AlertDialogTitle, AlertDialogDescription, AlertDialogFooter,
  AlertDialogCancel, AlertDialogAction,
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

// AFAC33 — `onChanged` (optionnel) : l'écran appelant recharge ses factures
// après une création / annulation (le reste dû change).
export default function NoteDebitDialog({ facture, open, onOpenChange, onChanged }) {
  const isAdmin = useIsAdmin()
  const [notes, setNotes] = useState([])
  // Facture dont `notes` reflète déjà le chargement — `loading` est DÉRIVÉ de
  // la comparaison avec la facture courante (jamais un `setLoading(true)`
  // synchrone dans l'effet, react-hooks/set-state-in-effect).
  const [loadedFactureId, setLoadedFactureId] = useState(null)
  const [motif, setMotif] = useState('')
  const [creating, setCreating] = useState(false)
  // AFAC33 — jamais « toute la facture » par défaut : montant HT saisi + taux.
  const [montant, setMontant] = useState('')
  const [tauxTva, setTauxTva] = useState('20')
  const [erreur, setErreur] = useState('')
  const [annulationId, setAnnulationId] = useState(null)

  // À chaque OUVERTURE (flanc montant de `open`), le chargement doit repartir
  // de zéro — y compris pour la même facture qu'une précédente ouverture.
  // Ajustement PENDANT LE RENDU (pas dans un effet), la valeur de repli
  // (`null`) étant déjà connue — même motif que SiteProfilePage.jsx /
  // « Adjusting some state when a prop changes »
  // (react.dev/learn/you-might-not-need-an-effect).
  const [wasOpen, setWasOpen] = useState(open)
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) setLoadedFactureId(null)
  }

  const factureId = facture?.id ?? null
  const loading = Boolean(open && factureId) && loadedFactureId !== factureId

  useEffect(() => {
    if (!open || !factureId) return
    let active = true
    ventesApi.getNotesDebit({ facture: factureId })
      .then((r) => {
        if (!active) return
        const data = r.data
        setNotes(Array.isArray(data) ? data : (data?.results || []))
      })
      .catch(() => { if (active) setNotes([]) })
      .finally(() => { if (active) setLoadedFactureId(factureId) })
    return () => { active = false }
  }, [open, factureId])

  const creer = async () => {
    if (!facture?.id) return
    setCreating(true); setErreur('')
    try {
      const res = await ventesApi.creerNoteDebit(
        facture.id, { motif, montant, taux_tva: tauxTva })
      setNotes((n) => [res.data, ...n])
      setMotif(''); setMontant('')
      toast.success(`Note de débit ${res.data?.reference || ''} créée.`)
      onChanged?.()
    } catch (e) {
      // Le message serveur est affiché TEL QUEL sous le champ.
      setErreur(
        e?.response?.data?.detail || 'Création de la note de débit impossible.')
    } finally {
      setCreating(false)
    }
  }

  const annuler = async (note) => {
    setAnnulationId(note.id); setErreur('')
    try {
      await ventesApi.annulerNoteDebit(note.id)
      setNotes((n) => n.map((x) => (x.id === note.id ? { ...x, annulee: true } : x)))
      toast.success(`Note de débit ${note.reference || ''} annulée.`)
      onChanged?.()
    } catch (e) {
      setErreur(e?.response?.data?.detail || 'Annulation de la note de débit impossible.')
    } finally { setAnnulationId(null) }
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
            Saisissez le montant HT à majorer : une note de débit ne copie
            jamais toute la facture.
            {facture?.montant_du != null && (
              <> Reste dû : <strong>{formatMAD(facture.montant_du)}</strong>.</>
            )}
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
                  {n.annulee && <> · <em>Annulée</em></>}
                </span>
                <span className="flex items-center gap-1">
                  <Button size="sm" variant="ghost" onClick={() => telecharger(n)}>
                    <Download className="size-3.5" aria-hidden="true" />
                    PDF
                  </Button>
                  {isAdmin && !n.annulee && n.statut !== 'annulee' && (
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button size="sm" variant="outline" loading={annulationId === n.id}
                                className="border-destructive/40 text-destructive hover:bg-destructive/10">
                          Annuler
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Annuler la note de débit {n.reference} ?</AlertDialogTitle>
                          <AlertDialogDescription>
                            Un avoir de note de débit la neutralise : le reste dû de la facture diminue d’autant.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Retour</AlertDialogCancel>
                          <AlertDialogAction onClick={() => annuler(n)}>Annuler la note de débit</AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  )}
                </span>
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
        <div className="grid grid-cols-2 gap-3">
          <div className="grid gap-1.5">
            <Label htmlFor="nd-montant">Montant HT (MAD)</Label>
            <Input id="nd-montant" type="number" step="any" min="0"
                   value={montant} onChange={(e) => setMontant(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="nd-tva">TVA (%)</Label>
            <Input id="nd-tva" type="number" step="any" min="0"
                   value={tauxTva} onChange={(e) => setTauxTva(e.target.value)} />
          </div>
        </div>
        {erreur && (
          <p role="alert" className="text-sm text-destructive">{erreur}</p>
        )}

        <DialogFooter>
          <Button onClick={creer}
                  disabled={creating || !(Number(montant) > 0)}>
            <Plus className="size-3.5" aria-hidden="true" />
            Créer la note de débit
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

import { useEffect, useState } from 'react'
import { PartyPopper, FileText, MessageCircle } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import {
  Button, Badge, Card, EmptyState, Spinner,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Label, Textarea,
} from '../../ui'
import { formatMAD } from '../../lib/format'

export default function RelancesPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [target, setTarget] = useState(null)  // facture being relancée
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => {
    setLoading(true)
    ventesApi.getRelances()
      .then(r => setRows(r.data)).catch(() => {}).finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const relancer = async () => {
    setBusy(true)
    try {
      await ventesApi.relancerFacture(target.id, {
        niveau: target.niveau?.ordre, note,
      })
      setTarget(null); setNote(''); load()
    } catch { /* */ } finally { setBusy(false) }
  }
  const exclure = async (r) => {
    if (!window.confirm('Exclure cette facture des relances ?')) return
    try { await ventesApi.exclureRelance(r.id, true); load() } catch { /* */ }
  }
  const lettre = async (r) => {
    try {
      const res = await ventesApi.getLettreRelancePdf(r.id)
      openPdfBlob(res.data, `Relance_${r.reference}.pdf`)
    } catch { alert('PDF indisponible.') }
  }
  // Rappel de paiement par WhatsApp : message « relance » + lien public.
  const whatsapp = async (r) => {
    try {
      const res = await ventesApi.whatsappFacture(r.id, { modele: 'relance' })
      if (res.data?.wa_url) window.open(res.data.wa_url, '_blank', 'noopener')
    } catch (err) {
      alert(err?.response?.data?.detail ?? 'Envoi WhatsApp impossible.')
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          Relances / Impayés
          <Badge tone="warning" className="ml-2 align-middle">{rows.length}</Badge>
        </h2>
      </div>
      <p className="mb-3 text-sm text-muted-foreground">
        Vue de recouvrement — consigner et imprimer uniquement. Aucun envoi
        automatique (email/SMS) n'est effectué.
      </p>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={PartyPopper}
          title="Aucune facture impayée"
          description="Toutes les factures sont à jour — rien à relancer."
          className="mt-1"
        />
      ) : (
        <Card className="mt-1 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Facture</th><th>Client</th><th>Échéance</th>
                  <th className="ta-right">Dû</th><th>Retard</th><th>Niveau</th>
                  <th>Relances</th><th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.id}>
                    <td><strong>{r.reference}</strong></td>
                    <td>{r.client_nom}</td>
                    <td className={r.jours_retard > 0 ? 'font-semibold text-destructive' : undefined}>
                      {r.date_echeance || '—'}
                    </td>
                    <td className="ta-right tabular-nums">{formatMAD(r.montant_du)}</td>
                    <td className={r.jours_retard > 0 ? 'text-destructive' : undefined}>
                      {r.jours_retard > 0 ? `${r.jours_retard} j` : '—'}
                    </td>
                    <td>{r.niveau ? <Badge tone="warning">{r.niveau.nom}</Badge> : '—'}</td>
                    <td>{r.nb_relances}</td>
                    <td className="ta-right">
                      <div className="flex flex-wrap items-center justify-end gap-2">
                        <Button size="sm" onClick={() => { setTarget(r); setNote('') }}>Relancer</Button>
                        <Button size="sm" variant="outline" onClick={() => whatsapp(r)} title="Rappel de paiement par WhatsApp">
                          <MessageCircle /> WhatsApp
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => lettre(r)}>
                          <FileText /> Lettre
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => exclure(r)}>Exclure</Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Dialog open={!!target} onOpenChange={(o) => { if (!o) setTarget(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Consigner une relance — {target?.reference}</DialogTitle>
            <DialogDescription>
              {target?.niveau ? `Niveau courant : ${target.niveau.nom}. ` : ''}
              Cette action journalise la relance (aucun envoi).
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="relance-note">Note (appel, courrier remis…)</Label>
            <Textarea id="relance-note" rows={3} value={note} onChange={e => setNote(e.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setTarget(null)}>Annuler</Button>
            <Button loading={busy} onClick={relancer}>Consigner</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

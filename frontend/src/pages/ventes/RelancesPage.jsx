import { useEffect, useMemo, useState } from 'react'
import { PartyPopper, FileText, MessageCircle, Mail } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { openPdfBlob } from '../../utils/pdfBlob'
import {
  Button, Badge, Card, EmptyState, Spinner,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Label, Textarea,
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
} from '../../ui'
import { formatMAD, toNumber } from '../../lib/format'

// Balance âgée : libellé du bucket d'ancienneté dérivé des jours de retard,
// cohérent avec /reporting/balance-agee (0–30 / 31–60 / 61–90 / 90+).
function ageBucket(joursRetard) {
  const jr = Number(joursRetard) || 0
  if (jr <= 0) return null
  if (jr <= 30) return '0–30 j'
  if (jr <= 60) return '31–60 j'
  if (jr <= 90) return '61–90 j'
  return '90+ j'
}

export default function RelancesPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [target, setTarget] = useState(null)  // facture being relancée
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [niveauFilter, setNiveauFilter] = useState('')  // '' = tous
  const [sortByDu, setSortByDu] = useState(false)  // tri par montant dû décroissant

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
  // Lettre de relance premium (langage visuel du devis) — niveau 1/2/3.
  const lettrePremium = async (r, niveau) => {
    try {
      const res = await ventesApi.getLettreRelancePremiumPdf(r.id, niveau)
      openPdfBlob(res.data, `Relance_${r.reference}_N${niveau}.pdf`)
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

  // Niveaux distincts présents (pour le filtre).
  const niveaux = useMemo(() => {
    const map = new Map()
    rows.forEach(r => { if (r.niveau) map.set(r.niveau.ordre, r.niveau.nom) })
    return [...map.entries()].sort((a, b) => a[0] - b[0])
  }, [rows])

  // Lignes affichées : filtre par niveau courant + tri optionnel par dû.
  const displayed = useMemo(() => {
    let list = rows
    if (niveauFilter === 'none') list = list.filter(r => !r.niveau)
    else if (niveauFilter !== '') {
      list = list.filter(r => r.niveau && String(r.niveau.ordre) === niveauFilter)
    }
    if (sortByDu) {
      list = [...list].sort(
        (a, b) => (toNumber(b.montant_du) || 0) - (toNumber(a.montant_du) || 0))
    }
    return list
  }, [rows, niveauFilter, sortByDu])

  // Encours total à recouvrer (somme des montants dus affichés).
  const totalDu = useMemo(
    () => displayed.reduce((s, r) => s + (toNumber(r.montant_du) || 0), 0),
    [displayed])

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

      {!loading && rows.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <Card className="px-4 py-2 text-sm">
            <span className="text-muted-foreground">Total à recouvrer : </span>
            <strong className="tabular-nums">{formatMAD(totalDu)}</strong>
            <span className="text-muted-foreground"> sur {displayed.length} facture{displayed.length > 1 ? 's' : ''}</span>
          </Card>
          <label className="flex items-center gap-1.5 text-sm">
            Niveau&nbsp;:
            <select
              className="rounded border px-2 py-1"
              value={niveauFilter}
              onChange={e => setNiveauFilter(e.target.value)}
            >
              <option value="">Tous</option>
              <option value="none">Sans niveau</option>
              {niveaux.map(([ordre, nom]) => (
                <option key={ordre} value={String(ordre)}>{nom}</option>
              ))}
            </select>
          </label>
        </div>
      )}

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
                  <th
                    className="ta-right cursor-pointer select-none"
                    onClick={() => setSortByDu(v => !v)}
                    title="Trier par montant dû décroissant"
                  >
                    Dû{sortByDu ? ' ↓' : ''}
                  </th>
                  <th>Retard</th><th>Âge</th><th>Niveau</th>
                  <th>Relances</th><th></th>
                </tr>
              </thead>
              <tbody>
                {displayed.map(r => (
                  <tr key={r.id}>
                    <td><strong>{r.reference}</strong></td>
                    <td>{r.client_nom}</td>
                    <td className={r.jours_retard > 0 ? 'font-semibold text-destructive' : undefined}>
                      {r.date_echeance || '—'}
                    </td>
                    <td className="ta-right tabular-nums">{formatMAD(r.montant_du)}</td>
                    <td className={r.jours_retard > 0 ? 'text-destructive' : undefined}>
                      {r.jours_retard > 0
                        ? `${r.jours_retard} j`
                        : <span className="text-muted-foreground">À échoir</span>}
                    </td>
                    <td>{ageBucket(r.jours_retard)
                      ? <Badge tone="warning">{ageBucket(r.jours_retard)}</Badge>
                      : '—'}</td>
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
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button size="sm" variant="outline" title="Lettre de relance premium">
                              <Mail /> Relance premium
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => lettrePremium(r, 1)}>
                              Niveau 1 — courtois
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => lettrePremium(r, 2)}>
                              Niveau 2 — ferme
                            </DropdownMenuItem>
                            <DropdownMenuItem onClick={() => lettrePremium(r, 3)}>
                              Niveau 3 — mise en demeure
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
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

import { useEffect, useMemo, useState } from 'react'
import { PackageOpen, Plus } from 'lucide-react'
import contratsApi from '../../api/contratsApi'
import stockApi from '../../api/stockApi'
import crmApi from '../../api/crmApi'
import {
  Card, Badge, Button, Segmented, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea,
} from '../../ui'
import { StatutLocation, StatutCautionLocation } from './locationStatus'
import { formatMAD, formatDate } from '../../lib/format'
import { openPdfInGesture } from '../../utils/pdfBlob'
import SimpleTable from './SimpleTable'

/* ============================================================================
   XCTR17-21 — Location SORTANTE de matériel (module « Location »).
   ----------------------------------------------------------------------------
   Liste des ordres de location (OrdreLocation) avec création (produit louable +
   client + fenêtre), machine d'états locale gardée (réservée → enlevée →
   retournée → clôturée / annulée), caution (encaisser / restituer / retenir —
   XCTR18), retour + inspection + retards (XCTR19), longue durée (facturer un
   cycle, prolonger, écourter — XCTR20), et bons PDF (enlèvement / restitution).
   Aucune donnée de coût interne (prix d'achat / ROI admin) n'apparaît ici.
   ========================================================================== */

const listData = (res) => (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const STATUT_FILTERS = [
  { value: 'tous', label: 'Tous' },
  { value: 'reservee', label: 'Réservées' },
  { value: 'enlevee', label: 'Enlevées' },
  { value: 'retournee', label: 'Retournées' },
  { value: 'cloturee', label: 'Clôturées' },
  { value: 'retard', label: 'En retard' },
]

export default function LocationPage() {
  const [ordres, setOrdres] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('tous')
  const [creating, setCreating] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    const call = filter === 'retard'
      ? contratsApi.ordresLocationEnRetard()
      : contratsApi.getOrdresLocation(filter === 'tous' ? {} : { statut: filter })
    call
      .then((r) => setOrdres(listData(r)))
      .catch(() => setError('Impossible de charger les locations.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refetch on filter change
  }, [filter])

  const changerStatut = async (ordre, statut, label) => {
    setBusyId(ordre.id)
    try {
      await contratsApi.changerStatutOrdreLocation(ordre.id, statut)
      toast.success(label)
      load()
    } catch (e) { toast.error(errMsg(e, 'Transition refusée.')) } finally { setBusyId(null) }
  }

  const action = async (fn, ok) => {
    try { await fn(); toast.success(ok); load() }
    catch (e) { toast.error(errMsg(e, 'Action impossible.')) }
  }

  // VX48 — onglet pré-ouvert SYNCHRONE avant l'await (Safari iOS bloque
  // silencieusement un window.open() post-await).
  const bonPdf = async (ordre, kind) => {
    const pending = openPdfInGesture()
    try {
      const res = kind === 'enlevement'
        ? await contratsApi.getBonEnlevement(ordre.id)
        : await contratsApi.getBonRestitution(ordre.id)
      const blob = new Blob([res.data], { type: 'application/pdf' })
      if (!pending.deliver(blob, `${kind}-${ordre.id}.pdf`)) {
        toast.error('Ouverture bloquée par le navigateur.')
      }
    } catch { toast.error('Bon PDF indisponible.') }
  }

  const rows = useMemo(() => ordres, [ordres])

  const columns = [
    { header: 'Produit', cell: (o) => <span className="font-medium">{o.produit_nom || `#${o.produit}`}</span> },
    { header: 'Client', cell: (o) => <span className="font-mono text-xs">#{o.client_id}</span> },
    { header: 'Enlèvement', cell: (o) => (o.date_enlevement_prevue ? formatDate(o.date_enlevement_prevue) : '—') },
    { header: 'Retour', cell: (o) => (o.date_retour_prevue ? formatDate(o.date_retour_prevue) : '—') },
    { header: 'Estimé', cell: (o) => (o.montant_estime != null ? formatMAD(o.montant_estime) : '—'), align: 'right' },
    { header: 'Caution', cell: (o) => <StatutCautionLocation status={o.caution_statut} /> },
    { header: 'Statut', cell: (o) => <StatutLocation status={o.statut} /> },
    {
      header: 'Actions',
      align: 'right',
      cell: (o) => <OrdreActions ordre={o} busy={busyId === o.id} changerStatut={changerStatut} action={action} bonPdf={bonPdf} />,
    },
  ]

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <PackageOpen className="size-5 text-muted-foreground" aria-hidden="true" />
          <h1 className="font-display text-xl font-semibold tracking-tight">Location de matériel</h1>
        </div>
        <Button onClick={() => setCreating(true)}><Plus /> Nouvel ordre</Button>
      </div>

      <Segmented options={STATUT_FILTERS} value={filter} onChange={setFilter} aria-label="Filtrer par statut" />

      {error ? (
        <Card className="border-destructive/40 p-3">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={load}>Réessayer</Button>
        </Card>
      ) : (
        <SimpleTable
          emptyText={loading ? 'Chargement…' : 'Aucun ordre de location.'}
          rows={rows}
          columns={columns}
        />
      )}

      {creating && (
        <CreateOrdreDialog onClose={() => setCreating(false)} onDone={() => { setCreating(false); load() }} />
      )}
    </div>
  )
}

function OrdreActions({ ordre, busy, changerStatut, action, bonPdf }) {
  const s = ordre.statut
  return (
    <div className="flex flex-wrap justify-end gap-1.5">
      {s === 'reservee' && (
        <>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => changerStatut(ordre, 'enlevee', 'Matériel enlevé.')}>Enlever</Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => changerStatut(ordre, 'annulee', 'Ordre annulé.')}>Annuler</Button>
          <Button size="sm" variant="ghost" onClick={() => bonPdf(ordre, 'enlevement')}>Bon</Button>
        </>
      )}
      {s === 'enlevee' && (
        <>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => changerStatut(ordre, 'retournee', 'Matériel retourné.')}>Retour</Button>
          <CautionActions ordre={ordre} action={action} />
        </>
      )}
      {s === 'retournee' && (
        <>
          <InspecterButton ordre={ordre} action={action} />
          <Button size="sm" variant="outline" disabled={busy} onClick={() => action(() => contratsApi.cloturerOrdreLocation(ordre.id), 'Ordre clôturé.')}>Clôturer</Button>
          <Button size="sm" variant="ghost" onClick={() => bonPdf(ordre, 'restitution')}>Bon</Button>
          <CautionActions ordre={ordre} action={action} />
        </>
      )}
      {(s === 'cloturee' || s === 'annulee') && (
        <Button size="sm" variant="ghost" onClick={() => bonPdf(ordre, 'restitution')}>Bon</Button>
      )}
    </div>
  )
}

// XCTR18 — caution : encaisser (réservée/enlevée) / restituer / retenir.
function CautionActions({ ordre, action }) {
  if (ordre.caution_statut === 'encaissee') {
    return (
      <>
        <Button size="sm" variant="ghost" onClick={() => action(() => contratsApi.cautionRestituer(ordre.id), 'Caution restituée.')}>Rendre caution</Button>
        <RetenirCautionButton ordre={ordre} action={action} />
      </>
    )
  }
  return (
    <EncaisserCautionButton ordre={ordre} action={action} />
  )
}

function EncaisserCautionButton({ ordre, action }) {
  const [open, setOpen] = useState(false)
  const [montant, setMontant] = useState('')
  return (
    <>
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>Encaisser caution</Button>
      {open && (
        <Dialog open onOpenChange={(o) => { if (!o) setOpen(false) }}>
          <DialogContent className="max-w-sm">
            <DialogHeader><DialogTitle>Encaisser la caution</DialogTitle></DialogHeader>
            <form
              className="flex flex-col gap-4"
              noValidate
              onSubmit={(e) => {
                e.preventDefault()
                action(() => contratsApi.cautionEncaisser(ordre.id, montant ? Number(montant) : undefined), 'Caution encaissée.')
                setOpen(false)
              }}
            >
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="cau-montant">Montant (optionnel — défaut : caution prévue)</Label>
                <Input id="cau-montant" type="number" step="any" value={montant} onChange={(e) => setMontant(e.target.value)} />
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>Annuler</Button>
                <Button type="submit">Encaisser</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}
    </>
  )
}

function RetenirCautionButton({ ordre, action }) {
  const [open, setOpen] = useState(false)
  const [montant, setMontant] = useState('')
  const [motif, setMotif] = useState('')
  return (
    <>
      <Button size="sm" variant="ghost" onClick={() => setOpen(true)}>Retenir caution</Button>
      {open && (
        <Dialog open onOpenChange={(o) => { if (!o) setOpen(false) }}>
          <DialogContent className="max-w-sm">
            <DialogHeader><DialogTitle>Retenir sur la caution</DialogTitle></DialogHeader>
            <form
              className="flex flex-col gap-4"
              noValidate
              onSubmit={(e) => {
                e.preventDefault()
                action(() => contratsApi.cautionRetenir(ordre.id, { montant_retenu: Number(montant), motif }), 'Retenue enregistrée + facturée.')
                setOpen(false)
              }}
            >
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="ret-montant">Montant retenu</Label>
                <Input id="ret-montant" type="number" step="any" value={montant} onChange={(e) => setMontant(e.target.value)} required />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="ret-motif">Motif</Label>
                <Textarea id="ret-motif" rows={2} value={motif} onChange={(e) => setMotif(e.target.value)} />
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>Annuler</Button>
                <Button type="submit" variant="destructive">Retenir</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}
    </>
  )
}

// XCTR19 — inspection de retour (checklist + relevé + dommages chiffrés).
function InspecterButton({ ordre, action }) {
  const [open, setOpen] = useState(false)
  const [releve, setReleve] = useState('')
  const [dommages, setDommages] = useState('')
  const [motif, setMotif] = useState('')
  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>Inspecter</Button>
      {open && (
        <Dialog open onOpenChange={(o) => { if (!o) setOpen(false) }}>
          <DialogContent className="max-w-md">
            <DialogHeader><DialogTitle>Inspection de retour</DialogTitle></DialogHeader>
            <form
              className="flex flex-col gap-4"
              noValidate
              onSubmit={(e) => {
                e.preventDefault()
                const data = {}
                if (releve.trim()) data.releve_compteur = releve.trim()
                if (dommages !== '') { data.dommages_montant = Number(dommages); data.motif_dommages = motif }
                action(() => contratsApi.inspecterOrdreLocation(ordre.id, data), 'Inspection enregistrée.')
                setOpen(false)
              }}
            >
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="insp-releve">Relevé compteur</Label>
                <Input id="insp-releve" value={releve} onChange={(e) => setReleve(e.target.value)} placeholder="Optionnel" />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="insp-dommages">Dommages chiffrés (MAD)</Label>
                <Input id="insp-dommages" type="number" step="any" value={dommages} onChange={(e) => setDommages(e.target.value)} placeholder="0 si RAS" />
              </div>
              {dommages !== '' && (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="insp-motif">Motif des dommages</Label>
                  <Textarea id="insp-motif" rows={2} value={motif} onChange={(e) => setMotif(e.target.value)} />
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Des dommages chiffrés génèrent une ligne de facture + un ticket SAV.
              </p>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setOpen(false)}>Annuler</Button>
                <Button type="submit">Enregistrer</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}
    </>
  )
}

// XCTR17 — création d'un ordre : produit louable + client + fenêtre.
function CreateOrdreDialog({ onClose, onDone }) {
  const [produits, setProduits] = useState([])
  const [clients, setClients] = useState([])
  const [produitId, setProduitId] = useState('')
  const [clientId, setClientId] = useState('')
  const [numeroSerie, setNumeroSerie] = useState('')
  const [dateReservation, setDateReservation] = useState('')
  const [dateEnlevement, setDateEnlevement] = useState('')
  const [dateRetour, setDateRetour] = useState('')
  const [tarifJour, setTarifJour] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  useEffect(() => {
    stockApi.getProduits()
      // Seuls les produits marqués « louable » peuvent faire l'objet d'un ordre
      // (le backend refuse les autres — on filtre côté client pour l'ergonomie).
      .then((r) => setProduits(listData(r).filter((p) => p.louable)))
      .catch(() => setProduits([]))
    crmApi.getClients({ page: 1 })
      .then((r) => setClients(listData(r)))
      .catch(() => setClients([]))
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    if (!produitId || !clientId || !dateReservation || !dateEnlevement || !dateRetour) {
      setErr('Produit, client et les trois dates sont requis.')
      return
    }
    setSaving(true)
    setErr(null)
    try {
      await contratsApi.createOrdreLocation({
        produit: Number(produitId),
        client_id: Number(clientId),
        numero_serie: numeroSerie,
        date_reservation: dateReservation,
        date_enlevement_prevue: dateEnlevement,
        date_retour_prevue: dateRetour,
        tarif_jour: tarifJour ? Number(tarifJour) : undefined,
        note,
      })
      toast.success('Ordre de location créé.')
      onDone()
    } catch (e2) {
      const d = e2?.response?.data
      setErr(d?.detail || d?.produit || d?.client_id || 'Création impossible.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle>Nouvel ordre de location</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="loc-produit">Produit louable</Label>
            <select
              id="loc-produit"
              value={produitId}
              onChange={(e) => setProduitId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {produits.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
            </select>
            {produits.length === 0 && (
              <p className="text-xs text-muted-foreground">Aucun produit marqué « louable » dans le stock.</p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="loc-client">Client</Label>
            <select
              id="loc-client"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Choisir —</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>{c.nom || c.raison_sociale || `Client #${c.id}`}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="loc-serie">Numéro de série</Label>
            <Input id="loc-serie" value={numeroSerie} onChange={(e) => setNumeroSerie(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="loc-res">Réservation</Label>
              <Input id="loc-res" type="date" value={dateReservation} onChange={(e) => setDateReservation(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="loc-enl">Enlèvement</Label>
              <Input id="loc-enl" type="date" value={dateEnlevement} onChange={(e) => setDateEnlevement(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="loc-ret">Retour</Label>
              <Input id="loc-ret" type="date" value={dateRetour} onChange={(e) => setDateRetour(e.target.value)} />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="loc-tarif">Tarif / jour (MAD)</Label>
            <Input id="loc-tarif" type="number" step="any" value={tarifJour} onChange={(e) => setTarifJour(e.target.value)} placeholder="Optionnel — défaut du produit" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="loc-note">Note</Label>
            <Textarea id="loc-note" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          {err && <p className="text-sm text-destructive" role="alert"><Badge tone="danger">Erreur</Badge> {err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer l’ordre'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

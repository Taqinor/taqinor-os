import { useEffect, useMemo, useState } from 'react'
import { Banknote, FileText, Plus, AlertTriangle } from 'lucide-react'
import api from '../../api/axios'
import { PageHeader } from '../../ui/PageHeader'
import { VENTES_ACCENT_STYLE } from '../../features/ventes/accent'
import {
  Badge, Button, Card, Checkbox, EmptyState, Input, Label, Skeleton, Textarea,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../../ui'
import { Table } from '../reporting/Table'
import { formatMAD, formatDate, toNumber } from '../../lib/format'
import { openPdfBlob } from '../../utils/pdfBlob'
import { toast, useConfirmDialog } from '../../ui/confirm'

/* ============================================================================
   PACT46 — Remises d'encaissement terrain (XFSM19).
   ----------------------------------------------------------------------------
   Un technicien qui encaisse des ESPÈCES ou des CHÈQUES chez le client déclare
   sa collecte ; le responsable la clôture, ce qui génère un bordereau PDF.
   Sans écran, il n'existait AUCUN contrôle sur l'argent liquide collecté.

   L'ÉCART (montant déclaré − somme des paiements rattachés) est calculé par le
   serveur et n'est JAMAIS masqué ici : il est affiché en permanence sur la
   ligne, et la clôture d'une remise à écart non nul lève une alerte explicite
   (la clôture reste possible — c'est un contrôle, pas un blocage).

   Endpoints (apps/ventes/views/remise_encaissement.py) :
     GET  /ventes/remises-encaissement/                liste (scopée société)
     POST /ventes/remises-encaissement/                déclaration + lignes
     POST /ventes/remises-encaissement/{id}/cloturer/  clôture (responsable)
     GET  /ventes/remises-encaissement/{id}/pdf/       bordereau PDF
   ========================================================================== */

const MODES_TERRAIN = ['especes', 'cheque']
const TONE_STATUT = { ouverte: 'warning', cloturee: 'info', validee: 'success' }

const aujourdhui = () => new Date().toISOString().slice(0, 10)

export default function RemisesEncaissementPage() {
  const { confirm } = useConfirmDialog()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(false)
  const [busyId, setBusyId] = useState(null)
  // Alerte d'écart renvoyée par la clôture (jamais masquée).
  const [alerteEcart, setAlerteEcart] = useState(null)

  // ── Déclaration d'une nouvelle remise ──
  const [creationOuverte, setCreationOuverte] = useState(false)
  const [dateCollecte, setDateCollecte] = useState(aujourdhui())
  const [montantDeclare, setMontantDeclare] = useState('')
  const [note, setNote] = useState('')
  const [paiements, setPaiements] = useState([])
  const [selection, setSelection] = useState({})
  const [creationBusy, setCreationBusy] = useState(false)

  const charger = () => api.get('/ventes/remises-encaissement/')
    .then((r) => {
      const data = r.data
      setRows(Array.isArray(data) ? data : (data?.results || []))
      setErreur(false)
    })
    .catch(() => { setRows([]); setErreur(true) })
    .finally(() => setLoading(false))

  // `loading`/`erreur` démarrent déjà à leurs valeurs de chargement : aucun
  // reset synchrone dans l'effet (react-hooks/set-state-in-effect).
  useEffect(() => { charger() }, [])

  const ouvrirCreation = async () => {
    setCreationOuverte(true)
    setDateCollecte(aujourdhui())
    setMontantDeclare('')
    setNote('')
    setSelection({})
    try {
      const res = await api.get('/ventes/paiements/')
      const data = res.data
      const liste = Array.isArray(data) ? data : (data?.results || [])
      // Seuls les encaissements TERRAIN (espèces / chèque) sont remisables.
      setPaiements(liste.filter((p) => MODES_TERRAIN.includes(p.mode)))
    } catch {
      setPaiements([])
    }
  }

  const basculer = (id) => setSelection((s) => ({ ...s, [id]: !s[id] }))

  const totalSelection = useMemo(
    () => paiements
      .filter((p) => selection[p.id])
      .reduce((s, p) => s + (toNumber(p.montant) || 0), 0),
    [paiements, selection],
  )

  // Écart PRÉVISIONNEL montré pendant la saisie : le responsable voit l'écart
  // avant même de déclarer, il ne le découvre pas à la clôture.
  const ecartPrevisionnel = (toNumber(montantDeclare) || 0) - totalSelection

  const creer = async () => {
    setCreationBusy(true)
    try {
      // `company`, `reference`, `created_by` sont imposés par le serveur.
      await api.post('/ventes/remises-encaissement/', {
        date_collecte: dateCollecte,
        montant_declare: montantDeclare,
        note,
        lignes: Object.keys(selection)
          .filter((id) => selection[id])
          .map((id) => ({ paiement: Number(id) })),
      })
      toast.success('Remise déclarée.')
      setCreationOuverte(false)
      setLoading(true)
      await charger()
    } catch {
      toast.error('Déclaration de la remise impossible.')
    } finally { setCreationBusy(false) }
  }

  const cloturer = async (remise) => {
    const ok = await confirm({
      title: `Clôturer la remise ${remise.reference || `#${remise.id}`} ?`,
      description: 'Les lignes seront verrouillées et le bordereau PDF généré.',
      confirmLabel: 'Clôturer',
      destructive: false,
    })
    if (!ok) return
    setBusyId(remise.id)
    try {
      const res = await api.post(
        `/ventes/remises-encaissement/${remise.id}/cloturer/`)
      if (res.data?.ecart_non_nul) {
        setAlerteEcart({
          reference: res.data.reference || remise.reference,
          ecart: res.data.ecart,
        })
      } else {
        toast.success('Remise clôturée — aucun écart.')
      }
      setLoading(true)
      await charger()
    } catch {
      toast.error('Clôture impossible.')
    } finally { setBusyId(null) }
  }

  const bordereau = async (remise) => {
    try {
      const res = await api.get(
        `/ventes/remises-encaissement/${remise.id}/pdf/`,
        { responseType: 'blob' })
      openPdfBlob(res.data, `Bordereau_${remise.reference || remise.id}.pdf`)
    } catch {
      toast.error('Bordereau indisponible.')
    }
  }

  const colonnes = [
    {
      key: 'reference',
      header: 'Remise',
      cell: (r) => <strong>{r.reference || `#${r.id}`}</strong>,
    },
    { key: 'technicien', header: 'Technicien', cell: (r) => r.technicien_nom || '—' },
    {
      key: 'date_collecte',
      header: 'Collecte',
      cell: (r) => (r.date_collecte ? formatDate(r.date_collecte) : '—'),
    },
    {
      key: 'montant_declare',
      header: 'Déclaré',
      align: 'right',
      cell: (r) => formatMAD(r.montant_declare),
    },
    {
      key: 'montant_lignes',
      header: 'Lignes',
      align: 'right',
      cell: (r) => formatMAD(r.montant_lignes),
    },
    {
      // L'écart n'est JAMAIS masqué — c'est la raison d'être de cet écran.
      key: 'ecart',
      header: 'Écart',
      align: 'right',
      cell: (r) => (toNumber(r.ecart)
        ? <Badge tone="danger">{formatMAD(r.ecart)}</Badge>
        : <span className="text-muted-foreground">{formatMAD(0)}</span>),
    },
    {
      key: 'statut',
      header: 'Statut',
      cell: (r) => (
        <Badge tone={TONE_STATUT[r.statut] || 'neutral'}>
          {r.statut_display || r.statut}
        </Badge>
      ),
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      cell: (r) => (
        <div className="flex flex-wrap items-center justify-end gap-2">
          {r.statut === 'ouverte' && (
            <Button size="sm" loading={busyId === r.id} disabled={busyId === r.id}
                    onClick={() => cloturer(r)}>
              Clôturer
            </Button>
          )}
          {r.statut !== 'ouverte' && (
            <Button size="sm" variant="outline" onClick={() => bordereau(r)}>
              <FileText /> Bordereau PDF
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="page">
      <PageHeader
        style={VENTES_ACCENT_STYLE}
        className="app-accent-rail"
        icon={Banknote}
        title="Remises d'encaissement terrain"
        subtitle="Collectes espèces et chèques déclarées par les techniciens, clôturées par le responsable. L'écart déclaré / encaissé est toujours affiché."
        actions={(
          <Button onClick={ouvrirCreation}>
            <Plus /> Déclarer une remise
          </Button>
        )}
      />

      {/* Alerte d'écart à la clôture — explicite, jamais un simple toast. */}
      {alerteEcart && (
        <Card className="mb-4 flex items-start gap-2 border-destructive/40 p-3 text-sm"
              role="alert">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive"
                         aria-hidden="true" />
          <div>
            <p className="m-0 font-semibold text-destructive">
              Écart constaté à la clôture — {formatMAD(alerteEcart.ecart)}
            </p>
            <p className="m-0 text-muted-foreground">
              La remise {alerteEcart.reference} a été clôturée, mais le montant
              déclaré ne correspond pas à la somme des paiements rattachés.
            </p>
          </div>
          <Button size="sm" variant="ghost" className="ml-auto"
                  onClick={() => setAlerteEcart(null)}>
            Fermer
          </Button>
        </Card>
      )}

      <Card className="overflow-hidden">
        {loading && <Skeleton className="m-4 h-24" />}
        {!loading && erreur && (
          <EmptyState
            title="Chargement impossible"
            description="Les remises d'encaissement n'ont pas pu être chargées."
          />
        )}
        {!loading && !erreur && rows.length === 0 && (
          <EmptyState
            icon={Banknote}
            title="Aucune remise"
            description="Aucune collecte terrain déclarée pour votre société."
          />
        )}
        {!loading && !erreur && rows.length > 0 && (
          <Table
            aria-label="Remises d'encaissement terrain"
            caption="Remises d'encaissement terrain par technicien"
            rows={rows}
            getRowKey={(r) => r.id}
            columns={colonnes}
          />
        )}
      </Card>

      {/* ── Déclaration d'une collecte ── */}
      <Dialog open={creationOuverte}
              onOpenChange={(o) => { if (!o) setCreationOuverte(false) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Déclarer une remise d&apos;encaissement</DialogTitle>
            <DialogDescription>
              Rattachez les encaissements espèces / chèque déjà enregistrés, puis
              déclarez le montant réellement collecté. L&apos;écart est calculé et
              affiché immédiatement.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="remise-date">Date de collecte</Label>
              <Input id="remise-date" type="date" value={dateCollecte}
                     onChange={(e) => setDateCollecte(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="remise-montant">Montant déclaré (MAD)</Label>
              <Input id="remise-montant" type="number" step="any"
                     value={montantDeclare}
                     onChange={(e) => setMontantDeclare(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <span className="text-sm font-medium">Encaissements terrain</span>
              {paiements.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Aucun encaissement espèces ou chèque disponible.
                </p>
              ) : (
                <ul className="max-h-48 space-y-1 overflow-y-auto text-sm">
                  {paiements.map((p) => (
                    <li key={p.id} className="flex items-center gap-2">
                      <Checkbox checked={!!selection[p.id]}
                                onCheckedChange={() => basculer(p.id)}
                                aria-label={`Rattacher le paiement ${p.id}`} />
                      <span className="tabular-nums">{formatMAD(p.montant)}</span>
                      <span className="text-muted-foreground">
                        {p.mode_display || p.mode}
                        {p.facture_reference ? ` · ${p.facture_reference}` : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <p className="text-sm">
              <span className="text-muted-foreground">Somme rattachée : </span>
              <strong className="tabular-nums">{formatMAD(totalSelection)}</strong>
              <span className="text-muted-foreground"> — écart : </span>
              <strong className={ecartPrevisionnel !== 0
                ? 'tabular-nums text-destructive' : 'tabular-nums'}>
                {formatMAD(ecartPrevisionnel)}
              </strong>
            </p>
            <div className="grid gap-1.5">
              <Label htmlFor="remise-note">Note</Label>
              <Textarea id="remise-note" rows={2} value={note}
                        onChange={(e) => setNote(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreationOuverte(false)}>
              Annuler
            </Button>
            <Button loading={creationBusy}
                    disabled={!dateCollecte || !montantDeclare}
                    onClick={creer}>
              Déclarer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

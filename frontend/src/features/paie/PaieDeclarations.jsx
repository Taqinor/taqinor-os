import { useEffect, useState } from 'react'
import {
  Banknote, FileDown, Send, RefreshCw, FileSpreadsheet, ListChecks,
} from 'lucide-react'
import {
  Button, Card, Spinner, EmptyState, Badge, toast,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { DataTable } from '../../ui'
import { formatMAD } from '../../lib/format'
import paieApi from '../../api/paieApi'
import { StatutOrdre } from './statuses.jsx'
import { ORDRE_STATUTS } from './paieLogic.js'

/* ============================================================================
   UX13 — Déclarations & virements.
   ----------------------------------------------------------------------------
   Ordres de virement (fichier banque), déclaration CNSS + fichier DAMANCOM,
   état IR, livre de paie, avances & saisies, cumuls annuels. Les états/fichiers
   descendent en JSON (le serveur ne renvoie pas de blob binaire ici) et sont
   proposés au téléchargement en JSON. Montants via formatMAD ; aucune marge.
   ========================================================================== */
export default function PaieDeclarations() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Déclarations & virements
        </h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Ordres de virement, CNSS/DAMANCOM, états IR, livre de paie, avances &
          saisies, cumuls.
        </p>
      </div>
      <Tabs defaultValue="virements">
        <TabsList className="flex-wrap">
          <TabsTrigger value="virements">Virements</TabsTrigger>
          <TabsTrigger value="declarations">Déclarations</TabsTrigger>
          <TabsTrigger value="avances">Avances & saisies</TabsTrigger>
          <TabsTrigger value="cumuls">Cumuls annuels</TabsTrigger>
        </TabsList>
        <TabsContent value="virements"><VirementsTab /></TabsContent>
        <TabsContent value="declarations"><DeclarationsTab /></TabsContent>
        <TabsContent value="avances"><AvancesTab /></TabsContent>
        <TabsContent value="cumuls"><CumulsTab /></TabsContent>
      </Tabs>
    </div>
  )
}

/* Télécharge un objet JSON (état/fichier généré) en pièce jointe. */
function downloadJson(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 2)],
    { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 10000)
}

/* ── Ordres de virement ── */
function VirementsTab() {
  const [rows, setRows] = useState([])
  const [periodes, setPeriodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [periodeId, setPeriodeId] = useState('')
  const [busy, setBusy] = useState('')

  const load = () =>
    Promise.all([paieApi.getOrdresVirement(), paieApi.getPeriodes()])
      .then(([o, p]) => {
        setRows(listOf(o.data))
        setPeriodes(listOf(p.data))
      })
      .catch(() => toast.error('Chargement des virements impossible.'))
      .finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const generer = async () => {
    if (!periodeId) { toast.error('Choisissez une période.'); return }
    setBusy('generer')
    try {
      await paieApi.genererOrdreVirement({ periode: Number(periodeId) })
      toast.success('Ordre de virement généré.')
      await load()
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Génération impossible.')
    } finally { setBusy('') }
  }

  const emettre = async (row) => {
    setBusy(`emettre-${row.id}`)
    try {
      await paieApi.emettreOrdreVirement(row.id)
      toast.success('Ordre émis (figé).')
      await load()
    } catch {
      toast.error('Émission impossible.')
    } finally { setBusy('') }
  }

  const fichier = async (row) => {
    setBusy(`fichier-${row.id}`)
    try {
      const { data } = await paieApi.fichierVirement(row.id)
      downloadJson(data, `virement_${row.reference || row.id}.json`)
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Fichier indisponible.')
    } finally { setBusy('') }
  }

  const columns = [
    { id: 'ref', header: 'Référence', accessor: (r) => r.reference || `#${r.id}` },
    { id: 'periode', header: 'Période', accessor: (r) => r.periode,
      cell: (_v, r) => `Période ${r.periode}` },
    { id: 'total', header: 'Total', align: 'right',
      accessor: (r) => Number(r.total) || 0, cell: (_v, r) => formatMAD(r.total) },
    { id: 'lignes', header: 'Lignes', align: 'right',
      accessor: (r) => r.nombre_lignes },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut,
      cell: (_v, r) => <StatutOrdre status={r.statut} /> },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-2">
        <Select value={periodeId} onValueChange={setPeriodeId}>
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Période…" />
          </SelectTrigger>
          <SelectContent>
            {periodes.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.libelle || `${p.mois}/${p.annee}`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button onClick={generer} loading={busy === 'generer'}>
          <RefreshCw size={16} aria-hidden="true" /> Générer l’ordre
        </Button>
      </div>
      <Card className="p-4 sm:p-5">
        {loading ? <Loading /> : rows.length === 0 ? (
          <EmptyState icon={Banknote} title="Aucun ordre de virement"
            description="Générez un ordre depuis les bulletins validés d’une période." />
        ) : (
          <DataTable data={rows} columns={columns} exportName="ordres-virement"
            rowActions={(r) => [
              ...(r.statut !== ORDRE_STATUTS.EMIS ? [{
                id: 'emettre', label: 'Émettre', icon: Send,
                onClick: () => emettre(r),
              }] : []),
              { id: 'fichier', label: 'Fichier banque', icon: FileDown,
                onClick: () => fichier(r) },
            ]} />
        )}
      </Card>
    </div>
  )
}

/* ── Déclarations (CNSS/DAMANCOM/IR/livre) par période ── */
function DeclarationsTab() {
  const [periodes, setPeriodes] = useState([])
  const [periodeId, setPeriodeId] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [annee, setAnnee] = useState(String(new Date().getFullYear()))

  useEffect(() => {
    paieApi.getPeriodes()
      .then((r) => setPeriodes(listOf(r.data)))
      .catch(() => toast.error('Chargement impossible.'))
      .finally(() => setLoading(false))
  }, [])

  const gen = async (kind, fn, name) => {
    if (!periodeId) { toast.error('Choisissez une période.'); return }
    setBusy(kind)
    try {
      const { data } = await fn(Number(periodeId))
      downloadJson(data, `${name}_periode_${periodeId}.json`)
      toast.success('État généré.')
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Génération impossible.')
    } finally { setBusy('') }
  }

  const irAnnuel = async () => {
    setBusy('ir-annuel')
    try {
      const { data } = await paieApi.etatIrAnnuel(Number(annee))
      downloadJson(data, `etat_ir_annuel_${annee}.json`)
      toast.success('État IR annuel généré.')
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Génération impossible.')
    } finally { setBusy('') }
  }

  if (loading) return <Card className="p-4"><Loading /></Card>

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <p className="text-sm text-muted-foreground">
          Sélectionnez une période puis générez les fichiers déclaratifs.
        </p>
        <Select value={periodeId} onValueChange={setPeriodeId}>
          <SelectTrigger className="w-56">
            <SelectValue placeholder="Période…" />
          </SelectTrigger>
          <SelectContent>
            {periodes.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.libelle || `${p.mois}/${p.annee}`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" loading={busy === 'cnss'}
            onClick={() => gen('cnss', paieApi.declarationCnss, 'declaration_cnss')}>
            <FileDown size={16} aria-hidden="true" /> Déclaration CNSS
          </Button>
          <Button variant="outline" loading={busy === 'damancom'}
            onClick={() => gen('damancom', paieApi.fichierDamancom, 'damancom')}>
            <FileDown size={16} aria-hidden="true" /> Fichier DAMANCOM
          </Button>
          <Button variant="outline" loading={busy === 'ir'}
            onClick={() => gen('ir', paieApi.etatIr, 'etat_ir')}>
            <FileDown size={16} aria-hidden="true" /> État IR
          </Button>
          <Button variant="outline" loading={busy === 'livre'}
            onClick={() => gen('livre', paieApi.livreDePaie, 'livre_de_paie')}>
            <FileSpreadsheet size={16} aria-hidden="true" /> Livre de paie
          </Button>
        </div>
      </Card>

      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="font-display font-semibold">État IR annuel</h3>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Année</span>
            <input
              type="number" step="any" value={annee}
              onChange={(e) => setAnnee(e.target.value)}
              className="h-[var(--control-h)] w-28 rounded-md border border-input bg-card px-3 text-sm"
            />
          </label>
          <Button variant="outline" loading={busy === 'ir-annuel'}
            onClick={irAnnuel}>
            <FileDown size={16} aria-hidden="true" /> État IR annuel
          </Button>
        </div>
      </Card>
    </div>
  )
}

/* ── Avances & saisies ── */
function AvancesTab() {
  const [avances, setAvances] = useState([])
  const [saisies, setSaisies] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([paieApi.getAvances(), paieApi.getSaisies()])
      .then(([a, s]) => {
        setAvances(listOf(a.data))
        setSaisies(listOf(s.data))
      })
      .catch(() => toast.error('Chargement impossible.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Card className="p-4"><Loading /></Card>

  const avanceCols = [
    { id: 'profil', header: 'Profil', accessor: (r) => r.profil,
      cell: (_v, r) => `#${r.profil}` },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle || r.type },
    { id: 'total', header: 'Montant', align: 'right',
      accessor: (r) => Number(r.montant_total) || 0,
      cell: (_v, r) => formatMAD(r.montant_total) },
    { id: 'restant', header: 'Solde restant', align: 'right',
      accessor: (r) => Number(r.solde_restant) || 0,
      cell: (_v, r) => formatMAD(r.solde_restant) },
    { id: 'soldee', header: 'État', accessor: (r) => r.soldee,
      cell: (_v, r) => (r.soldee
        ? <Badge tone="success">Soldée</Badge>
        : <Badge tone="warning">En cours</Badge>) },
  ]
  const saisieCols = [
    { id: 'profil', header: 'Profil', accessor: (r) => r.profil,
      cell: (_v, r) => `#${r.profil}` },
    { id: 'creancier', header: 'Créancier', accessor: (r) => r.creancier },
    { id: 'total', header: 'Montant', align: 'right',
      accessor: (r) => Number(r.montant_total) || 0,
      cell: (_v, r) => formatMAD(r.montant_total) },
    { id: 'restant', header: 'Solde restant', align: 'right',
      accessor: (r) => Number(r.solde_restant) || 0,
      cell: (_v, r) => formatMAD(r.solde_restant) },
    { id: 'prio', header: 'Prioritaire', accessor: (r) => r.prioritaire,
      cell: (_v, r) => (r.prioritaire ? 'Oui' : 'Non') },
  ]

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4 sm:p-5">
        <h3 className="mb-3 font-display font-semibold">Avances / prêts</h3>
        {avances.length === 0 ? (
          <EmptyState icon={ListChecks} title="Aucune avance" />
        ) : (
          <DataTable data={avances} columns={avanceCols} exportName="avances" />
        )}
      </Card>
      <Card className="p-4 sm:p-5">
        <h3 className="mb-3 font-display font-semibold">Saisies-arrêts</h3>
        {saisies.length === 0 ? (
          <EmptyState icon={ListChecks} title="Aucune saisie" />
        ) : (
          <DataTable data={saisies} columns={saisieCols} exportName="saisies" />
        )}
      </Card>
    </div>
  )
}

/* ── Cumuls annuels ── */
function CumulsTab() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    paieApi.getCumulsAnnuels({ ordering: '-annee' })
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement des cumuls impossible.'))
      .finally(() => setLoading(false))
  }, [])

  const columns = [
    { id: 'profil', header: 'Profil', accessor: (r) => r.profil,
      cell: (_v, r) => `#${r.profil}` },
    { id: 'annee', header: 'Année', accessor: (r) => r.annee },
    { id: 'brut', header: 'Brut', align: 'right',
      accessor: (r) => Number(r.brut) || 0, cell: (_v, r) => formatMAD(r.brut) },
    { id: 'ir', header: 'IR', align: 'right',
      accessor: (r) => Number(r.ir) || 0, cell: (_v, r) => formatMAD(r.ir) },
    { id: 'net', header: 'Net à payer', align: 'right',
      accessor: (r) => Number(r.net_a_payer) || 0,
      cell: (_v, r) => formatMAD(r.net_a_payer) },
    { id: 'nb', header: 'Bulletins', align: 'right',
      accessor: (r) => r.nombre_bulletins },
  ]

  return (
    <Card className="p-4 sm:p-5">
      {loading ? <Loading /> : rows.length === 0 ? (
        <EmptyState icon={ListChecks} title="Aucun cumul"
          description="Les cumuls se recalculent depuis les bulletins validés." />
      ) : (
        <DataTable data={rows} columns={columns} searchable
          exportName="cumuls-annuels" />
      )}
    </Card>
  )
}

function Loading() {
  return (
    <div className="flex items-center gap-2 py-6 text-muted-foreground">
      <Spinner className="size-4" /> Chargement…
    </div>
  )
}
function listOf(data) {
  return Array.isArray(data) ? data : (data?.results ?? [])
}

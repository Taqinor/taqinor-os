import { useEffect, useState } from 'react'
import {
  Banknote, FileDown, Send, RefreshCw, FileSpreadsheet, ListChecks,
  XCircle, RotateCcw, UploadCloud, Calculator, History,
} from 'lucide-react'
import {
  Button, Card, Input, Spinner, EmptyState, Badge, toast,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../ui'
import { DataTable } from '../../ui'
import { formatMAD } from '../../lib/format'
import paieApi from '../../api/paieApi'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
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
          <TabsTrigger value="charges">Charges & GL</TabsTrigger>
          <TabsTrigger value="rh">RH & registres</TabsTrigger>
          <TabsTrigger value="avances">Avances & saisies</TabsTrigger>
          <TabsTrigger value="cumuls">Cumuls annuels</TabsTrigger>
          <TabsTrigger value="analyse">Analyse</TabsTrigger>
        </TabsList>
        <TabsContent value="virements"><VirementsTab /></TabsContent>
        <TabsContent value="declarations"><DeclarationsTab /></TabsContent>
        <TabsContent value="charges"><ChargesGlTab /></TabsContent>
        <TabsContent value="rh"><RhRegistresTab /></TabsContent>
        <TabsContent value="avances"><AvancesTab /></TabsContent>
        <TabsContent value="cumuls"><CumulsTab /></TabsContent>
        <TabsContent value="analyse"><AnalyseTab /></TabsContent>
      </Tabs>
    </div>
  )
}

/* Télécharge un objet JSON (état/fichier généré) en pièce jointe.
   VX172 — appelé avec la donnée déjà résolue (post-`await` de l'appelant) :
   pas de fenêtre pré-ouverte possible ici, mais `downloadBlobInGesture()`
   tente quand même l'onglet visible en iOS/standalone (repli `a.download`
   automatique si bloqué) plutôt que le téléchargement invisible d'avant. */
function downloadJson(obj, filename) {
  const blob = new Blob([JSON.stringify(obj, null, 2)],
    { type: 'application/json' })
  downloadBlobInGesture().deliver(blob, filename)
}

/* ── Ordres de virement ── */
function VirementsTab() {
  const [rows, setRows] = useState([])
  const [periodes, setPeriodes] = useState([])
  const [loading, setLoading] = useState(true)
  const [periodeId, setPeriodeId] = useState('')
  const [busy, setBusy] = useState('')
  const [formatBanque, setFormatBanque] = useState('csv')
  const [lignesOrdre, setLignesOrdre] = useState(null)

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

  // XPAI8 — sélecteur de format banque : CSV/JSON générique ou SIMT
  // (format bancaire marocain, longueurs fixes).
  const fichier = async (row) => {
    setBusy(`fichier-${row.id}`)
    try {
      const { data } = await paieApi.fichierVirement(
        row.id, formatBanque === 'simt' ? 'simt' : undefined)
      downloadJson(
        data, `virement_${row.reference || row.id}_${formatBanque}.json`)
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
        <Select value={formatBanque} onValueChange={setFormatBanque}>
          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="csv">Format CSV</SelectItem>
            <SelectItem value="simt">Format SIMT</SelectItem>
          </SelectContent>
        </Select>
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
              { id: 'fichier', label: `Fichier (${formatBanque.toUpperCase()})`,
                icon: FileDown, onClick: () => fichier(r) },
              { id: 'lignes', label: 'Lignes / rejets', icon: XCircle,
                onClick: () => setLignesOrdre(r) },
            ]} />
        )}
      </Card>
      {lignesOrdre && (
        <LignesOrdreDialog ordre={lignesOrdre}
          onClose={() => setLignesOrdre(null)} />
      )}
    </div>
  )
}

/* ── XPAI9 — Lignes de virement d'un ordre : rejet RIB invalide + réémission ── */
function LignesOrdreDialog({ ordre, onClose }) {
  const [lignes, setLignes] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [ribParLigne, setRibParLigne] = useState({})

  const load = () =>
    paieApi.getLignesVirement({ ordre: ordre.id })
      .then((r) => setLignes(listOf(r.data)))
      .catch(() => toast.error('Chargement des lignes impossible.'))
      .finally(() => setLoading(false))
  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const rejeter = async (ligne) => {
    setBusy(`rejeter-${ligne.id}`)
    try {
      await paieApi.rejeterLigneVirement(ligne.id, 'RIB invalide')
      toast.success('Ligne rejetée.')
      await load()
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Rejet impossible.')
    } finally { setBusy('') }
  }

  const reemettre = async (ligne) => {
    const rib = ribParLigne[ligne.id]
    if (!rib) { toast.error('Saisissez le RIB corrigé.'); return }
    setBusy(`reemettre-${ligne.id}`)
    try {
      await paieApi.reemettreLigneVirement(ligne.id, rib)
      toast.success('Ligne réémise avec le RIB corrigé.')
      await load()
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Réémission impossible.')
    } finally { setBusy('') }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            Lignes de l’ordre {ordre.reference || `#${ordre.id}`}
          </DialogTitle>
        </DialogHeader>
        {loading ? <Loading /> : lignes.length === 0 ? (
          <EmptyState icon={Banknote} title="Aucune ligne" />
        ) : (
          <ul className="flex flex-col gap-2">
            {lignes.map((l) => (
              <li key={l.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border p-2 text-sm">
                <div>
                  <p className="font-medium">Bulletin #{l.bulletin}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatMAD(l.montant)} · RIB {l.rib || '—'}
                    {l.statut ? ` · ${l.statut}` : ''}
                  </p>
                </div>
                {l.statut === 'rejetee' ? (
                  <div className="flex items-center gap-1.5">
                    <Input value={ribParLigne[l.id] || ''}
                      onChange={(e) => setRibParLigne(
                        (m) => ({ ...m, [l.id]: e.target.value }))}
                      placeholder="RIB corrigé" className="h-8 w-48 text-xs" />
                    <Button size="sm" variant="outline"
                      onClick={() => reemettre(l)}
                      loading={busy === `reemettre-${l.id}`}>
                      <RotateCcw size={14} aria-hidden="true" /> Réémettre
                    </Button>
                  </div>
                ) : (
                  <Button size="sm" variant="destructive"
                    onClick={() => rejeter(l)}
                    loading={busy === `rejeter-${l.id}`}>
                    <XCircle size={14} aria-hidden="true" /> Rejeter
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  )
}

/* ── Déclarations (CNSS/DAMANCOM/IR/livre) par période ── */
function DeclarationsTab() {
  const [periodes, setPeriodes] = useState([])
  const [periodeId, setPeriodeId] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [annee, setAnnee] = useState(String(new Date().getFullYear()))
  const [profilsDelta, setProfilsDelta] = useState('')

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

  // XPAI13 — XML EDI SIMPL-IR de l'état IR 9421 annuel.
  const irAnnuelXml = async () => {
    setBusy('ir-annuel-xml')
    try {
      const { data } = await paieApi.etatIrAnnuelXml(Number(annee))
      downloadJson(data, `etat_ir_annuel_${annee}_simpl-ir.xml.json`)
      toast.success('XML SIMPL-IR généré.')
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Génération impossible.')
    } finally { setBusy('') }
  }

  // XPAI12 — dépôt PRINCIPAL puis dépôt(s) COMPLÉMENTAIRE(s) de la BDS
  // (delta uniquement : numéros CNSS/ids omis ou corrigés).
  const deposerBds = async (complementaire) => {
    if (!periodeId) { toast.error('Choisissez une période.'); return }
    if (complementaire && !profilsDelta.trim()) {
      toast.error('Indiquez le delta (profils omis/corrigés).')
      return
    }
    const kind = complementaire ? 'bds-comp' : 'bds-principal'
    setBusy(kind)
    try {
      const fn = complementaire
        ? paieApi.deposerBdsComplementaire : paieApi.deposerBds
      const body = complementaire
        ? { profils_delta: profilsDelta.split(',').map((s) => s.trim()).filter(Boolean) }
        : {}
      const { data } = await fn(Number(periodeId), body)
      downloadJson(data, `${kind}_periode_${periodeId}.json`)
      toast.success(complementaire
        ? 'Dépôt BDS complémentaire enregistré.'
        : 'Dépôt BDS principal enregistré.')
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Dépôt impossible.')
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
        <div className="flex flex-wrap items-end gap-2 border-t border-border pt-3">
          <Button variant="outline" loading={busy === 'bds-principal'}
            onClick={() => deposerBds(false)}>
            <UploadCloud size={16} aria-hidden="true" /> Déposer BDS (principal)
          </Button>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Delta (n° CNSS, séparés par virgule)</span>
            <Input value={profilsDelta} onChange={(e) => setProfilsDelta(e.target.value)}
              placeholder="123456, 789012" className="w-56" />
          </label>
          <Button variant="outline" loading={busy === 'bds-comp'}
            onClick={() => deposerBds(true)}>
            <UploadCloud size={16} aria-hidden="true" /> BDS complémentaire
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
          <Button variant="outline" loading={busy === 'ir-annuel-xml'}
            onClick={irAnnuelXml}>
            <FileDown size={16} aria-hidden="true" /> XML SIMPL-IR
          </Button>
        </div>
      </Card>
    </div>
  )
}

/* ── XPAI5 — État des charges + rapprochement GL/AFFEBDS ── */
function ChargesGlTab() {
  const [periodes, setPeriodes] = useState([])
  const [periodeId, setPeriodeId] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [file, setFile] = useState(null)
  // WIR37 — journal de paie → comptabilité (PAIE33/XPAI17).
  const [ecritureResult, setEcritureResult] = useState(null)

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

  const rapprocherAffebds = async () => {
    if (!file) { toast.error('Choisissez un fichier AFFEBDS.'); return }
    setBusy('affebds')
    try {
      const form = new FormData()
      form.append('file', file)
      const { data } = await paieApi.affebdsRapprochement(form)
      downloadJson(data, 'rapprochement_affebds.json')
      toast.success('Rapprochement AFFEBDS effectué.')
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Rapprochement impossible.')
    } finally { setBusy('') }
  }

  // WIR37 — passe l'écriture OD équilibrée du journal de paie (bulletins
  // validés de la période) vers compta, via `compta.services` côté serveur.
  // `ventile` = variante avec ventilation analytique (XPAI17).
  const passerEcriture = async (ventile) => {
    if (!periodeId) { toast.error('Choisissez une période.'); return }
    const kind = ventile ? 'ecriture-ventilee' : 'ecriture'
    setBusy(kind)
    try {
      const { data } = ventile
        ? await paieApi.journalVentile(Number(periodeId))
        : await paieApi.journalDePaie(Number(periodeId))
      setEcritureResult(data)
      toast.success('Écriture comptable passée.')
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Passage en comptabilité impossible.')
    } finally { setBusy('') }
  }

  if (loading) return <Card className="p-4"><Loading /></Card>

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <p className="text-sm text-muted-foreground">
          État consolidé des charges sociales par organisme et rapprochement
          du livre de paie au grand livre.
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
          <Button variant="outline" loading={busy === 'charges'}
            onClick={() => gen('charges', paieApi.etatCharges, 'etat_charges')}>
            <FileDown size={16} aria-hidden="true" /> État des charges
          </Button>
          <Button variant="outline" loading={busy === 'gl'}
            onClick={() => gen('gl', paieApi.rapprochementGl, 'rapprochement_gl')}>
            <Calculator size={16} aria-hidden="true" /> Rapprochement GL
          </Button>
          <Button variant="outline" loading={busy === 'cout-global'}
            onClick={() => gen('cout-global', paieApi.coutGlobal, 'cout_global')}>
            <Calculator size={16} aria-hidden="true" /> Coût global (par employé)
          </Button>
          <Button variant="outline" loading={busy === 'cout-employeur'}
            onClick={() => gen('cout-employeur', paieApi.coutEmployeur, 'cout_employeur')}>
            <Calculator size={16} aria-hidden="true" /> Coût employeur (consolidé)
          </Button>
        </div>
      </Card>

      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="font-display font-semibold">Rapprochement AFFEBDS</h3>
        <p className="text-sm text-muted-foreground">
          Importez le fichier AFFEBDS reçu de la CNSS pour le rapprocher
          contre les profils de paie.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input type="file" accept=".csv,.txt"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="text-sm" />
          <Button variant="outline" loading={busy === 'affebds'}
            onClick={rapprocherAffebds}>
            <UploadCloud size={16} aria-hidden="true" /> Rapprocher
          </Button>
        </div>
      </Card>

      {/* WIR37 — journal de paie → comptabilité (PAIE33). Aucun déclencheur
          UI n'existait jusqu'ici pour `paieApi.journalDePaie`/`journalVentile`
          (backend + service compta déjà construits et testés). */}
      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="font-display font-semibold">
          Journal de paie → comptabilité
        </h3>
        <p className="text-sm text-muted-foreground">
          Passe l’écriture OD équilibrée des bulletins validés de la période
          sélectionnée (débit rémunérations/charges patronales, crédit
          CNSS/AMO, IR, CIMR, net à payer).
        </p>
        <div className="flex flex-wrap gap-2">
          <Button loading={busy === 'ecriture'}
            onClick={() => passerEcriture(false)}>
            <Banknote size={16} aria-hidden="true" /> Passer l’écriture comptable
          </Button>
          <Button variant="outline" loading={busy === 'ecriture-ventilee'}
            onClick={() => passerEcriture(true)}>
            <Banknote size={16} aria-hidden="true" /> Écriture ventilée (analytique)
          </Button>
        </div>
        {ecritureResult && (
          <p className="text-sm text-success">
            Écriture {ecritureResult.reference
              || `#${ecritureResult.ecriture_id || ecritureResult.id}`} passée en comptabilité.
          </p>
        )}
      </Card>
    </div>
  )
}

/* ── XPAI26/XPAI10/XPAI11 — registres RH & fichiers CIMR ── */
function RhRegistresTab() {
  const [annee, setAnnee] = useState(String(new Date().getFullYear()))
  const [registre, setRegistre] = useState(null)
  const [periodes, setPeriodes] = useState([])
  const [periodeId, setPeriodeId] = useState('')
  const [profilId, setProfilId] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')

  useEffect(() => {
    paieApi.getPeriodes()
      .then((r) => setPeriodes(listOf(r.data)))
      .catch(() => toast.error('Chargement impossible.'))
      .finally(() => setLoading(false))
  }, [])

  const chargerRegistre = async () => {
    setBusy('registre')
    try {
      const { data } = await paieApi.registreConges({ annee: Number(annee) })
      setRegistre(data)
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Registre indisponible.')
    } finally { setBusy('') }
  }

  const telechargerRegistre = async (format) => {
    const pending = downloadBlobInGesture()
    setBusy(`registre-${format}`)
    try {
      const { data } = await paieApi.registreCongesFichier(
        Number(annee), format)
      pending.deliver(new Blob([data]), `registre_conges_${annee}.${format}`)
    } catch {
      toast.error('Export indisponible.')
    } finally { setBusy('') }
  }

  const historique = async () => {
    if (!profilId) { toast.error('Indiquez un identifiant de profil.'); return }
    setBusy('historique')
    try {
      const { data } = await paieApi.historiqueCarriere(Number(profilId))
      downloadJson(data, `historique_carriere_${profilId}.json`)
      toast.success('Historique de carrière généré.')
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Historique indisponible.')
    } finally { setBusy('') }
  }

  const cimr = async (kind) => {
    if (!periodeId) { toast.error('Choisissez une période.'); return }
    setBusy(kind)
    try {
      const fn = kind === 'cimr-decl' ? paieApi.declarationCimr : paieApi.fichierCimr
      const { data } = await fn(Number(periodeId))
      downloadJson(data, `${kind}_periode_${periodeId}.json`)
      toast.success('Fichier CIMR généré.')
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Génération impossible.')
    } finally { setBusy('') }
  }

  if (loading) return <Card className="p-4"><Loading /></Card>

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="font-display font-semibold">Registre des congés (XPAI26)</h3>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Année</span>
            <Input type="number" step="any" value={annee}
              onChange={(e) => setAnnee(e.target.value)} className="w-28" />
          </label>
          <Button variant="outline" loading={busy === 'registre'}
            onClick={chargerRegistre}>
            <ListChecks size={16} aria-hidden="true" /> Charger
          </Button>
          <Button variant="outline" loading={busy === 'registre-pdf'}
            onClick={() => telechargerRegistre('pdf')}>
            <FileDown size={16} aria-hidden="true" /> PDF
          </Button>
          <Button variant="outline" loading={busy === 'registre-csv'}
            onClick={() => telechargerRegistre('csv')}>
            <FileDown size={16} aria-hidden="true" /> CSV
          </Button>
        </div>
        {registre && (
          <DataTable
            data={registre.lignes || []}
            columns={[
              { id: 'matricule', header: 'Matricule', accessor: (r) => r.matricule },
              { id: 'nom', header: 'Nom', accessor: (r) => r.nom },
              { id: 'droits', header: 'Droits (j)', align: 'right', accessor: (r) => r.droits },
              { id: 'pris', header: 'Pris (j)', align: 'right', accessor: (r) => r.pris },
              { id: 'solde', header: 'Solde (j)', align: 'right', accessor: (r) => r.solde },
            ]}
            searchable exportName="registre-conges" />
        )}
      </Card>

      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="font-display font-semibold">Historique de carrière (XPAI26)</h3>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">ID profil</span>
            <Input value={profilId} onChange={(e) => setProfilId(e.target.value)}
              className="w-28" />
          </label>
          <Button variant="outline" loading={busy === 'historique'}
            onClick={historique}>
            <History size={16} aria-hidden="true" /> Fiche historique
          </Button>
        </div>
      </Card>

      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="font-display font-semibold">Télédéclaration CIMR (XPAI10)</h3>
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
          <Button variant="outline" loading={busy === 'cimr-decl'}
            onClick={() => cimr('cimr-decl')}>
            <FileDown size={16} aria-hidden="true" /> Déclaration CIMR
          </Button>
          <Button variant="outline" loading={busy === 'cimr-fichier'}
            onClick={() => cimr('cimr-fichier')}>
            <FileDown size={16} aria-hidden="true" /> Fichier e-CIMR
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
  const [, setBusy] = useState('')
  const [lotOuvert, setLotOuvert] = useState(false)

  const load = () =>
    Promise.all([paieApi.getAvances(), paieApi.getSaisies()])
      .then(([a, s]) => {
        setAvances(listOf(a.data))
        setSaisies(listOf(s.data))
      })
      .catch(() => toast.error('Chargement impossible.'))
      .finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  // ZPAI6 — annule une saisie (stoppe les retenues futures, historique intact).
  const annuler = async (saisie) => {
    setBusy(`annuler-${saisie.id}`)
    try {
      await paieApi.annulerSaisie(saisie.id, '')
      toast.success('Saisie annulée.')
      await load()
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Annulation impossible.')
    } finally { setBusy('') }
  }

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
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display font-semibold">Saisies-arrêts</h3>
          <Button variant="outline" size="sm" onClick={() => setLotOuvert(true)}>
            <ListChecks size={15} aria-hidden="true" /> Créer un lot
          </Button>
        </div>
        {saisies.length === 0 ? (
          <EmptyState icon={ListChecks} title="Aucune saisie" />
        ) : (
          <DataTable data={saisies} columns={saisieCols} exportName="saisies"
            rowActions={(r) => [
              { id: 'annuler', label: 'Annuler', icon: XCircle,
                onClick: () => annuler(r) },
            ]} />
        )}
      </Card>
      {lotOuvert && (
        <LotSaisiesDialog onClose={() => setLotOuvert(false)}
          onCreated={load} />
      )}
    </div>
  )
}

/* ── ZPAI7 — Éclate une saisie en lot, une fiche par profil ── */
function LotSaisiesDialog({ onClose, onCreated }) {
  const [profils, setProfils] = useState('')
  const [montantTotal, setMontantTotal] = useState('')
  const [creancier, setCreancier] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [busy, setBusy] = useState(false)

  const creer = async () => {
    const ids = profils.split(',').map((s) => Number(s.trim())).filter(Boolean)
    if (!ids.length || !montantTotal || !dateDebut) {
      toast.error('Profils, montant total et date de début sont requis.')
      return
    }
    setBusy(true)
    try {
      const { data } = await paieApi.creerLotSaisies({
        profils: ids,
        montant_total: Number(montantTotal),
        creancier,
        date_debut: dateDebut,
      })
      const n = Array.isArray(data) ? data.length : data?.crees ?? ids.length
      toast.success(`${n} saisie(s) créée(s).`)
      onCreated()
      onClose()
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Création du lot impossible.')
    } finally { setBusy(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Créer un lot de saisies-arrêts</DialogTitle></DialogHeader>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">IDs de profils (séparés par virgule)</span>
            <Input value={profils} onChange={(e) => setProfils(e.target.value)}
              placeholder="12, 15, 21" />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Montant total par profil</span>
            <Input type="number" step="any" value={montantTotal}
              onChange={(e) => setMontantTotal(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Créancier</span>
            <Input value={creancier} onChange={(e) => setCreancier(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Date de début</span>
            <Input type="date" value={dateDebut}
              onChange={(e) => setDateDebut(e.target.value)} />
          </label>
        </div>
        <DialogFooter>
          <Button onClick={creer} loading={busy}>Créer le lot</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/* ── ZPAI1 — Analyse de paie pivot rubrique/département × mois ── */
function AnalyseTab() {
  const [debut, setDebut] = useState('')
  const [fin, setFin] = useState('')
  const [groupBy, setGroupBy] = useState('rubrique')
  const [data, setData] = useState(null)
  const [busy, setBusy] = useState(false)

  const charger = async () => {
    if (!debut || !fin) { toast.error('Choisissez la fenêtre debut/fin.'); return }
    setBusy(true)
    try {
      const { data: res } = await paieApi.analysePaie({
        debut, fin, group_by: groupBy,
      })
      setData(res)
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Analyse impossible.')
    } finally { setBusy(false) }
  }

  const exporter = async () => {
    const pending = downloadBlobInGesture()
    setBusy(true)
    try {
      const { data: blob } = await paieApi.analysePaieCsv({
        debut, fin, group_by: groupBy,
      })
      pending.deliver(new Blob([blob]), 'analyse_paie.csv')
    } catch {
      toast.error('Export CSV impossible.')
    } finally { setBusy(false) }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <p className="text-sm text-muted-foreground">
          Rapport pivot rubrique/département × mois — fenêtre inclusive
          (format AAAA-MM).
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Début</span>
            <Input placeholder="2026-01" value={debut}
              onChange={(e) => setDebut(e.target.value)} className="w-32" />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Fin</span>
            <Input placeholder="2026-06" value={fin}
              onChange={(e) => setFin(e.target.value)} className="w-32" />
          </label>
          <Select value={groupBy} onValueChange={setGroupBy}>
            <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="rubrique">Par rubrique</SelectItem>
              <SelectItem value="departement">Par département</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={charger} loading={busy}>
            <Calculator size={16} aria-hidden="true" /> Analyser
          </Button>
          {data && (
            <Button variant="outline" onClick={exporter} loading={busy}>
              <FileDown size={16} aria-hidden="true" /> Export CSV
            </Button>
          )}
        </div>
      </Card>
      {data && (
        <Card className="p-4 sm:p-5">
          <DataTable
            data={data.lignes || []}
            columns={[
              { id: 'libelle', header: data.group_by === 'departement' ? 'Département' : 'Rubrique',
                accessor: (r) => r.libelle },
              ...(data.mois || []).map((m) => ({
                id: m, header: m, align: 'right',
                accessor: (r) => Number(r.totaux_par_mois?.[m]) || 0,
                cell: (_v, r) => formatMAD(r.totaux_par_mois?.[m] || 0),
              })),
              { id: 'total', header: 'Total', align: 'right',
                accessor: (r) => Number(r.total) || 0,
                cell: (_v, r) => formatMAD(r.total) },
            ]}
            searchable exportName="analyse-paie" />
          <p className="mt-3 text-sm font-medium">
            Total général : {formatMAD(data.total_general)}
          </p>
        </Card>
      )}
    </div>
  )
}

/* ── Cumuls annuels ── */
function CumulsTab() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState('')
  const [apercu, setApercu] = useState(null)

  const load = () =>
    paieApi.getCumulsAnnuels({ ordering: '-annee' })
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement des cumuls impossible.'))
      .finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  // XPAI22 — import de reprise des cumuls (go-live) : aperçu SANS écriture,
  // puis commit qui ne recouvre jamais un cumul déjà calculé.
  const dryRun = async () => {
    if (!file) { toast.error('Choisissez un fichier CSV/XLSX.'); return }
    setBusy('dry-run')
    try {
      const { data } = await paieApi.repriseDryRun(file)
      setApercu(data)
      toast.success('Aperçu généré — vérifiez avant de valider.')
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Aperçu impossible.')
    } finally { setBusy('') }
  }

  const commit = async () => {
    if (!file) return
    setBusy('commit')
    try {
      const { data } = await paieApi.repriseCommit(file)
      toast.success(
        `Reprise validée : ${data?.crees ?? 0} cumul(s) créé(s)/complété(s).`)
      setApercu(null)
      setFile(null)
      await load()
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Commit impossible.')
    } finally { setBusy('') }
  }

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
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4 sm:p-5">
        <h3 className="font-display font-semibold">
          Import de reprise des cumuls (go-live)
        </h3>
        <p className="text-sm text-muted-foreground">
          Importez les cumuls annuels d’un système précédent. L’aperçu signale
          les matricules inconnus AVANT tout commit ; le commit ne recouvre
          jamais un cumul déjà calculé depuis de vrais bulletins validés.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <input type="file" accept=".csv,.xlsx"
            onChange={(e) => { setFile(e.target.files?.[0] || null); setApercu(null) }}
            className="text-sm" />
          <Button variant="outline" loading={busy === 'dry-run'} onClick={dryRun}>
            <UploadCloud size={16} aria-hidden="true" /> Aperçu (dry-run)
          </Button>
          {apercu && (
            <Button onClick={commit} loading={busy === 'commit'}>
              Valider l’import
            </Button>
          )}
        </div>
        {apercu && (
          <div className="rounded-lg bg-muted/50 p-3 text-xs">
            {apercu.matricules_inconnus?.length > 0 ? (
              <p className="text-destructive">
                Matricules inconnus : {apercu.matricules_inconnus.join(', ')}
              </p>
            ) : (
              <p className="text-success">Aucun matricule inconnu.</p>
            )}
            <p className="mt-1 text-muted-foreground">
              {apercu.lignes?.length ?? 0} ligne(s) à importer.
            </p>
          </div>
        )}
      </Card>
      <Card className="p-4 sm:p-5">
        {loading ? <Loading /> : rows.length === 0 ? (
          <EmptyState icon={ListChecks} title="Aucun cumul"
            description="Les cumuls se recalculent depuis les bulletins validés." />
        ) : (
          <DataTable data={rows} columns={columns} searchable
            exportName="cumuls-annuels" />
        )}
      </Card>
    </div>
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

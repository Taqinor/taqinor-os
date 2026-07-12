import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Pencil, Download, FileText, Send, Bell, GitCompare } from 'lucide-react'
import { ListShell, statusPill } from '../../../ui/module'
import { Button, Segmented, Card, Label, EmptyState, toast } from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import { stampedFilename } from '../../../utils/downloadBlob'
import { store } from '../../../store'
import comptaApi from '../../../api/comptaApi'
import useComptaList, { unwrap } from '../components/useComptaList.js'
import useTabParam from '../components/useTabParam'
import CrudDialog from '../components/CrudDialog.jsx'

/* ============================================================================
   UX7 — Fiscalité & déclarations.
   ----------------------------------------------------------------------------
   CRUD des déclarations TVA / retenues à la source / timbres fiscaux, l'onglet
   XACC9 « Échéances fiscales » (lecture seule + génération/rappels J-7), plus
   un bloc d'exports fichiers (téléchargement de blob) : FEC, liasse fiscale,
   export fiduciaire, relevé des déductions TVA, déclaration des honoraires et
   aide au calcul de l'IS. Ces exports exigent « ?export=... » côté backend
   (jamais « ?format= ») — géré dans comptaApi. ZACC10 : bordereau PDF +
   comparatif M-1 en actions de ligne sur les déclarations TVA.
   ========================================================================== */

const TABS = [
  { value: 'declarationsTva', label: 'Déclarations TVA' },
  { value: 'retenuesSource', label: 'Retenues à la source' },
  { value: 'timbresFiscaux', label: 'Timbres fiscaux' },
  { value: 'echeances', label: 'Échéances fiscales' },
]

const RESOURCE = {
  declarationsTva: comptaApi.declarationsTva,
  retenuesSource: comptaApi.retenuesSource,
  timbresFiscaux: comptaApi.timbresFiscaux,
}

const StatutFiscal = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  prepare: { label: 'Préparée', tone: 'info' },
  preparee: { label: 'Préparée', tone: 'info' },
  declaree: { label: 'Déclarée', tone: 'success' },
  deposee: { label: 'Déposée', tone: 'success' },
  verse: { label: 'Versé', tone: 'success' },
  versee: { label: 'Versée', tone: 'success' },
  du: { label: 'Dû', tone: 'warning' },
  a_preparer: { label: 'À préparer', tone: 'warning' },
  a_declarer: { label: 'À déclarer', tone: 'warning' },
  a_verser: { label: 'À verser', tone: 'warning' },
})

const money = (v) => formatMAD(v)

const COLUMNS = {
  declarationsTva: [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'regime', header: 'Régime', accessor: (r) => r.regime_display || r.regime || '—' },
    { id: 'periode', header: 'Période', accessor: (r) => `${r.date_debut || ''} → ${r.date_fin || ''}`,
      searchable: false },
    { id: 'a_declarer', header: 'TVA à déclarer', accessor: (r) => Number(r.tva_a_declarer) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutFiscal status={v} /> },
  ],
  retenuesSource: [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'tiers', header: 'Tiers', accessor: (r) => r.tiers_nom || '—' },
    { id: 'type', header: 'Prestation', accessor: (r) => r.type_prestation_display || r.type_prestation || '—' },
    { id: 'base', header: 'Base', accessor: (r) => Number(r.base) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'montant', header: 'Retenue', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutFiscal status={v} /> },
  ],
  timbresFiscaux: [
    { id: 'reference', header: 'Référence', accessor: (r) => r.reference,
      cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'facture', header: 'Facture', accessor: (r) => r.facture_ref || '—' },
    { id: 'tiers', header: 'Tiers', accessor: (r) => r.tiers_nom || '—' },
    { id: 'montant', header: 'Montant', accessor: (r) => Number(r.montant) || 0,
      align: 'right', numeric: true, searchable: false, cell: money },
    { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
      cell: (v) => <StatutFiscal status={v} /> },
  ],
}

const FIELDS = {
  declarationsTva: [
    { name: 'libelle', label: 'Libellé', required: true },
    { name: 'date_debut', label: 'Début', type: 'date', required: true },
    { name: 'date_fin', label: 'Fin', type: 'date', required: true },
    { name: 'regime', label: 'Régime', options: [
      { value: 'encaissement', label: 'Encaissement' },
      { value: 'debit', label: 'Débit' },
    ] },
    { name: 'tva_collectee', label: 'TVA collectée', type: 'number' },
    { name: 'tva_deductible', label: 'TVA déductible', type: 'number' },
  ],
  retenuesSource: [
    { name: 'piece', label: 'Pièce', required: true },
    { name: 'date_piece', label: 'Date pièce', type: 'date', required: true },
    { name: 'tiers_nom', label: 'Tiers', required: true },
    { name: 'identifiant_fiscal', label: 'Identifiant fiscal' },
    { name: 'base', label: 'Base', type: 'number', required: true },
    { name: 'taux', label: 'Taux (%)', type: 'number' },
  ],
  timbresFiscaux: [
    { name: 'facture_ref', label: 'Réf. facture', required: true },
    { name: 'tiers_nom', label: 'Tiers' },
    { name: 'base', label: 'Base', type: 'number', required: true },
    { name: 'taux', label: 'Taux (%)', type: 'number' },
  ],
}

// Exports fichiers (blob). Ceux exigeant un exercice sont marqués `needsExercice`.
// VX81 — `base`/`ext` (plutôt qu'un `file` figé) : le nom réel est horodaté au
// moment du téléchargement par `runExport` (stampedFilename), jamais un nom nu
// — ces CSV partent chez le comptable, deux exports le même jour ne doivent
// plus être indistinguables derrière un (1)/(2) de navigateur.
// VX232 — un mot d'aide (`hint`) par export : « FEC »/« liasse »/« IS » ne
// disaient rien à qui ne les connaît pas déjà.
const EXPORTS = [
  { key: 'exportFec', label: 'FEC (DGI)', fn: comptaApi.etats.exportFec, base: 'FEC', ext: 'txt', needsExercice: true,
    hint: 'Format DGI officiel du Fichier des Écritures Comptables, à fournir en cas de contrôle fiscal.' },
  { key: 'liasseFiscale', label: 'Liasse fiscale', fn: comptaApi.etats.liasseFiscale, base: 'liasse-fiscale', ext: 'csv', needsExercice: true,
    hint: 'Bilan, CPC, ESG et ETIC de l’exercice, prêts à transmettre au comptable ou à la DGI.' },
  { key: 'exportFiduciaire', label: 'Export fiduciaire', fn: comptaApi.etats.exportFiduciaire, base: 'export-fiduciaire', ext: 'csv', needsExercice: true,
    hint: 'Export consolidé de l’exercice, au format attendu par le cabinet fiduciaire externe.' },
  { key: 'releveDeductionsTva', label: 'Relevé déductions TVA', fn: comptaApi.etats.releveDeductionsTva, base: 'releve-deductions-tva', ext: 'csv',
    hint: 'Détail des lignes de TVA déductible de la période, à joindre à la déclaration TVA.' },
  { key: 'declarationHonoraires', label: 'Déclaration honoraires', fn: comptaApi.etats.declarationHonoraires, base: 'declaration-honoraires', ext: 'csv',
    hint: 'Récapitulatif des honoraires versés à des tiers non-salariés sur la période.' },
  { key: 'aideIs', label: 'Aide au calcul IS', fn: comptaApi.etats.aideIs, base: 'aide-is', ext: 'csv', needsExercice: true,
    hint: 'Base de calcul de l’Impôt sur les Sociétés (IS) à partir du résultat fiscal de l’exercice.' },
]

// XACC9 — Calendrier des échéances fiscales : lecture seule + génération/rappels.
function EcheancesPanel() {
  const [exercice, setExercice] = useState('')
  const [exercices, setExercices] = useState([])
  const list = useComptaList(comptaApi.obligationsFiscales.list, undefined)

  useEffect(() => {
    comptaApi.exercices.list().then((res) => setExercices(unwrap(res))).catch(() => {})
  }, [])

  const generer = async () => {
    if (!exercice) {
      toast.error('Sélectionnez un exercice à générer.')
      return
    }
    try {
      await comptaApi.obligationsFiscales.generer({ exercice })
      toast.success('Calendrier fiscal généré.')
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Génération impossible.'))
    }
  }

  const envoyerRappels = async () => {
    try {
      const res = await comptaApi.obligationsFiscales.rappels()
      const n = unwrap(res).length
      toast.success(`${n} rappel(s) envoyé(s).`)
    } catch {
      toast.error('Envoi des rappels impossible.')
    }
  }

  const rows = list.rows || []

  return (
    <div className="flex flex-col gap-3">
      <Card className="p-4 sm:p-5">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1 sm:max-w-xs">
            <Label htmlFor="ech-ex">Exercice</Label>
            <select
              id="ech-ex"
              className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
              value={exercice} onChange={(e) => setExercice(e.target.value)}
            >
              <option value="">—</option>
              {exercices.map((ex) => (
                <option key={ex.id} value={ex.id}>{ex.libelle}</option>
              ))}
            </select>
          </div>
          <Button variant="outline" onClick={generer}>Générer le calendrier</Button>
          <Button variant="outline" onClick={envoyerRappels}>
            <Bell className="size-4" /> Envoyer les rappels (J-7)
          </Button>
        </div>
      </Card>
      {!rows.length ? (
        <EmptyState title="Aucune échéance" description="Générez le calendrier fiscal d’un exercice pour commencer." />
      ) : (
        <ListShell
          title="Échéances fiscales"
          columns={[
            { id: 'type', header: 'Obligation', accessor: (r) => r.type_display || r.type || '—' },
            { id: 'date_limite', header: 'Date limite', accessor: (r) => r.date_limite,
              searchable: false, cell: (v) => formatDate(v) },
            { id: 'statut', header: 'Statut', accessor: (r) => r.statut, searchable: false,
              cell: (v) => <StatutFiscal status={v} /> },
          ]}
          rows={rows}
          loading={list.loading}
          error={list.error}
          exportName="echeances-fiscales"
          emptyTitle="Aucune échéance"
          emptyDescription="Rien à afficher."
        />
      )}
    </div>
  )
}

export default function FiscalitePage() {
  const navigate = useNavigate()
  const [tab, setTab] = useTabParam('declarationsTva')  // VX231(c) — onglet persisté (?onglet=)
  const [dialog, setDialog] = useState(null)
  const [exercice, setExercice] = useState('')
  const [exercices, setExercices] = useState([])

  const isEcheances = tab === 'echeances'
  const list = useComptaList(
    isEcheances ? comptaApi.exercices.list : RESOURCE[tab].list, undefined)

  useEffect(() => {
    comptaApi.exercices.list().then((res) => setExercices(unwrap(res))).catch(() => {})
  }, [])

  const download = async (fn, filename, okMsg) => {
    try {
      const res = await fn()
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      comptaApi.downloadBlob(blob, filename)
      if (okMsg) toast.success(okMsg)
    } catch {
      toast.error('Téléchargement indisponible.')
    }
  }

  const act = async (fn, okMsg) => {
    try {
      await fn()
      toast.success(okMsg)
      list.reload()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Action impossible.'))
    }
  }

  const rowActions = (row) => {
    if (tab === 'declarationsTva') {
      return [
        { id: 'bordereau', label: 'Bordereau PDF', icon: FileText,
          onClick: () => download(
            () => comptaApi.declarationsTva.bordereauPdf(row.id),
            `bordereau_tva_${row.reference || row.id}.pdf`) },
        { id: 'comparatif', label: 'Comparatif N-1', icon: Download,
          onClick: () => download(
            () => comptaApi.declarationsTva.export(row.id),
            `declaration_tva_${row.reference || row.id}.csv`) },
        // VX231(d) — vérifier une déclaration TVA contre le Grand-livre sans
        // renoter deux chiffres à la main : ouvre le GL pré-filtré sur la MÊME
        // période (date_debut/date_fin de la déclaration).
        ...(row.date_debut && row.date_fin ? [{
          id: 'comparer-gl', label: 'Comparer au Grand-livre', icon: GitCompare,
          onClick: () => navigate(
            `/comptabilite/etats?etat=grand-livre`
            + `&date_debut=${row.date_debut}&date_fin=${row.date_fin}`),
        }] : []),
        ...(row.statut !== 'deposee' ? [{
          id: 'deposer', label: 'Déposer', icon: Send,
          onClick: () => act(() => comptaApi.declarationsTva.deposer(row.id), 'Déclaration déposée.'),
        }] : []),
        { id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) },
      ]
    }
    if (tab === 'retenuesSource' && row.statut !== 'versee') {
      return [
        { id: 'verser', label: 'Marquer versée', icon: Send,
          onClick: () => act(() => comptaApi.retenuesSource.verser(row.id), 'Retenue marquée versée.') },
        { id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) },
      ]
    }
    if (tab === 'timbresFiscaux' && row.statut !== 'verse') {
      return [
        { id: 'verser', label: 'Marquer versé', icon: Send,
          onClick: () => act(() => comptaApi.timbresFiscaux.verser(row.id), 'Timbre marqué versé.') },
        { id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }) },
      ]
    }
    return [{
      id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => setDialog({ row }),
    }]
  }

  const submit = (payload) => {
    const api = RESOURCE[tab]
    return dialog?.row ? api.update(dialog.row.id, payload) : api.create(payload)
  }

  const runExport = async (exp) => {
    if (exp.needsExercice && !exercice) {
      toast.error('Renseignez l’exercice avant cet export.')
      return
    }
    try {
      const params = exp.needsExercice ? { exercice } : {}
      const res = await exp.fn(params)
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      const societe = store.getState().parametres?.profile?.nom
      comptaApi.downloadBlob(blob, stampedFilename(exp.base, exp.ext, societe))
      toast.success('Export téléchargé.')
    } catch {
      toast.error('Export indisponible — vérifiez les paramètres.')
    }
  }

  const singular = useMemo(() => ({
    declarationsTva: 'déclaration TVA',
    retenuesSource: 'retenue',
    timbresFiscaux: 'timbre',
  }[tab]), [tab])

  return (
    <div className="page">
      <div className="page-header">
        <h2>Fiscalité & déclarations</h2>
        {!isEcheances && (
          <div className="page-header-actions">
            <Button onClick={() => setDialog({ row: null })}>
              <Plus /> Nouvelle {singular}
            </Button>
          </div>
        )}
      </div>

      <div className="mb-3">
        <Segmented options={TABS} value={tab} onChange={setTab} aria-label="Onglet fiscalité" />
      </div>

      {isEcheances ? (
        <EcheancesPanel />
      ) : (
        <ListShell
          title={TABS.find((t) => t.value === tab).label}
          columns={COLUMNS[tab]}
          rows={list.rows}
          loading={list.loading}
          error={list.error}
          rowActions={rowActions}
          exportName={tab}
          emptyTitle="Aucun élément"
          emptyDescription="Rien à afficher pour cet onglet."
        />
      )}

      {/* Bloc exports fichiers / télédéclarations (blob download). */}
      {!isEcheances && (
        <Card className="mt-4 p-4 sm:p-5">
          <h3 className="mb-3 font-display text-base font-semibold">Exports & télédéclarations</h3>
          <div className="mb-3 flex flex-col gap-1 sm:max-w-xs">
            <Label htmlFor="fx-exercice">Exercice — requis pour FEC / liasse / IS</Label>
            <select
              id="fx-exercice"
              className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
              value={exercice} onChange={(e) => setExercice(e.target.value)}
            >
              <option value="">—</option>
              {exercices.map((ex) => (
                <option key={ex.id} value={ex.id}>{ex.libelle}</option>
              ))}
            </select>
          </div>
          {/* VX232 — 2 rangées sous-titrées : la routine mensuelle ne se mélange
              plus avec l'annuel (exercice requis), chaque export porte sa phrase. */}
          <div className="flex flex-col gap-4">
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Mensuel</h4>
              <div className="grid gap-2 sm:grid-cols-2">
                {EXPORTS.filter((exp) => !exp.needsExercice).map((exp) => (
                  <div key={exp.key} className="flex flex-col gap-1 rounded-lg border border-border p-3">
                    <Button variant="outline" size="sm" className="w-fit" onClick={() => runExport(exp)}>
                      <Download className="size-4" /> {exp.label}
                    </Button>
                    <p className="text-xs text-muted-foreground">{exp.hint}</p>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Annuel — exercice requis
              </h4>
              <div className="grid gap-2 sm:grid-cols-2">
                {EXPORTS.filter((exp) => exp.needsExercice).map((exp) => (
                  <div key={exp.key} className="flex flex-col gap-1 rounded-lg border border-border p-3">
                    <Button variant="outline" size="sm" className="w-fit" onClick={() => runExport(exp)}>
                      <Download className="size-4" /> {exp.label}
                    </Button>
                    <p className="text-xs text-muted-foreground">{exp.hint}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}

      {dialog && !isEcheances && (
        <CrudDialog
          open
          onClose={() => setDialog(null)}
          title={dialog.row ? `Modifier la ${singular}` : `Nouvelle ${singular}`}
          fields={FIELDS[tab]}
          initial={dialog.row}
          onSubmit={submit}
          onSaved={list.reload}
        />
      )}
    </div>
  )
}

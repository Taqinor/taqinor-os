import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Download, RefreshCw, FileText, GitCompare } from 'lucide-react'
import { Button, Segmented, Input, Label, Card, EmptyState, toast } from '../../../ui'
import { formatMAD } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import { unwrap } from '../components/useComptaList.js'
import useTabParam from '../components/useTabParam'

/* ============================================================================
   UX5 — États comptables CGNC.
   ----------------------------------------------------------------------------
   Sélecteur d'exercice / période + rendu de chaque état (grand-livre, balance,
   CPC, bilan, ESG, ETIC, ZACC3 tableau des flux, ZACC12 tableau des
   immobilisations, ZACC4 journal items, ZACC16 dossier de clôture) et export
   CSV/PDF (« ?export=csv|pdf », jamais « ?format= ») quand disponible, plus le
   mode comparatif N-1 (ZACC2, « ?comparer=1 »). Le rendu est ADAPTATIF : une
   réponse { lignes:[…] } → tableau, un tableau de groupes (grand-livre) →
   sections, sinon liste clé/valeur des agrégats. Les états exigeant un
   exercice (tableau-flux/immobilisations/dossier-clôture) sont marqués
   `needsExercice` et se satisfont du sélecteur d'exercice déjà présent.
   ========================================================================== */

const ETATS = [
  { value: 'balance', label: 'Balance', fetch: comptaApi.etats.balance, supportsPdf: true, supportsComparer: true },
  { value: 'grand-livre', label: 'Grand-livre', fetch: comptaApi.etats.grandLivre, supportsPdf: true },
  { value: 'cpc', label: 'CPC', fetch: comptaApi.etats.cpc, supportsPdf: true, supportsComparer: true },
  { value: 'bilan', label: 'Bilan', fetch: comptaApi.etats.bilan, supportsPdf: true, supportsComparer: true },
  { value: 'esg', label: 'ESG', fetch: comptaApi.etats.esg, supportsComparer: true },
  { value: 'etic', label: 'ETIC', fetch: comptaApi.etats.etic, needsExercice: true },
  { value: 'tableau-flux', label: 'Tableau des flux', fetch: comptaApi.etats.tableauFlux,
    needsExercice: true, supportsPdf: true },
  { value: 'tableau-immobilisations', label: 'Immobilisations (tableau)',
    fetch: comptaApi.etats.tableauImmobilisations, needsExercice: true, supportsPdf: true },
  { value: 'journal-items', label: 'Journal items', fetch: comptaApi.etats.journalItems },
  { value: 'balance-agee-fournisseurs', label: 'Balance âgée fournisseurs',
    fetch: comptaApi.etats.balanceAgeeFournisseurs, supportsPdf: true },
  { value: 'continuite-sequences', label: 'Continuité séquences',
    fetch: comptaApi.etats.continuiteSequences },
  { value: 'controle-ice', label: 'Contrôle ICE/IF', fetch: comptaApi.etats.controleIce },
]

// Détecte les colonnes montant à formater en MAD.
const MONEY_KEYS = new Set([
  'debit', 'credit', 'solde', 'solde_debiteur', 'solde_crediteur',
  'total_debit', 'total_credit', 'montant', 'valeur', 'brut', 'net',
])

function cellValue(key, val) {
  if (val == null) return '—'
  if (typeof val === 'number' && MONEY_KEYS.has(key)) return formatMAD(val)
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

// Tableau générique à partir d'un tableau de lignes plates.
function GenericTable({ lignes }) {
  if (!lignes.length) {
    return <EmptyState title="Aucune donnée" description="Aucune ligne pour cette période." />
  }
  const cols = Object.keys(lignes[0]).filter((k) => typeof lignes[0][k] !== 'object')
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
            {cols.map((c) => (
              <th key={c} className="px-2 py-2 font-medium">{c.replace(/_/g, ' ')}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lignes.map((row, i) => (
            <tr key={i} className="border-b last:border-0">
              {cols.map((c) => (
                <td key={c} className="px-2 py-1.5 tabular-nums">{cellValue(c, row[c])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function KeyValue({ obj }) {
  const entries = Object.entries(obj).filter(([, v]) => typeof v !== 'object')
  return (
    <dl className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {entries.map(([k, v]) => (
        <div key={k} className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2">
          <dt className="text-sm text-muted-foreground">{k.replace(/_/g, ' ')}</dt>
          <dd className="tabular-nums font-medium">{cellValue(k, v)}</dd>
        </div>
      ))}
    </dl>
  )
}

function EtatRender({ data }) {
  if (data == null) return null
  // Grand-livre : tableau de groupes { numero, intitule, lignes[] }.
  if (Array.isArray(data)) {
    if (!data.length) return <EmptyState title="Aucune donnée" description="Aucun mouvement." />
    if (data[0]?.lignes) {
      return (
        <div className="flex flex-col gap-4">
          {data.map((grp) => (
            <div key={grp.numero}>
              <h4 className="mb-1 font-medium">
                {grp.numero} — {grp.intitule}
                <span className="ml-2 text-sm text-muted-foreground">
                  Solde : {formatMAD(grp.solde)}
                </span>
              </h4>
              <GenericTable lignes={grp.lignes} />
            </div>
          ))}
        </div>
      )
    }
    return <GenericTable lignes={data} />
  }
  // Objet avec { lignes:[…] } → tableau + éventuels totaux en clé/valeur.
  if (Array.isArray(data.lignes)) {
    const totaux = Object.fromEntries(
      Object.entries(data).filter(([k]) => k !== 'lignes'))
    return (
      <div className="flex flex-col gap-4">
        <GenericTable lignes={data.lignes} />
        {Object.keys(totaux).length > 0 && <KeyValue obj={totaux} />}
      </div>
    )
  }
  // Sinon : agrégats clé/valeur.
  return <KeyValue obj={data} />
}

export default function EtatsPage() {
  // VX231(c/d) — l'état actif est persisté dans l'URL (?etat=…) ET c'est la
  // cible du deep-link « Comparer au Grand-livre » (FiscalitePage) qui passe
  // aussi ?date_debut/?date_fin ; on pré-remplit la plage depuis l'URL au
  // montage pour ouvrir le GL déjà filtré sur la période de la déclaration.
  const [searchParams] = useSearchParams()
  const [etat, setEtat] = useTabParam('balance', 'etat')
  const [dateDebut, setDateDebut] = useState(() => searchParams.get('date_debut') || '')
  const [dateFin, setDateFin] = useState(() => searchParams.get('date_fin') || '')
  const [exercice, setExercice] = useState('')
  const [exercices, setExercices] = useState([])
  const [comparer, setComparer] = useState(false)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    comptaApi.exercices.list()
      .then((res) => setExercices(unwrap(res)))
      .catch(() => {})
  }, [])

  const current = ETATS.find((e) => e.value === etat)

  const params = useMemo(() => {
    const p = {}
    if (dateDebut) p.date_debut = dateDebut
    if (dateFin) p.date_fin = dateFin
    if (exercice) p.exercice = exercice
    if (comparer && current?.supportsComparer) p.comparer = '1'
    return p
  }, [dateDebut, dateFin, exercice, comparer, current])

  const run = useCallback(() => {
    if (current.needsExercice && !exercice) {
      setData(null)
      return
    }
    const fetcher = current.fetch
    setLoading(true)
    setError(null)
    fetcher(params)
      .then((res) => setData(res.data))
      .catch(() => {
        setError('État indisponible.')
        toast.error('Impossible de générer cet état.')
      })
      .finally(() => setLoading(false))
  }, [current, exercice, params])

  // Recharge à chaque changement d'état / de paramètres.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { run() }, [run])

  // Export CSV via ?export=csv sur les états qui le supportent (balance/GL/etc.).
  const exportCsv = async () => {
    try {
      const res = await current.fetch({ ...params, export: 'csv' })
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      comptaApi.downloadBlob(blob, `${etat}.csv`)
    } catch {
      toast.error('Export CSV indisponible pour cet état.')
    }
  }

  // ZACC1 — export PDF (quand l'état le supporte).
  const exportPdf = async () => {
    try {
      const res = await current.fetch({ ...params, export: 'pdf' })
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      comptaApi.downloadBlob(blob, `${etat}.pdf`)
    } catch {
      toast.error('Export PDF indisponible pour cet état.')
    }
  }

  // ZACC16 — dossier de clôture xlsx multi-onglets (exige un exercice).
  const exportDossierCloture = async () => {
    if (!exercice) {
      toast.error("Sélectionnez un exercice avant l'export du dossier de clôture.")
      return
    }
    try {
      const res = await comptaApi.etats.dossierCloture({ exercice })
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      comptaApi.downloadBlob(blob, `dossier-cloture-${exercice}.xlsx`)
    } catch {
      toast.error('Dossier de clôture indisponible — vérifiez l’exercice.')
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>États comptables (CGNC)</h2>
        <div className="page-header-actions">
          <Button variant="outline" onClick={run}><RefreshCw /> Actualiser</Button>
          <Button variant="outline" onClick={exportCsv}><Download /> Export CSV</Button>
          {current?.supportsPdf && (
            <Button variant="outline" onClick={exportPdf}><FileText /> Export PDF</Button>
          )}
          <Button variant="outline" onClick={exportDossierCloture}>
            <Download /> Dossier de clôture (xlsx)
          </Button>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-end gap-3">
        <Segmented options={ETATS} value={etat} onChange={setEtat} aria-label="Choisir l'état" />
        <div className="flex flex-col gap-1">
          <Label htmlFor="et-debut">Du</Label>
          <Input id="et-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="et-fin">Au</Label>
          <Input id="et-fin" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="et-ex">Exercice{current?.needsExercice ? ' (requis)' : ''}</Label>
          <select
            id="et-ex"
            className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
            value={exercice} onChange={(e) => setExercice(e.target.value)}
          >
            <option value="">—</option>
            {exercices.map((ex) => (
              <option key={ex.id} value={ex.id}>{ex.libelle}</option>
            ))}
          </select>
        </div>
        {current?.supportsComparer && (
          <Button
            variant={comparer ? 'default' : 'outline'}
            size="sm"
            onClick={() => setComparer((v) => !v)}
          >
            <GitCompare className="size-4" /> Comparer N-1
          </Button>
        )}
      </div>

      <Card className="p-4 sm:p-5">
        {current?.needsExercice && !exercice ? (
          <EmptyState title="Exercice requis" description="Sélectionnez un exercice pour générer cet état." />
        ) : loading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Génération de l'état…</p>
        ) : error ? (
          <EmptyState title="Impossible de charger l'état" description="Vérifiez la période puis réessayez." />
        ) : (
          <EtatRender data={data} />
        )}
      </Card>
    </div>
  )
}

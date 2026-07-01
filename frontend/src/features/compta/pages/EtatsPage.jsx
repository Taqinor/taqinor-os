import { useCallback, useEffect, useMemo, useState } from 'react'
import { Download, RefreshCw } from 'lucide-react'
import { Button, Segmented, Input, Label, Card, EmptyState, toast } from '../../../ui'
import { formatMAD } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import { unwrap } from '../components/useComptaList.js'

/* ============================================================================
   UX5 — États comptables CGNC.
   ----------------------------------------------------------------------------
   Sélecteur d'exercice / période + rendu de chaque état (grand-livre, balance,
   CPC, bilan, ESG, ETIC) et export CSV (« ?export=csv ») quand disponible.
   Le rendu est ADAPTATIF : une réponse { lignes:[…] } → tableau, un tableau de
   groupes (grand-livre) → sections, sinon liste clé/valeur des agrégats.
   ========================================================================== */

const ETATS = [
  { value: 'balance', label: 'Balance', fetch: comptaApi.etats.balance },
  { value: 'grand-livre', label: 'Grand-livre', fetch: comptaApi.etats.grandLivre },
  { value: 'cpc', label: 'CPC', fetch: comptaApi.etats.cpc },
  { value: 'bilan', label: 'Bilan', fetch: comptaApi.etats.bilan },
  { value: 'esg', label: 'ESG', fetch: comptaApi.etats.esg },
  { value: 'etic', label: 'ETIC', fetch: comptaApi.etats.etic },
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
  const [etat, setEtat] = useState('balance')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [exercice, setExercice] = useState('')
  const [exercices, setExercices] = useState([])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    comptaApi.exercices.list()
      .then((res) => setExercices(unwrap(res)))
      .catch(() => {})
  }, [])

  const params = useMemo(() => {
    const p = {}
    if (dateDebut) p.date_debut = dateDebut
    if (dateFin) p.date_fin = dateFin
    if (exercice) p.exercice = exercice
    return p
  }, [dateDebut, dateFin, exercice])

  const current = ETATS.find((e) => e.value === etat)

  const run = useCallback(() => {
    const fetcher = ETATS.find((e) => e.value === etat).fetch
    setLoading(true)
    setError(null)
    fetcher(params)
      .then((res) => setData(res.data))
      .catch(() => {
        setError('État indisponible.')
        toast.error('Impossible de générer cet état.')
      })
      .finally(() => setLoading(false))
  }, [etat, params])

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

  return (
    <div className="page">
      <div className="page-header">
        <h2>États comptables (CGNC)</h2>
        <div className="page-header-actions">
          <Button variant="outline" onClick={run}><RefreshCw /> Actualiser</Button>
          <Button variant="outline" onClick={exportCsv}><Download /> Export CSV</Button>
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
          <Label htmlFor="et-ex">Exercice</Label>
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
      </div>

      <Card className="p-4 sm:p-5">
        {loading ? (
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

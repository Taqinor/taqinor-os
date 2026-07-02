import { useEffect, useMemo, useState } from 'react'
import { Check } from 'lucide-react'
import { ListShell } from '../../ui/module'
import { Segmented, Badge, toast } from '../../ui'
import { formatDate } from '../../lib/format'
import rhApi from '../../api/rhApi'
import { GraviteAccident, StatutAccident, StatutAnalyse } from './constants.jsx'

/* ============================================================================
   UX27 — HSE RH (registres).
   ----------------------------------------------------------------------------
   Registres Hygiène-Sécurité-Environnement : accidents du travail,
   presqu'accidents, causeries de sécurité, analyses de risques chantier. La
   validation d'une analyse passe par l'@action serveur.
   ========================================================================== */

const VUES = [
  { value: 'accidents', label: 'Accidents du travail' },
  { value: 'presqu', label: 'Presqu’accidents' },
  { value: 'causeries', label: 'Causeries' },
  { value: 'analyses', label: 'Analyses de risques' },
]

export default function Hse() {
  const [vue, setVue] = useState('accidents')
  const [accidents, setAccidents] = useState([])
  const [presqu, setPresqu] = useState([])
  const [causeries, setCauseries] = useState([])
  const [analyses, setAnalyses] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const recharger = () => {
    let vivant = true
    setLoading(true)
    setError(null)
    Promise.all([
      rhApi.getAccidentsTravail(),
      rhApi.getPresquAccidents(),
      rhApi.getCauseriesSecurite(),
      rhApi.getAnalysesRisques(),
    ])
      .then(([ac, pa, ca, an]) => {
        if (!vivant) return
        setAccidents(unwrap(ac.data))
        setPresqu(unwrap(pa.data))
        setCauseries(unwrap(ca.data))
        setAnalyses(unwrap(an.data))
      })
      .catch(() => {
        if (!vivant) return
        setError('Impossible de charger le registre HSE.')
        toast.error('Impossible de charger le registre HSE.')
      })
      .finally(() => { if (vivant) setLoading(false) })
    return () => { vivant = false }
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(recharger, [])

  const validerAnalyse = async (a) => {
    try {
      await rhApi.validerAnalyseRisques(a.id)
      toast.success('Analyse validée.')
      recharger()
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Validation impossible.')
    }
  }

  const accidentColumns = useMemo(() => [
    { id: 'reference', header: 'Référence', width: 140, accessor: (a) => a.reference || '', cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'employe', header: 'Blessé', width: 170, accessor: (a) => a.employe_nom || String(a.employe || ''), cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (a) => a.date_accident || '', cell: (v) => formatDate(v) },
    { id: 'lieu', header: 'Lieu', width: 160, accessor: (a) => a.lieu || '', cell: (v) => v || '—' },
    { id: 'gravite', header: 'Gravité', width: 110, accessor: (a) => a.gravite || '', cell: (_v, a) => <GraviteAccident status={a.gravite} label={a.gravite_display} /> },
    { id: 'statut', header: 'Statut', width: 110, accessor: (a) => a.statut || '', cell: (_v, a) => <StatutAccident status={a.statut} label={a.statut_display} /> },
  ], [])

  const presquColumns = useMemo(() => [
    { id: 'reference', header: 'Référence', width: 140, accessor: (p) => p.reference || '', cell: (v) => <span className="font-mono text-xs">{v || '—'}</span> },
    { id: 'date', header: 'Constaté le', width: 120, searchable: false, accessor: (p) => p.date_constat || '', cell: (v) => formatDate(v) },
    { id: 'lieu', header: 'Lieu', width: 160, accessor: (p) => p.lieu || '', cell: (v) => v || '—' },
    { id: 'gravite', header: 'Gravité potentielle', width: 160, accessor: (p) => p.gravite_potentielle_display || p.gravite_potentielle || '', cell: (v) => v || '—' },
    { id: 'statut', header: 'Statut', width: 110, accessor: (p) => p.statut_display || p.statut || '', cell: (v) => v || '—' },
  ], [])

  const causerieColumns = useMemo(() => [
    { id: 'theme', header: 'Thème', width: 220, accessor: (c) => c.theme || '', cell: (v) => <span className="font-medium">{v || '—'}</span> },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (c) => c.date_causerie || '', cell: (v) => formatDate(v) },
    { id: 'animateur', header: 'Animateur', width: 160, accessor: (c) => c.animateur_nom || String(c.animateur || ''), cell: (v) => v || '—' },
    { id: 'lieu', header: 'Lieu', width: 160, accessor: (c) => c.lieu || '', cell: (v) => v || '—' },
  ], [])

  const analyseColumns = useMemo(() => [
    { id: 'chantier', header: 'Chantier', width: 140, accessor: (a) => String(a.chantier_id ?? ''), cell: (v) => v || '—' },
    { id: 'date', header: 'Date', width: 120, searchable: false, accessor: (a) => a.date_analyse || '', cell: (v) => formatDate(v) },
    { id: 'redacteur', header: 'Rédacteur', width: 160, accessor: (a) => a.redacteur_nom || String(a.redacteur || ''), cell: (v) => v || '—' },
    { id: 'risques', header: 'Risques', width: 90, align: 'right', searchable: false, accessor: (a) => (Array.isArray(a.risques) ? a.risques.length : 0), cell: (v) => <Badge tone="neutral">{v}</Badge> },
    { id: 'statut', header: 'Statut', width: 120, accessor: (a) => a.statut || '', cell: (_v, a) => <StatutAnalyse status={a.statut} label={a.statut_display} /> },
  ], [])

  const analyseActions = (a) => (a.statut === 'brouillon'
    ? [{ id: 'valider', label: 'Valider', icon: Check, onClick: () => validerAnalyse(a) }]
    : [])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>HSE — Hygiène, sécurité & environnement</h2>
      </div>

      <Segmented options={VUES} value={vue} onChange={setVue} aria-label="Vue HSE" />

      {vue === 'accidents' && (
        <ListShell title="Accidents du travail" columns={accidentColumns} rows={accidents} loading={loading} error={error}
          searchable exportName="accidents-travail" emptyTitle="Aucun accident" emptyDescription="Aucun accident déclaré." />
      )}
      {vue === 'presqu' && (
        <ListShell title="Presqu’accidents" columns={presquColumns} rows={presqu} loading={loading} error={error}
          searchable exportName="presqu-accidents" emptyTitle="Aucun presqu’accident" emptyDescription="Aucun presqu’accident signalé." />
      )}
      {vue === 'causeries' && (
        <ListShell title="Causeries de sécurité" columns={causerieColumns} rows={causeries} loading={loading} error={error}
          searchable exportName="causeries-securite" emptyTitle="Aucune causerie" emptyDescription="Aucune causerie enregistrée." />
      )}
      {vue === 'analyses' && (
        <ListShell title="Analyses de risques chantier" columns={analyseColumns} rows={analyses} loading={loading} error={error}
          searchable rowActions={analyseActions} exportName="analyses-risques"
          emptyTitle="Aucune analyse" emptyDescription="Aucune analyse de risques." />
      )}
    </div>
  )
}

function unwrap(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}

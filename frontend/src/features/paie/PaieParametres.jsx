import { useEffect, useState } from 'react'
import { Sprout, Plus } from 'lucide-react'
import {
  Button, Card, Input, Spinner, EmptyState, Badge, toast,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { DataTable } from '../../ui'
import { formatMAD, formatPercent } from '../../lib/format'
import paieApi from '../../api/paieApi'

/* ============================================================================
   UX12 — Paramètres & barèmes de la paie.
   ----------------------------------------------------------------------------
   Constantes versionnées (SMIG/CNSS/AMO/frais pro, date_effet), barème IR,
   catalogue de rubriques (semis en un clic), profils par employé. Édition
   directe des lignes actives ; les montants via formatMAD, taux via
   formatPercent. Aucun prix d'achat/marge.
   ========================================================================== */
export default function PaieParametres() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-xl font-semibold tracking-tight">
          Paramètres de paie
        </h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Constantes légales, barème IR, rubriques et profils.
        </p>
      </div>
      <Tabs defaultValue="parametres">
        <TabsList className="flex-wrap">
          <TabsTrigger value="parametres">Paramètres sociaux</TabsTrigger>
          <TabsTrigger value="bareme">Barème IR</TabsTrigger>
          <TabsTrigger value="rubriques">Rubriques</TabsTrigger>
          <TabsTrigger value="profils">Profils</TabsTrigger>
        </TabsList>
        <TabsContent value="parametres"><ParametresTab /></TabsContent>
        <TabsContent value="bareme"><BaremeTab /></TabsContent>
        <TabsContent value="rubriques"><RubriquesTab /></TabsContent>
        <TabsContent value="profils"><ProfilsTab /></TabsContent>
      </Tabs>
    </div>
  )
}

/* ── Paramètres sociaux versionnés ── */
function ParametresTab() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  const load = () =>
    paieApi.getParametres({ ordering: '-date_effet' })
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement des paramètres impossible.'))
      .finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const seed = async () => {
    setBusy(true)
    try {
      await paieApi.seedParametresDefaults()
      toast.success('Valeurs légales 2026 provisionnées.')
      await load()
    } catch {
      toast.error('Semis impossible.')
    } finally { setBusy(false) }
  }

  const columns = [
    { id: 'date', header: 'Effet', accessor: (r) => r.date_effet },
    { id: 'smig', header: 'SMIG', align: 'right',
      accessor: (r) => Number(r.smig) || 0, cell: (_v, r) => formatMAD(r.smig) },
    { id: 'plafond', header: 'Plafond CNSS', align: 'right',
      accessor: (r) => Number(r.plafond_cnss) || 0,
      cell: (_v, r) => formatMAD(r.plafond_cnss) },
    { id: 'cnss', header: 'CNSS sal.', align: 'right',
      accessor: (r) => Number(r.taux_cnss_salarial) || 0,
      cell: (_v, r) => formatPercent(r.taux_cnss_salarial, { decimals: 2 }) },
    { id: 'amo', header: 'AMO sal.', align: 'right',
      accessor: (r) => Number(r.taux_amo_salarial) || 0,
      cell: (_v, r) => formatPercent(r.taux_amo_salarial, { decimals: 2 }) },
    { id: 'actif', header: 'État', accessor: (r) => r.actif,
      cell: (_v, r) => (
        <span className="flex items-center gap-1.5">
          {r.actif && <Badge tone="success">Actif</Badge>}
          {r.valide_par_fondateur
            ? <Badge tone="info">Validé</Badge>
            : <Badge tone="warning">À valider</Badge>}
        </span>
      ) },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button onClick={seed} loading={busy} variant="outline">
          <Sprout size={16} aria-hidden="true" /> Provisionner 2026
        </Button>
      </div>
      <Card className="p-4 sm:p-5">
        {loading ? <Loading /> : rows.length === 0 ? (
          <EmptyState icon={Sprout} title="Aucun paramètre"
            description="Provisionnez les valeurs légales 2026 pour démarrer." />
        ) : (
          <DataTable data={rows} columns={columns}
            exportName="parametres-paie" />
        )}
      </Card>
    </div>
  )
}

/* ── Barème IR ── */
function BaremeTab() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    paieApi.getBaremes({ ordering: '-date_effet' })
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement du barème IR impossible.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Card className="p-4"><Loading /></Card>
  if (!rows.length) {
    return (
      <Card className="p-4 sm:p-5">
        <EmptyState icon={Sprout} title="Aucun barème IR"
          description="Le barème IR est provisionné avec les paramètres 2026 (onglet Paramètres sociaux)." />
      </Card>
    )
  }
  return (
    <div className="flex flex-col gap-4">
      {rows.map((b) => (
        <Card key={b.id} className="p-4 sm:p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-display font-semibold">{b.libelle}</h3>
            <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
              Effet {b.date_effet}
              {b.actif && <Badge tone="success">Actif</Badge>}
            </span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted-foreground">
                <th className="py-1.5 font-medium">De</th>
                <th className="py-1.5 font-medium">À</th>
                <th className="py-1.5 text-right font-medium">Taux</th>
                <th className="py-1.5 text-right font-medium">À déduire</th>
              </tr>
            </thead>
            <tbody>
              {(b.tranches || []).map((t) => (
                <tr key={t.id} className="border-b border-border/60">
                  <td className="py-1.5 tabular-nums">{formatMAD(t.borne_min)}</td>
                  <td className="py-1.5 tabular-nums">
                    {t.borne_max ? formatMAD(t.borne_max) : '∞'}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {formatPercent(t.taux, { decimals: 0 })}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">
                    {formatMAD(t.somme_a_deduire)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ))}
    </div>
  )
}

/* ── Rubriques ── */
function RubriquesTab() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')

  const load = () =>
    paieApi.getRubriques({ ordering: 'ordre' })
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement des rubriques impossible.'))
      .finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const seed = async (kind) => {
    setBusy(kind)
    try {
      if (kind === 'standard') await paieApi.seedRubriquesStandard()
      else await paieApi.seedRubriquesDefaults()
      toast.success('Rubriques provisionnées.')
      await load()
    } catch {
      toast.error('Semis impossible.')
    } finally { setBusy('') }
  }

  const columns = [
    { id: 'code', header: 'Code', width: 100, accessor: (r) => r.code },
    { id: 'libelle', header: 'Libellé', accessor: (r) => r.libelle },
    { id: 'type', header: 'Type', accessor: (r) => r.type,
      cell: (_v, r) => <Badge tone={r.type === 'retenue' ? 'danger' : 'success'}>
        {r.type}</Badge> },
    { id: 'imposable', header: 'Imposable', accessor: (r) => r.imposable,
      cell: (_v, r) => (r.imposable ? 'Oui' : 'Non') },
    { id: 'cnss', header: 'CNSS', accessor: (r) => r.soumis_cnss,
      cell: (_v, r) => (r.soumis_cnss ? 'Oui' : 'Non') },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap justify-end gap-2">
        <Button onClick={() => seed('defaut')} loading={busy === 'defaut'}
          variant="outline">
          <Sprout size={16} aria-hidden="true" /> Rubriques de base
        </Button>
        <Button onClick={() => seed('standard')} loading={busy === 'standard'}
          variant="outline">
          <Sprout size={16} aria-hidden="true" /> Catalogue standard
        </Button>
      </div>
      <Card className="p-4 sm:p-5">
        {loading ? <Loading /> : rows.length === 0 ? (
          <EmptyState icon={Sprout} title="Aucune rubrique"
            description="Provisionnez le catalogue en un clic." />
        ) : (
          <DataTable data={rows} columns={columns} searchable
            exportName="rubriques-paie" />
        )}
      </Card>
    </div>
  )
}

/* ── Profils de paie par employé ── */
function ProfilsTab() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    paieApi.getProfils()
      .then((r) => setRows(listOf(r.data)))
      .catch(() => toast.error('Chargement des profils impossible.'))
      .finally(() => setLoading(false))
  }, [])

  const columns = [
    { id: 'employe', header: 'Employé', accessor: (r) => r.employe_nom || '',
      cell: (_v, r) => r.employe_nom || `Employé #${r.employe}` },
    { id: 'type', header: 'Rémunération', accessor: (r) => r.type_remuneration },
    { id: 'cnss', header: 'N° CNSS', accessor: (r) => r.numero_cnss || '' },
    { id: 'banque', header: 'Banque', accessor: (r) => r.banque || '' },
    { id: 'actif', header: 'État', accessor: (r) => r.actif,
      cell: (_v, r) => (r.actif
        ? <Badge tone="success">Actif</Badge>
        : <Badge tone="neutral">Inactif</Badge>) },
  ]

  return (
    <Card className="p-4 sm:p-5">
      {loading ? <Loading /> : rows.length === 0 ? (
        <EmptyState icon={Plus} title="Aucun profil de paie"
          description="Les profils rattachent chaque employé RH à ses règles de paie (salaire de base sensible, jamais exposé)." />
      ) : (
        <DataTable data={rows} columns={columns} searchable
          exportName="profils-paie" />
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

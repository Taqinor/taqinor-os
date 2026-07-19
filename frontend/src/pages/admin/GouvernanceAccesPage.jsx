import { useEffect, useState } from 'react'
import { ShieldCheck, Plus, Trash2, Download, AlertTriangle, ClipboardList } from 'lucide-react'
import accessReviewApi from '../../api/accessReviewApi'
import {
  Card, CardContent, CardHeader, CardTitle, Button, Input, Badge, Spinner,
  EmptyState, toast, Tabs, TabsList, TabsTrigger, TabsContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { formatDate } from '../../lib/format'

/* ============================================================================
   WIR135 — Écran d'administration « Gouvernance des accès ».
   ----------------------------------------------------------------------------
   Surface le backend jusqu'ici sans consommateur (gouverné IsAdminRole) :
   • Campagnes de revue d'accès + attestation/révocation par item (NTSEC19) ;
   • Règles SoD + rapport de violations (NTSEC20) ;
   • Rapport de certification des accès (roles.revue-acces, JSON + CSV, XPLT12).
   La révocation retire réellement le rôle via roles.services (côté serveur).
   ========================================================================== */

const asList = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

const SEVERITE_TONE = { info: 'info', warning: 'warning', critique: 'danger' }

// ── Campagnes de revue d'accès ────────────────────────────────────────────────
function CampagnesTab() {
  const [campaigns, setCampaigns] = useState([])
  const [nom, setNom] = useState('')
  const [perimetre, setPerimetre] = useState('all')
  const [loading, setLoading] = useState(true)
  const [openId, setOpenId] = useState(null)

  const load = () => accessReviewApi.campaigns.list()
    .then((r) => setCampaigns(asList(r.data))).catch(() => {}).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const create = async () => {
    if (!nom.trim()) { toast.error('Nom de campagne requis.'); return }
    try {
      await accessReviewApi.campaigns.create({ nom: nom.trim(), perimetre, statut: 'ouverte' })
      setNom(''); load(); toast.success('Campagne lancée.')
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Lancement impossible.') }
  }
  const attester = async (campaign, item, decision) => {
    try {
      await accessReviewApi.campaigns.attester(campaign.id, { item: item.id, decision })
      const r = await accessReviewApi.campaigns.get(campaign.id)
      setCampaigns((cs) => cs.map((c) => (c.id === campaign.id ? r.data : c)))
      toast.success(decision === 'revoque' ? 'Accès révoqué (rôle retiré).' : 'Accès maintenu.')
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Décision impossible.') }
  }

  if (loading) return <Spinner />
  return (
    <Card>
      <CardHeader><CardTitle>Campagnes de revue d'accès</CardTitle></CardHeader>
      <CardContent className="space-y-3" data-testid="campaigns">
        <div className="flex flex-wrap items-end gap-2">
          <Input placeholder="Nom de la campagne" value={nom} aria-label="Nom de la campagne"
            onChange={(e) => setNom(e.target.value)} className="max-w-[240px]" />
          <Select value={perimetre} onValueChange={setPerimetre}>
            <SelectTrigger aria-label="Périmètre" className="w-[160px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les comptes</SelectItem>
              <SelectItem value="role">Par rôle</SelectItem>
              <SelectItem value="module">Par module</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={create}><Plus size={16} /> Lancer une campagne</Button>
        </div>

        {campaigns.length === 0 && <EmptyState title="Aucune campagne" className="py-4" />}
        {campaigns.map((c) => (
          <div key={c.id} className="rounded-md border">
            <button type="button"
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-muted"
              onClick={() => setOpenId(openId === c.id ? null : c.id)}>
              <span className="font-medium">{c.nom}</span>
              <Badge tone={c.statut === 'ouverte' ? 'success' : 'neutral'}>{c.statut}</Badge>
              <span className="ml-auto text-muted-foreground">{(c.items ?? []).length} item(s)</span>
            </button>
            {openId === c.id && (
              <div className="border-t px-3 py-2">
                {(c.items ?? []).length === 0 && <p className="text-sm text-muted-foreground">Aucun item.</p>}
                {(c.items ?? []).map((it) => (
                  <div key={it.id} className="flex items-center gap-2 py-1 text-sm">
                    <span>Compte #{it.user}</span>
                    <span className="text-muted-foreground">{it.role_snapshot}</span>
                    <Badge tone={it.decision === 'revoque' ? 'danger' : it.decision === 'maintenu' ? 'success' : 'neutral'}>
                      {it.decision}
                    </Badge>
                    {it.decision === 'en_attente' && (
                      <span className="ml-auto flex gap-1">
                        <Button size="sm" variant="ghost" onClick={() => attester(c, it, 'maintenu')}>Maintenir</Button>
                        <Button size="sm" variant="ghost" onClick={() => attester(c, it, 'revoque')}>Révoquer</Button>
                      </span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

// ── Règles SoD + violations ───────────────────────────────────────────────────
function SodTab() {
  const [rules, setRules] = useState([])
  const [violations, setViolations] = useState([])
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const [loading, setLoading] = useState(true)

  const load = () => Promise.all([
    accessReviewApi.sodRules.list(),
    accessReviewApi.sodRules.violations(),
  ]).then(([r, v]) => {
    setRules(asList(r.data)); setViolations(asList(v.data))
  }).catch(() => {}).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const create = async () => {
    if (!a.trim() || !b.trim()) { toast.error('Deux codes de permission requis.'); return }
    try {
      await accessReviewApi.sodRules.create({ permission_a: a.trim(), permission_b: b.trim(), severite: 'warning', libelle: `${a} ⊗ ${b}` })
      setA(''); setB(''); load()
    } catch (e) { toast.error(e?.response?.data?.permission_a ?? e?.response?.data?.detail ?? 'Création impossible.') }
  }
  const remove = async (r) => {
    try { await accessReviewApi.sodRules.remove(r.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }
  const seed = async () => {
    try { await accessReviewApi.sodRules.seedStandard(); load(); toast.success('Jeu SoD standard semé.') }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Semis impossible.') }
  }

  if (loading) return <Spinner />
  return (
    <Card>
      <CardHeader><CardTitle>Règles de séparation des tâches (SoD)</CardTitle></CardHeader>
      <CardContent className="space-y-3" data-testid="sod">
        <div className="flex flex-wrap items-end gap-2">
          <Input placeholder="permission_a" value={a} aria-label="Permission A"
            onChange={(e) => setA(e.target.value)} className="max-w-[200px]" />
          <Input placeholder="permission_b" value={b} aria-label="Permission B"
            onChange={(e) => setB(e.target.value)} className="max-w-[200px]" />
          <Button onClick={create}><Plus size={16} /> Ajouter une règle</Button>
          <Button variant="secondary" onClick={seed}>Semer le jeu standard</Button>
        </div>

        <div className="flex flex-col gap-1.5">
          {rules.length === 0 && <EmptyState title="Aucune règle SoD" className="py-4" />}
          {rules.map((r) => (
            <div key={r.id} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
              <code>{r.permission_a}</code><span className="text-muted-foreground">⊗</span><code>{r.permission_b}</code>
              <Badge tone={SEVERITE_TONE[r.severite] ?? 'neutral'}>{r.severite}</Badge>
              <Button size="sm" variant="ghost" className="ml-auto"
                onClick={() => remove(r)} aria-label="Supprimer la règle"><Trash2 size={14} /></Button>
            </div>
          ))}
        </div>

        <div>
          <div className="mb-1 flex items-center gap-1.5 text-sm font-medium">
            <AlertTriangle size={15} className="text-warning" /> Violations
          </div>
          {violations.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucune violation SoD détectée.</p>
          ) : (
            <ul className="list-disc pl-5 text-sm" data-testid="violations">
              {violations.map((v, i) => (
                <li key={i}>Compte #{v.user ?? v.user_id} — {v.libelle ?? `${v.permission_a} ⊗ ${v.permission_b}`}</li>
              ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// ── Rapport de certification des accès ────────────────────────────────────────
function RapportTab() {
  const [rows, setRows] = useState(null)
  useEffect(() => {
    accessReviewApi.revueAcces()
      .then((r) => setRows(asList(r.data))).catch(() => setRows([]))
  }, [])
  const exportCsv = async () => {
    try {
      const res = await accessReviewApi.revueAccesCsv()
      const url = URL.createObjectURL(new Blob([res.data], { type: 'text/csv' }))
      const link = document.createElement('a')
      link.href = url; link.download = 'revue-acces.csv'; link.click()
      URL.revokeObjectURL(url)
    } catch { toast.error('Export impossible.') }
  }
  if (rows === null) return <Spinner />
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Rapport de certification des accès</CardTitle>
        <Button size="sm" variant="secondary" onClick={exportCsv}><Download size={14} /> CSV</Button>
      </CardHeader>
      <CardContent data-testid="rapport">
        {rows.length === 0 ? <EmptyState title="Aucune ligne" className="py-4" /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground">
                  <th className="py-1">Compte</th><th>Rôle</th><th>Dernière connexion</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t">
                    <td className="py-1">{r.username ?? r.user ?? '—'}</td>
                    <td>{r.role ?? r.role_nom ?? '—'}</td>
                    <td>{r.last_login ? formatDate(r.last_login) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function GouvernanceAccesPage() {
  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center gap-2">
        <ShieldCheck className="text-primary" aria-hidden="true" />
        <h1 className="text-lg font-semibold">Gouvernance des accès</h1>
      </div>
      <Tabs defaultValue="campagnes">
        <TabsList className="flex-wrap">
          <TabsTrigger value="campagnes"><ClipboardList size={14} /> Campagnes</TabsTrigger>
          <TabsTrigger value="sod"><ShieldCheck size={14} /> Règles SoD</TabsTrigger>
          <TabsTrigger value="rapport"><Download size={14} /> Rapport</TabsTrigger>
        </TabsList>
        <TabsContent value="campagnes"><CampagnesTab /></TabsContent>
        <TabsContent value="sod"><SodTab /></TabsContent>
        <TabsContent value="rapport"><RapportTab /></TabsContent>
      </Tabs>
    </div>
  )
}

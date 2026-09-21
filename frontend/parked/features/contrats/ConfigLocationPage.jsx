import { useEffect, useState } from 'react'
import { Settings2, Plus, Trash2 } from 'lucide-react'
import contratsApi from '../../api/contratsApi'
import {
  Card, Badge, Button, Input, Label, Tabs, TabsList, TabsTrigger, TabsContent, toast,
} from '../../ui'
import SimpleTable from './SimpleTable'

/* ============================================================================
   ZCTR1/3/4 — Écrans de configuration de la location.
   ----------------------------------------------------------------------------
   Trois volets : plans de facturation récurrente réutilisables (PlanRecurrent),
   référentiel des motifs de résiliation (MotifResiliation), et réglages
   singleton de la location (ParametresLocation — durée minimale, temps de
   sécurité, frais de retard par défaut).
   ========================================================================== */

const listData = (res) => (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const UNITES = [
  { value: 'mensuel', label: 'Mensuel' },
  { value: 'trimestriel', label: 'Trimestriel' },
  { value: 'semestriel', label: 'Semestriel' },
  { value: 'annuel', label: 'Annuel' },
]

export default function ConfigLocationPage() {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Settings2 className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">Réglages location</h1>
      </div>
      <Tabs defaultValue="plans">
        <TabsList className="flex-wrap">
          <TabsTrigger value="plans">Plans récurrents</TabsTrigger>
          <TabsTrigger value="motifs">Motifs de résiliation</TabsTrigger>
          <TabsTrigger value="parametres">Paramètres</TabsTrigger>
        </TabsList>
        <TabsContent value="plans"><PlansTab /></TabsContent>
        <TabsContent value="motifs"><MotifsTab /></TabsContent>
        <TabsContent value="parametres"><ParametresTab /></TabsContent>
      </Tabs>
    </div>
  )
}

function PlansTab() {
  const [rows, setRows] = useState([])
  const [nom, setNom] = useState('')
  const [unite, setUnite] = useState('mensuel')
  const [intervalle, setIntervalle] = useState('1')

  const load = () => contratsApi.getPlansRecurrents().then((r) => setRows(listData(r))).catch(() => setRows([]))
  useEffect(() => { load() }, [])

  const create = async (e) => {
    e.preventDefault()
    if (!nom.trim()) return
    try {
      await contratsApi.createPlanRecurrent({ nom: nom.trim(), unite, intervalle: Number(intervalle) || 1 })
      setNom(''); setIntervalle('1')
      toast.success('Plan créé.'); load()
    } catch (e2) { toast.error(errMsg(e2, 'Création impossible.')) }
  }

  const remove = async (id) => {
    try { await contratsApi.deletePlanRecurrent(id); toast.success('Plan supprimé.'); load() }
    catch (e) { toast.error(errMsg(e, 'Suppression impossible.')) }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <form onSubmit={create} className="flex flex-wrap items-end gap-3" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pl-nom">Nom</Label>
            <Input id="pl-nom" value={nom} onChange={(e) => setNom(e.target.value)} placeholder="ex. Mensuel standard" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pl-unite">Unité</Label>
            <select id="pl-unite" value={unite} onChange={(e) => setUnite(e.target.value)} className="h-9 rounded-md border border-border bg-card px-3 text-sm">
              {UNITES.map((u) => <option key={u.value} value={u.value}>{u.label}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pl-int">Intervalle</Label>
            <Input id="pl-int" type="number" min="1" step="any" value={intervalle} onChange={(e) => setIntervalle(e.target.value)} className="w-24" />
          </div>
          <Button type="submit"><Plus /> Ajouter</Button>
        </form>
      </Card>
      <SimpleTable
        emptyText="Aucun plan récurrent."
        rows={rows}
        columns={[
          { header: 'Nom', cell: (p) => <span className="font-medium">{p.nom}</span> },
          { header: 'Unité', cell: (p) => p.unite_display || p.unite },
          { header: 'Intervalle', cell: (p) => p.intervalle },
          { header: 'Actif', cell: (p) => <Badge tone={p.actif ? 'success' : 'neutral'}>{p.actif ? 'Actif' : 'Inactif'}</Badge> },
          { header: '', align: 'right', cell: (p) => <Button size="sm" variant="ghost" onClick={() => remove(p.id)}><Trash2 className="size-3.5" /></Button> },
        ]}
      />
    </div>
  )
}

function MotifsTab() {
  const [rows, setRows] = useState([])
  const [code, setCode] = useState('')
  const [libelle, setLibelle] = useState('')

  const load = () => contratsApi.getMotifsResiliation().then((r) => setRows(listData(r))).catch(() => setRows([]))
  useEffect(() => { load() }, [])

  const create = async (e) => {
    e.preventDefault()
    if (!code.trim() || !libelle.trim()) return
    try {
      await contratsApi.createMotifResiliation({ code: code.trim(), libelle: libelle.trim() })
      setCode(''); setLibelle('')
      toast.success('Motif créé.'); load()
    } catch (e2) { toast.error(errMsg(e2, 'Création impossible.')) }
  }

  const remove = async (id) => {
    try { await contratsApi.deleteMotifResiliation(id); toast.success('Motif supprimé.'); load() }
    catch (e) { toast.error(errMsg(e, 'Suppression impossible.')) }
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <form onSubmit={create} className="flex flex-wrap items-end gap-3" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="mo-code">Code</Label>
            <Input id="mo-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="ex. PRIX" className="w-32" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="mo-lib">Libellé</Label>
            <Input id="mo-lib" value={libelle} onChange={(e) => setLibelle(e.target.value)} placeholder="ex. Tarif trop élevé" />
          </div>
          <Button type="submit"><Plus /> Ajouter</Button>
        </form>
      </Card>
      <SimpleTable
        emptyText="Aucun motif de résiliation."
        rows={rows}
        columns={[
          { header: 'Code', cell: (m) => <span className="font-mono text-xs">{m.code}</span> },
          { header: 'Libellé', cell: (m) => <span className="font-medium">{m.libelle}</span> },
          { header: 'Catégorie', cell: (m) => m.categorie_display || m.categorie || '—' },
          { header: 'Actif', cell: (m) => <Badge tone={m.actif ? 'success' : 'neutral'}>{m.actif ? 'Actif' : 'Inactif'}</Badge> },
          { header: '', align: 'right', cell: (m) => <Button size="sm" variant="ghost" onClick={() => remove(m.id)}><Trash2 className="size-3.5" /></Button> },
        ]}
      />
    </div>
  )
}

function ParametresTab() {
  const [params, setParams] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    contratsApi.getParametresLocation().then((r) => setParams(r.data)).catch(() => setParams(null))
  }, [])

  const save = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const r = await contratsApi.updateParametresLocation({
        duree_minimale_jours: Number(params.duree_minimale_jours) || 0,
        temps_securite_heures: Number(params.temps_securite_heures) || 0,
        frais_retard_jour_defaut: params.frais_retard_jour_defaut === '' || params.frais_retard_jour_defaut == null
          ? null : Number(params.frais_retard_jour_defaut),
      })
      setParams(r.data)
      toast.success('Réglages enregistrés.')
    } catch (e2) { toast.error(errMsg(e2, 'Enregistrement impossible.')) } finally { setSaving(false) }
  }

  if (!params) return <Card className="p-4"><p className="text-sm text-muted-foreground">Chargement…</p></Card>

  const set = (k) => (e) => setParams((p) => ({ ...p, [k]: e.target.value }))

  return (
    <Card className="p-4">
      <form onSubmit={save} className="flex max-w-md flex-col gap-4" noValidate>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pa-duree">Durée minimale de location (jours)</Label>
          <Input id="pa-duree" type="number" min="0" step="any" value={params.duree_minimale_jours ?? 0} onChange={set('duree_minimale_jours')} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pa-secu">Temps de sécurité entre locations (heures)</Label>
          <Input id="pa-secu" type="number" min="0" step="any" value={params.temps_securite_heures ?? 0} onChange={set('temps_securite_heures')} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="pa-retard">Frais de retard par jour (défaut, MAD)</Label>
          <Input id="pa-retard" type="number" step="any" value={params.frais_retard_jour_defaut ?? ''} onChange={set('frais_retard_jour_defaut')} placeholder="Optionnel" />
        </div>
        <Button type="submit" className="self-start" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
      </form>
    </Card>
  )
}

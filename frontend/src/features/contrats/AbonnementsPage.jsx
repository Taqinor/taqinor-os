import { useEffect, useState } from 'react'
import { CreditCard, Plus } from 'lucide-react'
import api from '../../api/axios'
import contratsApi from '../../api/contratsApi'
import {
  Badge, Button, Tabs, TabsList, TabsTrigger, TabsContent, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Label, Input, Textarea,
} from '../../ui'
import SimpleTable from './SimpleTable'

/* ============================================================================
   PACT138 — Abonnements : plans, options, paliers d'usage, compteurs.
   ----------------------------------------------------------------------------
   NTSUB1-4 (`apps/contrats`) livraient déjà 4 ressources ``PlanAbonnement``/
   ``AddOnAbonnement``/``AbonnementAddOnLigne``/``PalierUsage``/``CompteurUsage``
   SANS AUCUN écran (endpoints `/contrats/plans-abonnement/`,
   `/contrats/addons-abonnement/`, `/contrats/addon-lignes/`,
   `/contrats/paliers-usage/`, `/contrats/compteurs-usage/`). Un seul écran à
   onglets : Plans, Options (add-ons + leurs lignes de rattachement), Paliers
   d'usage, Compteurs d'usage. `contratsApi.getPlansRecurrents()` (existant)
   alimente le sélecteur de cadence de facturation d'un plan — jamais une
   nouvelle notion de périodicité recréée ici.

   PIÈGE DE NOMMAGE (rappelé par le modèle backend) : ce ``PlanAbonnement``
   est l'offre VENDUE AUX CLIENTS (maintenance/monitoring/location) — sans
   aucun rapport avec le plan de LICENCE du tenant à l'ERP lui-même
   (``adminops.PlanLicence``). Aucune donnée de licence n'apparaît ici.
   ========================================================================== */

const listData = (res) => (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))
const errMsg = (e, fallback) => e?.response?.data?.detail || fallback

const FACTURATIONS = [
  { value: 'recurrente', label: 'Récurrente' },
  { value: 'ponctuelle', label: 'Ponctuelle' },
]
const TYPES_CIBLE = [
  { value: 'contrat', label: 'Contrat' },
  { value: 'sav_maintenance', label: 'Maintenance SAV' },
]
const MODES_PALIER = [
  { value: 'volume', label: 'Volume (dernier palier atteint)' },
  { value: 'graduated', label: 'Graduated (par tranche)' },
]
const SOURCES_COMPTEUR = [
  { value: 'manuel', label: 'Manuel' },
  { value: 'api', label: 'API' },
  { value: 'calcule', label: 'Calculé' },
]

export default function AbonnementsPage() {
  const [plans, setPlans] = useState([])
  const [addons, setAddons] = useState([])
  const [lignes, setLignes] = useState([])
  const [paliers, setPaliers] = useState([])
  const [compteurs, setCompteurs] = useState([])
  const [plansRecurrents, setPlansRecurrents] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [dialog, setDialog] = useState(null) // 'plan' | 'addon' | 'ligne' | 'palier' | 'compteur'

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([
      api.get('/contrats/plans-abonnement/').then((r) => setPlans(listData(r))),
      api.get('/contrats/addons-abonnement/').then((r) => setAddons(listData(r))),
      api.get('/contrats/addon-lignes/').then((r) => setLignes(listData(r))),
      api.get('/contrats/paliers-usage/').then((r) => setPaliers(listData(r))),
      api.get('/contrats/compteurs-usage/').then((r) => setCompteurs(listData(r))),
      contratsApi.getPlansRecurrents().then((r) => setPlansRecurrents(listData(r))),
    ])
      .catch(() => setError('Impossible de charger le catalogue d’abonnements.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const onCreated = (message) => {
    setDialog(null)
    toast.success(message)
    load()
  }

  const nomPlan = (id) => plans.find((p) => p.id === id)?.nom || `Plan #${id}`
  const nomAddon = (id) => addons.find((a) => a.id === id)?.nom || `Add-on #${id}`

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <CreditCard className="size-5 text-muted-foreground" aria-hidden="true" />
          <h1 className="font-display text-xl font-semibold tracking-tight">Abonnements</h1>
        </div>
      </div>

      <Tabs defaultValue="plans">
        <TabsList className="flex-wrap">
          <TabsTrigger value="plans">Plans ({plans.length})</TabsTrigger>
          <TabsTrigger value="options">Options ({addons.length})</TabsTrigger>
          <TabsTrigger value="paliers">Paliers d’usage ({paliers.length})</TabsTrigger>
          <TabsTrigger value="compteurs">Compteurs d’usage ({compteurs.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="plans">
          <div className="mb-2 flex justify-end">
            <Button size="sm" variant="outline" onClick={() => setDialog('plan')}><Plus /> Nouveau plan</Button>
          </div>
          <SimpleTable
            emptyText="Aucun plan d’abonnement."
            rows={loading ? [] : plans}
            columns={[
              { header: 'Code', cell: (p) => <span className="font-mono text-xs">{p.code}</span> },
              { header: 'Nom', cell: (p) => <span className="font-medium">{p.nom}</span> },
              { header: 'Prix de base', cell: (p) => p.prix_base, align: 'right' },
              { header: 'Engagement', cell: (p) => (p.engagement_mois ? `${p.engagement_mois} mois` : '—') },
              { header: 'Statut', cell: (p) => <Badge tone={p.actif ? 'success' : 'neutral'}>{p.actif ? 'Actif' : 'Inactif'}</Badge> },
            ]}
          />
        </TabsContent>

        <TabsContent value="options">
          <div className="flex flex-col gap-4">
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-sm font-semibold">Add-ons du catalogue</h2>
                <Button size="sm" variant="outline" onClick={() => setDialog('addon')}><Plus /> Nouvel add-on</Button>
              </div>
              <SimpleTable
                emptyText="Aucun add-on."
                rows={loading ? [] : addons}
                columns={[
                  { header: 'Code', cell: (a) => <span className="font-mono text-xs">{a.code}</span> },
                  { header: 'Nom', cell: (a) => <span className="font-medium">{a.nom}</span> },
                  { header: 'Plan rattaché', cell: (a) => (a.plan_abonnement ? nomPlan(a.plan_abonnement) : '—') },
                  { header: 'Prix unitaire', cell: (a) => a.prix_unitaire, align: 'right' },
                  { header: 'Facturation', cell: (a) => a.facturation_display || a.facturation },
                  { header: 'Statut', cell: (a) => <Badge tone={a.actif ? 'success' : 'neutral'}>{a.actif ? 'Actif' : 'Inactif'}</Badge> },
                ]}
              />
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-sm font-semibold">Rattachements (lignes)</h2>
                <Button size="sm" variant="outline" onClick={() => setDialog('ligne')}><Plus /> Nouveau rattachement</Button>
              </div>
              <SimpleTable
                emptyText="Aucun rattachement."
                rows={loading ? [] : lignes}
                columns={[
                  { header: 'Add-on', cell: (l) => nomAddon(l.addon) },
                  { header: 'Cible', cell: (l) => `${l.type_cible_display || l.type_cible} #${l.cible_id}` },
                  { header: 'Quantité', cell: (l) => l.quantite, align: 'right' },
                  { header: 'Actif depuis', cell: (l) => l.actif_depuis },
                  { header: 'Montant / période', cell: (l) => l.montant_periode, align: 'right' },
                ]}
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="paliers">
          <div className="mb-2 flex justify-end">
            <Button size="sm" variant="outline" onClick={() => setDialog('palier')}><Plus /> Nouveau palier</Button>
          </div>
          <SimpleTable
            emptyText="Aucun palier d’usage."
            rows={loading ? [] : paliers}
            columns={[
              { header: 'Cible', cell: (p) => (p.addon ? `Add-on ${nomAddon(p.addon)}` : (p.plan_abonnement ? `Plan ${nomPlan(p.plan_abonnement)}` : '—')) },
              { header: 'Seuil min', cell: (p) => p.seuil_min, align: 'right' },
              { header: 'Seuil max', cell: (p) => p.seuil_max ?? '∞', align: 'right' },
              { header: 'Prix unitaire', cell: (p) => p.prix_unitaire, align: 'right' },
              { header: 'Mode', cell: (p) => p.mode_display || p.mode },
            ]}
          />
        </TabsContent>

        <TabsContent value="compteurs">
          <div className="mb-2 flex justify-end">
            <Button size="sm" variant="outline" onClick={() => setDialog('compteur')}><Plus /> Nouveau relevé</Button>
          </div>
          <SimpleTable
            emptyText="Aucun compteur d’usage."
            rows={loading ? [] : compteurs}
            columns={[
              { header: 'Compteur', cell: (c) => c.code_compteur },
              { header: 'Cible', cell: (c) => `${c.type_cible_display || c.type_cible} #${c.cible_id}` },
              { header: 'Période', cell: (c) => `${c.periode_debut} → ${c.periode_fin}` },
              { header: 'Quantité', cell: (c) => c.quantite, align: 'right' },
              { header: 'Source', cell: (c) => c.source_display || c.source },
            ]}
          />
        </TabsContent>
      </Tabs>

      {dialog === 'plan' && (
        <PlanDialog
          plansRecurrents={plansRecurrents}
          onClose={() => setDialog(null)}
          onDone={() => onCreated('Plan d’abonnement créé.')}
        />
      )}
      {dialog === 'addon' && (
        <AddonDialog
          plans={plans}
          onClose={() => setDialog(null)}
          onDone={() => onCreated('Add-on créé.')}
        />
      )}
      {dialog === 'ligne' && (
        <LigneDialog
          addons={addons}
          onClose={() => setDialog(null)}
          onDone={() => onCreated('Rattachement créé.')}
        />
      )}
      {dialog === 'palier' && (
        <PalierDialog
          addons={addons}
          plans={plans}
          onClose={() => setDialog(null)}
          onDone={() => onCreated('Palier créé.')}
        />
      )}
      {dialog === 'compteur' && (
        <CompteurDialog
          onClose={() => setDialog(null)}
          onDone={() => onCreated('Relevé de compteur enregistré.')}
        />
      )}
    </div>
  )
}

function PlanDialog({ plansRecurrents, onClose, onDone }) {
  const [code, setCode] = useState('')
  const [nom, setNom] = useState('')
  const [description, setDescription] = useState('')
  const [planRecurrent, setPlanRecurrent] = useState('')
  const [prixBase, setPrixBase] = useState('')
  const [engagementMois, setEngagementMois] = useState('')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!code.trim()) { setErr('Le code est requis.'); return }
    if (!nom.trim()) { setErr('Le nom est requis.'); return }
    if (!planRecurrent) { setErr('La cadence de facturation est requise.'); return }
    setSaving(true)
    setErr(null)
    const data = {
      code: code.trim(), nom: nom.trim(), plan_recurrent: Number(planRecurrent),
    }
    if (description.trim()) data.description = description.trim()
    if (prixBase !== '') data.prix_base = Number(prixBase)
    if (engagementMois !== '') data.engagement_mois = Number(engagementMois)
    try {
      await api.post('/contrats/plans-abonnement/', data)
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouveau plan d’abonnement</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pa-code" required>Code</Label>
              <Input id="pa-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="ex. MAINT-STD" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pa-nom" required>Nom</Label>
              <Input id="pa-nom" value={nom} onChange={(e) => setNom(e.target.value)} placeholder="ex. Maintenance standard" />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pa-desc">Description</Label>
            <Textarea id="pa-desc" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optionnel" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="pa-cadence" required>Cadence de facturation</Label>
            <select
              id="pa-cadence"
              value={planRecurrent}
              onChange={(e) => setPlanRecurrent(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">Choisir une cadence…</option>
              {plansRecurrents.map((p) => (
                <option key={p.id} value={p.id}>{p.nom}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pa-prix">Prix de base</Label>
              <Input id="pa-prix" type="number" step="any" value={prixBase} onChange={(e) => setPrixBase(e.target.value)} placeholder="0" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pa-engagement">Engagement (mois)</Label>
              <Input id="pa-engagement" type="number" step="any" value={engagementMois} onChange={(e) => setEngagementMois(e.target.value)} placeholder="Optionnel" />
            </div>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer le plan'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function AddonDialog({ plans, onClose, onDone }) {
  const [planAbonnement, setPlanAbonnement] = useState('')
  const [code, setCode] = useState('')
  const [nom, setNom] = useState('')
  const [prixUnitaire, setPrixUnitaire] = useState('')
  const [facturation, setFacturation] = useState('recurrente')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!code.trim()) { setErr('Le code est requis.'); return }
    if (!nom.trim()) { setErr('Le nom est requis.'); return }
    setSaving(true)
    setErr(null)
    const data = { code: code.trim(), nom: nom.trim(), facturation }
    if (planAbonnement) data.plan_abonnement = Number(planAbonnement)
    if (prixUnitaire !== '') data.prix_unitaire = Number(prixUnitaire)
    try {
      await api.post('/contrats/addons-abonnement/', data)
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouvel add-on</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ad-code" required>Code</Label>
              <Input id="ad-code" value={code} onChange={(e) => setCode(e.target.value)} placeholder="ex. SUPERVISION" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ad-nom" required>Nom</Label>
              <Input id="ad-nom" value={nom} onChange={(e) => setNom(e.target.value)} placeholder="ex. Supervision avancée" />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ad-plan">Plan rattaché</Label>
            <select
              id="ad-plan"
              value={planAbonnement}
              onChange={(e) => setPlanAbonnement(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">— Générique (aucun plan) —</option>
              {plans.map((p) => (
                <option key={p.id} value={p.id}>{p.nom}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ad-prix">Prix unitaire</Label>
              <Input id="ad-prix" type="number" step="any" value={prixUnitaire} onChange={(e) => setPrixUnitaire(e.target.value)} placeholder="0" />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ad-fact">Facturation</Label>
              <select
                id="ad-fact"
                value={facturation}
                onChange={(e) => setFacturation(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {FACTURATIONS.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
            </div>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : "Créer l'add-on"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function LigneDialog({ addons, onClose, onDone }) {
  const [typeCible, setTypeCible] = useState('contrat')
  const [cibleId, setCibleId] = useState('')
  const [addon, setAddon] = useState('')
  const [quantite, setQuantite] = useState('1')
  const [actifDepuis, setActifDepuis] = useState(() => new Date().toISOString().slice(0, 10))
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!addon) { setErr('L’add-on est requis.'); return }
    if (!cibleId) { setErr('L’identifiant de la cible est requis.'); return }
    setSaving(true)
    setErr(null)
    const data = {
      type_cible: typeCible, cible_id: Number(cibleId), addon: Number(addon),
      quantite: Number(quantite) || 1, actif_depuis: actifDepuis,
    }
    try {
      await api.post('/contrats/addon-lignes/', data)
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouveau rattachement d’add-on</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="li-addon" required>Add-on</Label>
            <select
              id="li-addon"
              value={addon}
              onChange={(e) => setAddon(e.target.value)}
              className="h-9 rounded-md border border-border bg-card px-3 text-sm"
            >
              <option value="">Choisir un add-on…</option>
              {addons.map((a) => (
                <option key={a.id} value={a.id}>{a.nom}</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="li-type" required>Type de cible</Label>
              <select
                id="li-type"
                value={typeCible}
                onChange={(e) => setTypeCible(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {TYPES_CIBLE.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="li-cible" required>ID de la cible</Label>
              <Input id="li-cible" type="number" step="1" value={cibleId} onChange={(e) => setCibleId(e.target.value)} placeholder="ex. 12" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="li-qte">Quantité</Label>
              <Input id="li-qte" type="number" step="1" value={quantite} onChange={(e) => setQuantite(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="li-depuis">Actif depuis</Label>
              <Input id="li-depuis" type="date" value={actifDepuis} onChange={(e) => setActifDepuis(e.target.value)} />
            </div>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer le rattachement'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function PalierDialog({ addons, plans, onClose, onDone }) {
  const [cibleType, setCibleType] = useState('addon') // 'addon' | 'plan'
  const [cibleId, setCibleId] = useState('')
  const [seuilMin, setSeuilMin] = useState('0')
  const [seuilMax, setSeuilMax] = useState('')
  const [prixUnitaire, setPrixUnitaire] = useState('')
  const [mode, setMode] = useState('volume')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!cibleId) { setErr('La cible (add-on ou plan) est requise.'); return }
    setSaving(true)
    setErr(null)
    const data = {
      seuil_min: Number(seuilMin) || 0, prix_unitaire: Number(prixUnitaire) || 0, mode,
    }
    if (cibleType === 'addon') data.addon = Number(cibleId)
    else data.plan_abonnement = Number(cibleId)
    if (seuilMax !== '') data.seuil_max = Number(seuilMax)
    try {
      await api.post('/contrats/paliers-usage/', data)
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Création impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouveau palier d’usage</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pu-ciblet" required>Cible</Label>
              <select
                id="pu-ciblet"
                value={cibleType}
                onChange={(e) => { setCibleType(e.target.value); setCibleId('') }}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="addon">Add-on</option>
                <option value="plan">Plan d’abonnement</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pu-cible" required>{cibleType === 'addon' ? 'Add-on' : 'Plan'}</Label>
              <select
                id="pu-cible"
                value={cibleId}
                onChange={(e) => setCibleId(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">Choisir…</option>
                {(cibleType === 'addon' ? addons : plans).map((x) => (
                  <option key={x.id} value={x.id}>{x.nom}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pu-min">Seuil min</Label>
              <Input id="pu-min" type="number" step="any" value={seuilMin} onChange={(e) => setSeuilMin(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pu-max">Seuil max</Label>
              <Input id="pu-max" type="number" step="any" value={seuilMax} onChange={(e) => setSeuilMax(e.target.value)} placeholder="Vide = infini" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pu-prix">Prix unitaire de la tranche</Label>
              <Input id="pu-prix" type="number" step="any" value={prixUnitaire} onChange={(e) => setPrixUnitaire(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="pu-mode">Mode</Label>
              <select
                id="pu-mode"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {MODES_PALIER.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer le palier'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function CompteurDialog({ onClose, onDone }) {
  const [typeCible, setTypeCible] = useState('contrat')
  const [cibleId, setCibleId] = useState('')
  const [codeCompteur, setCodeCompteur] = useState('')
  const [periodeDebut, setPeriodeDebut] = useState('')
  const [periodeFin, setPeriodeFin] = useState('')
  const [quantite, setQuantite] = useState('')
  const [source, setSource] = useState('manuel')
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!cibleId) { setErr('L’identifiant de la cible est requis.'); return }
    if (!codeCompteur.trim()) { setErr('Le code du compteur est requis.'); return }
    if (!periodeDebut || !periodeFin) { setErr('La période (début et fin) est requise.'); return }
    setSaving(true)
    setErr(null)
    const data = {
      type_cible: typeCible, cible_id: Number(cibleId), code_compteur: codeCompteur.trim(),
      periode_debut: periodeDebut, periode_fin: periodeFin,
      quantite: Number(quantite) || 0, source,
    }
    try {
      await api.post('/contrats/compteurs-usage/', data)
      onDone()
    } catch (e2) {
      setErr(errMsg(e2, 'Enregistrement impossible.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle>Nouveau relevé de compteur</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="co-type" required>Type de cible</Label>
              <select
                id="co-type"
                value={typeCible}
                onChange={(e) => setTypeCible(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {TYPES_CIBLE.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="co-cible" required>ID de la cible</Label>
              <Input id="co-cible" type="number" step="1" value={cibleId} onChange={(e) => setCibleId(e.target.value)} placeholder="ex. 12" />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="co-code" required>Code du compteur</Label>
            <Input id="co-code" value={codeCompteur} onChange={(e) => setCodeCompteur(e.target.value)} placeholder="ex. interventions" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="co-debut" required>Début de période</Label>
              <Input id="co-debut" type="date" value={periodeDebut} onChange={(e) => setPeriodeDebut(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="co-fin" required>Fin de période</Label>
              <Input id="co-fin" type="date" value={periodeFin} onChange={(e) => setPeriodeFin(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="co-qte">Quantité</Label>
              <Input id="co-qte" type="number" step="any" value={quantite} onChange={(e) => setQuantite(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="co-source">Source</Label>
              <select
                id="co-source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                {SOURCES_COMPTEUR.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>
          {err && <p className="text-sm text-destructive" role="alert">{err}</p>}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
            <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer le relevé'}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

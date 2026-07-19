import { useEffect, useState } from 'react'
import { Shield, Plus, Trash2, Network, Smartphone, Activity, KeyRound, ServerCog, FileText } from 'lucide-react'
import identityApi from '../../api/identityApi'
import parametresApi from '../../api/parametresApi'
import {
  Card, CardContent, CardHeader, CardTitle, Button, Input, Textarea, Label,
  Badge, Spinner, EmptyState, toast,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'

/* ============================================================================
   WIR134 — Écran d'administration « Sécurité & Identité » (apps/identity).
   ----------------------------------------------------------------------------
   Surface le backend jusqu'ici sans aucun consommateur (gouverné IsAdminRole) :
   politique réseau + règles IP/CIDR (NTSEC11), appareils de confiance (NTSEC14),
   posture de sécurité (NTSEC27), break-glass (NTSEC22), comptes de service
   (NTSEC24), bannière légale de connexion + seuil de verrouillage (NTSEC28/FG22).
   Company forcée côté serveur partout.
   ========================================================================== */

const asList = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

// ── Réseau : politique + règles IP/CIDR ──────────────────────────────────────
function ReseauTab() {
  const [policy, setPolicy] = useState(null)
  const [rules, setRules] = useState([])
  const [cidr, setCidr] = useState('')
  const [label, setLabel] = useState('')
  const [loading, setLoading] = useState(true)

  const load = () => Promise.all([
    identityApi.networkPolicies.list(),
    identityApi.ipRules.list(),
  ]).then(([p, r]) => {
    setPolicy(asList(p.data)[0] ?? null)
    setRules(asList(r.data))
  }).catch(() => {}).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const ensurePolicy = async () => {
    if (policy) return policy
    const r = await identityApi.networkPolicies.create({ mode: 'allowlist', applies_to: 'all' })
    setPolicy(r.data)
    return r.data
  }
  const addRule = async () => {
    if (!cidr.trim()) { toast.error('Plage CIDR requise (ex. 10.0.0.0/8).'); return }
    try {
      const p = await ensurePolicy()
      await identityApi.ipRules.create({ policy: p.id, cidr: cidr.trim(), label })
      setCidr(''); setLabel(''); load()
    } catch (e) { toast.error(e?.response?.data?.cidr ?? e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const removeRule = async (r) => {
    try { await identityApi.ipRules.remove(r.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }

  if (loading) return <Spinner />
  return (
    <Card>
      <CardHeader><CardTitle>Politique réseau (allowlist IP/CIDR)</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Restreint l'accès aux plages d'adresses IP autorisées. Sans règle, aucun
          filtrage n'est appliqué (comportement historique).
        </p>
        <div className="flex flex-col gap-2" data-testid="ip-rules">
          {rules.length === 0 && <EmptyState title="Aucune règle IP" className="py-4" />}
          {rules.map((r) => (
            <div key={r.id} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
              <code className="font-medium">{r.cidr}</code>
              <span className="text-muted-foreground">{r.label}</span>
              <Button size="sm" variant="ghost" className="ml-auto"
                onClick={() => removeRule(r)} aria-label="Supprimer la règle">
                <Trash2 size={14} />
              </Button>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-end gap-2 pt-1">
          <Input placeholder="10.0.0.0/8" value={cidr} aria-label="Plage CIDR"
            onChange={(e) => setCidr(e.target.value)} className="max-w-[200px]" />
          <Input placeholder="Libellé (bureau…)" value={label} aria-label="Libellé"
            onChange={(e) => setLabel(e.target.value)} className="max-w-[200px]" />
          <Button onClick={addRule}><Plus size={16} /> Ajouter une règle IP</Button>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Appareils de confiance ────────────────────────────────────────────────────
function AppareilsTab() {
  const [devices, setDevices] = useState([])
  const [loading, setLoading] = useState(true)
  const load = () => identityApi.trustedDevices.list()
    .then((r) => setDevices(asList(r.data))).catch(() => {}).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const forget = async (d) => {
    try { await identityApi.trustedDevices.forget(d.id); toast.success('Appareil oublié — MFA reforcée.'); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Action impossible.') }
  }
  if (loading) return <Spinner />
  return (
    <Card>
      <CardHeader><CardTitle>Appareils de confiance</CardTitle></CardHeader>
      <CardContent className="space-y-2" data-testid="devices">
        {devices.length === 0 && <EmptyState title="Aucun appareil de confiance" className="py-4" />}
        {devices.map((d) => (
          <div key={d.id} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
            <Smartphone size={15} className="text-muted-foreground" />
            <span className="font-medium">{d.label || 'Appareil'}</span>
            {d.is_active && <Badge tone="success">Actif</Badge>}
            <Button size="sm" variant="ghost" className="ml-auto"
              onClick={() => forget(d)}>Oublier cet appareil</Button>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

// ── Posture de sécurité ───────────────────────────────────────────────────────
function PostureTab() {
  const [posture, setPosture] = useState(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    identityApi.posture().then((r) => setPosture(r.data)).catch(() => {})
      .finally(() => setLoading(false))
  }, [])
  if (loading) return <Spinner />
  if (!posture) return <EmptyState title="Posture indisponible" />
  const faibles = posture.items_faibles ?? []
  return (
    <Card>
      <CardHeader><CardTitle>Posture de sécurité</CardTitle></CardHeader>
      <CardContent className="space-y-3" data-testid="posture">
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-semibold">{posture.score ?? '—'}</span>
          <span className="text-muted-foreground">/ 100</span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <div>Couverture MFA : <strong>{posture.mfa_pct ?? 0}%</strong></div>
          <div>SSO : <strong>{posture.sso ? 'configuré' : 'non configuré'}</strong></div>
          <div>Comptes dormants : <strong>{posture.dormant ?? 0}</strong></div>
          <div>Violations SoD ouvertes : <strong>{posture.sod_open ?? 0}</strong></div>
        </div>
        {faibles.length > 0 && (
          <div>
            <div className="mb-1 text-sm font-medium">À corriger</div>
            <ul className="list-disc pl-5 text-sm text-muted-foreground">
              {faibles.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ── Break-glass ───────────────────────────────────────────────────────────────
function BreakGlassTab() {
  const [grants, setGrants] = useState([])
  const [userId, setUserId] = useState('')
  const [motif, setMotif] = useState('')
  const [duree, setDuree] = useState('60')
  const [loading, setLoading] = useState(true)
  const load = () => identityApi.breakGlass.list()
    .then((r) => setGrants(asList(r.data))).catch(() => {}).finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  const grant = async () => {
    if (!userId || !motif.trim()) { toast.error('Utilisateur et motif requis.'); return }
    try {
      await identityApi.breakGlass.grant({ user_id: userId, motif: motif.trim(), duree_minutes: Number(duree) || 60 })
      setUserId(''); setMotif(''); load()
      toast.success('Accès break-glass accordé.')
    } catch (e) { toast.error(e?.response?.data?.detail ?? e?.response?.data?.motif ?? 'Octroi impossible.') }
  }
  if (loading) return <Spinner />
  return (
    <Card>
      <CardHeader><CardTitle>Accès break-glass</CardTitle></CardHeader>
      <CardContent className="space-y-3" data-testid="break-glass">
        <p className="text-sm text-muted-foreground">
          Élévation temporaire d'un compte (urgence). Une MFA active du Directeur
          est exigée côté serveur ; chaque octroi est tracé.
        </p>
        <div className="flex flex-col gap-2">
          {grants.length === 0 && <EmptyState title="Aucun octroi" className="py-4" />}
          {grants.map((g) => (
            <div key={g.id} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
              <span>Compte #{g.user}</span>
              <span className="text-muted-foreground">{g.motif}</span>
              <Badge tone={g.actif ? 'warning' : 'neutral'} className="ml-auto">
                {g.actif ? 'Actif' : 'Expiré'}
              </Badge>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-end gap-2 pt-1">
          <Input placeholder="ID utilisateur" value={userId} aria-label="ID utilisateur cible"
            onChange={(e) => setUserId(e.target.value)} className="max-w-[130px]" />
          <Input placeholder="Motif" value={motif} aria-label="Motif"
            onChange={(e) => setMotif(e.target.value)} className="max-w-[220px]" />
          <Input placeholder="Durée (min)" value={duree} aria-label="Durée minutes"
            onChange={(e) => setDuree(e.target.value)} className="max-w-[110px]" />
          <Button onClick={grant}>Octroyer</Button>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Comptes de service ────────────────────────────────────────────────────────
function ServiceAccountsTab() {
  const [accounts, setAccounts] = useState([])
  const [nom, setNom] = useState('')
  const [loading, setLoading] = useState(true)
  const load = () => identityApi.serviceAccounts.list()
    .then((r) => setAccounts(asList(r.data))).catch(() => {}).finally(() => setLoading(false))
  useEffect(() => { load() }, [])
  const create = async () => {
    if (!nom.trim()) { toast.error('Nom requis.'); return }
    try { await identityApi.serviceAccounts.create({ nom: nom.trim() }); setNom(''); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Création impossible.') }
  }
  const remove = async (a) => {
    try { await identityApi.serviceAccounts.remove(a.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }
  if (loading) return <Spinner />
  return (
    <Card>
      <CardHeader><CardTitle>Comptes de service</CardTitle></CardHeader>
      <CardContent className="space-y-2" data-testid="service-accounts">
        {accounts.length === 0 && <EmptyState title="Aucun compte de service" className="py-4" />}
        {accounts.map((a) => (
          <div key={a.id} className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
            <ServerCog size={15} className="text-muted-foreground" />
            <span className="font-medium">{a.nom || a.name || `#${a.id}`}</span>
            <Button size="sm" variant="ghost" className="ml-auto"
              onClick={() => remove(a)} aria-label="Supprimer le compte de service">
              <Trash2 size={14} />
            </Button>
          </div>
        ))}
        <div className="flex items-end gap-2 pt-1">
          <Input placeholder="Nom du compte de service" value={nom} aria-label="Nom du compte de service"
            onChange={(e) => setNom(e.target.value)} className="max-w-[260px]" />
          <Button onClick={create}><Plus size={16} /> Créer</Button>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Bannière légale + seuil de verrouillage ──────────────────────────────────
function BanniereTab() {
  const [banner, setBanner] = useState('')
  const [lockout, setLockout] = useState('')
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    parametresApi.getProfile()
      .then((r) => {
        setBanner(r.data?.login_banner_text ?? '')
        setLockout(String(r.data?.lockout_max_attempts ?? ''))
      })
      .catch(() => {}).finally(() => setLoading(false))
  }, [])
  const save = async () => {
    try {
      await parametresApi.updateProfile({
        login_banner_text: banner,
        lockout_max_attempts: Number(lockout) || 0,
      })
      toast.success('Enregistré.')
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Enregistrement impossible.') }
  }
  if (loading) return <Spinner />
  return (
    <Card>
      <CardHeader><CardTitle>Bannière de connexion & verrouillage</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div>
          <Label htmlFor="banner">Mention légale affichée à la connexion</Label>
          <Textarea id="banner" value={banner} rows={4}
            onChange={(e) => setBanner(e.target.value)}
            placeholder="Accès réservé au personnel autorisé…" />
          <p className="mt-1 text-xs text-muted-foreground">
            Vide = aucun bandeau (écran de connexion inchangé).
          </p>
        </div>
        <div className="max-w-[220px]">
          <Label htmlFor="lockout">Seuil de verrouillage (tentatives)</Label>
          <Input id="lockout" value={lockout} type="number"
            onChange={(e) => setLockout(e.target.value)} placeholder="0 = désactivé" />
        </div>
        <Button onClick={save}>Enregistrer</Button>
      </CardContent>
    </Card>
  )
}

export default function SecuriteIdentitePage() {
  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center gap-2">
        <Shield className="text-primary" aria-hidden="true" />
        <h1 className="text-lg font-semibold">Sécurité & Identité</h1>
      </div>
      <Tabs defaultValue="reseau">
        <TabsList className="flex-wrap">
          <TabsTrigger value="reseau"><Network size={14} /> Réseau</TabsTrigger>
          <TabsTrigger value="appareils"><Smartphone size={14} /> Appareils</TabsTrigger>
          <TabsTrigger value="posture"><Activity size={14} /> Posture</TabsTrigger>
          <TabsTrigger value="breakglass"><KeyRound size={14} /> Break-glass</TabsTrigger>
          <TabsTrigger value="comptes"><ServerCog size={14} /> Comptes de service</TabsTrigger>
          <TabsTrigger value="banniere"><FileText size={14} /> Bannière</TabsTrigger>
        </TabsList>
        <TabsContent value="reseau"><ReseauTab /></TabsContent>
        <TabsContent value="appareils"><AppareilsTab /></TabsContent>
        <TabsContent value="posture"><PostureTab /></TabsContent>
        <TabsContent value="breakglass"><BreakGlassTab /></TabsContent>
        <TabsContent value="comptes"><ServiceAccountsTab /></TabsContent>
        <TabsContent value="banniere"><BanniereTab /></TabsContent>
      </Tabs>
    </div>
  )
}

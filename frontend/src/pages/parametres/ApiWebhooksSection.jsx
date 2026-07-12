// Onglet « API & Webhooks » de la page Paramètres (N89) — section AUTONOME.
// Permet de créer/révoquer des clés d'API publiques (la clé en clair n'est
// montrée qu'UNE fois, à la création) et de gérer des webhooks sortants signés
// (le secret n'est lui aussi montré qu'une fois). Aucun secret n'est jamais
// re-affiché après coup : on régénère ou on supprime.
import { useEffect, useState } from 'react'
import {
  KeyRound, Webhook as WebhookIcon, Plus, Trash2, Copy, Check, Ban, BookOpen,
} from 'lucide-react'
import publicapiApi from '../../api/publicapiApi'
import {
  Card, CardContent, Button, Input, Spinner, Badge, Switch, Checkbox, toast,
} from '../../ui'
import { ConfirmDialog } from '../../ui/ConfirmDialog'
import { SectionTitle } from './peComponents'

// Bloc « copier une fois » : affiche un secret généré avec un bouton copier.
function RevealOnce({ label, value, onDismiss }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      toast.success('Copié.')
    } catch {
      toast.error('Copie impossible — copiez la valeur manuellement.')
    }
    setTimeout(() => setCopied(false), 1800)
  }
  return (
    <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3">
      <p className="mb-1 text-xs font-medium text-warning-foreground">
        {label} — copiez-le maintenant, il ne sera plus affiché.
      </p>
      <div className="flex items-center gap-2">
        <code className="flex-1 break-all rounded bg-background px-2 py-1 text-xs">{value}</code>
        <Button type="button" size="sm" variant="outline" onClick={copy}>
          {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDismiss}>OK</Button>
      </div>
    </div>
  )
}

// FG105 — Référence de l'API publique (endpoints, auth, scopes, évènements,
// recette HMAC). Chargée à la demande depuis /publicapi/docs/ (page statique
// servie par le backend, sans dépendance d'auto-génération).
function DocsReference() {
  const [open, setOpen] = useState(false)
  const [doc, setDoc] = useState(null)
  const [error, setError] = useState(false)

  const toggle = () => {
    const next = !open
    setOpen(next)
    if (next && !doc) {
      publicapiApi.getDocs()
        .then(r => setDoc(r.data))
        .catch(() => setError(true))
    }
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <div className="flex items-center justify-between gap-2">
          <SectionTitle icon={<BookOpen className="size-4" />} label="Référence de l'API" />
          <Button type="button" size="sm" variant="outline" onClick={toggle}>
            {open ? 'Masquer' : 'Voir la référence'}
          </Button>
        </div>
        <p className="mb-3 text-sm text-muted-foreground">
          Documentation des endpoints en lecture seule, de l'authentification par
          clé (<code>Authorization: Api-Key …</code>), des scopes, des évènements
          webhook et de la vérification de signature HMAC.
        </p>

        {open && error && (
          <p className="text-sm text-destructive">
            Référence indisponible pour le moment.
          </p>
        )}
        {open && !doc && !error && (
          <p className="text-sm text-muted-foreground">
            <Spinner /> Chargement de la référence…
          </p>
        )}
        {open && doc && (
          <div className="flex flex-col gap-4 text-sm">
            <p className="text-muted-foreground">{doc.introduction}</p>

            <div>
              <p className="font-medium">Authentification</p>
              <p className="text-muted-foreground">{doc.authentification?.methode}</p>
              <code className="mt-1 block break-all rounded bg-background px-2 py-1 text-xs">
                {doc.authentification?.entete}
              </code>
              <p className="mt-1 text-xs text-muted-foreground">
                {doc.authentification?.note_societe}
              </p>
            </div>

            <div>
              <p className="font-medium">Endpoints (lecture seule)</p>
              <div className="mt-1 flex flex-col gap-2">
                {(doc.endpoints || []).map(ep => (
                  <div key={ep.chemin} className="rounded-lg border border-border p-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <code className="text-xs">GET {ep.chemin}</code>
                      <Badge variant="secondary">{ep.scope}</Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{ep.description}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Filtres : {(ep.filtres || []).join(', ') || '—'} · Tri :{' '}
                      {(ep.tri || []).join(', ') || '—'} ·{' '}
                      <code>?updated_since={ep.updated_since}</code>
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <p className="font-medium">Synchro incrémentale &amp; filtres</p>
              <p className="text-xs text-muted-foreground">
                {doc.parametres_communs?.synchro_incrementale}
              </p>
              <p className="text-xs text-muted-foreground">
                {doc.parametres_communs?.filtres}
              </p>
            </div>

            <div>
              <p className="font-medium">Évènements webhook</p>
              <p className="text-xs text-muted-foreground">{doc.webhooks?.description}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Entêtes : <code>{doc.webhooks?.entetes?.signature}</code> ·{' '}
                <code>{doc.webhooks?.entetes?.evenement}</code>
              </p>
              <ul className="mt-1 list-inside list-disc text-xs text-muted-foreground">
                {(doc.webhooks?.evenements || []).map(ev => (
                  <li key={ev.code}><code>{ev.code}</code> — {ev.libelle}</li>
                ))}
              </ul>
            </div>

            <div>
              <p className="font-medium">Vérification de la signature HMAC</p>
              <p className="text-xs text-muted-foreground">
                {doc.webhooks?.verification_signature?.algorithme}
              </p>
              <pre className="mt-1 overflow-x-auto rounded bg-background px-2 py-1 text-xs">
                <code>{doc.webhooks?.verification_signature?.exemple_python}</code>
              </pre>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function ApiWebhooksSection() {
  const [loading, setLoading] = useState(true)
  const [catalogue, setCatalogue] = useState({ scopes: [], events: [] })
  const [keys, setKeys] = useState([])
  const [webhooks, setWebhooks] = useState([])

  // Formulaire de création de clé.
  const [newKeyLabel, setNewKeyLabel] = useState('')
  const [newKeyScopes, setNewKeyScopes] = useState([])
  const [revealedKey, setRevealedKey] = useState(null)

  // Formulaire de création de webhook.
  const [newHookUrl, setNewHookUrl] = useState('')
  const [newHookLabel, setNewHookLabel] = useState('')
  const [newHookEvents, setNewHookEvents] = useState([])
  const [revealedSecret, setRevealedSecret] = useState(null)

  // VX244 — un secret webhook / une clé d'API a le plus fort blast-radius du
  // module (intégrations tierces cassées, secret régénéré = tout client déjà
  // branché doit être mis à jour) : confirmation à SÉVÉRITÉ au lieu d'un
  // `window.confirm` unique pour tout. `pendingAction` pilote UN dialog
  // partagé pour les 4 actions destructives de cet écran.
  const [pendingAction, setPendingAction] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)

  const runPendingAction = async () => {
    if (!pendingAction) return
    setActionLoading(true)
    try {
      await pendingAction.run()
    } finally {
      setActionLoading(false)
      setPendingAction(null)
    }
  }

  const loadAll = () => {
    Promise.all([
      publicapiApi.getKeys().then(r => setKeys(r.data.results ?? r.data)).catch(() => {}),
      publicapiApi.getWebhooks().then(r => setWebhooks(r.data.results ?? r.data)).catch(() => {}),
    ]).finally(() => setLoading(false))
  }

  useEffect(() => {
    publicapiApi.getCatalogue()
      .then(r => setCatalogue(r.data))
      .catch(() => setCatalogue({ scopes: [], events: [] }))
    loadAll()
  }, [])

  const toggle = (list, setList, code) =>
    setList(list.includes(code) ? list.filter(c => c !== code) : [...list, code])

  const createKey = async () => {
    if (!newKeyLabel.trim()) return
    try {
      const r = await publicapiApi.createKey({
        label: newKeyLabel.trim(), scopes: newKeyScopes })
      setRevealedKey(r.data.key)
      setNewKeyLabel(''); setNewKeyScopes([])
      loadAll()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Création impossible.') }
  }
  const revokeKey = (k) => setPendingAction({
    severity: 'medium',
    title: `Désactiver la clé « ${k.label} » ?`,
    description: 'La clé cessera immédiatement de fonctionner pour tout système externe qui l’utilise. Réversible (réactivable ensuite).',
    confirmLabel: 'Désactiver',
    run: async () => { try { await publicapiApi.revokeKey(k.id); loadAll() } catch { /* */ } },
  })
  const deleteKey = (k) => setPendingAction({
    severity: 'high',
    title: 'Suppression définitive de la clé',
    description: `La clé « ${k.label} » sera supprimée définitivement. Tout système externe qui l’utilise cessera de fonctionner.`,
    confirmText: k.label,
    confirmLabel: 'Supprimer définitivement',
    run: async () => { try { await publicapiApi.deleteKey(k.id); loadAll() } catch { /* */ } },
  })

  const createWebhook = async () => {
    if (!newHookUrl.trim()) return
    try {
      const r = await publicapiApi.createWebhook({
        target_url: newHookUrl.trim(), label: newHookLabel.trim(),
        events: newHookEvents })
      setRevealedSecret(r.data.secret)
      setNewHookUrl(''); setNewHookLabel(''); setNewHookEvents([])
      loadAll()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Création impossible.') }
  }
  const toggleWebhook = async (h) => {
    try { await publicapiApi.updateWebhook(h.id, { enabled: !h.enabled }); loadAll() }
    catch { /* */ }
  }
  const rotateSecret = (h) => setPendingAction({
    severity: 'high',
    title: 'Régénérer le secret webhook',
    description: `Toute intégration déjà branchée sur « ${h.label || h.target_url} » cessera de valider les signatures tant qu'elle n'aura pas repris le nouveau secret.`,
    confirmText: 'REGENERER',
    confirmLabel: 'Régénérer le secret',
    run: async () => {
      try { const r = await publicapiApi.rotateWebhookSecret(h.id); setRevealedSecret(r.data.secret) }
      catch { /* */ }
    },
  })
  const deleteWebhook = (h) => setPendingAction({
    severity: 'high',
    title: 'Supprimer ce webhook',
    description: `« ${h.label || h.target_url} » sera définitivement supprimé — les notifications sortantes vers cette URL cesseront.`,
    confirmText: 'SUPPRIMER',
    confirmLabel: 'Supprimer',
    run: async () => { try { await publicapiApi.deleteWebhook(h.id); loadAll() } catch { /* */ } },
  })

  if (loading) {
    return (
      <Card><CardContent className="pt-4 sm:pt-5">
        <Spinner /> <span className="text-xs text-muted-foreground">Chargement…</span>
      </CardContent></Card>
    )
  }

  return (
    <>
      {/* ── Clés API ── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle icon={<KeyRound className="size-4" />} label="Clés d'API" />
          <p className="mb-3 text-sm text-muted-foreground">
            Les clés permettent à un système externe de lire vos données via l'API
            publique (<code>/api/public/</code>). Chaque clé est limitée aux droits
            cochés. La clé complète n'est affichée qu'à la création.
          </p>

          {/* Création */}
          <div className="rounded-lg border border-border p-3">
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                placeholder="Libellé (ex. Intégration comptabilité)"
                value={newKeyLabel}
                onChange={e => setNewKeyLabel(e.target.value)} />
              <Button type="button" onClick={createKey} disabled={!newKeyLabel.trim()}>
                <Plus className="size-4" /> Créer la clé
              </Button>
            </div>
            <div className="mt-2 flex flex-wrap gap-3">
              {catalogue.scopes.map(s => (
                <label key={s.code} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={newKeyScopes.includes(s.code)}
                    onCheckedChange={() => toggle(newKeyScopes, setNewKeyScopes, s.code)} />
                  {s.label}
                </label>
              ))}
            </div>
            {revealedKey && (
              <RevealOnce label="Votre nouvelle clé API" value={revealedKey}
                onDismiss={() => setRevealedKey(null)} />
            )}
          </div>

          {/* Liste */}
          <div className="mt-3 flex flex-col gap-2">
            {keys.length === 0 && (
              <p className="text-sm text-muted-foreground">Aucune clé pour l'instant.</p>
            )}
            {keys.map(k => (
              <div key={k.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{k.label}</span>
                    {!k.enabled && <Badge variant="secondary">Révoquée</Badge>}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    <code>{k.prefix}…</code> · {(k.scopes || []).join(', ') || 'aucun droit'}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {k.enabled && (
                    <Button type="button" size="sm" variant="ghost" onClick={() => revokeKey(k)}>
                      <Ban className="size-4" /> Révoquer
                    </Button>
                  )}
                  <Button type="button" size="sm" variant="ghost" onClick={() => deleteKey(k)}>
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ── Webhooks ── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle icon={<WebhookIcon className="size-4" />} label="Webhooks" />
          <p className="mb-3 text-sm text-muted-foreground">
            Recevez une notification HTTP signée (HMAC-SHA256) sur vos évènements
            métier. Le secret de signature n'est affiché qu'à la création.
          </p>

          {/* Création */}
          <div className="rounded-lg border border-border p-3">
            <div className="flex flex-col gap-2">
              <Input
                placeholder="URL cible (https://…)"
                value={newHookUrl}
                onChange={e => setNewHookUrl(e.target.value)} />
              <Input
                placeholder="Libellé (optionnel)"
                value={newHookLabel}
                onChange={e => setNewHookLabel(e.target.value)} />
            </div>
            <div className="mt-2 flex flex-wrap gap-3">
              {catalogue.events.map(ev => (
                <label key={ev.code} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={newHookEvents.includes(ev.code)}
                    onCheckedChange={() => toggle(newHookEvents, setNewHookEvents, ev.code)} />
                  {ev.label}
                </label>
              ))}
            </div>
            <div className="mt-2">
              <Button type="button" onClick={createWebhook} disabled={!newHookUrl.trim()}>
                <Plus className="size-4" /> Ajouter le webhook
              </Button>
            </div>
            {revealedSecret && (
              <RevealOnce label="Secret de signature du webhook" value={revealedSecret}
                onDismiss={() => setRevealedSecret(null)} />
            )}
          </div>

          {/* Liste */}
          <div className="mt-3 flex flex-col gap-2">
            {webhooks.length === 0 && (
              <p className="text-sm text-muted-foreground">Aucun webhook pour l'instant.</p>
            )}
            {webhooks.map(h => (
              <div key={h.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2">
                <div className="min-w-0">
                  <div className="font-medium">{h.label || h.target_url}</div>
                  <div className="break-all text-xs text-muted-foreground">
                    {h.target_url} · {(h.events || []).join(', ') || 'aucun évènement'}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Switch checked={h.enabled} onCheckedChange={() => toggleWebhook(h)} />
                  <Button type="button" size="sm" variant="ghost" onClick={() => rotateSecret(h)}>
                    Régénérer le secret
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => deleteWebhook(h)}>
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ── Référence de l'API (FG105) ── */}
      <DocsReference />

      <ConfirmDialog
        open={!!pendingAction}
        onOpenChange={(o) => { if (!o) setPendingAction(null) }}
        severity={pendingAction?.severity || 'medium'}
        title={pendingAction?.title || ''}
        description={pendingAction?.description}
        confirmText={pendingAction?.confirmText}
        confirmLabel={pendingAction?.confirmLabel}
        loading={actionLoading}
        onConfirm={runPendingAction}
      />
    </>
  )
}

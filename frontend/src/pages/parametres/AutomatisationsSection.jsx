// N72 / N73 / FG3 — Onglet « Automatisations » de la page Paramètres.
//
// Moteur sans code « si ceci → alors cela » sur les ÉVÉNEMENTS PROPRES de l'app
// (changement d'étape lead, devis accepté, statut chantier, facture en retard,
// stock sous seuil…). Chaque règle est éditable, activable/désactivable, et
// chaque exécution est journalisée. Une règle peut exiger une APPROBATION
// propriétaire avant de lancer son action (N73) ; les approbations en attente
// sont listées et décidées ici.
//
// Section autonome : charge ses propres données et s'enregistre seule (sans le
// bouton « Enregistrer » global). Texte en français ; clés techniques en anglais.
import { useEffect, useState } from 'react'
import { Plus, Trash2, RefreshCw, Wand2, Sparkles } from 'lucide-react'
import { toast } from '../../ui/confirm'
import automationApi from '../../api/automationApi'
import { formatDateTime } from '../../lib/format'
import {
  Card, CardContent, Input, Textarea, Button, IconButton, Badge, Spinner,
  EmptyState, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle } from './peComponents'

// Déclencheurs (événements internes) — libellés FR, clés EN alignées sur le
// backend (apps.automation.models.TriggerType).
const TRIGGERS = [
  { key: 'lead_stage_change', label: "Changement d'étape d'un lead" },
  { key: 'devis_accepted', label: 'Devis accepté' },
  { key: 'chantier_status', label: 'Chantier atteint un statut' },
  { key: 'facture_overdue', label: 'Facture en retard' },
  { key: 'warranty_expiring', label: 'Garantie proche expiration' },
  { key: 'maintenance_due', label: 'Visite de maintenance due' },
  { key: 'stock_below_threshold', label: 'Stock sous le seuil' },
  // WIR61 — les 5 déclencheurs backend jusqu'ici invisibles côté UI.
  { key: 'date_echeance_champ', label: 'Échéance de champ (± N jours)' },
  { key: 'webhook_inbound', label: 'Webhook entrant' },
  { key: 'record_state_change', label: "Changement d'état d'un enregistrement" },
  { key: 'projet_status_change', label: 'Changement de statut de projet' },
  { key: 'projet_phase_change', label: 'Changement de phase de projet' },
]

// Actions — clés EN alignées sur ActionType.
const ACTIONS = [
  { key: 'send_whatsapp', label: 'Envoyer un WhatsApp' },
  { key: 'send_email', label: 'Envoyer un email' },
  { key: 'send_sms', label: 'Envoyer un SMS' },
  { key: 'create_activity', label: 'Créer une activité / tâche' },
  { key: 'assign_record', label: 'Assigner un enregistrement' },
  { key: 'set_field', label: 'Mettre à jour un champ' },
  { key: 'create_sav_ticket', label: 'Créer un ticket SAV' },
]

const triggerLabel = (k) => TRIGGERS.find((t) => t.key === k)?.label ?? k
const actionLabel = (k) => ACTIONS.find((a) => a.key === k)?.label ?? k

const RUN_TONE = {
  success: 'success', noop: 'info', skipped: 'neutral',
  pending_approval: 'warning', failed: 'danger',
}

function safeParse(text) {
  const t = (text || '').trim()
  if (!t) return {}
  try { return JSON.parse(t) } catch { return null }
}

// FG3 — formatte la config JSON pour affichage dans le textarea.
function toJson(obj) {
  if (!obj || !Object.keys(obj).length) return ''
  try { return JSON.stringify(obj, null, 2) } catch { return '' }
}

// WIR61 / XPLT4 — Panneau des webhooks entrants tokenisés. Chaque webhook est
// attaché à UNE règle de type `webhook_inbound` : le POST externe reçu sur son
// URL tokenisée devient le contexte des conditions/actions. Le token/URL sont
// générés côté serveur ; la rotation invalide immédiatement l'ancien token.
function IncomingWebhookPanel({ rules }) {
  const [hooks, setHooks] = useState([])
  const [ruleId, setRuleId] = useState('')
  const [secret, setSecret] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => automationApi.getWebhooks()
    .then((r) => setHooks(r.data.results ?? r.data)).catch(() => {})
  useEffect(() => { load() }, [])

  // Seules les règles de type `webhook_inbound` peuvent porter un webhook.
  const webhookRules = rules.filter((r) => r.trigger_type === 'webhook_inbound')

  const create = async () => {
    if (!ruleId) { toast.error('Choisissez une règle « Webhook entrant ».'); return }
    setBusy(true)
    try {
      await automationApi.createWebhook({ rule: ruleId, hmac_secret: secret })
      setRuleId(''); setSecret(''); load()
      toast.success('Webhook créé.')
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Création impossible.') }
    finally { setBusy(false) }
  }
  const rotate = async (h) => {
    try { await automationApi.rotateWebhook(h.id); load(); toast.success('Token régénéré.') }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Rotation impossible.') }
  }
  const toggle = async (h) => {
    try { await automationApi.updateWebhook(h.id, { enabled: !h.enabled }); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Modification impossible.') }
  }
  const remove = async (h) => {
    if (!window.confirm('Supprimer ce webhook ? Son URL cessera de fonctionner.')) return
    try { await automationApi.deleteWebhook(h.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5" data-testid="webhook-panel">
        <SectionTitle label="Webhooks entrants"
          icon={<><path d="M18 16.98h-5.99c-1.66 0-3.01-1.34-3.01-3s1.34-3 3.01-3H18"/><path d="m21 12-3-3v6z"/><circle cx="6" cy="18" r="3"/></>}/>
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Attachez une URL tokenisée à une règle « Webhook entrant » : un POST
          externe reçu sur cette URL déclenche la règle. Ajoutez un secret HMAC
          pour exiger une signature. La rotation invalide immédiatement l'ancien
          token.
        </p>

        {webhookRules.length === 0 ? (
          <EmptyState title="Aucune règle « Webhook entrant »"
            description="Créez d'abord une règle dont le déclencheur est « Webhook entrant »." className="py-6" />
        ) : (
          <div className="mb-3 flex flex-wrap items-end gap-2">
            <div className="min-w-[200px] flex-1">
              <Select value={ruleId} onValueChange={setRuleId}>
                <SelectTrigger aria-label="Règle webhook"><SelectValue placeholder="Règle « Webhook entrant »" /></SelectTrigger>
                <SelectContent>
                  {webhookRules.map((r) => (
                    <SelectItem key={r.id} value={String(r.id)}>{r.nom}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Input placeholder="Secret HMAC (optionnel)" value={secret}
              onChange={(e) => setSecret(e.target.value)} className="max-w-[220px]" />
            <Button onClick={create} disabled={busy}><Plus size={16} /> Générer l'URL</Button>
          </div>
        )}

        <div className="flex flex-col gap-2">
          {hooks.map((h) => (
            <div key={h.id} className="rounded-lg border border-border p-3 text-xs">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-medium">{h.rule_nom ?? `Règle #${h.rule}`}</span>
                <Badge tone={h.enabled ? 'success' : 'neutral'}>
                  {h.enabled ? 'Actif' : 'Inactif'}
                </Badge>
                <code className="ml-auto break-all rounded bg-muted px-1.5 py-0.5">{h.url_path}</code>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Button size="sm" variant="ghost" onClick={() => rotate(h)}>
                  <RefreshCw size={14} /> Rotation du token
                </Button>
                <Button size="sm" variant="ghost" onClick={() => toggle(h)}>
                  {h.enabled ? 'Désactiver' : 'Activer'}
                </Button>
                <IconButton size="sm" variant="ghost" label="Supprimer"
                  onClick={() => remove(h)}>
                  <Trash2 className="size-4" aria-hidden="true" />
                </IconButton>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export default function AutomatisationsSection() {
  const [rules, setRules] = useState([])
  const [runs, setRuns] = useState([])
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading] = useState(true)
  // FG3 — modèles prédéfinis.
  const [templates, setTemplates] = useState([])
  const [showTemplates, setShowTemplates] = useState(false)
  // XPLT18 — génération de règle par l'IA (propose→confirme). Le brouillon
  // proposé crée TOUJOURS une règle désactivée : la confirmation se fait en
  // l'activant depuis la liste ci-dessus, comme toute règle manuelle.
  const [showAiDraft, setShowAiDraft] = useState(false)
  const [aiDraft, setAiDraft] = useState({
    nom: '', trigger_type: 'lead_stage_change', trigger_config: '',
    action_type: 'create_activity', action_config: '',
  })
  const [aiDraftBusy, setAiDraftBusy] = useState(false)
  const [aiDraftError, setAiDraftError] = useState(null)
  const [aiDraftResult, setAiDraftResult] = useState(null)
  // Brouillon de nouvelle règle.
  const [draft, setDraft] = useState({
    nom: '', trigger_type: 'lead_stage_change', trigger_config: '',
    action_type: 'create_activity', action_config: '',
    requires_approval: false, approval_threshold: '',
  })

  const loadRules = () => automationApi.getRules()
    .then((r) => setRules(r.data.results ?? r.data)).catch(() => {})
  const loadRuns = () => automationApi.getRuns({ ordering: '-timestamp' })
    .then((r) => setRuns((r.data.results ?? r.data).slice(0, 30))).catch(() => {})
  const loadApprovals = () => automationApi.getApprovals({ status: 'pending' })
    .then((r) => setApprovals(r.data.results ?? r.data)).catch(() => {})

  useEffect(() => {
    Promise.all([loadRules(), loadRuns(), loadApprovals()])
      .finally(() => setLoading(false))
    // FG3 — charge les modèles au montage (best-effort).
    automationApi.getTemplates()
      .then((r) => setTemplates(Array.isArray(r.data) ? r.data : []))
      .catch(() => {})
  }, [])

  // FG3 — préremplir le formulaire depuis un modèle.
  const applyTemplate = (tpl) => {
    setDraft({
      nom: tpl.nom,
      trigger_type: tpl.trigger_type,
      trigger_config: toJson(tpl.trigger_config),
      action_type: tpl.action_type,
      action_config: toJson(tpl.action_config),
      requires_approval: Boolean(tpl.requires_approval),
      approval_threshold: '',
    })
    setShowTemplates(false)
  }

  // XPLT18 — propose : envoie le brouillon (description + déclencheur/action
  // choisis dans le catalogue fermé) à l'agent, qui crée une règle TOUJOURS
  // désactivée. Rien ne s'exécute avant que l'admin ne l'active ci-dessus.
  const proposeAiDraft = async () => {
    const nom = aiDraft.nom.trim()
    if (!nom) { setAiDraftError('Décrivez la règle souhaitée.'); return }
    const trigCfg = safeParse(aiDraft.trigger_config)
    const actCfg = safeParse(aiDraft.action_config)
    if (trigCfg === null || actCfg === null) {
      setAiDraftError('Configuration JSON invalide (déclencheur ou action).')
      return
    }
    setAiDraftBusy(true); setAiDraftError(null); setAiDraftResult(null)
    try {
      const { data } = await automationApi.proposeDraft({
        nom,
        trigger_type: aiDraft.trigger_type,
        trigger_config: trigCfg,
        action_type: aiDraft.action_type,
        action_config: actCfg,
      })
      setAiDraftResult(data)
      loadRules()
    } catch (e) {
      setAiDraftError(e?.response?.data?.detail ?? 'Génération impossible.')
    } finally { setAiDraftBusy(false) }
  }

  const resetAiDraft = () => {
    setAiDraft({
      nom: '', trigger_type: 'lead_stage_change', trigger_config: '',
      action_type: 'create_activity', action_config: '',
    })
    setAiDraftError(null); setAiDraftResult(null)
  }

  const addRule = async () => {
    const nom = draft.nom.trim()
    if (!nom) return
    const trigCfg = safeParse(draft.trigger_config)
    const actCfg = safeParse(draft.action_config)
    if (trigCfg === null || actCfg === null) {
      toast.error('Configuration JSON invalide (déclencheur ou action).')
      return
    }
    try {
      await automationApi.saveRule(null, {
        nom,
        trigger_type: draft.trigger_type,
        trigger_config: trigCfg,
        action_type: draft.action_type,
        action_config: actCfg,
        requires_approval: draft.requires_approval,
        approval_threshold: draft.approval_threshold === ''
          ? null : Number(draft.approval_threshold),
        ordre: rules.length,
      })
      setDraft({
        nom: '', trigger_type: 'lead_stage_change', trigger_config: '',
        action_type: 'create_activity', action_config: '',
        requires_approval: false, approval_threshold: '',
      })
      loadRules()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }

  const toggle = async (r) => {
    try { await automationApi.toggleRule(r.id); loadRules() } catch { /* */ }
  }
  const delRule = async (r) => {
    if (!window.confirm(`Supprimer la règle « ${r.nom} » ?`)) return
    try { await automationApi.deleteRule(r.id); loadRules() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }

  const decide = async (a, ok) => {
    try {
      if (ok) await automationApi.approve(a.id)
      else await automationApi.reject(a.id)
      loadApprovals(); loadRuns()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Décision impossible.') }
  }

  if (loading) return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )

  return (
    <div className="flex flex-col gap-4">
      {/* ── Règles (N72) ── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Automatisations"
            icon={<><path d="M12 2v4"/><path d="m16.2 7.8 2.9-2.9"/><path d="M18 12h4"/><circle cx="12" cy="12" r="4"/></>}/>
          <p className="mb-3.5 text-[11.5px] text-muted-foreground">
            Composez des règles « si ceci → alors cela » sur les événements de
            votre activité (étape d'un lead, devis accepté, statut de chantier,
            facture en retard, stock sous le seuil…). Chaque règle est
            activable/désactivable et chaque exécution est journalisée. Sans
            règle activée, rien ne change. Les configurations avancées
            (déclencheur / action) acceptent un objet JSON optionnel, par ex.
            {' '}<code>{'{"stage": "SIGNED"}'}</code> ou{' '}
            <code>{'{"field": "priorite", "value": "haute"}'}</code>.
          </p>

          <div className="flex flex-col gap-3">
            {rules.length === 0 && (
              <EmptyState title="Aucune règle"
                description="Ajoutez votre première automatisation ci-dessous." className="py-6" />
            )}
            {rules.map((r) => (
              <div key={r.id} className="rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className={['min-w-[140px] flex-[1_1_140px] font-medium text-sm',
                    r.enabled ? '' : 'opacity-50'].join(' ')}>{r.nom}</span>
                  <Badge tone="info">{triggerLabel(r.trigger_type)}</Badge>
                  <span className="text-muted-foreground text-xs">→</span>
                  <Badge tone="primary">{actionLabel(r.action_type)}</Badge>
                  {r.requires_approval && (
                    <Badge tone="warning">Approbation requise</Badge>
                  )}
                  <div className="ml-auto flex items-center gap-1">
                    <Button type="button" size="sm"
                      variant={r.enabled ? 'success' : 'secondary'}
                      title={r.enabled ? 'Désactiver' : 'Activer'}
                      onClick={() => toggle(r)}>
                      {r.enabled ? 'Activée' : 'Désactivée'}
                    </Button>
                    <IconButton size="sm" variant="outline" label="Supprimer la règle"
                      className="text-destructive hover:text-destructive"
                      onClick={() => delRule(r)}>
                      <Trash2 className="size-4" aria-hidden="true" />
                    </IconButton>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* ── XPLT18 : Générer une règle (IA) — propose→confirme ── */}
          <div className="mt-2">
            <Button type="button" size="sm" variant="outline"
              onClick={() => setShowAiDraft((v) => !v)}>
              <Sparkles className="size-4" aria-hidden="true" />
              Générer une règle (IA)
            </Button>
            {showAiDraft && (
              <div className="mt-2 rounded-lg border border-border bg-muted/30 p-3">
                <p className="mb-2 text-xs text-muted-foreground">
                  Décrivez la règle souhaitée et choisissez son déclencheur/action
                  dans le catalogue existant. La règle proposée est TOUJOURS créée
                  <strong> désactivée</strong> : confirmez-la en l'activant dans la
                  liste ci-dessus, après relecture.
                </p>
                <Input className="w-full" placeholder="Décrivez la règle (ex. « Relancer 2 jours après un devis accepté »)"
                  value={aiDraft.nom}
                  onChange={(e) => setAiDraft((d) => ({ ...d, nom: e.target.value }))} />
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <div className="min-w-[180px] flex-1">
                    <Select value={aiDraft.trigger_type}
                      onValueChange={(v) => setAiDraft((d) => ({ ...d, trigger_type: v }))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {TRIGGERS.map((t) => (
                          <SelectItem key={t.key} value={t.key}>{t.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="min-w-[180px] flex-1">
                    <Select value={aiDraft.action_type}
                      onValueChange={(v) => setAiDraft((d) => ({ ...d, action_type: v }))}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {ACTIONS.map((a) => (
                          <SelectItem key={a.key} value={a.key}>{a.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <Textarea className="min-w-[160px] flex-1 font-mono text-xs" rows={2}
                    placeholder='Config déclencheur (JSON, optionnel)'
                    value={aiDraft.trigger_config}
                    onChange={(e) => setAiDraft((d) => ({ ...d, trigger_config: e.target.value }))} />
                  <Textarea className="min-w-[160px] flex-1 font-mono text-xs" rows={2}
                    placeholder='Config action (JSON, optionnel)'
                    value={aiDraft.action_config}
                    onChange={(e) => setAiDraft((d) => ({ ...d, action_config: e.target.value }))} />
                </div>
                {aiDraftError && (
                  <p className="mt-1.5 text-xs text-destructive">{aiDraftError}</p>
                )}
                {aiDraftResult && (
                  <p className="mt-1.5 text-xs text-success">
                    Brouillon « {aiDraftResult.nom} » créé, désactivé — activez-le
                    dans la liste ci-dessus pour le confirmer.
                  </p>
                )}
                <div className="mt-1.5 flex items-center gap-2">
                  <Button type="button" onClick={proposeAiDraft} disabled={aiDraftBusy}>
                    {aiDraftBusy ? 'Génération…' : 'Proposer le brouillon'}
                  </Button>
                  <Button type="button" variant="outline" onClick={resetAiDraft} disabled={aiDraftBusy}>
                    Réinitialiser
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* ── FG3 : Créer depuis un modèle ── */}
          {templates.length > 0 && (
            <div className="mt-2">
              <Button type="button" size="sm" variant="outline"
                onClick={() => setShowTemplates((v) => !v)}>
                <Wand2 className="size-4" aria-hidden="true" />
                Créer depuis un modèle
              </Button>
              {showTemplates && (
                <div className="mt-2 rounded-lg border border-border bg-muted/30 p-2">
                  <p className="mb-1.5 text-xs text-muted-foreground">
                    Sélectionnez un modèle pour préremplir le formulaire :
                  </p>
                  <div className="flex flex-col gap-1.5">
                    {templates.map((tpl) => (
                      <button key={tpl.id} type="button"
                        className="group flex flex-col items-start rounded-md border border-border bg-background px-3 py-2 text-left hover:border-primary hover:bg-primary/5 transition-colors"
                        onClick={() => applyTemplate(tpl)}>
                        <span className="text-sm font-medium group-hover:text-primary">{tpl.nom}</span>
                        <span className="text-xs text-muted-foreground">{tpl.description}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── Ajout d'une règle ── */}
          <div className="mt-3 rounded-lg border border-dashed border-border p-3">
            <div className="flex flex-wrap gap-1.5">
              <Input className="min-w-[160px] flex-[1_1_160px]" placeholder="Nom de la règle"
                value={draft.nom} onChange={(e) => setDraft((d) => ({ ...d, nom: e.target.value }))} />
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              <div className="min-w-[180px] flex-1">
                <Select value={draft.trigger_type}
                  onValueChange={(v) => setDraft((d) => ({ ...d, trigger_type: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {TRIGGERS.map((t) => (
                      <SelectItem key={t.key} value={t.key}>{t.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="min-w-[180px] flex-1">
                <Select value={draft.action_type}
                  onValueChange={(v) => setDraft((d) => ({ ...d, action_type: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ACTIONS.map((a) => (
                      <SelectItem key={a.key} value={a.key}>{a.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              <Textarea className="min-w-[160px] flex-1 font-mono text-xs" rows={2}
                placeholder='Config déclencheur (JSON, ex. {"stage": "SIGNED"})'
                value={draft.trigger_config}
                onChange={(e) => setDraft((d) => ({ ...d, trigger_config: e.target.value }))} />
              <Textarea className="min-w-[160px] flex-1 font-mono text-xs" rows={2}
                placeholder='Config action (JSON, ex. {"body": "..."} )'
                value={draft.action_config}
                onChange={(e) => setDraft((d) => ({ ...d, action_config: e.target.value }))} />
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-1.5 text-sm">
                <input type="checkbox" checked={draft.requires_approval}
                  onChange={(e) => setDraft((d) => ({ ...d, requires_approval: e.target.checked }))} />
                Exiger une approbation
              </label>
              {draft.requires_approval && (
                <Input className="w-[170px]" type="number" step="any"
                  placeholder="Seuil (ex. remise %)"
                  value={draft.approval_threshold}
                  onChange={(e) => setDraft((d) => ({ ...d, approval_threshold: e.target.value }))} />
              )}
              <Button type="button" className="ml-auto" onClick={addRule}>
                <Plus className="size-4" aria-hidden="true" /> Ajouter la règle
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── Approbations en attente (N73) ── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <SectionTitle label="Approbations en attente"
            icon={<><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></>}/>
          {approvals.length === 0 ? (
            <EmptyState title="Aucune approbation en attente"
              description="Les actions exigeant une validation apparaîtront ici." className="py-6" />
          ) : (
            <div className="flex flex-col gap-2">
              {approvals.map((a) => (
                <div key={a.id} className="flex flex-wrap items-center gap-1.5 rounded-lg border border-border p-2.5">
                  <span className="min-w-[160px] flex-[1_1_160px] text-sm">
                    {a.description || a.rule_nom || `Règle #${a.rule}`}
                  </span>
                  {a.target_model && (
                    <Badge tone="info">{a.target_model} #{a.target_id}</Badge>
                  )}
                  <div className="ml-auto flex items-center gap-1">
                    <Button type="button" size="sm" variant="success"
                      onClick={() => decide(a, true)}>Approuver</Button>
                    <Button type="button" size="sm" variant="secondary"
                      onClick={() => decide(a, false)}>Rejeter</Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Journal d'exécutions (N72) ── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <div className="flex items-center justify-between">
            <SectionTitle label="Journal d'exécutions"
              icon={<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/></>}/>
            <IconButton size="sm" variant="ghost" label="Rafraîchir"
              onClick={loadRuns}>
              <RefreshCw className="size-4" aria-hidden="true" />
            </IconButton>
          </div>
          {runs.length === 0 ? (
            <EmptyState title="Aucune exécution"
              description="Les déclenchements de vos règles seront tracés ici." className="py-6" />
          ) : (
            <div className="flex flex-col gap-1.5">
              {runs.map((run) => (
                <div key={run.id} className="flex flex-wrap items-center gap-1.5 text-xs">
                  <Badge tone={RUN_TONE[run.status] ?? 'neutral'}>{run.status_display}</Badge>
                  <span className="font-medium">{run.rule_nom ?? `Règle #${run.rule}`}</span>
                  <span className="text-muted-foreground">{run.message}</span>
                  <span className="ml-auto text-muted-foreground">
                    {run.timestamp ? formatDateTime(run.timestamp) : ''}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* WIR61 / XPLT4 — Webhooks entrants tokenisés (par règle webhook_inbound). */}
      <IncomingWebhookPanel rules={rules} />
    </div>
  )
}

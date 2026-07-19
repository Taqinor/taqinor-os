import { useEffect, useState } from 'react'
import { Plus, Trash2, Send, CheckCircle2, XCircle } from 'lucide-react'
import notificationsApi from '../../api/notificationsApi'
import {
  Badge, Button, Card, CardContent, IconButton, Input, Label, Spinner, Switch,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem, toast,
} from '../../ui'
import { SectionTitle } from './peComponents'

/* ============================================================================
   WIR154 — Administration Notifications (Paramètres > Notifications). Quatre
   backends complets sans UI, désormais gérables :
     - FG4  NotificationRoutingRule : routage par événement/rôle ;
     - FG5  WorkingHoursConfig + Holiday : calendrier ouvré + jours fériés ;
     - XKB5 Annonce : annonces internes (créer/publier/cibler) ;
     - XMKT25 WhatsAppTemplate : registre + cycle d'approbation.
   Tout est admin-gated côté backend ; company posée serveur.
   ========================================================================== */

const JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
const ROLES = [
  { value: 'admin', label: 'Admin' },
  { value: 'responsable', label: 'Responsable' },
  { value: 'normal', label: 'Normal' },
]

function RoutingRulesPanel() {
  const [rules, setRules] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ event_type: '', target_role: 'responsable' })

  const load = () => {
    setLoading(true)
    notificationsApi.getRoutingRules()
      .then((r) => setRules(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])))
      .catch(() => toast.error('Chargement des règles impossible.'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const creer = async () => {
    if (!form.event_type.trim()) { toast.error('Événement requis.'); return }
    try {
      await notificationsApi.saveRoutingRule(null, {
        event_type: form.event_type.trim(), target_role: form.target_role, enabled: true,
      })
      toast.success('Règle ajoutée.')
      setForm({ event_type: '', target_role: 'responsable' })
      load()
    } catch { toast.error('Création impossible (événement invalide ?).') }
  }
  const supprimer = async (id) => {
    try { await notificationsApi.deleteRoutingRule(id); load() }
    catch { toast.error('Suppression impossible.') }
  }

  return (
    <Card className="mb-4"><CardContent className="pt-4">
      <SectionTitle label="Règles de routage" />
      <p className="mb-3 text-[11.5px] text-muted-foreground">
        Dirige chaque type d'événement vers un rôle destinataire.
      </p>
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <div>
          <Label>Événement (clé)</Label>
          <Input value={form.event_type} placeholder="lead_assigned"
                 onChange={(e) => setForm((f) => ({ ...f, event_type: e.target.value }))} />
        </div>
        <div>
          <Label>Rôle cible</Label>
          <Select value={form.target_role}
                  onValueChange={(v) => setForm((f) => ({ ...f, target_role: v }))}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              {ROLES.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Button type="button" onClick={creer}><Plus className="size-4" /> Ajouter</Button>
      </div>
      {loading ? <Spinner /> : rules.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune règle définie.</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {rules.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm">
              <span className="flex items-center gap-2">
                <Badge tone="info">{r.event_label || r.event_type}</Badge>
                <span className="text-muted-foreground">→ {r.target_role_label || r.target_role || `#${r.target_user}`}</span>
                {!r.enabled && <Badge tone="neutral">désactivée</Badge>}
              </span>
              <IconButton size="md" variant="ghost" label="Supprimer"
                          className="text-destructive hover:text-destructive"
                          onClick={() => supprimer(r.id)}>
                <Trash2 className="size-4" />
              </IconButton>
            </li>
          ))}
        </ul>
      )}
    </CardContent></Card>
  )
}

function CalendrierPanel() {
  const [wh, setWh] = useState(null)
  const [holidays, setHolidays] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [holForm, setHolForm] = useState({ date: '', nom: '', recurrent_annuel: false })

  const load = () => {
    setLoading(true)
    Promise.all([notificationsApi.getWorkingHours(), notificationsApi.getHolidays()])
      .then(([w, h]) => {
        setWh(w.data)
        setHolidays(Array.isArray(h.data) ? h.data : (h.data?.results ?? []))
      })
      .catch(() => toast.error('Chargement du calendrier impossible.'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const toggleJour = (idx) => setWh((w) => {
    const days = new Set(w.working_days || [])
    if (days.has(idx)) days.delete(idx); else days.add(idx)
    return { ...w, working_days: [...days].sort((a, b) => a - b) }
  })
  const saveWh = async () => {
    setSaving(true)
    try {
      const r = await notificationsApi.saveWorkingHours({
        working_days: wh.working_days, hours_per_day: wh.hours_per_day,
      })
      setWh(r.data)
      toast.success('Calendrier ouvré enregistré.')
    } catch { toast.error('Enregistrement impossible (réservé admin ?).') }
    finally { setSaving(false) }
  }
  const ajouterFerie = async () => {
    if (!holForm.date) { toast.error('Date requise.'); return }
    try {
      await notificationsApi.createHoliday(holForm)
      toast.success('Jour férié ajouté.')
      setHolForm({ date: '', nom: '', recurrent_annuel: false })
      load()
    } catch { toast.error('Ajout impossible.') }
  }
  const supprimerFerie = async (id) => {
    try { await notificationsApi.deleteHoliday(id); load() }
    catch { toast.error('Suppression impossible.') }
  }

  if (loading || !wh) return <Card className="mb-4"><CardContent className="pt-4"><Spinner /></CardContent></Card>

  return (
    <Card className="mb-4"><CardContent className="pt-4">
      <SectionTitle label="Calendrier ouvré & jours fériés" />
      <div className="mb-3 flex flex-wrap gap-2">
        {JOURS.map((j, idx) => (
          <label key={j} className="flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-sm">
            <input type="checkbox" checked={(wh.working_days || []).includes(idx)}
                   onChange={() => toggleJour(idx)} aria-label={j} />
            {j.slice(0, 3)}
          </label>
        ))}
      </div>
      <div className="mb-3 flex items-end gap-2">
        <div>
          <Label>Heures par jour</Label>
          <Input type="number" step="any" value={wh.hours_per_day ?? ''}
                 onChange={(e) => setWh((w) => ({ ...w, hours_per_day: e.target.value }))} />
        </div>
        <Button type="button" onClick={saveWh} disabled={saving}>Enregistrer le calendrier</Button>
      </div>

      <h4 className="mb-1 mt-3 text-sm font-semibold">Jours fériés</h4>
      <div className="mb-2 flex flex-wrap items-end gap-2">
        <div>
          <Label>Date</Label>
          <Input type="date" value={holForm.date}
                 onChange={(e) => setHolForm((f) => ({ ...f, date: e.target.value }))} />
        </div>
        <div>
          <Label>Nom</Label>
          <Input value={holForm.nom} placeholder="Fête du Travail"
                 onChange={(e) => setHolForm((f) => ({ ...f, nom: e.target.value }))} />
        </div>
        <label className="flex items-center gap-1.5 text-sm">
          <Switch checked={holForm.recurrent_annuel}
                  onCheckedChange={(v) => setHolForm((f) => ({ ...f, recurrent_annuel: !!v }))} />
          Récurrent
        </label>
        <Button type="button" onClick={ajouterFerie}><Plus className="size-4" /> Ajouter</Button>
      </div>
      {holidays.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {holidays.map((h) => (
            <li key={h.id} className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm">
              <span>{h.date} — {h.nom}{h.recurrent_annuel ? ' (récurrent)' : ''}</span>
              <IconButton size="md" variant="ghost" label="Supprimer"
                          className="text-destructive hover:text-destructive"
                          onClick={() => supprimerFerie(h.id)}>
                <Trash2 className="size-4" />
              </IconButton>
            </li>
          ))}
        </ul>
      )}
    </CardContent></Card>
  )
}

function AnnoncesPanel() {
  const [annonces, setAnnonces] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ titre: '', corps: '', lecture_obligatoire: false })

  const load = () => {
    setLoading(true)
    notificationsApi.getAnnonces()
      .then((r) => setAnnonces(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])))
      .catch(() => toast.error('Chargement des annonces impossible.'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const creer = async () => {
    if (!form.titre.trim()) { toast.error('Titre requis.'); return }
    try {
      await notificationsApi.createAnnonce({
        titre: form.titre.trim(), corps: form.corps,
        cible_type: 'tous', lecture_obligatoire: form.lecture_obligatoire,
      })
      toast.success('Annonce créée (brouillon).')
      setForm({ titre: '', corps: '', lecture_obligatoire: false })
      load()
    } catch { toast.error('Création impossible.') }
  }
  const publier = async (id) => {
    try { await notificationsApi.publierAnnonce(id); toast.success('Annonce publiée.'); load() }
    catch { toast.error('Publication impossible.') }
  }
  const supprimer = async (id) => {
    try { await notificationsApi.deleteAnnonce(id); load() }
    catch { toast.error('Suppression impossible.') }
  }

  return (
    <Card className="mb-4"><CardContent className="pt-4">
      <SectionTitle label="Annonces internes" />
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <div>
          <Label>Titre</Label>
          <Input value={form.titre}
                 onChange={(e) => setForm((f) => ({ ...f, titre: e.target.value }))} />
        </div>
        <div className="flex-1">
          <Label>Message</Label>
          <Input value={form.corps}
                 onChange={(e) => setForm((f) => ({ ...f, corps: e.target.value }))} />
        </div>
        <label className="flex items-center gap-1.5 text-sm">
          <Switch checked={form.lecture_obligatoire}
                  onCheckedChange={(v) => setForm((f) => ({ ...f, lecture_obligatoire: !!v }))} />
          Lecture obligatoire
        </label>
        <Button type="button" onClick={creer}><Plus className="size-4" /> Créer</Button>
      </div>
      {loading ? <Spinner /> : annonces.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune annonce.</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {annonces.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm">
              <span className="flex items-center gap-2">
                <span className="font-medium">{a.titre}</span>
                <Badge tone={a.publiee ? 'success' : 'neutral'}>{a.publiee ? 'Publiée' : 'Brouillon'}</Badge>
                {a.lecture_obligatoire && <Badge tone="warning">Lecture obligatoire</Badge>}
              </span>
              <span className="flex items-center gap-1.5">
                {!a.publiee && (
                  <Button type="button" variant="outline" size="sm" onClick={() => publier(a.id)}>
                    <Send className="size-3.5" /> Publier
                  </Button>
                )}
                <IconButton size="md" variant="ghost" label="Supprimer"
                            className="text-destructive hover:text-destructive"
                            onClick={() => supprimer(a.id)}>
                  <Trash2 className="size-4" />
                </IconButton>
              </span>
            </li>
          ))}
        </ul>
      )}
    </CardContent></Card>
  )
}

function WhatsAppTemplatesPanel() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ name: '', body_fr: '', language: 'fr' })

  const load = () => {
    setLoading(true)
    notificationsApi.getWhatsAppTemplates()
      .then((r) => setTemplates(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])))
      .catch(() => toast.error('Chargement des gabarits impossible.'))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const creer = async () => {
    if (!form.name.trim()) { toast.error('Nom requis.'); return }
    try {
      await notificationsApi.createWhatsAppTemplate({
        name: form.name.trim(), body_fr: form.body_fr, language: form.language,
      })
      toast.success('Gabarit créé (brouillon).')
      setForm({ name: '', body_fr: '', language: 'fr' })
      load()
    } catch { toast.error('Création impossible.') }
  }
  const soumettre = async (id) => {
    try { await notificationsApi.submitWhatsAppTemplate(id); toast.success('Gabarit soumis.'); load() }
    catch { toast.error('Soumission impossible.') }
  }
  const decider = async (id, statut) => {
    try {
      await notificationsApi.decisionWhatsAppTemplate(
        id, statut, statut === 'rejete' ? 'Rejeté' : '')
      toast.success('Décision enregistrée.')
      load()
    } catch { toast.error('Décision impossible.') }
  }
  const supprimer = async (id) => {
    try { await notificationsApi.deleteWhatsAppTemplate(id); load() }
    catch { toast.error('Suppression impossible.') }
  }

  return (
    <Card className="mb-4"><CardContent className="pt-4">
      <SectionTitle label="Gabarits WhatsApp" />
      <div className="mb-3 flex flex-wrap items-end gap-2">
        <div>
          <Label>Nom</Label>
          <Input value={form.name}
                 onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
        </div>
        <div className="flex-1">
          <Label>Corps (FR)</Label>
          <Input value={form.body_fr}
                 onChange={(e) => setForm((f) => ({ ...f, body_fr: e.target.value }))} />
        </div>
        <Button type="button" onClick={creer}><Plus className="size-4" /> Créer</Button>
      </div>
      {loading ? <Spinner /> : templates.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucun gabarit.</p>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {templates.map((t) => (
            <li key={t.id} className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-sm">
              <span className="flex items-center gap-2">
                <span className="font-medium">{t.name}</span>
                <Badge tone="info">{t.statut_approbation_label || t.statut_approbation}</Badge>
              </span>
              <span className="flex items-center gap-1.5">
                {t.statut_approbation === 'brouillon' && (
                  <Button type="button" variant="outline" size="sm" onClick={() => soumettre(t.id)}>
                    <Send className="size-3.5" /> Soumettre
                  </Button>
                )}
                {t.statut_approbation === 'soumis' && (
                  <>
                    <Button type="button" variant="outline" size="sm" onClick={() => decider(t.id, 'approuve')}>
                      <CheckCircle2 className="size-3.5" /> Approuver
                    </Button>
                    <Button type="button" variant="outline" size="sm" onClick={() => decider(t.id, 'rejete')}>
                      <XCircle className="size-3.5" /> Rejeter
                    </Button>
                  </>
                )}
                <IconButton size="md" variant="ghost" label="Supprimer"
                            className="text-destructive hover:text-destructive"
                            onClick={() => supprimer(t.id)}>
                  <Trash2 className="size-4" />
                </IconButton>
              </span>
            </li>
          ))}
        </ul>
      )}
    </CardContent></Card>
  )
}

export default function NotificationsAdminSection() {
  return (
    <div>
      <RoutingRulesPanel />
      <CalendrierPanel />
      <AnnoncesPanel />
      <WhatsAppTemplatesPanel />
    </div>
  )
}

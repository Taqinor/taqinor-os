// ZSAV2/ZMFG1/ZMFG2/XSAV14/XSAV23 — Paramètres SAV : référentiels édités par
// responsable/admin (catégories de ticket, causes/remèdes de panne, réponses
// types/macros, équipes de maintenance, catégories d'équipement). Page
// autonome (même patron que WarrantyClaimsPage) plutôt qu'un nouvel onglet
// dans la grosse page Paramètres (surface de risque plus faible).
import { useEffect, useState } from 'react'
import { Plus, Pencil, Check, X } from 'lucide-react'
import savApi from '../../api/savApi'
import api from '../../api/axios'
import {
  TooltipProvider, Card, Tabs, TabsList, TabsTrigger, TabsContent,
  Button, Input, Textarea, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, EmptyState, Skeleton, Switch, toast,
} from '../../ui'
import SimpleRefListEditor from './SimpleRefListEditor'

// ── Réponses types (macros) — titre + corps + statut optionnel ──
const STATUT_OPTIONS = [
  { value: '', label: '— Aucun changement de statut —' },
  { value: 'planifie', label: 'Planifié' },
  { value: 'en_cours', label: 'En cours' },
  { value: 'resolu', label: 'Résolu' },
  { value: 'cloture', label: 'Clôturé' },
]

function ReponsesTypeSection() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ titre: '', corps: '', nouveau_statut: '' })
  const [edit, setEdit] = useState(null)

  const load = () => savApi.getReponsesType().then((r) => setRows(r.data.results ?? r.data ?? []))
    .catch(() => {}).finally(() => setLoading(false))

  const charger = () => { setLoading(true); return load() }

  useEffect(() => { load() }, [])

  const add = async () => {
    if (!form.titre.trim() || !form.corps.trim()) return
    try {
      await savApi.saveReponseType(null, form)
      setForm({ titre: '', corps: '', nouveau_statut: '' })
      toast.success('Réponse type ajoutée')
      charger()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const startEdit = (r) => setEdit({ id: r.id, titre: r.titre, corps: r.corps, nouveau_statut: r.nouveau_statut ?? '' })
  const saveEdit = async () => {
    try {
      await savApi.saveReponseType(edit.id, {
        titre: edit.titre, corps: edit.corps, nouveau_statut: edit.nouveau_statut,
      })
      setEdit(null)
      toast.success('Réponse type mise à jour')
      charger()
    } catch { toast.error('Mise à jour impossible.') }
  }
  const toggleArchive = async (r) => {
    try { await savApi.saveReponseType(r.id, { archived: !r.archived }); charger() }
    catch { toast.error('Bascule impossible.') }
  }

  if (loading) return <Skeleton className="h-32 w-full" />

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Insérables en un clic dans le chatter d'un ticket. Placeholders
        disponibles : <code>{'{client}'}</code> <code>{'{reference}'}</code>{' '}
        <code>{'{technicien}'}</code> <code>{'{date}'}</code>.
      </p>
      <Card className="flex flex-col gap-2 p-4">
        <Input placeholder="Titre" value={form.titre}
               onChange={(e) => setForm((f) => ({ ...f, titre: e.target.value }))} />
        <Textarea rows={3} placeholder="Corps du message"
                  value={form.corps}
                  onChange={(e) => setForm((f) => ({ ...f, corps: e.target.value }))} />
        <Select value={form.nouveau_statut || '__none'}
                onValueChange={(v) => setForm((f) => ({ ...f, nouveau_statut: v === '__none' ? '' : v }))}>
          <SelectTrigger className="w-64"><SelectValue /></SelectTrigger>
          <SelectContent>
            {STATUT_OPTIONS.map((s) => (
              <SelectItem key={s.value || '__none'} value={s.value || '__none'}>{s.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button type="button" size="sm" className="self-start" onClick={add}>
          <Plus /> Ajouter
        </Button>
      </Card>
      {rows.length === 0 ? <EmptyState title="Aucune réponse type" /> : (
        <ul className="flex flex-col gap-2">
          {rows.map((r) => (
            <li key={r.id} className="rounded-lg border border-border bg-card p-3 text-sm">
              {edit?.id === r.id ? (
                <div className="flex flex-col gap-2">
                  <Input value={edit.titre} onChange={(e) => setEdit((s) => ({ ...s, titre: e.target.value }))} />
                  <Textarea rows={3} value={edit.corps} onChange={(e) => setEdit((s) => ({ ...s, corps: e.target.value }))} />
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={saveEdit}><Check /> Enregistrer</Button>
                    <Button size="sm" variant="ghost" onClick={() => setEdit(null)}><X /></Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{r.titre}</p>
                    <p className="whitespace-pre-wrap text-muted-foreground">{r.corps}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <Button size="sm" variant="ghost" onClick={() => startEdit(r)}><Pencil /></Button>
                    <Button size="sm" variant="ghost" onClick={() => toggleArchive(r)}>
                      {r.archived ? 'Réactiver' : 'Archiver'}
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Équipes de maintenance (ZMFG1) — nom + actif, sans gestion des membres
// (réservée à une itération future : ce référentiel simple débloque déjà le
// filtre équipe + le tableau de bord ZMFG4). ──
function EquipesMaintenanceSection() {
  return (
    <SimpleRefListEditor
      loadFn={savApi.getEquipesMaintenance}
      saveFn={savApi.saveEquipeMaintenance}
      nameField="nom"
      label="équipe"
      emptyLabel="Aucune équipe"
      isArchived={(r) => !r.actif}
      archivePayload={() => ({ actif: false })}
      unarchivePayload={() => ({ actif: true })}
    />
  )
}

// ── Catégories d'équipement (ZMFG2/ZMFG7/WIR117) — nom + alias e-mail +
// équipe responsable. L'alias e-mail route un message entrant (FG373) vers un
// ticket correctif pré-catégorisé (câblé dans apps.py) ; l'équipe responsable
// est affectée automatiquement. Jusqu'ici seul `nom` était éditable. ──
function CategoriesEquipementSection() {
  const [rows, setRows] = useState([])
  const [equipes, setEquipes] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ nom: '', alias_email: '', equipe_responsable: '' })
  const [busy, setBusy] = useState(false)
  const [edits, setEdits] = useState({})

  const load = () => savApi.getCategoriesEquipement()
    .then((r) => setRows(r.data.results ?? r.data ?? []))
    .catch(() => {})
    .finally(() => setLoading(false))

  useEffect(() => {
    load()
    savApi.getEquipesMaintenance()
      .then((r) => setEquipes(r.data.results ?? r.data ?? []))
      .catch(() => {})
  }, [])

  const add = async () => {
    const nom = form.nom.trim()
    if (!nom) return
    setBusy(true)
    try {
      await savApi.saveCategorieEquipement(null, {
        nom,
        alias_email: form.alias_email.trim() || null,
        equipe_responsable: form.equipe_responsable || null,
      })
      setForm({ nom: '', alias_email: '', equipe_responsable: '' })
      toast.success("Catégorie d'équipement ajoutée")
      setLoading(true); load()
    } catch (e) {
      toast.error(e?.response?.data?.alias_email ?? e?.response?.data?.detail ?? 'Ajout impossible.')
    } finally { setBusy(false) }
  }

  const rowEdit = (row) => edits[row.id] ?? {
    alias_email: row.alias_email ?? '',
    equipe_responsable: row.equipe_responsable ? String(row.equipe_responsable) : '',
  }
  const setRowEdit = (id, patch) =>
    setEdits((e) => ({ ...e, [id]: { ...rowEdit({ id, ...e[id] }), ...patch } }))

  const saveRow = async (row) => {
    const e = rowEdit(row)
    try {
      await savApi.saveCategorieEquipement(row.id, {
        alias_email: e.alias_email.trim() || null,
        equipe_responsable: e.equipe_responsable || null,
      })
      toast.success('Catégorie mise à jour')
      setEdits((prev) => { const n = { ...prev }; delete n[row.id]; return n })
      setLoading(true); load()
    } catch (err) {
      toast.error(err?.response?.data?.alias_email ?? err?.response?.data?.detail ?? 'Enregistrement impossible.')
    }
  }

  if (loading) return <Skeleton className="h-24 w-full" />

  return (
    <div className="flex flex-col gap-3">
      <div className="grid items-end gap-2 sm:grid-cols-[2fr_2fr_2fr_auto]">
        <Input placeholder="Nouvelle catégorie…" value={form.nom}
               onChange={(e) => setForm((f) => ({ ...f, nom: e.target.value }))}
               onKeyDown={(e) => { if (e.key === 'Enter') add() }} />
        <Input type="email" placeholder="Alias e-mail (optionnel)…" value={form.alias_email}
               onChange={(e) => setForm((f) => ({ ...f, alias_email: e.target.value }))} />
        <Select value={form.equipe_responsable || '__none'}
                onValueChange={(v) => setForm((f) => ({ ...f, equipe_responsable: v === '__none' ? '' : v }))}>
          <SelectTrigger><SelectValue placeholder="— Équipe responsable —" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__none">— Aucune équipe —</SelectItem>
            {equipes.map((eq) => (
              <SelectItem key={eq.id} value={String(eq.id)}>{eq.nom}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button type="button" size="sm" loading={busy} onClick={add}><Plus /> Ajouter</Button>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="Aucune catégorie d'équipement" />
      ) : (
        <ul className="flex flex-col gap-1.5">
          {rows.map((r) => {
            const e = rowEdit(r)
            return (
              <li key={r.id}
                  className="grid items-end gap-2 rounded-lg border border-border bg-card px-3 py-2 sm:grid-cols-[2fr_2fr_2fr_auto]">
                <span className="text-sm font-medium">{r.nom}</span>
                <Input type="email" aria-label={`Alias e-mail — ${r.nom}`}
                       placeholder="Alias e-mail…" value={e.alias_email}
                       onChange={(ev) => setRowEdit(r.id, { alias_email: ev.target.value })} />
                <Select value={e.equipe_responsable || '__none'}
                        onValueChange={(v) => setRowEdit(r.id, { equipe_responsable: v === '__none' ? '' : v })}>
                  <SelectTrigger aria-label={`Équipe responsable — ${r.nom}`}>
                    <SelectValue placeholder="— Équipe —" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none">— Aucune équipe —</SelectItem>
                    {equipes.map((eq) => (
                      <SelectItem key={eq.id} value={String(eq.id)}>{eq.nom}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button type="button" size="sm" variant="outline" onClick={() => saveRow(r)}>
                  <Check /> Enregistrer
                </Button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

// ── Compatibilités pièces (XSAV25/WIR117) — mappe une pièce catalogue comme
// compatible avec un produit d'équipement, pour que le picker de pièces du
// ticket la propose EN PREMIER. CRUD minimal (ajout + suppression). ──
function CompatibilitesPieceSection() {
  const [rows, setRows] = useState([])
  const [produits, setProduits] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ produit_equipement: '', piece: '', note: '' })
  const [busy, setBusy] = useState(false)

  const load = () => savApi.getCompatibilitesPiece()
    .then((r) => setRows(r.data.results ?? r.data ?? []))
    .catch(() => {})
    .finally(() => setLoading(false))

  useEffect(() => {
    load()
    api.get('/stock/produits/')
      .then((r) => setProduits(r.data.results ?? r.data ?? []))
      .catch(() => {})
  }, [])

  const add = async () => {
    if (!form.produit_equipement || !form.piece) return
    setBusy(true)
    try {
      await savApi.saveCompatibilitePiece(null, {
        produit_equipement: form.produit_equipement,
        piece: form.piece,
        note: form.note.trim(),
      })
      setForm({ produit_equipement: '', piece: '', note: '' })
      toast.success('Compatibilité ajoutée')
      setLoading(true); load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Ajout impossible.')
    } finally { setBusy(false) }
  }

  const remove = async (id) => {
    try {
      await savApi.deleteCompatibilitePiece(id)
      setLoading(true); load()
    } catch { toast.error('Suppression impossible.') }
  }

  const produitOptions = (placeholder) => (
    <SelectContent>
      <SelectItem value="__none">{placeholder}</SelectItem>
      {produits.map((p) => (
        <SelectItem key={p.id} value={String(p.id)}>{p.nom}{p.sku ? ` (${p.sku})` : ''}</SelectItem>
      ))}
    </SelectContent>
  )

  if (loading) return <Skeleton className="h-24 w-full" />

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted-foreground">
        Associez une pièce catalogue à un produit d'équipement : le picker de
        pièces du ticket (équipement lié) proposera ces pièces en premier.
      </p>
      <div className="grid items-end gap-2 sm:grid-cols-[2fr_2fr_2fr_auto]">
        <Select value={form.produit_equipement || '__none'}
                onValueChange={(v) => setForm((f) => ({ ...f, produit_equipement: v === '__none' ? '' : v }))}>
          <SelectTrigger aria-label="Produit d'équipement">
            <SelectValue placeholder="— Produit d'équipement —" />
          </SelectTrigger>
          {produitOptions("— Produit d'équipement —")}
        </Select>
        <Select value={form.piece || '__none'}
                onValueChange={(v) => setForm((f) => ({ ...f, piece: v === '__none' ? '' : v }))}>
          <SelectTrigger aria-label="Pièce compatible">
            <SelectValue placeholder="— Pièce compatible —" />
          </SelectTrigger>
          {produitOptions('— Pièce compatible —')}
        </Select>
        <Input placeholder="Note (optionnel)…" value={form.note}
               onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} />
        <Button type="button" size="sm" loading={busy}
                disabled={!form.produit_equipement || !form.piece} onClick={add}>
          <Plus /> Ajouter
        </Button>
      </div>
      {rows.length === 0 ? (
        <EmptyState title="Aucune compatibilité" />
      ) : (
        <ul className="flex flex-col gap-1.5">
          {rows.map((r) => (
            <li key={r.id}
                className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm">
              <span>
                <span className="font-medium">{r.produit_equipement_nom ?? `#${r.produit_equipement}`}</span>
                {' → '}
                {r.piece_nom ?? `#${r.piece}`}
                {r.note ? ` · ${r.note}` : ''}
              </span>
              <Button type="button" size="sm" variant="ghost" onClick={() => remove(r.id)}>
                <X /> Supprimer
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── WIR30 — Réglages SLA / automatisation SAV (SavSlaSettings, singleton par
// société). 14 champs déjà exposés côté serveur (GET/POST /sav/sla-settings/,
// SavSlaSettingsViewSet.list()/create() = upsert du singleton) mais sans
// aucune surface frontend jusqu'ici. Notamment `generation_auto_visites`, qui
// bloque la génération auto des visites préventives déjà planifiée au beat
// (YSERV5, sav.generer_visites_dues_quotidien) tant qu'aucune société ne
// l'active ici — et `sla_warning_days`/`escalade_activee`, qui pilotent le
// scan pré-alertes désormais lui aussi planifié (WIR30).
const SLA_SETTINGS_DEFAULTS = {
  sla_response_days: 1,
  sla_resolution_days: 7,
  sla_breach_enabled: false,
  notifications_client_sav: false,
  sla_jours_ouvres: false,
  sla_warning_days: 0,
  escalade_activee: false,
  affectation_auto_sav: false,
  auto_cloture_jours: 0,
  recidive_fenetre_jours: 30,
  generation_auto_visites: false,
  visites_avance_jours: 7,
  worksheets_maintenance_actifs: false,
}

const SLA_TOGGLES = [
  { key: 'sla_breach_enabled', label: 'Notifier le technicien au dépassement du SLA' },
  { key: 'notifications_client_sav', label: 'Notifications client aux transitions du ticket' },
  { key: 'sla_jours_ouvres', label: "Calculer l'échéance SLA en jours ouvrés" },
  { key: 'escalade_activee', label: 'Escalader au responsable à la violation du SLA' },
  { key: 'affectation_auto_sav', label: 'Affectation automatique des tickets à la création' },
  { key: 'generation_auto_visites', label: 'Génération automatique des visites préventives dues' },
  { key: 'worksheets_maintenance_actifs', label: 'Feuilles de maintenance (worksheets) actives' },
]

const SLA_NUMBER_FIELDS = [
  { key: 'sla_response_days', label: 'Délai de première réponse (jours)' },
  { key: 'sla_resolution_days', label: 'Délai de résolution cible (jours)' },
  { key: 'sla_warning_days', label: 'Pré-alerte SLA (jours avant échéance, 0 = désactivée)' },
  { key: 'auto_cloture_jours', label: 'Auto-clôture des tickets résolus (jours, 0 = désactivée)' },
  { key: 'recidive_fenetre_jours', label: 'Fenêtre de récidive (jours)' },
  { key: 'visites_avance_jours', label: 'Avance de génération des visites (jours)' },
]

function SlaAutomationSection() {
  const [form, setForm] = useState(SLA_SETTINGS_DEFAULTS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.get('/sav/sla-settings/')
      .then((r) => setForm((f) => ({ ...f, ...(r.data ?? {}) })))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const setField = (key) => (value) => setForm((f) => ({ ...f, [key]: value }))
  const setNumberField = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  const save = async () => {
    setSaving(true)
    try {
      const r = await api.post('/sav/sla-settings/', form)
      setForm((f) => ({ ...f, ...(r.data ?? {}) }))
      toast.success('Réglages SLA enregistrés')
    } catch {
      toast.error("Échec de l'enregistrement des réglages SLA.")
    } finally { setSaving(false) }
  }

  if (loading) return <Skeleton className="h-32 w-full" />

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">
        Délais SLA et automatisations SAV, par société. Chaque automatisation
        reste désactivée (comportement actuel inchangé) tant qu'elle n'est pas
        activée explicitement ici.
      </p>
      <Card className="flex flex-col gap-4 p-4">
        <div className="grid gap-3 sm:grid-cols-2">
          {SLA_NUMBER_FIELDS.map((f) => (
            <label key={f.key} className="flex flex-col gap-1 text-sm text-foreground">
              {f.label}
              <Input type="number" min="0" step="1" value={form[f.key] ?? 0}
                     onChange={setNumberField(f.key)} />
            </label>
          ))}
        </div>
        <div className="flex flex-col gap-2 border-t border-border pt-3">
          {SLA_TOGGLES.map((t) => (
            <div key={t.key}
                 className="flex items-center justify-between gap-2 rounded-lg border border-border p-2.5 text-sm text-foreground">
              <span>{t.label}</span>
              <Switch aria-label={t.label} checked={!!form[t.key]}
                      onCheckedChange={setField(t.key)} />
            </div>
          ))}
        </div>
        <Button type="button" size="sm" className="self-start" loading={saving} onClick={save}>
          Enregistrer
        </Button>
      </Card>
    </div>
  )
}

export default function SavParametresPage() {
  const [tab, setTab] = useState('categories-ticket')

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-4xl flex-col gap-5 p-1">
        <header>
          <h1 className="font-display text-2xl font-bold tracking-tight">Paramètres SAV</h1>
          <p className="text-sm text-muted-foreground">
            Référentiels après-vente : catégories, causes/remèdes de panne,
            réponses types, équipes.
          </p>
        </header>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="flex w-full flex-wrap justify-start">
            <TabsTrigger value="categories-ticket">Catégories de ticket</TabsTrigger>
            <TabsTrigger value="causes-remedes">Causes / remèdes de panne</TabsTrigger>
            <TabsTrigger value="reponses-type">Réponses types</TabsTrigger>
            <TabsTrigger value="equipes">Équipes de maintenance</TabsTrigger>
            <TabsTrigger value="categories-equipement">Catégories d'équipement</TabsTrigger>
            <TabsTrigger value="compatibilites-piece">Pièces compatibles</TabsTrigger>
            <TabsTrigger value="sla-automatisation">SLA / Automatisation</TabsTrigger>
          </TabsList>

          <TabsContent value="categories-ticket">
            <SimpleRefListEditor
              loadFn={savApi.getCategoriesTicket}
              saveFn={savApi.saveCategorieTicket}
              nameField="libelle"
              label="catégorie"
              emptyLabel="Aucune catégorie"
              isArchived={(r) => !r.actif}
              archivePayload={() => ({ actif: false })}
              unarchivePayload={() => ({ actif: true })}
            />
          </TabsContent>

          <TabsContent value="causes-remedes">
            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <h3 className="mb-2 font-display text-base font-semibold">Causes</h3>
                <SimpleRefListEditor
                  loadFn={savApi.getCausesDefaillance}
                  saveFn={savApi.saveCauseDefaillance}
                  nameField="nom"
                  label="cause"
                  emptyLabel="Aucune cause"
                  isArchived={(r) => r.archived}
                  archivePayload={() => ({ archived: true })}
                  unarchivePayload={() => ({ archived: false })}
                />
              </div>
              <div>
                <h3 className="mb-2 font-display text-base font-semibold">Remèdes</h3>
                <SimpleRefListEditor
                  loadFn={savApi.getRemedesDefaillance}
                  saveFn={savApi.saveRemedeDefaillance}
                  nameField="nom"
                  label="remède"
                  isArchived={(r) => r.archived}
                  archivePayload={() => ({ archived: true })}
                  unarchivePayload={() => ({ archived: false })}
                />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="reponses-type">
            <ReponsesTypeSection />
          </TabsContent>

          <TabsContent value="equipes">
            <EquipesMaintenanceSection />
          </TabsContent>

          <TabsContent value="categories-equipement">
            <CategoriesEquipementSection />
          </TabsContent>

          <TabsContent value="compatibilites-piece">
            <CompatibilitesPieceSection />
          </TabsContent>

          <TabsContent value="sla-automatisation">
            <SlaAutomationSection />
          </TabsContent>
        </Tabs>
      </div>
    </TooltipProvider>
  )
}

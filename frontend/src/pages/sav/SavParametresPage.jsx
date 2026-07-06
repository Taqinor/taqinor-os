// ZSAV2/ZMFG1/ZMFG2/XSAV14/XSAV23 — Paramètres SAV : référentiels édités par
// responsable/admin (catégories de ticket, causes/remèdes de panne, réponses
// types/macros, équipes de maintenance, catégories d'équipement). Page
// autonome (même patron que WarrantyClaimsPage) plutôt qu'un nouvel onglet
// dans la grosse page Paramètres (surface de risque plus faible).
import { useEffect, useState } from 'react'
import { Plus, Pencil, Check, X } from 'lucide-react'
import savApi from '../../api/savApi'
import {
  TooltipProvider, Card, Tabs, TabsList, TabsTrigger, TabsContent,
  Button, Input, Textarea, Select, SelectTrigger, SelectValue, SelectContent,
  SelectItem, EmptyState, Skeleton, toast,
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

  const load = () => {
    setLoading(true)
    savApi.getReponsesType().then((r) => setRows(r.data.results ?? r.data ?? []))
      .catch(() => {}).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const add = async () => {
    if (!form.titre.trim() || !form.corps.trim()) return
    try {
      await savApi.saveReponseType(null, form)
      setForm({ titre: '', corps: '', nouveau_statut: '' })
      toast.success('Réponse type ajoutée')
      load()
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
      load()
    } catch { toast.error('Mise à jour impossible.') }
  }
  const toggleArchive = async (r) => {
    try { await savApi.saveReponseType(r.id, { archived: !r.archived }); load() }
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
      isArchived={(r) => !r.actif}
      archivePayload={() => ({ actif: false })}
      unarchivePayload={() => ({ actif: true })}
    />
  )
}

// ── Catégories d'équipement (ZMFG2) — nom + commentaire, sans gestion de
// l'alias e-mail/équipe responsable (édité via l'API pour l'instant). ──
function CategoriesEquipementSection() {
  return (
    <SimpleRefListEditor
      loadFn={savApi.getCategoriesEquipement}
      saveFn={savApi.saveCategorieEquipement}
      nameField="nom"
      label="catégorie d'équipement"
      isArchived={() => false}
      archivePayload={() => ({})}
      unarchivePayload={() => ({})}
    />
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
          </TabsList>

          <TabsContent value="categories-ticket">
            <SimpleRefListEditor
              loadFn={savApi.getCategoriesTicket}
              saveFn={savApi.saveCategorieTicket}
              nameField="libelle"
              label="catégorie"
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
        </Tabs>
      </div>
    </TooltipProvider>
  )
}

// N74 — Onglet « Checklists » de la page Paramètres : modèles NOMMÉS de
// checklist chantier/onboarding, auto-sélectionnés par type d'installation.
//
// Chaque modèle regroupe des étapes ordonnées. À la création d'un chantier, le
// modèle dont le type correspond est sélectionné automatiquement ; sinon c'est
// le modèle « Défaut » (protégé) qui porte EXACTEMENT les étapes d'aujourd'hui
// — le comportement reste donc identique tant qu'aucun modèle typé n'est créé.
//
// Section autonome : charge ses propres données (comme le reste des Paramètres,
// elle s'enregistre seule, sans le bouton « Enregistrer » global). Tout le
// texte est en français ; les identifiants techniques (clés) restent en anglais.
import { useEffect, useState } from 'react'
import { Plus, Trash2, ChevronUp, ChevronDown, AlertCircle } from 'lucide-react'
import { toast } from '../../ui/confirm'
import installationsApi from '../../api/installationsApi'
import {
  Card, CardContent, Input, Button, IconButton, Badge, Spinner, EmptyState,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle } from './peComponents'

// Types d'installation qui peuvent auto-sélectionner un modèle (miroir des
// choix serveur Installation.TypeInstallation). « __none__ » = repli « Défaut ».
const TYPE_CHOICES = [
  ['__none__', 'Aucun (modèle « Défaut »)'],
  ['residentiel', 'Résidentiel'],
  ['industriel', 'Industriel / Commercial'],
  ['agricole', 'Agricole (pompage)'],
]
const TYPE_LABELS = Object.fromEntries(TYPE_CHOICES)

// Clé technique stable dérivée d'un libellé (anglais/ASCII, sans accents).
const slugify = (s) => s.trim().toLowerCase()
  .normalize('NFD').replace(/[̀-ͯ]/g, '')
  .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40)

export default function ChecklistSection() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  // ERR62 — un échec de chargement affiche une erreur + Réessayer (pas un état
  // « vide » trompeur faisant croire qu'aucun modèle n'existe).
  const [loadError, setLoadError] = useState(false)
  const [newTemplate, setNewTemplate] = useState('')
  const [newType, setNewType] = useState('__none__')
  const [newEtape, setNewEtape] = useState({}) // { [templateId]: libellé }

  const load = () => installationsApi.getChecklistTemplates()
    .then(r => { setTemplates(r.data.results ?? r.data); setLoadError(false) })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))
  useEffect(() => { load() }, [])

  // ── Modèles ──
  const addTemplate = async () => {
    const nom = newTemplate.trim()
    if (!nom) return
    try {
      await installationsApi.saveChecklistTemplate(null, {
        nom,
        type_installation: newType === '__none__' ? null : newType,
        ordre: templates.length,
      })
      setNewTemplate(''); setNewType('__none__'); load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const renameTemplate = async (t, nom) => {
    if (!nom.trim() || nom === t.nom) return
    try { await installationsApi.saveChecklistTemplate(t.id, { nom }); load() }
    catch { /* */ }
  }
  const setTemplateType = async (t, type) => {
    try {
      await installationsApi.saveChecklistTemplate(t.id, {
        type_installation: type === '__none__' ? null : type })
      load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Type impossible à changer.') }
  }
  const toggleTemplateActif = async (t) => {
    try { await installationsApi.saveChecklistTemplate(t.id, { actif: !t.actif }); load() }
    catch { /* */ }
  }
  const moveTemplate = async (idx, dir) => {
    const j = idx + dir
    if (j < 0 || j >= templates.length) return
    const a = templates[idx]; const b = templates[j]
    try {
      await Promise.all([
        installationsApi.saveChecklistTemplate(a.id, { ordre: b.ordre }),
        installationsApi.saveChecklistTemplate(b.id, { ordre: a.ordre }),
      ])
      load()
    } catch { /* */ }
  }
  const delTemplate = async (t) => {
    if (!window.confirm(`Supprimer le modèle « ${t.nom} » et ses étapes ?`)) return
    try { await installationsApi.deleteChecklistTemplate(t.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible (modèle protégé ?).') }
  }

  // ── Étapes d'un modèle ──
  const addEtape = async (t) => {
    const libelle = (newEtape[t.id] ?? '').trim()
    if (!libelle) return
    try {
      await installationsApi.saveChecklistEtape(null, {
        template: t.id, cle: slugify(libelle) || `etape_${Date.now()}`,
        libelle, ordre: (t.etapes ?? []).length,
      })
      setNewEtape(p => ({ ...p, [t.id]: '' })); load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const renameEtape = async (et, libelle) => {
    if (!libelle.trim() || libelle === et.libelle) return
    try { await installationsApi.saveChecklistEtape(et.id, { libelle }); load() }
    catch { /* */ }
  }
  const toggleEtapeActif = async (et) => {
    try { await installationsApi.saveChecklistEtape(et.id, { actif: !et.actif }); load() }
    catch { /* */ }
  }
  const toggleCaptureSerie = async (et) => {
    try { await installationsApi.saveChecklistEtape(et.id, { capture_serie: !et.capture_serie }); load() }
    catch { /* */ }
  }
  const moveEtape = async (t, idx, dir) => {
    const etapes = t.etapes ?? []
    const j = idx + dir
    if (j < 0 || j >= etapes.length) return
    const a = etapes[idx]; const b = etapes[j]
    try {
      await Promise.all([
        installationsApi.saveChecklistEtape(a.id, { ordre: b.ordre }),
        installationsApi.saveChecklistEtape(b.id, { ordre: a.ordre }),
      ])
      load()
    } catch { /* */ }
  }
  const delEtape = async (et) => {
    if (!window.confirm(`Supprimer l'étape « ${et.libelle} » ?`)) return
    try { await installationsApi.deleteChecklistEtape(et.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible (étape protégée ?).') }
  }

  if (loading) return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )

  if (loadError) return (
    <div className="flex flex-col items-start gap-2">
      <p className="flex items-center gap-2 text-sm text-destructive">
        <AlertCircle className="size-4" aria-hidden="true" />
        Modèles de checklist indisponibles (serveur ?).
      </p>
      <Button type="button" size="sm" variant="outline" onClick={load}>Réessayer</Button>
    </div>
  )

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Chantiers — Modèles de checklist"
          icon={<><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></>}/>
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Composez des checklists nommées et associez chacune à un type
          d'installation : à la création d'un chantier, le modèle du type
          correspondant est sélectionné automatiquement. Sans correspondance,
          c'est le modèle « Défaut » (protégé) qui s'applique — il porte les
          étapes actuelles, donc rien ne change tant que vous ne créez pas de
          modèle typé. Désactiver une étape la retire des nouveaux chantiers
          sans toucher aux chantiers existants.
        </p>

        {/* ── Liste des modèles + leurs étapes ── */}
        <div className="flex flex-col gap-3">
          {templates.length === 0 && (
            <EmptyState title="Aucun modèle"
              description="Ajoutez votre premier modèle de checklist ci-dessous." className="py-6" />
          )}
          {templates.map((t, ti) => (
            <div key={t.id} className="rounded-lg border border-border p-3">
              {/* En-tête du modèle */}
              <div className="mb-2.5 flex flex-wrap items-center gap-1.5">
                {/* ERR102 — re-monte le champ si le serveur normalise le nom. */}
                <Input key={t.nom} className={['min-w-[140px] flex-[1_1_140px] font-medium', t.actif ? '' : 'opacity-50'].join(' ')}
                  defaultValue={t.nom} onBlur={e => renameTemplate(t, e.target.value)} />
                {t.protege ? (
                  <Badge tone="info">Défaut</Badge>
                ) : (
                  <div className="w-[180px]">
                    <Select value={t.type_installation || '__none__'}
                      onValueChange={v => setTemplateType(t, v)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {TYPE_CHOICES.map(([v, lbl]) => (
                          <SelectItem key={v} value={v}>{lbl}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                {t.protege && (
                  <Badge tone="neutral" title="Modèle de repli (type vide)">
                    {TYPE_LABELS[t.type_installation || '__none__']}
                  </Badge>
                )}
                <div className="ml-auto flex items-center gap-1">
                  <IconButton size="sm" variant="ghost" label="Monter"
                    disabled={ti === 0} onClick={() => moveTemplate(ti, -1)}>
                    <ChevronUp className="size-4" aria-hidden="true" />
                  </IconButton>
                  <IconButton size="sm" variant="ghost" label="Descendre"
                    disabled={ti === templates.length - 1} onClick={() => moveTemplate(ti, 1)}>
                    <ChevronDown className="size-4" aria-hidden="true" />
                  </IconButton>
                  <Button type="button" size="sm"
                    variant={t.actif ? 'success' : 'secondary'}
                    title={t.actif ? 'Désactiver' : 'Activer'}
                    onClick={() => toggleTemplateActif(t)}>
                    {t.actif ? 'Actif' : 'Inactif'}
                  </Button>
                  {!t.protege && (
                    <IconButton size="sm" variant="outline" label="Supprimer le modèle"
                      className="text-destructive hover:text-destructive"
                      onClick={() => delTemplate(t)}>
                      <Trash2 className="size-4" aria-hidden="true" />
                    </IconButton>
                  )}
                </div>
              </div>

              {/* Étapes du modèle */}
              {(t.etapes ?? []).map((et, ei) => (
                <div key={et.id} className="mb-1.5 flex flex-wrap items-center gap-1.5">
                  {/* ERR102 — re-monte le champ si le serveur normalise le libellé. */}
                  <Input key={et.libelle} className={['min-w-[120px] flex-[1_1_120px]', et.actif ? '' : 'opacity-50'].join(' ')}
                    defaultValue={et.libelle} onBlur={e => renameEtape(et, e.target.value)} />
                  <Button type="button" size="sm"
                    variant={et.capture_serie ? 'default' : 'outline'}
                    title="Saisie de n° de série sur cette étape"
                    onClick={() => toggleCaptureSerie(et)}>
                    Série
                  </Button>
                  <IconButton size="sm" variant="ghost" label="Monter l'étape"
                    disabled={ei === 0} onClick={() => moveEtape(t, ei, -1)}>
                    <ChevronUp className="size-4" aria-hidden="true" />
                  </IconButton>
                  <IconButton size="sm" variant="ghost" label="Descendre l'étape"
                    disabled={ei === (t.etapes ?? []).length - 1} onClick={() => moveEtape(t, ei, 1)}>
                    <ChevronDown className="size-4" aria-hidden="true" />
                  </IconButton>
                  <Button type="button" size="sm"
                    variant={et.actif ? 'success' : 'secondary'}
                    title={et.actif ? 'Désactiver' : 'Activer'}
                    onClick={() => toggleEtapeActif(et)}>
                    {et.actif ? 'Actif' : 'Inactif'}
                  </Button>
                  {et.protege ? (
                    <Badge tone="info">système</Badge>
                  ) : (
                    <IconButton size="sm" variant="outline" label="Supprimer l'étape"
                      className="text-destructive hover:text-destructive"
                      onClick={() => delEtape(et)}>
                      <Trash2 className="size-4" aria-hidden="true" />
                    </IconButton>
                  )}
                </div>
              ))}
              <div className="mt-1.5 flex gap-1.5">
                <Input className="flex-1" placeholder="Nouvelle étape"
                  value={newEtape[t.id] ?? ''}
                  onChange={e => setNewEtape(p => ({ ...p, [t.id]: e.target.value }))}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addEtape(t) } }} />
                <Button type="button" size="sm" onClick={() => addEtape(t)}>
                  <Plus className="size-4" aria-hidden="true" /> Étape
                </Button>
              </div>
            </div>
          ))}
        </div>

        {/* ── Ajout d'un modèle ── */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Input className="min-w-[160px] flex-[1_1_160px]" placeholder="Nouveau modèle de checklist"
            value={newTemplate} onChange={e => setNewTemplate(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTemplate() } }} />
          <div className="w-[200px]">
            <Select value={newType} onValueChange={setNewType}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {TYPE_CHOICES.map(([v, lbl]) => (
                  <SelectItem key={v} value={v}>{lbl}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="button" onClick={addTemplate}>
            <Plus className="size-4" aria-hidden="true" /> Ajouter
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

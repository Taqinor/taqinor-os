import { useCallback, useMemo, useState } from 'react'
import {
  ArrowDown, ArrowUp, Check, Plus, Trash2, X,
} from 'lucide-react'
import {
  Button, IconButton, Input, Textarea, Badge, Card, toast,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  EmptyState,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import coreApi from '../../api/coreApi'
import useWorkflowResource from './useWorkflowResource'
import {
  ajouterEtape, deplacerEtape, retirerEtape, validerDefinition,
  normaliserModeles, normaliserInstances,
} from './workflow'

/* ============================================================================
   XPLT8 -- ecran "Workflows" ("/workflow").
   ----------------------------------------------------------------------------
   Trois onglets :
     1. Definitions -- editeur FONCTIONNEL local (liste ordonnee d'etapes, pas
        de canvas graphique). GAP BACKEND CONFIRME : `core.WorkflowDefinition`
        / `WorkflowStepDefinition` n'ont AUCUN ViewSet CRUD (seul
        `workflow-templates/installer/` materialise ces lignes -- voir
        `core/views.py`, `core/urls.py`). Ce brouillon reste donc un etat
        local de la session (aucune persistance serveur) ; il sert a valider
        la forme/le Done ("creer une definition 3 etapes") et a preparer une
        future tache backend qui exposerait le CRUD reel.
     2. Modeles -- catalogue FG369 reel (`GET core/workflow-templates/`) +
        installation en un clic (`POST .../installer/`), qui, elle, persiste
        reellement cote serveur.
     3. Instances en cours -- agregees depuis la boite d'approbations
        transverse `reporting.approbations-en-attente` filtree sur
        `source=workflow` (XKB1) ; approuver/rejeter appelle
        `reporting/approbations-en-attente/decider/`. Il n'existe pas
        d'action "escalader" dediee cote API (l'escalade SLA est un job
        Beat/commande de management `escalate_workflow_sla`, pas un endpoint
        REST) -- l'ecran affiche donc le retard SLA visuellement et expose
        seulement approuver/rejeter, comme le confirme
        `apps/reporting/approbations.py` (`decider_approbation` n'accepte que
        `'approuver'|'refuser'`).
   ========================================================================== */

function nouvelleDefinition() {
  return { nom: '', description: '', steps: [] }
}

function DefinitionsTab() {
  // WIR51 — les definitions sont desormais PERSISTEES cote serveur
  // (`core/workflow-definitions/`, company forcee cote serveur). On charge les
  // definitions existantes au montage ; "Creer" POST reellement puis les
  // rajoute a la liste (un rechargement de l'ecran les conserve).
  const {
    data, error, reload, setData,
  } = useWorkflowResource(() => coreApi.workflowDefinitions.list())
  const [def, setDef] = useState(nouvelleDefinition)
  const [saving, setSaving] = useState(false)

  function majChamp(champ, valeur) {
    setDef((d) => ({ ...d, [champ]: valeur }))
  }

  function majEtape(index, champ, valeur) {
    setDef((d) => ({
      ...d,
      steps: d.steps.map((s, i) => (i === index ? { ...s, [champ]: valeur } : s)),
    }))
  }

  function ajouter() {
    setDef((d) => ({ ...d, steps: ajouterEtape(d.steps) }))
  }

  function retirer(index) {
    setDef((d) => ({ ...d, steps: retirerEtape(d.steps, index) }))
  }

  function monter(index) {
    setDef((d) => ({ ...d, steps: deplacerEtape(d.steps, index, -1) }))
  }

  function descendre(index) {
    setDef((d) => ({ ...d, steps: deplacerEtape(d.steps, index, 1) }))
  }

  async function creer() {
    const erreurs = validerDefinition(def)
    if (erreurs.length > 0) {
      toast.error(erreurs[0])
      return
    }
    if (saving) return
    setSaving(true)
    try {
      const payload = {
        nom: String(def.nom || '').trim(),
        description: def.description || '',
        steps: def.steps.map((s, i) => ({
          ordre: i + 1,
          nom: s.nom,
          type_approbation: s.type_approbation || 'manuelle',
          sla_heures:
            s.sla_heures === '' || s.sla_heures == null
              ? null
              : Number(s.sla_heures),
          role_requis: s.role_requis || '',
          escalade_vers: s.escalade_vers || '',
        })),
      }
      const res = await coreApi.workflowDefinitions.create(payload)
      const created = res?.data
      if (created && created.id != null) {
        setData((list) => [...(Array.isArray(list) ? list : []), created])
      } else {
        reload()
      }
      toast.success(`Definition "${def.nom}" enregistree (${def.steps.length} etapes).`)
      setDef(nouvelleDefinition())
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  const crees = Array.isArray(data) ? data : []

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4 sm:p-5">
        <div className="flex flex-col gap-3">
          <Input
            placeholder="Nom de la definition (ex. Validation devis)"
            value={def.nom}
            onChange={(e) => majChamp('nom', e.target.value)}
            data-testid="wf-def-nom"
          />
          <Textarea
            placeholder="Description (optionnel)"
            value={def.description}
            onChange={(e) => majChamp('description', e.target.value)}
          />

          <div className="flex flex-col gap-2" data-testid="wf-def-steps">
            {def.steps.length === 0 && (
              <p className="text-sm text-muted-foreground">Aucune etape -- ajoutez-en une.</p>
            )}
            {def.steps.map((step, i) => (
              <div
                key={i}
                className="flex flex-col gap-2 rounded-md border border-border p-3 sm:flex-row sm:items-center"
                data-testid={`wf-def-step-${i}`}
              >
                <span className="w-8 shrink-0 text-sm font-medium text-muted-foreground">
                  {step.ordre}.
                </span>
                <Input
                  className="sm:flex-1"
                  placeholder="Nom de l'etape"
                  value={step.nom}
                  onChange={(e) => majEtape(i, 'nom', e.target.value)}
                />
                <Select
                  value={step.type_approbation}
                  onValueChange={(v) => majEtape(i, 'type_approbation', v)}
                >
                  <SelectTrigger className="sm:w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manuelle">Manuelle</SelectItem>
                    <SelectItem value="auto">Automatique</SelectItem>
                    <SelectItem value="role">Par role</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  className="sm:w-32"
                  placeholder="SLA (h)"
                  inputMode="numeric"
                  noValidate
                  step="any"
                  value={step.sla_heures}
                  onChange={(e) => majEtape(i, 'sla_heures', e.target.value)}
                />
                <Input
                  className="sm:w-40"
                  placeholder="Assigne (role)"
                  value={step.role_requis}
                  onChange={(e) => majEtape(i, 'role_requis', e.target.value)}
                />
                <div className="flex items-center gap-1">
                  <IconButton label="Monter" variant="ghost" size="icon" disabled={i === 0} onClick={() => monter(i)}>
                    <ArrowUp />
                  </IconButton>
                  <IconButton label="Descendre" variant="ghost" size="icon" disabled={i === def.steps.length - 1} onClick={() => descendre(i)}>
                    <ArrowDown />
                  </IconButton>
                  <IconButton label="Retirer" variant="ghost" size="icon" onClick={() => retirer(i)}>
                    <Trash2 />
                  </IconButton>
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={ajouter} data-testid="wf-def-add-step">
              <Plus /> Ajouter une etape
            </Button>
            <Button onClick={creer} disabled={saving} data-testid="wf-def-create">
              <Check /> {saving ? 'Enregistrement...' : 'Creer la definition'}
            </Button>
          </div>
        </div>
      </Card>

      {error && (
        <div className="rounded-md border border-dashed border-border bg-muted/40 p-3 text-xs text-muted-foreground">
          Definitions existantes indisponibles ({error}).
        </div>
      )}

      {crees.length > 0 && (
        <Card className="p-4 sm:p-5">
          <h3 className="mb-3 text-sm font-medium text-foreground">
            Definitions enregistrees
          </h3>
          <ul className="flex flex-col gap-2" data-testid="wf-def-created-list">
            {crees.map((d) => (
              <li key={d.id} className="rounded-md border border-border p-3">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{d.nom}</span>
                  <Badge tone="neutral">{(d.steps || []).length} etapes</Badge>
                </div>
                {d.description && (
                  <p className="mt-1 text-sm text-muted-foreground">{d.description}</p>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

function ModelesTab() {
  const { data, loading, error, reload } = useWorkflowResource(
    () => coreApi.workflowTemplates.list(),
  )
  const modeles = useMemo(() => normaliserModeles(data), [data])
  const [installingCode, setInstallingCode] = useState(null)

  const installer = useCallback(async (code) => {
    if (installingCode) return
    setInstallingCode(code)
    try {
      const res = await coreApi.workflowTemplates.installer(code)
      toast.success(
        `Modele installe : "${res?.data?.nom || code}" (${res?.data?.nb_etapes ?? '?'} etapes).`,
      )
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Impossible d'installer ce modele.")
    } finally {
      setInstallingCode(null)
    }
  }, [installingCode])

  if (loading) {
    return <p className="text-sm text-muted-foreground">Chargement des modeles...</p>
  }
  if (error) {
    return <EmptyState title="Erreur" description={error} />
  }
  if (modeles.length === 0) {
    return (
      <EmptyState
        title="Aucun modele disponible"
        description="Le catalogue de modeles de workflow est vide."
        action={<Button variant="secondary" onClick={reload}>Rafraichir</Button>}
      />
    )
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="wf-templates-grid">
      {modeles.map((m) => (
        <Card key={m.code} className="flex flex-col gap-2 p-4">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">{m.nom}</h3>
            <Badge tone="neutral">{m.nb_etapes} etapes</Badge>
          </div>
          <p className="text-sm text-muted-foreground">{m.description}</p>
          <Button
            className="mt-2 self-start"
            onClick={() => installer(m.code)}
            data-testid={`wf-template-install-${m.code}`}
          >
            {installingCode === m.code ? 'Installation...' : 'Installer'}
          </Button>
        </Card>
      ))}
    </div>
  )
}

function InstancesTab() {
  const { data, loading, error, reload } = useWorkflowResource(
    () => coreApi.workflowInstances.listPending(),
  )
  const instances = useMemo(() => normaliserInstances(data), [data])
  const [decidingId, setDecidingId] = useState(null)

  const decider = useCallback(async (item, decision) => {
    if (decidingId) return
    let motif
    if (decision === 'refuser') {
      motif = window.prompt('Motif du rejet (obligatoire) :') || ''
      if (!motif.trim()) {
        toast.error('Un motif de refus est obligatoire.')
        return
      }
    }
    setDecidingId(item.id)
    try {
      await coreApi.workflowInstances.decider(item.id, decision, motif)
      toast.success(decision === 'approuver' ? 'Etape approuvee.' : 'Etape rejetee.')
      reload()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Action impossible.')
    } finally {
      setDecidingId(null)
    }
  }, [decidingId, reload])

  if (loading) {
    return <p className="text-sm text-muted-foreground">Chargement des instances...</p>
  }
  if (error) {
    return <EmptyState title="Erreur" description={error} />
  }
  if (instances.length === 0) {
    return (
      <EmptyState
        title="Aucune instance en cours"
        description="Aucune etape de workflow n'attend d'approbation."
        action={<Button variant="secondary" onClick={reload}>Rafraichir</Button>}
      />
    )
  }

  return (
    <ul className="flex flex-col gap-2" data-testid="wf-instances-list">
      {instances.map((it) => (
        <li key={it.id} className="rounded-md border border-border p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="font-medium">{it.libelle || `Etape #${it.id}`}</span>
              {it.demandeur && (
                <span className="ml-2 text-sm text-muted-foreground">-- {it.demandeur}</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {it.en_retard && <Badge tone="danger">SLA depasse</Badge>}
              <Button
                variant="secondary"
                size="sm"
                disabled={decidingId === it.id}
                onClick={() => decider(it, 'approuver')}
                data-testid={`wf-instance-approve-${it.id}`}
              >
                <Check /> Approuver
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={decidingId === it.id}
                onClick={() => decider(it, 'refuser')}
                data-testid={`wf-instance-reject-${it.id}`}
              >
                <X /> Rejeter
              </Button>
            </div>
          </div>
        </li>
      ))}
    </ul>
  )
}

export default function WorkflowsScreen() {
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Workflows"
        subtitle="Definitions & etapes, modeles installables, instances en cours (moteur BPM FG366/368/369)."
      />
      <Tabs defaultValue="definitions">
        <TabsList>
          <TabsTrigger value="definitions">Definitions</TabsTrigger>
          <TabsTrigger value="modeles">Modeles</TabsTrigger>
          <TabsTrigger value="instances">Instances en cours</TabsTrigger>
        </TabsList>
        <TabsContent value="definitions">
          <DefinitionsTab />
        </TabsContent>
        <TabsContent value="modeles">
          <ModelesTab />
        </TabsContent>
        <TabsContent value="instances">
          <InstancesTab />
        </TabsContent>
      </Tabs>
    </div>
  )
}

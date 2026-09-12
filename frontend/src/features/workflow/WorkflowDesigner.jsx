import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Check, GripVertical, LayoutList, Plus, Rows3, Trash2,
} from 'lucide-react'
import {
  Button, Input, Textarea, Badge, Card, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Checkbox, Sheet, SheetContent, SheetTitle,
  EmptyState,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import coreApi from '../../api/coreApi'
import {
  deplacerEtapeVersIndex, renumeroterEtapes, ajouterEtape, ajouterEtapeDeType,
  retirerEtape, swimlanesDe, validerEtapesDefinition, TYPES_ETAPE_PALETTE,
} from './workflow'

/* ============================================================================
   NTWFL6 -- Designer visuel (canvas) au-dessus de FG366/WIR51.
   ----------------------------------------------------------------------------
   Route : /workflow/:id/designer (voir module.config.jsx -- NON nichee sous
   /parametres/*, meme raison documentee dans ce fichier : un prefixe plus
   general y matcherait avant nos titres specifiques).

   Vue GRAPHIQUE complementaire de l'editeur liste XPLT8 (WorkflowsScreen ->
   onglet Definitions) sur la MEME donnee serveur (WorkflowDefinition/
   WorkflowStepDefinition, WIR51) -- glisser-deposer un noeud persiste le
   MEME `ordre` que l'editeur liste (deplacerEtapeVersIndex delegue a
   deplacerEtape, deja teste), les deux vues restent donc synchronisees SANS
   aucune migration ni double source de verite.

   Un noeud = une etape (rectangle avec nom/type/role/SLA) ; une arete =
   transition sequentielle. Glisser-deposer horizontal via l'API HTML5 Drag &
   Drop native (aucune nouvelle dependance -- pas de librairie de canvas).
   ========================================================================== */

// Sentinelle « aucune alternative » — Radix <Select.Item> refuse une valeur
// vide (réservée au clear interne), même convention que GedNavigator/
// PortailAdmin (__none/__root__/__all__) ailleurs dans le repo.
const AUCUNE_ALTERNATIVE = '__aucune__'

const TYPE_LABELS = {
  manuelle: 'Manuelle',
  auto: 'Automatique',
  role: 'Par role',
}

function resumeCondition(condition) {
  if (!condition || typeof condition !== 'object') return ''
  if (condition.field) {
    return `si ${condition.field} ${condition.operator} ${JSON.stringify(condition.value)}`
  }
  return 'condition composee'
}

function EtapeNoeud({
  etape, index, total, selectionnee, onSelect, onDragStart, onDragOver, onDrop,
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      draggable
      onDragStart={(e) => onDragStart(e, index)}
      onDragOver={(e) => { e.preventDefault(); onDragOver(index) }}
      onDrop={(e) => { e.preventDefault(); onDrop(index) }}
      onClick={() => onSelect(index)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect(index) }}
      data-testid={`wfd-node-${etape.ordre}`}
      className="flex min-w-[180px] cursor-grab flex-col gap-1 rounded-md border p-3 shadow-sm"
      style={{
        borderColor: selectionnee ? 'var(--accent, #6366f1)' : undefined,
        borderWidth: selectionnee ? 2 : 1,
      }}
    >
      <div className="flex items-center gap-1 text-xs text-muted-foreground">
        <GripVertical size={14} />
        <span>{index + 1}/{total}</span>
      </div>
      <span className="font-medium">{etape.nom || `Etape ${etape.ordre}`}</span>
      <div className="flex flex-wrap gap-1">
        <Badge tone="neutral">{TYPE_LABELS[etape.type_approbation] || etape.type_approbation}</Badge>
        {etape.role_requis && <Badge tone="neutral">{etape.role_requis}</Badge>}
        {etape.sla_heures ? <Badge tone="neutral">{etape.sla_heures}h</Badge> : null}
        {etape.groupe_parallele ? <Badge tone="warning">groupe {etape.groupe_parallele}</Badge> : null}
      </div>
      {etape.condition_transition && (
        <span className="text-xs text-muted-foreground" data-testid={`wfd-edge-label-${etape.ordre}`}>
          {resumeCondition(etape.condition_transition)}
          {etape.etape_alternative_si_echec ? ` -> sinon etape ${etape.etape_alternative_si_echec}` : ''}
        </span>
      )}
    </div>
  )
}

/* ============================================================================
   NTWFL8 -- Swimlanes par role : regroupement PUREMENT visuel (aucun champ
   backend nouveau, derive de `role_requis` existant, swimlanesDe testee).
   ========================================================================== */
function VueSwimlanes({
  steps, selection, onSelect, onDragStart, onDeplacerVersRole,
}) {
  const bandes = useMemo(() => swimlanesDe(steps), [steps])

  return (
    <div className="flex flex-col gap-3" data-testid="wfd-swimlanes">
      {bandes.map((bande) => (
        <div
          key={bande.role || '__sans_role__'}
          className="rounded-md border p-3"
          data-testid={`wfd-swimlane-${bande.role || 'sans-role'}`}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); onDeplacerVersRole(bande.role) }}
        >
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            {bande.role || 'Sans role'}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            {bande.steps.map((etape) => {
              const index = steps.findIndex((s) => s.ordre === etape.ordre)
              return (
                <EtapeNoeud
                  key={etape.ordre}
                  etape={etape}
                  index={index}
                  total={steps.length}
                  selectionnee={selection === index}
                  onSelect={onSelect}
                  onDragStart={onDragStart}
                  onDragOver={() => {}}
                  onDrop={() => {}}
                />
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

/* ============================================================================
   NTWFL9 -- Palette de noeuds reutilisables : ajoute une etape d'un type
   connu du backend (WorkflowStepDefinition.APPROBATION_CHOICES) en un clic.
   ========================================================================== */
function Palette({ onAjouter }) {
  return (
    <Card className="flex shrink-0 flex-col gap-2 p-3" data-testid="wfd-palette">
      <p className="text-xs font-medium text-muted-foreground">Palette</p>
      {TYPES_ETAPE_PALETTE.map(({ type, label }) => (
        <Button
          key={type}
          variant="secondary"
          size="sm"
          onClick={() => onAjouter(type)}
          data-testid={`wfd-palette-${type}`}
        >
          <Plus /> {label}
        </Button>
      ))}
    </Card>
  )
}

function PanneauEdition({ etape, autresOrdres, onChange, onClose, onSupprimer }) {
  const [conditionField, setConditionField] = useState(etape.condition_transition?.field || '')
  const [conditionOp, setConditionOp] = useState(etape.condition_transition?.operator || 'gt')
  const [conditionValue, setConditionValue] = useState(
    etape.condition_transition?.value != null ? String(etape.condition_transition.value) : '',
  )

  function appliquerCondition() {
    if (!conditionField.trim()) {
      onChange({ ...etape, condition_transition: null })
      return
    }
    const brut = conditionValue.trim()
    const valeur = brut !== '' && !Number.isNaN(Number(brut)) ? Number(brut) : brut
    onChange({
      ...etape,
      condition_transition: { field: conditionField.trim(), operator: conditionOp, value: valeur },
    })
  }

  return (
    <Sheet open onOpenChange={(o) => { if (!o) onClose() }}>
      <SheetContent side="right" className="flex flex-col gap-3 p-4" data-testid="wfd-panel">
        <SheetTitle>Etape {etape.ordre}</SheetTitle>
        <Input
          placeholder="Nom de l'etape"
          value={etape.nom}
          onChange={(e) => onChange({ ...etape, nom: e.target.value })}
          data-testid="wfd-panel-nom"
        />
        <Select
          value={etape.type_approbation}
          onValueChange={(v) => onChange({ ...etape, type_approbation: v })}
        >
          <SelectTrigger><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="manuelle">Manuelle</SelectItem>
            <SelectItem value="auto">Automatique</SelectItem>
            <SelectItem value="role">Par role</SelectItem>
          </SelectContent>
        </Select>
        <Input
          placeholder="Role requis"
          value={etape.role_requis || ''}
          onChange={(e) => onChange({ ...etape, role_requis: e.target.value })}
          data-testid="wfd-panel-role"
        />
        <Input
          placeholder="SLA (heures)"
          inputMode="numeric"
          noValidate
          step="any"
          value={etape.sla_heures ?? ''}
          onChange={(e) => onChange({ ...etape, sla_heures: e.target.value })}
        />
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={!!etape.calendrier_ouvre}
            onCheckedChange={(v) => onChange({ ...etape, calendrier_ouvre: !!v })}
          />
          Echeance en jours ouvres
        </label>
        <Input
          placeholder="Groupe parallele (optionnel)"
          inputMode="numeric"
          noValidate
          step="any"
          value={etape.groupe_parallele ?? ''}
          onChange={(e) => onChange({
            ...etape,
            groupe_parallele: e.target.value === '' ? null : Number(e.target.value),
          })}
          data-testid="wfd-panel-groupe"
        />

        <div className="mt-2 rounded-md border p-2">
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Garde de transition (etape automatique)
          </p>
          <div className="flex flex-col gap-2">
            <Input
              placeholder="Champ (ex. montant)"
              value={conditionField}
              onChange={(e) => setConditionField(e.target.value)}
              onBlur={appliquerCondition}
              data-testid="wfd-panel-condition-field"
            />
            <Select value={conditionOp} onValueChange={(v) => { setConditionOp(v); appliquerCondition() }}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {['eq', 'ne', 'gt', 'gte', 'lt', 'lte'].map((op) => (
                  <SelectItem key={op} value={op}>{op}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              placeholder="Valeur"
              value={conditionValue}
              onChange={(e) => setConditionValue(e.target.value)}
              onBlur={appliquerCondition}
              data-testid="wfd-panel-condition-value"
            />
          </div>
          <Select
            value={etape.etape_alternative_si_echec
              ? String(etape.etape_alternative_si_echec) : AUCUNE_ALTERNATIVE}
            onValueChange={(v) => onChange({
              ...etape,
              etape_alternative_si_echec: v === AUCUNE_ALTERNATIVE ? null : Number(v),
            })}
          >
            <SelectTrigger className="mt-2"><SelectValue placeholder="Etape alternative si echec" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={AUCUNE_ALTERNATIVE}>Aucune (reste en attente)</SelectItem>
              {autresOrdres.map((o) => (
                <SelectItem key={o} value={String(o)}>Etape {o}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="mt-auto flex justify-between">
          <Button variant="ghost" onClick={onSupprimer} data-testid="wfd-panel-supprimer">
            <Trash2 /> Retirer
          </Button>
          <Button onClick={onClose} data-testid="wfd-panel-fermer">
            <Check /> Terminer
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  )
}

export default function WorkflowDesigner() {
  const { id } = useParams()
  const [nom, setNom] = useState('')
  const [description, setDescription] = useState('')
  const [steps, setSteps] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [selection, setSelection] = useState(null)
  // NTWFL6/8 — l'index en cours de glisser n'est jamais lu directement, seul
  // le setter fonctionnel importe (patron déjà utilisé pour un état
  // write-only, ex. PaieDeclarations.jsx `const [, setBusy]`).
  const [, setDragIndex] = useState(null)
  // NTWFL8 — bascule séquence/swimlanes (aucune donnée nouvelle, pure vue).
  const [vueParRole, setVueParRole] = useState(false)
  // NTWFL9 — erreurs de validation AFFICHÉES avant sauvegarde (miroir client
  // de core.workflow.valider_definition_steps ; le serveur reste le dernier
  // mot — voir enregistrer()).
  const [erreursValidation, setErreursValidation] = useState([])

  useEffect(() => {
    let alive = true
    coreApi.workflowDefinitions.get(id).then((res) => {
      if (!alive) return
      const d = res?.data
      setNom(d?.nom || '')
      setDescription(d?.description || '')
      setSteps(renumeroterEtapes(
        (Array.isArray(d?.steps) ? d.steps : []).slice().sort((a, b) => a.ordre - b.ordre),
      ))
    }).catch(() => toast.error('Definition introuvable.')).finally(() => {
      if (alive) setLoading(false)
    })
    return () => { alive = false }
  }, [id])

  const onDragStart = useCallback((_e, index) => setDragIndex(index), [])
  const onDragOver = useCallback(() => {}, [])
  const onDrop = useCallback((indexCible) => {
    setDragIndex((source) => {
      if (source == null || source === indexCible) return null
      setSteps((prev) => deplacerEtapeVersIndex(prev, source, indexCible))
      return null
    })
  }, [])

  function majEtape(etapeMaj) {
    setSteps((prev) => prev.map((s) => (s.ordre === etapeMaj.ordre ? etapeMaj : s)))
  }

  // NTWFL8 — déposer un noeud dans une bande met à jour SON role_requis
  // (dérivé, aucun nouveau champ) ; journalisé au chatter côté serveur
  // (aucun ici — c'est un simple champ texte, comme l'éditeur liste).
  const onDeplacerVersRole = useCallback((role) => {
    setDragIndex((source) => {
      if (source == null) return null
      setSteps((prev) => prev.map(
        (s, i) => (i === source ? { ...s, role_requis: role } : s),
      ))
      return null
    })
  }, [])

  function ajouter() {
    setSteps((prev) => ajouterEtape(prev))
  }

  // NTWFL9 — ajout depuis la palette (type choisi explicitement).
  function ajouterDeType(type) {
    setSteps((prev) => ajouterEtapeDeType(prev, type))
  }

  function supprimerSelection() {
    if (selection == null) return
    setSteps((prev) => retirerEtape(prev, selection))
    setSelection(null)
  }

  async function enregistrer() {
    // NTWFL9 — validation cote client AVANT tout appel reseau : bloque
    // l'enregistrement avec une liste d'erreurs claire (le serveur revalide
    // de toute facon, defense en profondeur, jamais la seule barriere).
    const payloadSteps = steps.map((s, i) => ({ ...s, ordre: i + 1 }))
    const erreurs = validerEtapesDefinition(payloadSteps)
    setErreursValidation(erreurs)
    if (erreurs.length > 0) {
      toast.error(erreurs[0])
      return
    }
    setSaving(true)
    try {
      await coreApi.workflowDefinitions.update(id, {
        nom,
        description,
        steps: payloadSteps,
      })
      toast.success('Definition enregistree.')
    } catch (err) {
      const detail = err?.response?.data?.steps?.[0] || err?.response?.data?.detail
      toast.error(detail || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  const etapeSelectionnee = useMemo(
    () => (selection != null ? steps[selection] : null),
    [selection, steps],
  )

  if (loading) return <p className="text-sm text-muted-foreground">Chargement...</p>

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Designer de processus"
        subtitle="Vue graphique -- synchronisee avec l'editeur liste (memes donnees WIR51)."
      />
      <div className="flex items-center gap-2">
        <Link to="/workflow"><Button variant="ghost"><ArrowLeft /> Retour</Button></Link>
        <Input
          className="max-w-sm"
          value={nom}
          onChange={(e) => setNom(e.target.value)}
          placeholder="Nom de la definition"
        />
      </div>
      <Textarea
        placeholder="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
      />

      <div className="flex items-start gap-3">
        <Palette onAjouter={ajouterDeType} />
        <div className="flex-1">
          {steps.length === 0 ? (
            <EmptyState
              title="Aucune etape"
              description="Ajoutez une premiere etape pour commencer (bouton ci-dessous ou palette)."
              action={<Button onClick={ajouter}><Plus /> Ajouter une etape</Button>}
            />
          ) : (
            <>
              <div className="mb-2 flex items-center gap-2">
                <Button
                  variant={vueParRole ? 'ghost' : 'secondary'}
                  size="sm"
                  onClick={() => setVueParRole(false)}
                  data-testid="wfd-vue-sequence"
                >
                  <LayoutList /> Sequence
                </Button>
                <Button
                  variant={vueParRole ? 'secondary' : 'ghost'}
                  size="sm"
                  onClick={() => setVueParRole(true)}
                  data-testid="wfd-vue-swimlanes"
                >
                  <Rows3 /> Par role
                </Button>
              </div>
              <Card className="overflow-x-auto p-4">
                {vueParRole ? (
                  <VueSwimlanes
                    steps={steps}
                    selection={selection}
                    onSelect={setSelection}
                    onDragStart={onDragStart}
                    onDeplacerVersRole={onDeplacerVersRole}
                  />
                ) : (
                  <div className="flex items-center gap-6" data-testid="wfd-canvas">
                    {steps.map((etape, index) => (
                      <div key={etape.ordre} className="flex items-center gap-2">
                        <EtapeNoeud
                          etape={etape}
                          index={index}
                          total={steps.length}
                          selectionnee={selection === index}
                          onSelect={setSelection}
                          onDragStart={onDragStart}
                          onDragOver={onDragOver}
                          onDrop={onDrop}
                        />
                        {index < steps.length - 1 && (
                          <span aria-hidden="true" className="text-muted-foreground">&rarr;</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </>
          )}
        </div>
      </div>

      {erreursValidation.length > 0 && (
        <div
          className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive"
          data-testid="wfd-erreurs-validation"
        >
          <p className="font-medium">Definition invalide :</p>
          <ul className="ml-4 list-disc">
            {erreursValidation.map((err) => <li key={err}>{err}</li>)}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" onClick={ajouter} data-testid="wfd-add-step">
          <Plus /> Ajouter une etape
        </Button>
        <Button onClick={enregistrer} disabled={saving} data-testid="wfd-save">
          <Check /> {saving ? 'Enregistrement...' : 'Enregistrer'}
        </Button>
      </div>

      {etapeSelectionnee && (
        <PanneauEdition
          etape={etapeSelectionnee}
          autresOrdres={steps.filter((s) => s.ordre !== etapeSelectionnee.ordre).map((s) => s.ordre)}
          onChange={majEtape}
          onClose={() => setSelection(null)}
          onSupprimer={supprimerSelection}
        />
      )}
    </div>
  )
}

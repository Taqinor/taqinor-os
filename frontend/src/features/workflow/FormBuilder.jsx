import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Check, GripVertical, Trash2 } from 'lucide-react'
import {
  Button, Input, Card, toast, Checkbox,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import coreApi from '../../api/coreApi'
import DynamicForm from './DynamicForm'
import { deplacerChamp } from './workflow'

// Sentinelle « aucune condition » (même convention que WorkflowDesigner —
// Radix <Select.Item> refuse une valeur vide).
const AUCUNE_CONDITION = '__aucune__'
const OPERATEURS = ['eq', 'ne', 'gt', 'gte', 'lt', 'lte']

/* ============================================================================
   NTWFL14 -- Editeur de formulaire visuel (drag-and-drop de champs).
   ----------------------------------------------------------------------------
   Route : /workflow/formulaires/:id/editeur. Construit sur
   FormulaireDefinition.schema (NTWFL12), AUCUNE nouvelle donnee backend.
   Glisser un type depuis la palette vers le canevas ajoute un champ ;
   glisser un champ du canevas le reordonne. Previsualisation live via le
   MEME composant DynamicForm.jsx que l'ecran d'approbation reel.
   ========================================================================== */

const TYPES = [
  { type: 'texte', label: 'Texte' },
  { type: 'nombre', label: 'Nombre' },
  { type: 'date', label: 'Date' },
  { type: 'choix', label: 'Choix' },
  { type: 'booleen', label: 'Booléen' },
  { type: 'section', label: 'Section répétable' },
]

function nouveauChamp(type) {
  const base = { nom: `Nouveau champ ${type}`, type, requis: false }
  if (type === 'choix') return { ...base, options: [] }
  if (type === 'section') return { ...base, repetable: true }
  return base
}

function LignePalette({ type, label }) {
  return (
    <div
      draggable
      onDragStart={(e) => e.dataTransfer.setData('text/type-champ', type)}
      className="cursor-grab rounded-md border p-2 text-sm"
      data-testid={`fb-palette-${type}`}
    >
      {label}
    </div>
  )
}

function LigneChamp({
  champ, index, autresChamps, onChange, onSupprimer,
  onDragStart, onDragOver, onDrop,
}) {
  const condition = champ._visibleSi || {}

  function majCondition(patch) {
    const next = { ...condition, ...patch }
    if (!next.field) {
      onChange(index, { ...champ, _visibleSi: null })
      return
    }
    onChange(index, { ...champ, _visibleSi: next })
  }

  return (
    <div
      draggable
      onDragStart={(e) => { e.dataTransfer.setData('text/plain', ''); onDragStart(index) }}
      onDragOver={(e) => { e.preventDefault(); onDragOver(index) }}
      onDrop={(e) => { e.preventDefault(); onDrop(index) }}
      className="flex flex-col gap-2 rounded-md border p-2"
      data-testid={`fb-champ-${index}`}
    >
      <div className="flex items-center gap-2">
        <GripVertical size={14} className="text-muted-foreground" />
        <Input
          className="flex-1"
          value={champ.nom}
          onChange={(e) => onChange(index, { ...champ, nom: e.target.value })}
          data-testid={`fb-champ-${index}-nom`}
        />
        <span className="text-xs text-muted-foreground">{champ.type}</span>
        <label className="flex items-center gap-1 text-xs">
          <Checkbox
            checked={!!champ.requis}
            onCheckedChange={(v) => onChange(index, { ...champ, requis: !!v })}
            data-testid={`fb-champ-${index}-requis`}
          />
          Requis
        </label>
        {champ.type === 'section' && (
          <label className="flex items-center gap-1 text-xs">
            <Checkbox
              checked={!!champ.repetable}
              onCheckedChange={(v) => onChange(index, { ...champ, repetable: !!v })}
            />
            Répétable
          </label>
        )}
        <Button variant="ghost" size="sm" onClick={() => onSupprimer(index)} data-testid={`fb-champ-${index}-supprimer`}>
          <Trash2 />
        </Button>
      </div>

      {autresChamps.length > 0 && (
        <div className="flex items-center gap-2 pl-6 text-xs">
          <span className="text-muted-foreground">Visible si</span>
          <Select
            value={condition.field || AUCUNE_CONDITION}
            onValueChange={(v) => majCondition({ field: v === AUCUNE_CONDITION ? null : v })}
          >
            <SelectTrigger className="w-40" data-testid={`fb-champ-${index}-condition-champ`}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={AUCUNE_CONDITION}>(aucune condition)</SelectItem>
              {autresChamps.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
          {condition.field && (
            <>
              <Select
                value={condition.operator || 'eq'}
                onValueChange={(v) => majCondition({ operator: v })}
              >
                <SelectTrigger className="w-24"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {OPERATEURS.map((op) => <SelectItem key={op} value={op}>{op}</SelectItem>)}
                </SelectContent>
              </Select>
              <Input
                className="w-32"
                placeholder="Valeur"
                value={condition.value ?? ''}
                onChange={(e) => majCondition({ value: e.target.value })}
                data-testid={`fb-champ-${index}-condition-valeur`}
              />
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default function FormBuilder() {
  const { id } = useParams()
  const estNouveau = !id || id === 'nouveau'
  const [nom, setNom] = useState('')
  const [schema, setSchema] = useState([])
  const [loading, setLoading] = useState(!estNouveau)
  const [saving, setSaving] = useState(false)
  // Seul le setter fonctionnel importe (même patron que WorkflowDesigner.jsx).
  const [, setDragIndex] = useState(null)
  const [valeursApercu, setValeursApercu] = useState({})

  useEffect(() => {
    if (estNouveau) return
    let alive = true
    coreApi.formulaires.get(id).then((res) => {
      if (!alive) return
      setNom(res?.data?.nom || '')
      setSchema(Array.isArray(res?.data?.schema) ? res.data.schema : [])
    }).catch(() => toast.error('Formulaire introuvable.')).finally(() => {
      if (alive) setLoading(false)
    })
    return () => { alive = false }
  }, [id, estNouveau])

  const ajouterChamp = useCallback((type) => {
    setSchema((prev) => [...prev, nouveauChamp(type)])
  }, [])

  function majChamp(index, champ) {
    setSchema((prev) => prev.map((c, i) => (i === index ? champ : c)))
  }

  function supprimerChamp(index) {
    setSchema((prev) => prev.filter((_, i) => i !== index))
  }

  const onDragStartChamp = useCallback((index) => setDragIndex(index), [])
  const onDragOverChamp = useCallback(() => {}, [])
  const onDropChamp = useCallback((indexCible) => {
    setDragIndex((source) => {
      if (source == null) return null
      setSchema((prev) => deplacerChamp(prev, source, indexCible))
      return null
    })
  }, [])

  function onDropCanevas(e) {
    const type = e.dataTransfer.getData('text/type-champ')
    if (type) ajouterChamp(type)
  }

  // NTWFL12 -- schema envoyé à DynamicForm au format attendu (sans les
  // clés privées `_visibleSi` de l'éditeur, qui vivent dans
  // `champs_conditionnels`, pas dans `schema`, côté backend).
  const schemaAvecConditions = useMemo(() => schema.map((c) => ({
    nom: c.nom, type: c.type, requis: c.requis, options: c.options,
    repetable: c.repetable,
  })), [schema])
  const champsConditionnelsApercu = useMemo(() => {
    const out = {}
    schema.forEach((c) => {
      if (c._visibleSi && c._visibleSi.field) {
        out[c.nom] = { visible_si: c._visibleSi }
      }
    })
    return out
  }, [schema])

  async function enregistrer() {
    setSaving(true)
    try {
      const payload = {
        nom,
        // eslint-disable-next-line no-unused-vars -- `_visibleSi` extrait pour l'exclure du payload (rest sibling, cf. NTWFL12 plus haut)
        schema: schema.map(({ _visibleSi, ...c }) => c),
        champs_conditionnels: champsConditionnelsApercu,
      }
      if (estNouveau) {
        await coreApi.formulaires.create(payload)
      } else {
        await coreApi.formulaires.update(id, payload)
      }
      toast.success('Formulaire enregistré.')
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Enregistrement impossible.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <p className="text-sm text-muted-foreground">Chargement...</p>

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Éditeur de formulaire"
        subtitle="Glisser des champs depuis la palette -- prévisualisation identique à l'écran réel."
      />
      <div className="flex items-center gap-2">
        <Link to="/workflow"><Button variant="ghost"><ArrowLeft /> Retour</Button></Link>
        <Input
          className="max-w-sm"
          value={nom}
          onChange={(e) => setNom(e.target.value)}
          placeholder="Nom du formulaire"
        />
        <Button onClick={enregistrer} disabled={saving} data-testid="fb-save">
          <Check /> {saving ? 'Enregistrement...' : 'Enregistrer'}
        </Button>
      </div>

      <div className="flex items-start gap-3">
        <Card className="flex shrink-0 flex-col gap-2 p-3" data-testid="fb-palette">
          <p className="text-xs font-medium text-muted-foreground">Palette</p>
          {TYPES.map(({ type, label }) => <LignePalette key={type} type={type} label={label} />)}
        </Card>

        <Card
          className="flex-1 p-3"
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDropCanevas}
          data-testid="fb-canevas"
        >
          {schema.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Glissez un type de champ ici pour commencer.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {schema.map((champ, index) => (
                <LigneChamp
                  key={`${champ.nom}-${index}`}
                  champ={champ}
                  index={index}
                  autresChamps={schema
                    .filter((_, i) => i !== index)
                    .map((c) => c.nom)
                    .filter(Boolean)}
                  onChange={majChamp}
                  onSupprimer={supprimerChamp}
                  onDragStart={onDragStartChamp}
                  onDragOver={onDragOverChamp}
                  onDrop={onDropChamp}
                />
              ))}
            </div>
          )}
        </Card>

        <Card className="w-80 shrink-0 p-3" data-testid="fb-apercu">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Prévisualisation</p>
          <DynamicForm
            schema={schemaAvecConditions}
            champsConditionnels={champsConditionnelsApercu}
            valeurs={valeursApercu}
            onChange={(nomChamp, valeur) => setValeursApercu((v) => ({ ...v, [nomChamp]: valeur }))}
          />
        </Card>
      </div>
    </div>
  )
}

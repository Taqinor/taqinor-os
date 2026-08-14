// NTMFG27 — Assistant de création de gamme opératoire (« Nouvelle gamme
// guidée ») : produit → ajout d'opérations en liste RÉORDONNABLE (glisser-
// déposer, @dnd-kit/core déjà installé — seul le paquet `core` est présent
// dans ce dépôt, PAS `@dnd-kit/sortable` : le réordonnancement est donc
// implémenté à la main via `moveItem` + un couple `useDraggable`/
// `useDroppable` par ligne, pattern déjà en place côté KanbanView.jsx) →
// aperçu du temps total pour une quantité test → enregistrement (créé la
// `Gamme` NTMFG2 puis chaque `OperationGamme` dans l'ORDRE affiché — les
// endpoints existants n'exposent pas de création groupée atomique côté
// serveur ; Files de cette tâche = frontend seulement).
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DndContext, KeyboardSensor, PointerSensor, closestCenter, useDraggable,
  useDroppable, useSensor, useSensors,
} from '@dnd-kit/core'
import { CheckCircle2, GripVertical, ListPlus, Trash2, Wand2 } from 'lucide-react'
import mrpApi from '../../api/mrpApi'
import stockApi from '../../api/stockApi'
import { Badge, Button, Card, CardContent, Combobox, Input, Label, Spinner } from '../../ui'
import { PageHeader } from '../../ui/PageHeader'

let seq = 0
const nextKey = () => `assistant-gamme-op-${(seq += 1)}`

// Pure, testable sans simuler un vrai geste de glisser-déposer (jsdom ne
// prête pas aux pointer events de dnd-kit) : déplace l'élément `fromIndex`
// à `toIndex`, renvoie un NOUVEAU tableau (jamais de mutation en place).
export function moveItem(list, fromIndex, toIndex) {
  if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0
      || fromIndex >= list.length || toIndex >= list.length) {
    return list
  }
  const copie = list.slice()
  const [item] = copie.splice(fromIndex, 1)
  copie.splice(toIndex, 0, item)
  return copie
}

function OperationRow({ op, index, postes, onChange, onRemove }) {
  const { attributes, listeners, setNodeRef: setDragRef, isDragging } = useDraggable({ id: op.key })
  const { setNodeRef: setDropRef, isOver } = useDroppable({ id: op.key })

  return (
    <div
      ref={(node) => { setDragRef(node); setDropRef(node) }}
      className={`flex flex-wrap items-center gap-2 rounded-lg border p-2 ${isDragging ? 'opacity-50' : ''} ${isOver ? 'border-primary' : ''}`}
    >
      <button type="button" className="cursor-grab text-muted-foreground"
              aria-label={`Réordonner l'opération ${index + 1}`} {...listeners} {...attributes}>
        <GripVertical size={16} aria-hidden="true" />
      </button>
      <span className="text-sm text-muted-foreground w-5">{index + 1}.</span>
      <Input className="flex-1 min-w-[140px]" placeholder="Libellé de l'opération"
             value={op.libelle} onChange={(e) => onChange({ ...op, libelle: e.target.value })} />
      <select className="border rounded-md px-2 py-1.5 text-sm" value={op.poste_charge}
              onChange={(e) => onChange({ ...op, poste_charge: e.target.value })}>
        <option value="">— Poste —</option>
        {postes.map((p) => <option key={p.id} value={p.id}>{p.nom}</option>)}
      </select>
      <Input type="number" min="0" step="any" className="w-24" aria-label="Temps de préparation (min)"
             value={op.temps_prepa_min}
             onChange={(e) => onChange({ ...op, temps_prepa_min: e.target.value })} />
      <Input type="number" min="0" step="any" className="w-24" aria-label="Temps unitaire (min)"
             value={op.temps_unitaire_min}
             onChange={(e) => onChange({ ...op, temps_unitaire_min: e.target.value })} />
      <Button variant="ghost" size="icon" aria-label={`Retirer l'opération ${index + 1}`} onClick={onRemove}>
        <Trash2 size={16} />
      </Button>
    </div>
  )
}

export default function AssistantCreationGamme() {
  const navigate = useNavigate()

  const [produitId, setProduitId] = useState('')
  const [produitLabel, setProduitLabel] = useState('')
  const [nom, setNom] = useState('')
  const [postes, setPostes] = useState([])
  const [operations, setOperations] = useState([])
  const [quantiteTest, setQuantiteTest] = useState('1')
  const [saving, setSaving] = useState(false)
  const [erreur, setErreur] = useState(null)
  const [gammeCreee, setGammeCreee] = useState(null)

  useEffect(() => {
    mrpApi.getPostesCharge({ actif: true }).then((resp) => {
      setPostes(resp.data?.results || resp.data || [])
    })
  }, [])

  const onSearchProduit = async (query) => {
    const resp = await stockApi.getProduits({ search: query, page_size: 20 })
    const hits = resp.data?.results || resp.data || []
    return hits.map((p) => ({ value: String(p.id), label: p.nom }))
  }

  const ajouterOperation = () => {
    setOperations((ops) => [...ops, {
      key: nextKey(), libelle: '', poste_charge: '',
      temps_prepa_min: '0', temps_unitaire_min: '0',
    }])
  }

  const majOperation = (key, next) => {
    setOperations((ops) => ops.map((o) => (o.key === key ? next : o)))
  }

  const retirerOperation = (key) => {
    setOperations((ops) => ops.filter((o) => o.key !== key))
  }

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor),
  )

  const onDragEnd = (event) => {
    const { active, over } = event
    if (!over || active.id === over.id) return
    setOperations((ops) => {
      const from = ops.findIndex((o) => o.key === active.id)
      const to = ops.findIndex((o) => o.key === over.id)
      return moveItem(ops, from, to)
    })
  }

  const tempsTotalPrevisualise = useMemo(() => {
    const qte = Number(quantiteTest) || 0
    return operations.reduce((total, op) => {
      const prepa = Number(op.temps_prepa_min) || 0
      const unitaire = Number(op.temps_unitaire_min) || 0
      return total + prepa + unitaire * qte
    }, 0)
  }, [operations, quantiteTest])

  const peutEnregistrer = Boolean(produitId) && nom.trim().length > 0
    && operations.length > 0
    && operations.every((o) => o.libelle.trim() && o.poste_charge)

  const enregistrer = async () => {
    setSaving(true)
    setErreur(null)
    try {
      const gammeResp = await mrpApi.createGamme({ nom, produit: produitId })
      const gammeId = gammeResp.data.id
      for (let i = 0; i < operations.length; i += 1) {
        const op = operations[i]
        // eslint-disable-next-line no-await-in-loop -- ordre stable requis (ordre = i+1), pas de Promise.all.
        await mrpApi.createOperationGamme({
          gamme: gammeId, ordre: i + 1, poste_charge: op.poste_charge,
          libelle: op.libelle, temps_prepa_min: op.temps_prepa_min,
          temps_unitaire_min: op.temps_unitaire_min,
        })
      }
      setGammeCreee(gammeResp.data)
    } catch (err) {
      setErreur(err?.response?.data?.detail || 'Enregistrement de la gamme impossible.')
    } finally {
      setSaving(false)
    }
  }

  const recommencer = () => {
    setProduitId('')
    setProduitLabel('')
    setNom('')
    setOperations([])
    setQuantiteTest('1')
    setGammeCreee(null)
    setErreur(null)
  }

  return (
    <div>
      <PageHeader
        title="Nouvelle gamme guidée"
        subtitle="Construire une gamme opératoire, opération par opération, en un seul flux."
        icon={Wand2}
      />
      <Card>
        <CardContent className="pt-4">
          {gammeCreee ? (
            <div className="text-center py-6">
              <CheckCircle2 className="mx-auto mb-2 text-success" size={32} aria-hidden="true" />
              <p className="font-medium">Gamme « {gammeCreee.nom} » créée avec {operations.length} opération(s).</p>
              <div className="mt-4 flex justify-center gap-2">
                <Button variant="outline" onClick={recommencer}>Créer une autre gamme</Button>
                <Button onClick={() => navigate('/mrp/ordres-fabrication')}>
                  Voir les Ordres de fabrication
                </Button>
              </div>
            </div>
          ) : (
            <div className="grid gap-4">
              <div className="grid gap-3 max-w-md">
                <Label htmlFor="assistant-gamme-produit">Produit</Label>
                <Combobox
                  id="assistant-gamme-produit"
                  options={produitId ? [{ value: produitId, label: produitLabel }] : []}
                  value={produitId || null}
                  onSearch={onSearchProduit}
                  onChange={(v, opt) => { setProduitId(v || ''); setProduitLabel(opt?.label || '') }}
                  placeholder="Rechercher un produit…"
                  searchPlaceholder="Nom du produit…"
                />
                <Label htmlFor="assistant-gamme-nom">Nom de la gamme</Label>
                <Input id="assistant-gamme-nom" value={nom} onChange={(e) => setNom(e.target.value)}
                       placeholder="Ex. Gamme standard" />
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <Label>Opérations (glisser la poignée pour réordonner)</Label>
                  <Button type="button" variant="outline" size="sm" onClick={ajouterOperation}>
                    <ListPlus size={14} /> Ajouter une opération
                  </Button>
                </div>
                {operations.length === 0 && (
                  <p className="text-sm text-muted-foreground">Aucune opération — ajoutez-en au moins une.</p>
                )}
                {operations.length > 0 && (
                  <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                    <div className="grid gap-2">
                      {operations.map((op, i) => (
                        <OperationRow
                          key={op.key} op={op} index={i} postes={postes}
                          onChange={(next) => majOperation(op.key, next)}
                          onRemove={() => retirerOperation(op.key)}
                        />
                      ))}
                    </div>
                  </DndContext>
                )}
              </div>

              <div className="flex items-center gap-3 max-w-sm">
                <Label htmlFor="assistant-gamme-qte" className="shrink-0">Quantité test</Label>
                <Input id="assistant-gamme-qte" type="number" min="1" step="any"
                       value={quantiteTest} onChange={(e) => setQuantiteTest(e.target.value)} />
                <Badge tone="info">Temps total ≈ {tempsTotalPrevisualise} min</Badge>
              </div>

              {erreur && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
                  {erreur}
                </div>
              )}

              <div className="flex justify-end">
                {saving ? <Spinner /> : (
                  <Button disabled={!peutEnregistrer} onClick={enregistrer}>
                    Enregistrer la gamme
                  </Button>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

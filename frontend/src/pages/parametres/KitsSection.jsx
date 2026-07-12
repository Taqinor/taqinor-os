// F2 — Onglet « Kits d'outillage » de la page Paramètres : modèles NOMMÉS et
// réutilisables de kits, chacun une liste ordonnée d'outils du catalogue
// Outillage, éventuellement associé à un type d'intervention qui le
// pré-sélectionne. Les 3 kits par défaut (pose structure / raccordement /
// mise en service) sont semés au premier chargement et restent pleinement
// éditables (renommer / réordonner / désactiver). Désactiver préserve la
// valeur sur les enregistrements historiques.
//
// Section autonome : charge ses propres données et s'enregistre seule (sans le
// bouton « Enregistrer » global). Texte en français ; clés techniques en anglais.
import { useEffect, useState } from 'react'
import { Plus, Trash2, ChevronUp, ChevronDown, AlertCircle } from 'lucide-react'
import { toast } from '../../ui/confirm'
import outillageApi from '../../api/outillageApi'
import installationsApi from '../../api/installationsApi'
import {
  Card, CardContent, Input, Button, IconButton, Badge, Spinner, EmptyState,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle } from './peComponents'

const NONE = '__none__'

export default function KitsSection() {
  const [kits, setKits] = useState([])
  const [outils, setOutils] = useState([])
  const [types, setTypes] = useState([])
  const [loading, setLoading] = useState(true)
  // ERR62 — un échec de chargement affiche une erreur + Réessayer (pas un état
  // « vide » trompeur faisant croire qu'aucun kit n'existe).
  const [loadError, setLoadError] = useState(false)
  const [newKit, setNewKit] = useState('')
  const [newType, setNewType] = useState(NONE)
  const [newItem, setNewItem] = useState({}) // { [kitId]: outilId }

  const load = () => outillageApi.getKits()
    .then((r) => { setKits(r.data.results ?? r.data); setLoadError(false) })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  useEffect(() => {
    load()
    outillageApi.getOutils()
      .then((r) => setOutils(r.data.results ?? r.data))
      .catch(() => {})
    installationsApi.getTypesIntervention()
      .then((r) => setTypes((r.data.results ?? r.data).filter((t) => !t.archived)))
      .catch(() => {})
  }, [])

  const typeLabel = (cle) => types.find((t) => t.cle === cle)?.libelle ?? cle
  const outilNom = (id) => outils.find((o) => o.id === id)?.nom ?? `#${id}`

  // ── Kits ──
  const addKit = async () => {
    const nom = newKit.trim()
    if (!nom) return
    try {
      await outillageApi.saveKit(null, {
        nom, type_intervention: newType === NONE ? '' : newType, ordre: kits.length,
      })
      setNewKit(''); setNewType(NONE); load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
  }
  const renameKit = async (k, nom) => {
    if (!nom.trim() || nom === k.nom) return
    try { await outillageApi.saveKit(k.id, { nom }); load() } catch { /* */ }
  }
  const setKitType = async (k, type) => {
    try {
      await outillageApi.saveKit(k.id, { type_intervention: type === NONE ? '' : type })
      load()
    } catch { /* */ }
  }
  const toggleKitActif = async (k) => {
    try { await outillageApi.saveKit(k.id, { actif: !k.actif }); load() } catch { /* */ }
  }
  const moveKit = async (idx, dir) => {
    const j = idx + dir
    if (j < 0 || j >= kits.length) return
    const a = kits[idx]; const b = kits[j]
    try {
      await Promise.all([
        outillageApi.saveKit(a.id, { ordre: b.ordre }),
        outillageApi.saveKit(b.id, { ordre: a.ordre }),
      ])
      load()
    } catch { /* */ }
  }
  const delKit = async (k) => {
    if (!window.confirm(`Supprimer le kit « ${k.nom} » et sa liste d'outils ?`)) return
    try { await outillageApi.deleteKit(k.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }

  // ── Outils d'un kit ──
  const addItem = async (k) => {
    const outil = newItem[k.id]
    if (!outil) return
    try {
      await outillageApi.saveKitItem(null, {
        kit: k.id, outil: Number(outil), ordre: (k.items ?? []).length,
      })
      setNewItem((p) => ({ ...p, [k.id]: undefined })); load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible (outil déjà dans le kit ?).') }
  }
  const moveItem = async (k, idx, dir) => {
    const items = k.items ?? []
    const j = idx + dir
    if (j < 0 || j >= items.length) return
    const a = items[idx]; const b = items[j]
    try {
      await Promise.all([
        outillageApi.saveKitItem(a.id, { ordre: b.ordre }),
        outillageApi.saveKitItem(b.id, { ordre: a.ordre }),
      ])
      load()
    } catch { /* */ }
  }
  const delItem = async (it) => {
    try { await outillageApi.deleteKitItem(it.id); load() } catch { /* */ }
  }

  // Outils disponibles à l'ajout dans un kit (hors ceux déjà présents).
  const availableFor = (k) => {
    const used = new Set((k.items ?? []).map((it) => it.outil))
    return outils.filter((o) => !used.has(o.id))
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
        Kits d'outillage indisponibles (serveur ?).
      </p>
      <Button type="button" size="sm" variant="outline" onClick={load}>Réessayer</Button>
    </div>
  )

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Kits d'outillage"
          icon={<><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></>}/>
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Composez des kits d'outillage nommés (liste ordonnée d'outils du
          catalogue) et associez chacun à un type d'intervention : il sera
          pré-sélectionné à la préparation d'une intervention de ce type.
          Désactiver un kit le retire des nouvelles préparations sans toucher à
          l'historique. L'outillage durable n'est jamais du stock vendable.
        </p>

        <div className="flex flex-col gap-3">
          {kits.length === 0 && (
            <EmptyState title="Aucun kit"
              description="Ajoutez votre premier kit d'outillage ci-dessous." className="py-6" />
          )}
          {kits.map((k, ki) => (
            <div key={k.id} className="rounded-lg border border-border p-3">
              {/* En-tête du kit */}
              <div className="mb-2.5 flex flex-wrap items-center gap-1.5">
                {/* ERR102 — re-monte le champ si le serveur normalise le nom. */}
                <Input key={k.nom} className={['min-w-[140px] flex-[1_1_140px] font-medium', k.actif ? '' : 'opacity-50'].join(' ')}
                  defaultValue={k.nom} onBlur={(e) => renameKit(k, e.target.value)} />
                <div className="w-[200px]">
                  <Select value={k.type_intervention || NONE} onValueChange={(v) => setKitType(k, v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NONE}>Tout type d'intervention</SelectItem>
                      {types.map((t) => (
                        <SelectItem key={t.cle} value={t.cle}>{t.libelle}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="ml-auto flex items-center gap-1">
                  <IconButton size="sm" variant="ghost" label="Monter"
                    disabled={ki === 0} onClick={() => moveKit(ki, -1)}>
                    <ChevronUp className="size-4" aria-hidden="true" />
                  </IconButton>
                  <IconButton size="sm" variant="ghost" label="Descendre"
                    disabled={ki === kits.length - 1} onClick={() => moveKit(ki, 1)}>
                    <ChevronDown className="size-4" aria-hidden="true" />
                  </IconButton>
                  <Button type="button" size="sm"
                    variant={k.actif ? 'success' : 'secondary'}
                    title={k.actif ? 'Désactiver' : 'Activer'}
                    onClick={() => toggleKitActif(k)}>
                    {k.actif ? 'Actif' : 'Inactif'}
                  </Button>
                  <IconButton size="sm" variant="outline" label="Supprimer le kit"
                    className="text-destructive hover:text-destructive"
                    onClick={() => delKit(k)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                </div>
              </div>

              {/* Outils du kit */}
              {(k.items ?? []).length === 0 && (
                <p className="mb-1.5 text-[12px] text-muted-foreground">Aucun outil dans ce kit.</p>
              )}
              {(k.items ?? []).map((it, ii) => (
                <div key={it.id} className="mb-1.5 flex flex-wrap items-center gap-1.5">
                  <span className="min-w-[120px] flex-[1_1_120px] text-sm">{it.outil_nom ?? outilNom(it.outil)}</span>
                  <IconButton size="sm" variant="ghost" label="Monter l'outil"
                    disabled={ii === 0} onClick={() => moveItem(k, ii, -1)}>
                    <ChevronUp className="size-4" aria-hidden="true" />
                  </IconButton>
                  <IconButton size="sm" variant="ghost" label="Descendre l'outil"
                    disabled={ii === (k.items ?? []).length - 1} onClick={() => moveItem(k, ii, 1)}>
                    <ChevronDown className="size-4" aria-hidden="true" />
                  </IconButton>
                  <IconButton size="sm" variant="outline" label="Retirer l'outil"
                    className="text-destructive hover:text-destructive" onClick={() => delItem(it)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                </div>
              ))}

              {/* Ajout d'un outil au kit */}
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                <div className="min-w-[160px] flex-1">
                  <Select value={newItem[k.id] ? String(newItem[k.id]) : ''}
                    onValueChange={(v) => setNewItem((p) => ({ ...p, [k.id]: v }))}>
                    <SelectTrigger>
                      <SelectValue placeholder={outils.length ? 'Ajouter un outil…' : 'Aucun outil au catalogue'} />
                    </SelectTrigger>
                    <SelectContent>
                      {availableFor(k).map((o) => (
                        <SelectItem key={o.id} value={String(o.id)}>{o.nom}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button type="button" size="sm" disabled={!newItem[k.id]} onClick={() => addItem(k)}>
                  <Plus className="size-4" aria-hidden="true" /> Outil
                </Button>
              </div>
              {k.type_intervention && (
                <Badge tone="info" className="mt-2">Auto : {typeLabel(k.type_intervention)}</Badge>
              )}
            </div>
          ))}
        </div>

        {/* ── Ajout d'un kit ── */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Input className="min-w-[160px] flex-[1_1_160px]" placeholder="Nouveau kit d'outillage"
            value={newKit} onChange={(e) => setNewKit(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addKit() } }} />
          <div className="w-[200px]">
            <Select value={newType} onValueChange={setNewType}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>Tout type d'intervention</SelectItem>
                {types.map((t) => (
                  <SelectItem key={t.cle} value={t.cle}>{t.libelle}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button type="button" onClick={addKit}>
            <Plus className="size-4" aria-hidden="true" /> Ajouter
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

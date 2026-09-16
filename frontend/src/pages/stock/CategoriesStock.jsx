import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { useHasPermission, useIsAdmin, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { Plus, Trash2, Save, Boxes,
} from 'lucide-react'
import stockApi from '../../api/stockApi'
import {
  Button, IconButton, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
// APX24 — en-tête UNIQUE de l'app (VX28) + accent de la famille inventaire :
// les 15 écrans Stock parlaient chacun leur propre idiome d'en-tête.
import { PageHeader } from '../../ui/PageHeader'
import { INVENTAIRE_ACCENT } from '../../features/stock/inventaireAccent'

// L693/L694 — Écran de gestion des CATÉGORIES (renommer / ordre / type
// d'équipement) et des MARQUES produit. Le free-text par société est préservé :
// le tag « type d'équipement » est optionnel (None = catégorie non typée,
// comportement historique). Une marque utilisée par des produits ne peut pas
// être supprimée (le backend renvoie 409) — on affiche alors « archivez-la
// plutôt » au lieu d'une erreur brute.

// Types d'équipement — alignés sur stock.Categorie.TypeEquipement (backend).
// `__none` = sentinelle d'ecran (« Non typee »), jamais envoyee telle quelle.
// source-choix: stock.Categorie.type_equipement +__none
const TYPES_EQUIPEMENT = [
  { value: '__none', label: '— Non typée —' },
  { value: 'panneau', label: 'Panneau' },
  { value: 'onduleur', label: 'Onduleur' },
  { value: 'batterie', label: 'Batterie' },
  { value: 'structure', label: 'Structure' },
  { value: 'cable', label: 'Câble' },
  { value: 'protection', label: 'Protection' },
  { value: 'pompe', label: 'Pompe' },
  { value: 'variateur', label: 'Variateur' },
  { value: 'compteur', label: 'Compteur' },
  { value: 'accessoire', label: 'Accessoire' },
  // STKCAT2 — « Services & prestations » n'est pas un équipement : sans cette
  // valeur, la catégorie restait NULL (indistinguable d'une non typée).
  { value: 'service', label: 'Service' },
]

// STKCAT5 — assistant « Typer mes catégories ». Table nom exact → type,
// MIROIR de `seed_catalogue.TYPES_PAR_CATEGORIE` (backend, STKCAT3) : les
// mêmes noms exacts de la taxonomie seedée suggèrent le même type. Une
// SUGGESTION seulement — rien n'est jamais écrit sans un clic « Accepter ».
const TYPE_PAR_NOM_EXACT = {
  'Panneaux photovoltaïques': 'panneau',
  'Onduleurs réseau': 'onduleur',
  'Onduleurs hybrides': 'onduleur',
  'Onduleurs hors réseau': 'onduleur',
  'Batteries': 'batterie',
  'Structures & fixation': 'structure',
  'Protection & accessoires': 'protection',
  'Câbles': 'cable',
  'Pompes': 'pompe',
  'Variateurs': 'variateur',
  'Services & prestations': 'service',
  // Les trois catégories du jeu de démonstration (`seed_demo`), mêmes noms
  // que côté backend.
  'Panneaux solaires': 'panneau',
  'Onduleurs': 'onduleur',
  'Accessoires': 'accessoire',
}

// Repli mots-clés pour une catégorie libre (renommée ou créée par une
// société, absente de la taxonomie seedée ci-dessus). Un mot-clé sans
// ambiguïté suffit ; tout le reste retombe sur « aucune suggestion » —
// jamais un type deviné par ressemblance approximative.
const MOTCLES_PAR_TYPE = [
  [/panneau|module/i, 'panneau'],
  [/onduleur/i, 'onduleur'],
  [/batterie/i, 'batterie'],
  [/structure|fixation|pergola|carport/i, 'structure'],
  [/c[âa]ble/i, 'cable'],
  [/pompe/i, 'pompe'],
  [/variateur/i, 'variateur'],
  [/protection|disjoncteur|parafoudre|coffret/i, 'protection'],
  [/service|prestation|installation|pose/i, 'service'],
  [/compteur|smart meter/i, 'compteur'],
  [/accessoire/i, 'accessoire'],
]

function suggestionTypePourNom(nom) {
  const n = (nom ?? '').trim()
  if (!n) return null
  if (TYPE_PAR_NOM_EXACT[n]) return TYPE_PAR_NOM_EXACT[n]
  for (const [motif, type] of MOTCLES_PAR_TYPE) {
    if (motif.test(n)) return type
  }
  return null
}

function labelDuType(type) {
  return TYPES_EQUIPEMENT.find((t) => t.value === type)?.label ?? null
}

// Extrait un message FR lisible d'une erreur DRF (jamais de JSON brut).
function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  for (const v of Object.values(data)) {
    const m = Array.isArray(v) ? v[0] : v
    if (typeof m === 'string') return m
  }
  return fallback
}

export default function CategoriesStock() {
  // ARC47 — gating via le hook partagé. `hasFinePermissions` (présence de
  // codes ERP, PAS un droit) choisit la branche ; les deux hooks sont appelés
  // inconditionnellement (règle des hooks). Sémantique identique à l'origine.
  const hasFinePermissions = useSelector((s) => (s.auth.permissions || []).length > 0)
  const canWriteViaPerm = useHasPermission('stock_modifier')
  const canWriteViaRole = useIsAdminOrResponsable()
  const canWrite = hasFinePermissions ? canWriteViaPerm : canWriteViaRole
  const canDelete = useIsAdmin()

  const [categories, setCategories] = useState([])
  const [marques, setMarques] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)

  // Brouillons d'édition catégorie : { [id]: { nom, ordre, type_equipement } }
  const [drafts, setDrafts] = useState({})
  const [newCat, setNewCat] = useState('')
  const [newCatType, setNewCatType] = useState('__none')
  const [newCatOrdre, setNewCatOrdre] = useState(100)
  const [newMarque, setNewMarque] = useState('')
  const [savingId, setSavingId] = useState(null)
  // STKCAT5 — assistant « Typer mes catégories ».
  const [acceptingId, setAcceptingId] = useState(null)
  const [acceptingAll, setAcceptingAll] = useState(false)

  // STKCAT5 — compteur de produits par catégorie : dérivé du `produits` déjà
  // chargé ailleurs dans le slice stock (aucun nouvel appel réseau ici — si
  // la liste produit n'a pas encore été visitée, le compteur affiche 0).
  const produits = useSelector((s) => s.stock.produits ?? [])
  const nbProduitsParCategorie = useMemo(() => {
    const m = {}
    for (const p of produits) {
      if (p.is_archived) continue
      const id = p.categorie?.id
      if (id == null) continue
      m[id] = (m[id] ?? 0) + 1
    }
    return m
  }, [produits])

  const loadCategories = () =>
    stockApi.getCategories({ ordering: 'ordre' })
      .then((r) => setCategories(r.data?.results ?? r.data ?? []))
  const loadMarques = () =>
    stockApi.getMarques().then((r) => setMarques(r.data?.results ?? r.data ?? []))

  useEffect(() => {
    Promise.all([loadCategories(), loadMarques()])
      .catch(() => setError('Chargement impossible.'))
      .finally(() => setLoading(false))
  }, [])

  const baseDraft = (c) => ({
    nom: c.nom ?? '',
    ordre: c.ordre ?? 100,
    type_equipement: c.type_equipement ?? '__none',
  })
  const draftFor = (c) => drafts[c.id] ?? baseDraft(c)
  const setDraft = (id, patch) =>
    setDrafts((d) => {
      const cat = categories.find((c) => c.id === id)
      const current = d[id] ?? (cat ? baseDraft(cat) : {})
      return { ...d, [id]: { ...current, ...patch } }
    })

  const isDirty = (c) => {
    const d = drafts[c.id]
    if (!d) return false
    return d.nom !== (c.nom ?? '')
      || String(d.ordre) !== String(c.ordre ?? 100)
      || (d.type_equipement ?? '__none') !== (c.type_equipement ?? '__none')
  }

  const saveCategorie = async (c) => {
    const d = draftFor(c)
    const nom = (d.nom ?? '').trim()
    if (!nom) { setError('Le nom de la catégorie est requis.'); return }
    setError(null); setInfo(null); setSavingId(c.id)
    try {
      await stockApi.patchCategorie(c.id, {
        nom,
        ordre: Number(d.ordre) || 0,
        type_equipement: d.type_equipement === '__none' ? null : d.type_equipement,
      })
      setDrafts((dd) => { const next = { ...dd }; delete next[c.id]; return next })
      await loadCategories()
      setInfo('Catégorie enregistrée.')
    } catch (err) {
      setError(frErr(err, "L'enregistrement de la catégorie a échoué."))
    } finally { setSavingId(null) }
  }

  const addCategorie = async () => {
    const nom = newCat.trim()
    if (!nom) return
    setError(null); setInfo(null)
    try {
      await stockApi.createCategorie({
        nom,
        type_equipement: newCatType === '__none' ? null : newCatType,
        ordre: Number(newCatOrdre) || 100,
      })
      setNewCat('')
      setNewCatType('__none')
      setNewCatOrdre(100)
      await loadCategories()
    } catch (err) { setError(frErr(err, "L'ajout de la catégorie a échoué.")) }
  }

  // STKCAT5 — assistant « Typer mes catégories » : PATCH le type suggéré
  // (jamais autre chose) sur une catégorie non typée, une par une, sans
  // jamais écrire une suggestion qui n'a pas été explicitement acceptée.
  const acceptSuggestion = async (c, type) => {
    setError(null); setInfo(null)
    setAcceptingId(c.id)
    try {
      await stockApi.patchCategorie(c.id, { type_equipement: type })
      await loadCategories()
    } catch (err) {
      setError(frErr(err, "L'application de la suggestion a échoué."))
    } finally { setAcceptingId(null) }
  }

  const acceptAllSuggestions = async (rows) => {
    setError(null); setInfo(null)
    setAcceptingAll(true)
    let done = 0
    try {
      // Une par une, délibéré (PATCH séquentiel, jamais en rafale parallèle).
      for (const { categorie, type } of rows) {
        await stockApi.patchCategorie(categorie.id, { type_equipement: type })
        done += 1
      }
      setInfo(`${done} catégorie(s) typée(s).`)
    } catch (err) {
      // Un PATCH en échec n'annule pas les précédents : `loadCategories()`
      // (ci-dessous, hors du try) reflète toujours ce qui a réellement été
      // écrit avant l'échec.
      setError(frErr(err, "L'application des suggestions a échoué."))
    } finally {
      await loadCategories()
      setAcceptingAll(false)
    }
  }

  const delCategorie = async (c) => {
    if (!window.confirm(`Supprimer la catégorie « ${c.nom} » ?`)) return
    setError(null); setInfo(null)
    try {
      await stockApi.deleteCategorie(c.id)
      await loadCategories()
    } catch (err) {
      // Une catégorie reliée à des produits peut être protégée côté serveur.
      setError(frErr(err, 'Suppression impossible (catégorie utilisée).'))
    }
  }

  const addMarque = async () => {
    const nom = newMarque.trim()
    if (!nom) return
    setError(null); setInfo(null)
    try {
      await stockApi.saveMarque(null, { nom })
      setNewMarque('')
      await loadMarques()
    } catch (err) { setError(frErr(err, "L'ajout de la marque a échoué.")) }
  }

  // L694 — supprimer une marque en usage est refusé (409) : on affiche le
  // message FR « archivez-la plutôt » plutôt qu'une erreur brute.
  const delMarque = async (m) => {
    if (m.en_usage > 0) {
      setError(`La marque « ${m.nom} » est utilisée par ${m.en_usage} produit(s) — archivez-la plutôt.`)
      return
    }
    if (!window.confirm(`Supprimer la marque « ${m.nom} » ?`)) return
    setError(null); setInfo(null)
    try {
      await stockApi.deleteMarque(m.id)
      await loadMarques()
    } catch (err) {
      setError(frErr(err, 'Suppression impossible — archivez la marque plutôt.'))
    }
  }

  const sortedCategories = useMemo(
    () => [...categories].sort((a, b) => (a.ordre ?? 999) - (b.ordre ?? 999) || (a.nom ?? '').localeCompare(b.nom ?? '')),
    [categories])

  // STKCAT5 — catégories non typées + leur suggestion dérivée du nom.
  const suggestionsNonTypees = useMemo(
    () => sortedCategories
      .filter((c) => !c.type_equipement)
      .map((c) => ({ categorie: c, type: suggestionTypePourNom(c.nom) })),
    [sortedCategories])
  const suggestionsAvecType = useMemo(
    () => suggestionsNonTypees.filter((r) => r.type),
    [suggestionsNonTypees])

  return (
    <div className="ui-root flex flex-col gap-5 px-4 py-5 sm:px-5">
      <PageHeader
        style={{ '--module-accent': INVENTAIRE_ACCENT }}
        className="app-accent-rail mb-0"
        headingAs="h1"
        icon={Boxes}
        title="Catégories & marques"
        subtitle="Gérez les catégories du catalogue (nom, ordre d'affichage, type d'équipement) et les marques produit."
      />

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}
      {info && (
        <div className="rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
          {info}
        </div>
      )}

      {/* ── Catégories ── */}
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold">Catégories produit</h2>

        {/* STKCAT5 — assistant « Typer mes catégories » : une suggestion
            dérivée du nom pour chaque catégorie non typée, rien n'est écrit
            sans un clic « Accepter » (individuel ou groupé). */}
        {suggestionsNonTypees.length > 0 && (
          <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold">
                Typer mes catégories — {suggestionsNonTypees.length} catégorie(s) non typée(s)
              </p>
              {canWrite && suggestionsAvecType.length > 0 && (
                <Button type="button" size="sm" loading={acceptingAll}
                        disabled={acceptingAll || acceptingId != null}
                        onClick={() => acceptAllSuggestions(suggestionsAvecType)}>
                  Accepter tout ({suggestionsAvecType.length})
                </Button>
              )}
            </div>
            <ul className="flex flex-col gap-1.5">
              {suggestionsNonTypees.map(({ categorie: c, type }) => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-2">
                  <span>
                    <strong>{c.nom}</strong>
                    {' — '}
                    {type ? `suggestion : ${labelDuType(type)}` : 'aucune suggestion'}
                  </span>
                  {canWrite && type && (
                    <Button type="button" variant="outline" size="sm"
                            loading={acceptingId === c.id}
                            disabled={acceptingAll || (acceptingId != null && acceptingId !== c.id)}
                            onClick={() => acceptSuggestion(c, type)}>
                      Accepter
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[40rem] text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Nom</th>
                <th className="px-3 py-2 text-left font-semibold" style={{ width: 110 }}>Ordre</th>
                <th className="px-3 py-2 text-left font-semibold" style={{ width: 200 }}>Type d&apos;équipement</th>
                <th className="px-3 py-2 text-left font-semibold" style={{ width: 90 }}>Produits</th>
                <th className="w-28 px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={5} className="px-3 py-4 text-muted-foreground">Chargement…</td></tr>
              )}
              {!loading && sortedCategories.length === 0 && (
                <tr><td colSpan={5} className="px-3 py-4 text-muted-foreground">Aucune catégorie.</td></tr>
              )}
              {sortedCategories.map((c) => {
                const d = draftFor(c)
                return (
                  <tr key={c.id} className="border-t border-border">
                    <td className="px-3 py-2">
                      <Input className="h-9" value={d.nom} disabled={!canWrite}
                             onChange={(e) => setDraft(c.id, { nom: e.target.value })} />
                    </td>
                    <td className="px-3 py-2">
                      <Input type="number" step="any" inputMode="numeric" className="h-9 w-20"
                             value={d.ordre} disabled={!canWrite}
                             onChange={(e) => setDraft(c.id, { ordre: e.target.value })} />
                    </td>
                    <td className="px-3 py-2">
                      <Select value={d.type_equipement || '__none'} disabled={!canWrite}
                              onValueChange={(v) => setDraft(c.id, { type_equipement: v })}>
                        <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
                        <SelectContent>
                          {TYPES_EQUIPEMENT.map((t) => (
                            <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {nbProduitsParCategorie[c.id] ?? 0}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        {canWrite && (
                          <IconButton size="md" variant="outline" label="Enregistrer la catégorie"
                                      disabled={!isDirty(c) || savingId === c.id}
                                      onClick={() => saveCategorie(c)}>
                            <Save className="size-4" aria-hidden="true" />
                          </IconButton>
                        )}
                        {canDelete && (
                          <IconButton size="md" variant="outline" label="Supprimer la catégorie"
                                      className="text-destructive hover:text-destructive"
                                      onClick={() => delCategorie(c)}>
                            <Trash2 className="size-4" aria-hidden="true" />
                          </IconButton>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {canWrite && (
          <div className="flex flex-wrap items-center gap-2">
            <Input className="h-9 w-56" placeholder="Nouvelle catégorie" value={newCat}
                   onChange={(e) => setNewCat(e.target.value)}
                   onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCategorie() } }} />
            {/* Type + ordre en un geste (STKCAT5) — la valeur par défaut
                (« Non typée », 100) garde le chemin rapide « juste un nom »
                utilisable exactement comme avant. */}
            <Select value={newCatType} onValueChange={setNewCatType}>
              <SelectTrigger className="h-9 w-44"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TYPES_EQUIPEMENT.map((t) => (
                  <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input type="number" step="any" inputMode="numeric" className="h-9 w-20"
                   value={newCatOrdre} onChange={(e) => setNewCatOrdre(e.target.value)} />
            <Button type="button" onClick={addCategorie}><Plus className="size-4" aria-hidden="true" /> Ajouter</Button>
          </div>
        )}
      </section>

      {/* ── Marques ── */}
      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold">Marques produit</h2>
        <p className="text-[12px] text-muted-foreground">
          Une marque utilisée par des produits ne peut pas être supprimée — archivez-la plutôt.
        </p>
        <div className="flex max-w-md flex-col gap-1.5">
          {marques.map((m) => (
            <div key={m.id} className="flex items-center gap-1.5">
              <Input className="flex-1 h-9" defaultValue={m.nom} readOnly />
              {m.en_usage > 0 && (
                <span className="shrink-0 text-xs text-muted-foreground">{m.en_usage} produit(s)</span>
              )}
              {canDelete && (
                <IconButton size="md" variant="outline" label="Supprimer la marque"
                            className="text-destructive hover:text-destructive disabled:text-muted-foreground"
                            disabled={m.en_usage > 0}
                            title={m.en_usage > 0 ? 'Marque utilisée — archivez-la plutôt' : 'Supprimer'}
                            onClick={() => delMarque(m)}>
                  <Trash2 className="size-4" aria-hidden="true" />
                </IconButton>
              )}
            </div>
          ))}
          {!loading && marques.length === 0 && (
            <p className="text-sm text-muted-foreground">Aucune marque.</p>
          )}
        </div>
        {canWrite && (
          <div className="flex max-w-md gap-2">
            <Input className="flex-1" placeholder="Nouvelle marque" value={newMarque}
                   onChange={(e) => setNewMarque(e.target.value)}
                   onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addMarque() } }} />
            <Button type="button" onClick={addMarque}><Plus className="size-4" aria-hidden="true" /> Ajouter</Button>
          </div>
        )}
      </section>
    </div>
  )
}

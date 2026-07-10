import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { useHasPermission, useIsAdmin, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { Plus, Trash2, Save } from 'lucide-react'
import stockApi from '../../api/stockApi'
import {
  Button, IconButton, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

// L693/L694 — Écran de gestion des CATÉGORIES (renommer / ordre / type
// d'équipement) et des MARQUES produit. Le free-text par société est préservé :
// le tag « type d'équipement » est optionnel (None = catégorie non typée,
// comportement historique). Une marque utilisée par des produits ne peut pas
// être supprimée (le backend renvoie 409) — on affiche alors « archivez-la
// plutôt » au lieu d'une erreur brute.

// Types d'équipement — alignés sur stock.Categorie.TypeEquipement (backend).
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
]

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
  const [newMarque, setNewMarque] = useState('')
  const [savingId, setSavingId] = useState(null)

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
      await stockApi.createCategorie({ nom })
      setNewCat('')
      await loadCategories()
    } catch (err) { setError(frErr(err, "L'ajout de la catégorie a échoué.")) }
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

  return (
    <div className="ui-root flex flex-col gap-5 px-4 py-5 sm:px-5">
      <header>
        <h1 className="font-display text-xl font-semibold tracking-tight">Catégories &amp; marques</h1>
        <p className="text-sm text-muted-foreground">
          Gérez les catégories du catalogue (nom, ordre d&apos;affichage, type d&apos;équipement)
          et les marques produit.
        </p>
      </header>

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
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[40rem] text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Nom</th>
                <th className="px-3 py-2 text-left font-semibold" style={{ width: 110 }}>Ordre</th>
                <th className="px-3 py-2 text-left font-semibold" style={{ width: 200 }}>Type d&apos;équipement</th>
                <th className="w-28 px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={4} className="px-3 py-4 text-muted-foreground">Chargement…</td></tr>
              )}
              {!loading && sortedCategories.length === 0 && (
                <tr><td colSpan={4} className="px-3 py-4 text-muted-foreground">Aucune catégorie.</td></tr>
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
          <div className="flex max-w-md gap-2">
            <Input className="flex-1" placeholder="Nouvelle catégorie" value={newCat}
                   onChange={(e) => setNewCat(e.target.value)}
                   onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCategorie() } }} />
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

import { useEffect, useState } from 'react'
import { Card, Badge, Button, EmptyState, Spinner, Input, toast } from '../../ui'
import hospitalityApi from '../../api/hospitalityApi'

/* ============================================================================
   WIR146 — Recettes / menu (NTHOT13). Fiches techniques de plats + gestion
   des ingrédients (sous-ressource dédiée, jamais imbriquée dans le corps de
   la fiche). Backend complet et testé, aucun écran ne le consommait avant ce
   lot.
   ========================================================================== */

const CATEGORIES = [
  { value: 'entree', label: 'Entrée' },
  { value: 'plat', label: 'Plat' },
  { value: 'dessert', label: 'Dessert' },
  { value: 'boisson', label: 'Boisson' },
]

const CATEGORIE_TONE = { entree: 'info', plat: 'success', dessert: 'warning', boisson: 'neutral' }

const FORME_VIDE = { nom_plat: '', categorie_menu: 'plat', prix_vente_ht: '', description: '' }

function IngredientsPanel({ recette }) {
  const [ingredients, setIngredients] = useState(null)
  const [form, setForm] = useState({ produit: '', quantite: '', unite: '' })
  const [saving, setSaving] = useState(false)

  const load = () => {
    hospitalityApi
      .listIngredientsRecette(recette.id)
      .then((res) => setIngredients(res.data?.results ?? res.data ?? []))
      .catch(() => toast.error('Ingrédients indisponibles.'))
  }

  useEffect(() => { load() }, [recette.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const ajouter = (e) => {
    e.preventDefault()
    if (!form.produit || !form.quantite) return
    setSaving(true)
    hospitalityApi
      .ajouterIngredientRecette(recette.id, form)
      .then(() => {
        toast.success('Ingrédient ajouté.')
        setForm({ produit: '', quantite: '', unite: '' })
        load()
      })
      .catch(() => toast.error("Impossible d'ajouter cet ingrédient."))
      .finally(() => setSaving(false))
  }

  const retirer = (ingredientId) => {
    hospitalityApi
      .retirerIngredientRecette(recette.id, ingredientId)
      .then(() => load())
      .catch(() => toast.error("Impossible de retirer l'ingrédient."))
  }

  return (
    <div className="flex flex-col gap-2 border-t border-border pt-2">
      <form onSubmit={ajouter} className="flex flex-wrap items-end gap-2">
        <Input
          aria-label="ID produit (stock)" placeholder="ID produit (stock)"
          value={form.produit} onChange={(e) => setForm({ ...form, produit: e.target.value })}
        />
        <Input
          aria-label="Quantité" placeholder="Quantité"
          value={form.quantite} onChange={(e) => setForm({ ...form, quantite: e.target.value })}
        />
        <Input
          aria-label="Unité" placeholder="Unité (kg, L…)"
          value={form.unite} onChange={(e) => setForm({ ...form, unite: e.target.value })}
        />
        <Button type="submit" disabled={saving}>Ajouter</Button>
      </form>
      {ingredients === null && <p className="text-sm text-muted-foreground">Chargement…</p>}
      {ingredients && ingredients.length === 0 && (
        <p className="text-sm text-muted-foreground">Aucun ingrédient.</p>
      )}
      {ingredients && ingredients.map((ing) => (
        <div key={ing.id} className="flex items-center justify-between text-sm">
          <span>{ing.produit_nom || `Produit #${ing.produit}`} — {ing.quantite} {ing.unite}</span>
          <Button variant="outline" onClick={() => retirer(ing.id)}>Retirer</Button>
        </div>
      ))}
    </div>
  )
}

export default function Recettes() {
  const [recettes, setRecettes] = useState(null)
  const [error, setError] = useState(null)
  const [form, setForm] = useState(FORME_VIDE)
  const [saving, setSaving] = useState(false)
  const [ouverte, setOuverte] = useState(null)

  const load = () => {
    hospitalityApi
      .listRecettes()
      .then((res) => setRecettes(res.data?.results ?? res.data ?? []))
      .catch(() => setError('Recettes indisponibles.'))
  }

  useEffect(() => { load() }, [])

  const creer = (e) => {
    e.preventDefault()
    if (!form.nom_plat.trim()) return
    setSaving(true)
    hospitalityApi
      .createRecette(form)
      .then(() => {
        toast.success('Recette créée.')
        setForm(FORME_VIDE)
        load()
      })
      .catch(() => toast.error('Impossible de créer la recette.'))
      .finally(() => setSaving(false))
  }

  if (error) return <EmptyState title="Recettes indisponibles" description={error} />

  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-4">
        <form onSubmit={creer} className="flex flex-wrap items-end gap-2">
          <Input
            aria-label="Nom du plat" placeholder="Nom du plat"
            value={form.nom_plat} onChange={(e) => setForm({ ...form, nom_plat: e.target.value })}
          />
          <select
            aria-label="Catégorie" value={form.categorie_menu}
            onChange={(e) => setForm({ ...form, categorie_menu: e.target.value })}
            className="h-[var(--control-h)] rounded-md border border-input bg-card px-2 text-sm"
          >
            {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
          </select>
          <Input
            type="number" step="any" aria-label="Prix de vente HT" placeholder="Prix de vente HT"
            value={form.prix_vente_ht} onChange={(e) => setForm({ ...form, prix_vente_ht: e.target.value })}
          />
          <Button type="submit" disabled={saving || !form.nom_plat.trim()}>
            {saving ? <Spinner className="size-4" /> : 'Créer'}
          </Button>
        </form>
      </Card>

      {!recettes && (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Spinner className="size-4" /> Chargement des recettes…
        </div>
      )}
      {recettes && recettes.length === 0 && (
        <EmptyState title="Aucune recette" description="Ajoutez votre première fiche technique." />
      )}
      {recettes && recettes.map((r) => (
        <Card key={r.id} className="flex flex-col gap-2 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="font-medium">{r.nom_plat}</span>{' '}
              <Badge tone={CATEGORIE_TONE[r.categorie_menu] || 'neutral'}>
                {r.categorie_menu_display || r.categorie_menu}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{r.prix_vente_ht} HT</span>
              <Button variant="outline" onClick={() => setOuverte(ouverte === r.id ? null : r.id)}>
                {ouverte === r.id ? 'Fermer les ingrédients' : 'Ingrédients'}
              </Button>
            </div>
          </div>
          {ouverte === r.id && <IngredientsPanel recette={r} />}
        </Card>
      ))}
    </div>
  )
}

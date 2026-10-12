import { Pencil, Trash2 } from 'lucide-react'
import {
  DataTable, IconButton, Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../ui'

/* Petits composants PARTAGÉS des écrans Stock (sélecteur de produit, actions de
   ligne, tableau de liste). Un seul endroit — jamais recopiés écran par écran. */

/** Options d'un sélecteur de produit ; `detail` ajoute SKU et stock courant. */
export function OptionsProduits({ produits, detail = false }) {
  return produits.map((p) => (
    <SelectItem key={p.id} value={String(p.id)}>
      {detail
        ? <>{p.nom}{p.sku ? ` (${p.sku})` : ''} — stock : {p.quantite_stock}</>
        : p.nom}
    </SelectItem>
  ))
}

/** Sélecteur de fournisseur (valeur vide = « — Choisir un fournisseur — »). */
export function SelectFournisseur({
  id, value, onChange, fournisseurs, disabled, placeholder = '— Choisir un fournisseur —',
}) {
  return (
    <Select value={value ? String(value) : '__none'} disabled={disabled}
            onValueChange={(v) => onChange(v === '__none' ? '' : v)}>
      <SelectTrigger id={id}><SelectValue placeholder={placeholder} /></SelectTrigger>
      <SelectContent>
        <SelectItem value="__none">— Choisir un fournisseur —</SelectItem>
        {fournisseurs.map((f) => <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>)}
      </SelectContent>
    </Select>
  )
}

/** Boutons « Modifier » / « Supprimer » d'une ligne de liste. */
export function BoutonsModifierSupprimer({ onModifier, onSupprimer }) {
  return (
    <>
      <IconButton size="sm" variant="ghost" label="Modifier" onClick={onModifier}>
        <Pencil className="size-4" aria-hidden="true" />
      </IconButton>
      <IconButton size="sm" variant="ghost" label="Supprimer"
                  className="text-destructive hover:text-destructive"
                  onClick={onSupprimer}>
        <Trash2 className="size-4" aria-hidden="true" />
      </IconButton>
    </>
  )
}

/** DataTable de liste Stock : lignes `items`, identifiées par `id`. */
export function TableauStock({ items, ...props }) {
  return <DataTable data={items} getRowId={(r) => r.id} {...props} />
}

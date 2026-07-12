import { memo } from 'react'
import { Trash2 } from 'lucide-react'
import {
  Button, IconButton, Input,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import ProduitPicker from '../../components/ProduitPicker'
import {
  formatMoney, expectedTvaForDesignation, classifyProduct,
} from '../../features/ventes/solar'

// VX188 — ligne de devis extraite en composant mémoïsé. DevisGenerator.jsx a
// 64 useState ; le tableau de lignes était du JSX inline dans `lines.map()`,
// donc CHAQUE frappe sur n'importe lequel des 63 autres états (note,
// farmSurfaceHa, etc.) réconciliait N <ProduitPicker> à vide. Extraire la
// ligne en React.memo + callbacks stabilisés (clé en ARGUMENT, jamais en
// fermeture — VX188) restaure le memo : une ligne dont les props n'ont pas
// changé ne se re-rend plus.
//
// Règle fondateur absolue : ne JAMAIS snapper/rejeter un nombre tapé — cette
// extraction ne change AUCUNE logique de saisie, uniquement le découpage du
// rendu (mêmes <Input type="number" step="any">, formulaire noValidate côté
// parent inchangé).
function DevisLineRowImpl({
  line: l,
  produits,
  multiMode,
  villaGroups,
  canRenameLine,
  tarifBadge,
  tvaPanneaux,
  tvaStandard,
  onSetField,
  onDesignationBlur,
  onProduitChange,
  onProduitCreated,
  onQuantiteChange,
  onSetGroupe,
  onRemove,
}) {
  const lineTtc = (parseFloat(l.quantite) || 0) * (parseFloat(l.prix_unit_ttc) || 0)
  // Indice non bloquant : la désignation a été éditée et ne correspond plus
  // au nom du produit choisi — la classification (réseau/hybride/batterie/
  // panneau) pourrait changer la répartition d'options du PDF. On n'altère
  // jamais la saisie.
  const prodLie = l.produit
    ? produits.find(p => String(p.id) === String(l.produit))
    : null
  const designationDivergente = !!prodLie
    && (l.designation || '').trim() !== (prodLie.nom || '').trim()

  const t = parseFloat(l.taux_tva)
  let tvaWarning = null
  if (Number.isFinite(t) && (l.designation || '').trim()) {
    const expected = expectedTvaForDesignation(l.designation, { tvaPanneaux, tvaStandard })
    if (t !== expected) tvaWarning = `${expected} % attendu`
  }

  return (
    <tr key={l._key} data-line-key={l._key}>
      <td data-label="Désignation">
        {/* QP2 — désignation en LECTURE SEULE sauf pour Directeur + Commercial
            responsable. Un rôle non autorisé ne peut pas renommer une ligne
            (verrouillée au nom du produit) ; un rôle autorisé qui diverge du
            nom du produit reçoit au blur le choix « renommer ici » vs
            « créer un nouveau produit ». */}
        <Input className="h-[var(--control-h-sm)]" value={l.designation}
               readOnly={!canRenameLine}
               disabled={!canRenameLine}
               title={!canRenameLine
                 ? 'Renommer une ligne est réservé au Directeur et au Commercial responsable'
                 : undefined}
               onChange={e => onSetField(l._key, 'designation', e.target.value)}
               onBlur={() => onDesignationBlur(l._key)}
               placeholder="Désignation" />
        {designationDivergente && (
          <div className="mt-0.5 text-xs text-warning"
               title="La désignation diffère du nom du produit — vérifiez la classification PDF">
            Désignation modifiée (produit : {prodLie.nom})
          </div>
        )}
      </td>
      <td data-label="Produit (stock)">
        <ProduitPicker
          produits={produits}
          value={l.produit}
          onChange={id => onProduitChange(l._key, id)}
          typeFilter={classifyProduct(l.designation) || undefined}
          onProduitCreated={onProduitCreated}
        />
        {tarifBadge && (
          <span className="mt-0.5 inline-block rounded bg-primary/10 px-1.5 py-0.5 text-[11px] font-medium text-primary">
            Tarif : {tarifBadge}
          </span>
        )}
      </td>
      {multiMode === 'villas' && (
        <td data-label="Villa">
          <Select
            value={l.groupeIndex != null ? String(l.groupeIndex) : '0'}
            onValueChange={(v) => onSetGroupe(l._key, parseInt(v, 10))}>
            <SelectTrigger className="h-[var(--control-h-sm)]"><SelectValue /></SelectTrigger>
            <SelectContent>
              {villaGroups.map(g => (
                <SelectItem key={g.index} value={String(g.index)}>{g.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </td>
      )}
      <td data-label="Qté">
        <Input type="number" min="0" step="any"
               className="h-[var(--control-h-sm)] ta-right" value={l.quantite}
               onChange={e => onQuantiteChange(l._key, e.target.value)} />
      </td>
      <td data-label="Prix unit. TTC">
        <Input type="number" min="0" step="any"
               className="h-[var(--control-h-sm)] ta-right" value={l.prix_unit_ttc}
               onChange={e => onSetField(l._key, 'prix_unit_ttc', e.target.value)} />
      </td>
      <td data-label="TVA %">
        {/* VX249(b) — 1 des 4 champs VX93 exactement (avec owner/ville sur
            LeadForm.jsx et tva sur ProduitForm.jsx) : contour pointillé tant
            que le dernier taux mémorisé n'a pas été touché SUR CETTE LIGNE
            (`_tvaSuggested`, posé par emptyLine()/setLine() dans
            DevisGenerator.jsx) — retiré dès la première modification. Cellule
            étroite (table dense) : `title` porte le micro-libellé plutôt
            qu'une ligne de texte séparée qui casserait la hauteur de ligne. */}
        <Input type="number" min="0" step="any"
               className={`h-[var(--control-h-sm)] ta-right w-14 text-xs text-muted-foreground${l._tvaSuggested ? ' vx-suggested-field' : ''}`}
               value={l.taux_tva ?? '20'}
               title={l._tvaSuggested ? 'Suggéré — modifiable' : undefined}
               onChange={e => onSetField(l._key, 'taux_tva', e.target.value)} />
        {/* DC7 — AVERTISSEMENT de divergence uniquement : le taux attendu suit
            la désignation + les repères TVA société (expectedTvaForDesignation),
            et `Produit.tva` reste la source autoritaire par ligne. On n'altère
            JAMAIS la valeur saisie (frappe souveraine). */}
        {tvaWarning && <div className="mt-0.5 text-xs text-warning">{tvaWarning}</div>}
      </td>
      <td className="line-total" data-label="Total TTC">{formatMoney(lineTtc)}</td>
      <td>
        <IconButton type="button" label="Supprimer la ligne" size="sm"
                    className="text-destructive hover:bg-destructive/10"
                    onClick={() => onRemove(l._key)}>
          <Trash2 />
        </IconButton>
      </td>
    </tr>
  )
}

// Comparateur explicite : évite un re-rendu quand seule une AUTRE ligne (ou
// un état sans rapport, ex. « Note ») a changé. `produits`/`villaGroups` sont
// des tableaux recréés par render côté parent (setState immuable) — comparés
// par référence est correct ici car le parent ne les modifie que lorsqu'ils
// changent réellement (setProduits/setVillaGroups), jamais en cascade sur une
// frappe non liée.
function areEqual(prev, next) {
  return prev.line === next.line
    && prev.produits === next.produits
    && prev.multiMode === next.multiMode
    && prev.villaGroups === next.villaGroups
    && prev.canRenameLine === next.canRenameLine
    && prev.tarifBadge === next.tarifBadge
    && prev.tvaPanneaux === next.tvaPanneaux
    && prev.tvaStandard === next.tvaStandard
    && prev.onSetField === next.onSetField
    && prev.onDesignationBlur === next.onDesignationBlur
    && prev.onProduitChange === next.onProduitChange
    && prev.onProduitCreated === next.onProduitCreated
    && prev.onQuantiteChange === next.onQuantiteChange
    && prev.onSetGroupe === next.onSetGroupe
    && prev.onRemove === next.onRemove
}

export const DevisLineRow = memo(DevisLineRowImpl, areEqual)
export default DevisLineRow

import { useMemo } from 'react'
import {
  AlertTriangle, History, Pencil, Trash2, PackageSearch,
} from 'lucide-react'
import {
  Badge, Button, Checkbox, DataTable, EditableCell,
} from '../../ui'
import { useDelayedLoading } from '../../hooks/useDelayedLoading'
import { keySpec, prixTtc, sansPrix } from '../../features/stock/catalogue'
import { formatMAD } from '../../lib/format'

/* ============================================================================
   J142 — Stock refonte : le catalogue produits passe au moteur DataTable
   unifié (la même grille premium que les autres listes de l'ERP).

   Apports par rapport à l'ancien rendu en cartes groupées :
   - virtualisation automatique au-delà de ~100 lignes (gros catalogue) ;
   - édition de cellule sur le contrat clavier EditableCell (double-clic ou
     Entrée/F2 ouvre, Entrée valide, Échap annule) — prix HT, stock, seuil ;
   - états vide / chargement gérés par le moteur (squelettes calqués sur la
     vraie disposition, jamais de spinner en parallèle) + useDelayedLoading
     pour ne rien clignoter sur une attente imperceptible ;
   - cartes mobiles : repli automatique du moteur sous 768 px (data-dt-cards).

   STATUS / DONNÉES INTERNES : `prix_achat` n'est JAMAIS exposé ici (donnée
   interne). On affiche prix de vente HT, TTC, stock, seuil — comme l'écran
   historique.
   ========================================================================== */

const fmtNum2 = (n) => formatMAD(n, { withSymbol: false })

// Valeur de vente HT du catalogue affiché (somme prix_vente × quantité) — sert
// à la ligne de sous-totaux du moteur.
const valeurVente = (rows) => rows.reduce(
  (s, p) => s + (parseFloat(p.prix_vente) || 0) * (Number(p.quantite_stock) || 0), 0)

// Suggestion de réassort (alignée sur StockList) : vise 2× le seuil, jamais
// négative. Sert au libellé « commander ~N » sur un produit en stock bas.
const suggestionCommande = (p) => {
  const seuil = Number(p.seuil_alerte) || 0
  const stock = Number(p.quantite_stock) || 0
  return Math.max(seuil * 2 - stock, 0)
}

// Validation partagée : nombre fini ≥ 0 (stock, seuil, prix). Renvoie un
// message FR ou null. Le formulaire reste « libre » côté saisie ; cette
// validation est volontairement minimale (refuse seulement l'absurde).
const validatePositif = (v) => {
  if (v === '' || v === null || v === undefined) return 'Valeur requise'
  const n = Number(v)
  if (!Number.isFinite(n) || n < 0) return 'Valeur invalide'
  return null
}

export function CatalogueTable({
  produits,
  loading = false,
  canWrite = false,
  canDelete = false,
  onEdit,
  onDelete,
  onHistorique,
  onReapprovisionner,
  onInlineSave,
  onDetail,
  selected,
  onToggleSelect,
}) {
  // L153 — n'affiche les squelettes que si l'attente se prolonge (anti-clignotement).
  const { showSkeleton } = useDelayedLoading(loading && (produits?.length ?? 0) === 0)
  const editable = canWrite && typeof onInlineSave === 'function'

  const selectable = canWrite && typeof onToggleSelect === 'function' && selected instanceof Set

  const columns = useMemo(() => [
    // Colonne de selection (multi-selection pilotee par StockList → BulkProductBar).
    // Rendue uniquement quand l'ecran fournit un Set + un toggle (droit d'ecriture).
    ...(selectable ? [{
      id: '__select',
      header: '',
      width: 44,
      searchable: false,
      sortable: false,
      hideable: false,
      reorderable: false,
      pinnable: false,
      exportValue: () => '',
      cell: (value, p) => (
        <span onClick={(e) => e.stopPropagation()}>
          <Checkbox
            checked={selected.has(p.id)}
            onCheckedChange={() => onToggleSelect(p.id)}
            aria-label={`Sélectionner ${p.nom}`}
          />
        </span>
      ),
    }] : []),
    {
      id: 'nom',
      header: 'Produit',
      minWidth: 220,
      // Titre mobile (1re colonne) — nom + SKU + marque.
      cell: (value, p) => (
        <div className="min-w-0">
          <div className="truncate font-medium text-foreground">{p.nom}</div>
          <div className="flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
            {p.sku
              ? <span className="font-mono">{p.sku}</span>
              : <Badge tone="warning">SKU manquant</Badge>}
            {(p.marque || '').trim() && <span>· {p.marque}</span>}
          </div>
        </div>
      ),
      exportValue: (p) => `${p.nom}${p.sku ? ` (${p.sku})` : ''}`,
    },
    {
      id: 'categorie',
      header: 'Catégorie',
      minWidth: 130,
      searchable: false,
      accessor: (p) => p.categorie?.nom ?? '—',
    },
    {
      id: 'spec',
      header: 'Caractéristique',
      minWidth: 140,
      searchable: false,
      sortable: false,
      accessor: (p) => keySpec(p) ?? '',
      cell: (v) => (v ? <Badge tone="primary">{v}</Badge> : <span className="text-muted-foreground">—</span>),
      exportValue: (p) => keySpec(p) ?? '',
    },
    {
      id: 'prix_vente',
      header: 'Prix vente HT',
      align: 'right',
      numeric: true,
      width: 150,
      searchable: false,
      accessor: (p) => p.prix_vente,
      cell: (value, p) => {
        if (sansPrix(p) && !editable) return <Badge tone="warning">prix à renseigner</Badge>
        const display = `${formatMAD(value, { withSymbol: false })} HT`
        if (!editable) return <span className="tabular-nums">{display}</span>
        return (
          <EditableCell
            value={value}
            row={p}
            align="right"
            inputType="number"
            format={(v) => `${formatMAD(v, { withSymbol: false })} HT`}
            validate={validatePositif}
            onSave={(v, r) => onInlineSave(r, 'prix_vente', v)}
          />
        )
      },
      exportValue: (p) => p.prix_vente,
      // Sous-total : valeur de vente HT du catalogue affiché (prix × quantité).
      summaryFormat: (n) => `${fmtNum2(n)} DH HT`,
      summaryRender: (n) => <span className="text-foreground">{fmtNum2(n)} DH HT</span>,
    },
    {
      id: 'ttc',
      header: 'Prix TTC',
      align: 'right',
      numeric: true,
      width: 140,
      searchable: false,
      // Métrique clé en carte mobile (montant en grand).
      mobileMetric: true,
      accessor: (p) => prixTtc(p),
      cell: (v, p) => (
        sansPrix(p)
          ? <span className="text-muted-foreground">—</span>
          : (
            <span className="font-semibold tabular-nums">
              {formatMAD(v, { withSymbol: false })} DH{' '}
              <span className="text-xs font-normal text-muted-foreground">TTC · TVA {parseFloat(p.tva ?? 20)}%</span>
            </span>
          )
      ),
      exportValue: (p) => prixTtc(p),
    },
    {
      id: 'quantite_stock',
      header: 'Stock',
      align: 'right',
      numeric: true,
      width: 130,
      searchable: false,
      accessor: (p) => p.quantite_stock,
      cell: (value, p) => {
        const body = editable
          ? (
            <EditableCell
              value={value}
              row={p}
              align="right"
              inputType="number"
              validate={validatePositif}
              onSave={(v, r) => onInlineSave(r, 'quantite_stock', v)}
            />
          )
          : <strong className={p.is_low_stock ? 'text-destructive' : ''}>{value}</strong>
        return (
          <div className="flex flex-col items-end">
            {body}
            {p.quantite_reservee > 0 && (
              <span className="text-xs text-muted-foreground">{p.quantite_reservee} rés. · {p.quantite_disponible} dispo</span>
            )}
            {/* N15 — ventilation par emplacement (lecture) si stock réparti. */}
            {Array.isArray(p.stock_par_emplacement) && p.stock_par_emplacement.length > 1 && (
              <span className="text-xs text-muted-foreground">
                {p.stock_par_emplacement.map((b) => `${b.emplacement_nom} ${b.quantite}`).join(' · ')}
              </span>
            )}
          </div>
        )
      },
      exportValue: (p) => p.quantite_stock,
    },
    {
      id: 'seuil_alerte',
      header: 'Seuil',
      align: 'right',
      numeric: true,
      width: 150,
      searchable: false,
      accessor: (p) => p.seuil_alerte,
      cell: (value, p) => (
        <div className="flex flex-col items-end gap-0.5">
          {editable
            ? (
              <EditableCell
                value={value}
                row={p}
                align="right"
                inputType="number"
                validate={validatePositif}
                onSave={(v, r) => onInlineSave(r, 'seuil_alerte', v)}
              />
            )
            : <span className="tabular-nums">{value}</span>}
          {p.is_low_stock && (
            <Badge tone="danger"><AlertTriangle className="size-3" /> stock bas</Badge>
          )}
          {p.is_low_stock && suggestionCommande(p) > 0 && (
            <span className="text-xs text-muted-foreground">commander ~{suggestionCommande(p)}</span>
          )}
          {p.is_low_stock && onReapprovisionner && (
            <Button type="button" variant="outline" size="sm" className="h-7"
                    onClick={() => onReapprovisionner(p)}>
              Réapprovisionner
            </Button>
          )}
        </div>
      ),
      exportValue: (p) => p.seuil_alerte,
    },
  ], [editable, onInlineSave, onReapprovisionner, selectable, selected, onToggleSelect])

  // Actions de ligne (≤2 rapides + menu kebab) — historique / éditer / supprimer.
  const rowActions = (p) => {
    const acts = []
    // ZPUR10/ZSTK3 — fiche produit : quantité « en commande » + prévisionnel.
    if (onDetail) acts.push({ id: 'detail', label: 'Fiche produit (en commande, prévisionnel)', icon: PackageSearch, onClick: () => onDetail(p) })
    if (onHistorique) acts.push({ id: 'hist', label: 'Historique des mouvements', icon: History, onClick: () => onHistorique(p) })
    if (canWrite && onEdit) acts.push({ id: 'edit', label: 'Éditer', icon: Pencil, onClick: () => onEdit(p) })
    if (canDelete && onDelete) acts.push({ id: 'del', label: 'Supprimer', icon: Trash2, destructive: true, separatorBefore: true, onClick: () => onDelete(p) })
    return acts
  }

  // Ligne de sous-totaux : valeur de vente HT du catalogue affiché. La clé
  // correspond à la colonne `prix_vente`, où summaryFormat/summaryRender la rendent.
  const summary = useMemo(() => ({ prix_vente: (values, rows) => valeurVente(rows) }), [])

  // Le moteur gère lui-même le vide ET le chargement (squelettes calqués sur la
  // vraie disposition). useDelayedLoading n'arme le squelette que si l'attente
  // se prolonge — on ne fait clignoter aucun écran sur une attente brève.
  return (
    <DataTable
      data={produits ?? []}
      columns={columns}
      getRowId={(p) => p.id}
      loading={showSkeleton}
      searchable={false}
      rowActions={rowActions}
      virtualize={(produits?.length ?? 0) > 100}
      pageSize={50}
      pageSizeOptions={[25, 50, 100, 200]}
      summary={summary}
      summaryLabel="Valeur vente du catalogue affiché"
      emptyTitle={(produits?.length ?? 0) === 0 ? 'Aucun produit' : 'Aucun résultat'}
      emptyDescription="Aucun produit ne correspond au catalogue affiché."
      // VX40 — pictogramme solaire illustré réservé au vrai catalogue vide
      // (jamais au cas « filtres sans résultat », routine et non « rare »).
      emptyIllustrated={(produits?.length ?? 0) === 0}
      aria-label="Catalogue produits en stock"
      className="min-w-0"
    />
  )
}

export default CatalogueTable

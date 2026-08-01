import { useMemo } from 'react'
import {
  AlertTriangle, History, Pencil, Trash2, PackageSearch, PackagePlus,
  TrendingDown,
} from 'lucide-react'
import {
  Badge, Checkbox, DataTable, EditableCell, Progress,
} from '../../ui'
import { useDelayedLoading } from '../../hooks/useDelayedLoading'
import { categorieIcone, keySpec, prixTtc, sansPrix } from '../../features/stock/catalogue'
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

   APX18 — vignette 40 px en 1ʳᵉ colonne : la photo du produit, ou l'icône de
   sa catégorie. La boîte est identique dans les deux cas.

   APX19 — le niveau de stock se lit sans le lire : jauge colorée, sévérité
   RUPTURE ≠ SOUS SEUIL (elles partageaient un badge unique), et surtout UNE
   SEULE hauteur de ligne — chaque zone de cellule est réservée même vide, et
   le réassort a quitté la grille pour le menu de ligne.

   STATUS / DONNÉES INTERNES : `prix_achat` n'est JAMAIS exposé ici (donnée
   interne). On affiche prix de vente HT, TTC, stock, seuil — comme l'écran
   historique.
   ========================================================================== */

const fmtNum2 = (n) => formatMAD(n, { withSymbol: false })

/* APX18 — Vignette 40 px de la 1re colonne : la photo si le produit en a une,
   sinon l'ICÔNE de sa catégorie, teintée. La boîte fait exactement la même
   taille dans les deux cas (`.pcat-vignette`, dimensions fixes en CSS) : la
   hauteur de ligne ne dépend jamais de la présence d'une photo.
   La photo est INTERNE — cette vignette ne sort jamais vers un PDF ni vers un
   document client, et n'est jamais rendue à côté de `prix_achat`. */
function VignetteProduit({ produit }) {
  const Icone = categorieIcone(produit)
  return (
    <span className="pcat-vignette" data-testid="pcat-vignette" aria-hidden="true">
      {produit.image_url
        ? <img src={produit.image_url} alt="" loading="lazy" />
        : <Icone className="size-5" />}
    </span>
  )
}

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

/* ── APX19 — Le niveau de stock devient LISIBLE ────────────────────────────
   Avant : un chiffre nu passé en gras-rouge quand il était bas, et LE MÊME
   badge « stock bas » pour une rupture (0 en stock, on ne peut plus vendre)
   et pour un sous-seuil (il en reste, il faut recommander). Deux situations
   d'urgence très différentes, un seul signal.

   Maintenant : TROIS sévérités distinctes, lues sans lire — une jauge colorée
   (vert / orange / rouge) et, pour les deux états à problème, un badge dont le
   TON ET le libellé diffèrent. La sévérité vient de `is_low_stock` (calculé
   serveur, seule autorité) ; la rupture prime dessus. */
const SEV_RUPTURE = 'rupture'
const SEV_BAS = 'bas'
const SEV_OK = 'ok'

export function severiteStock(p) {
  const stock = Number(p?.quantite_stock) || 0
  if (stock <= 0) return SEV_RUPTURE
  const seuil = Number(p?.seuil_alerte) || 0
  if (p?.is_low_stock || (seuil > 0 && stock <= seuil)) return SEV_BAS
  return SEV_OK
}

const TON_SEV = {
  [SEV_RUPTURE]: 'danger',
  [SEV_BAS]: 'warning',
  [SEV_OK]: 'success',
}

/* Remplissage de la jauge, en %. La cible « saine » est 2× le seuil — la MÊME
   cible que la suggestion de réassort déjà affichée (`suggestionCommande`), on
   n'invente pas un second barème. Sans seuil renseigné, un stock non nul est
   plein (on ne peut rien promettre d'autre honnêtement). */
export function jaugeStock(p) {
  const stock = Math.max(0, Number(p?.quantite_stock) || 0)
  const seuil = Number(p?.seuil_alerte) || 0
  if (seuil <= 0) return stock > 0 ? 100 : 0
  return Math.round(Math.min(100, (stock / (seuil * 2)) * 100))
}

// Ligne de détail du stock — TOUJOURS rendue (vide si rien à dire) : c'est ce
// qui garantit une hauteur de ligne unique quelles que soient les données.
function detailStock(p) {
  if ((Number(p.quantite_reservee) || 0) > 0) {
    return `${p.quantite_reservee} rés. · ${p.quantite_disponible} dispo`
  }
  // N15 — ventilation par emplacement (lecture) si le stock est réparti.
  if (Array.isArray(p.stock_par_emplacement) && p.stock_par_emplacement.length > 1) {
    return p.stock_par_emplacement
      .map((b) => `${b.emplacement_nom} ${b.quantite}`).join(' · ')
  }
  return ''
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
      // APX18 — +40 px de vignette + gouttière : la largeur mini suit, sinon
      // le nom se tronque plus tôt qu'avant l'ajout du visuel.
      minWidth: 272,
      // Titre mobile (1re colonne) — vignette (APX18) + nom + SKU + marque.
      cell: (value, p) => (
        <div className="flex min-w-0 items-center gap-2.5">
          <VignetteProduit produit={p} />
          <div className="min-w-0">
            <div className="truncate font-medium text-foreground">{p.nom}</div>
            <div className="flex flex-wrap items-center gap-x-1.5 text-xs text-muted-foreground">
              {p.sku
                ? <span className="font-mono">{p.sku}</span>
                : <Badge tone="warning">SKU manquant</Badge>}
              {(p.marque || '').trim() && <span>· {p.marque}</span>}
            </div>
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
      // APX19 — la jauge et sa ligne de détail ont besoin d'un peu d'air.
      width: 150,
      searchable: false,
      accessor: (p) => p.quantite_stock,
      // APX19 — trois zones de hauteur FIXE : le chiffre, la jauge, une ligne
      // de détail toujours présente (vide si rien à dire). La ligne du tableau
      // a donc une seule hauteur, quelles que soient les données.
      cell: (value, p) => {
        const sev = severiteStock(p)
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
          : <strong className={sev === SEV_OK ? '' : 'text-destructive'}>{value}</strong>
        const detail = detailStock(p)
        return (
          <div className="pcat-stock">
            <div className="pcat-stock-val">{body}</div>
            <Progress
              className="pcat-jauge"
              value={jaugeStock(p)}
              tone={TON_SEV[sev]}
              aria-label={`Niveau de stock : ${value} en stock, seuil d'alerte ${p.seuil_alerte ?? 0}`}
            />
            <span className="pcat-stock-detail" data-testid="pcat-stock-detail">{detail}</span>
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
      // APX19 — la cellule ne porte plus que le seuil + un badge : elle n'a
      // plus besoin de la largeur qu'exigeait le bouton « Réapprovisionner ».
      width: 128,
      searchable: false,
      accessor: (p) => p.seuil_alerte,
      // APX19 — DEUX zones de hauteur fixe : le seuil, puis UN emplacement de
      // badge (occupé ou vide). Avant, cette cellule empilait jusqu'à quatre
      // éléments (seuil + badge + « commander ~N » + bouton) : c'est elle qui
      // faisait varier la hauteur de ligne d'un produit à l'autre. Le « commander
      // ~N » et l'action de réassort ont rejoint le menu de ligne (≤ 2 clics,
      // 1 seul au survol) — rien n'est perdu, la hauteur ne bouge plus.
      cell: (value, p) => {
        const sev = severiteStock(p)
        return (
          <div className="pcat-seuil">
            <div className="pcat-seuil-val">
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
            </div>
            <span className="pcat-sev" data-testid="pcat-sev">
              {sev === SEV_RUPTURE && (
                <Badge tone="danger"><AlertTriangle className="size-3" /> Rupture</Badge>
              )}
              {sev === SEV_BAS && (
                <Badge tone="warning"><TrendingDown className="size-3" /> Sous seuil</Badge>
              )}
            </span>
          </div>
        )
      },
      exportValue: (p) => p.seuil_alerte,
    },
  ], [editable, onInlineSave, selectable, selected, onToggleSelect])

  // Actions de ligne (≤2 rapides + menu kebab) — historique / éditer / supprimer.
  const rowActions = (p) => {
    const acts = []
    // APX19 — le réassort passe en PREMIÈRE action : le moteur révèle les deux
    // premières au survol (et en permanence au toucher), donc réapprovisionner
    // coûte 1 clic à la souris et 2 par le menu. Il n'apparaît que sur un
    // produit qui en a besoin, et la quantité suggérée est DANS le libellé —
    // c'est elle qui vivait en 3ᵉ ligne de la cellule Seuil.
    if (onReapprovisionner && severiteStock(p) !== SEV_OK) {
      const suggestion = suggestionCommande(p)
      acts.push({
        id: 'reappro',
        label: suggestion > 0
          ? `Réapprovisionner (commander ~${suggestion})`
          : 'Réapprovisionner',
        icon: PackagePlus,
        onClick: () => onReapprovisionner(p),
      })
    }
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

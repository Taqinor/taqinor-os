import { useEffect, useMemo, useRef, useState } from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { Plus } from 'lucide-react'
import { cn } from '../lib/cn'
import {
  groupCatalogue, searchCatalogue, keySpec, prixTtc, sansPrix,
  typeOfProduit, familleAttendue,
} from '../features/stock/catalogue'
import { classifyProduct } from '../features/ventes/calc/classification.js'
import { useCanCreateProduit } from '../hooks/useHasPermission'
import { useVoitPrixVente } from '../features/stock/useVoitPrixAchat'
import { useActiveDescendant } from '../hooks/useActiveDescendant'
import { formatMAD } from '../lib/format'
import stockApi from '../api/stockApi'
import ProduitQuickCreateModal from './ProduitQuickCreateModal'

/* G23 — Picker produit groupé CATÉGORIE → MARQUE → ARTICLE, search-first.
   Conçu pour la saisie ligne à ligne : ouvrir → taper → Entrée (le premier
   article trouvé PAR SON NOM est présélectionné — T4-V1-002) ; ↑/↓ naviguent, Échap ferme. Les produits sans
   prix sont visibles mais non sélectionnables.

   Reconstruit sur le Popover (G28) + jetons sémantiques (les anciennes classes
   pp-* d'index.css ne sont plus utilisées). Props/API préservés 1:1 :
   { produits, value, onChange, invalid }.

   QP1 — `typeFilter` (optionnel) signale le type de produit attendu par le
   slot de la ligne (ex. 'onduleur_hybride'), via classifyProduct (même
   classification que le moteur PDF, builder.py). Une ligne sans type inférable
   passe `typeFilter` à null/undefined et garde la liste complète.

   STKCAT12 — UNION jamais substitution : un `typeFilter` ne FILTRE plus rien,
   il ne fait que trier le catalogue en deux sections — « Recommandé pour
   cette ligne » (mot-clé `classifyProduct` OU famille typée `typeOfProduit`
   via `familleAttendue`) puis, dès qu'une recherche est tapée, « Tout le
   catalogue (m) » pour le reste des résultats. Sans recherche, seule la
   section Recommandé s'affiche (comportement historique) — un indice en tête
   de liste rappelle qu'on peut chercher dans tout le catalogue. Un produit
   hors mot-clé mais catégorisé (ex. « Pergola » rangée en catégorie typée
   structure) n'est donc plus jamais invisible : il est promu Recommandé, ou
   sinon reste atteignable via la recherche — jamais perdu. Curseur clavier
   continu sur UN seul tableau `selectables` couvrant les deux sections.

   STKCAT24 — Recommandé lit AUSSI le rôle EFFECTIF résolu côté serveur
   (STKCAT21 `role_devis_effectif` : déclaré → catégorie → mots-clés du nom) :
   un troisième terme, encore en UNION, jamais une substitution des deux
   précédents. `structure_acier`/`structure_alu` et le rôle générique
   `structure` se reconnaissent mutuellement via `familleAttendue` (même
   famille), dans les deux sens — un produit dont le rôle effectif est le
   générique `structure` reste Recommandé sur une ligne `structure_acier`,
   et réciproquement.

   QG6 — « + Nouveau produit » : visible uniquement pour Directeur + Commercial
   responsable (hook QG5, backend QG4 est la garde qui compte). `onProduitCreated`
   (optionnel) est appelé avec le produit créé EN PLUS de la sélection auto sur
   cette ligne — utile pour rafraîchir la liste des produits de l'appelant.

   VX238(b/c) — `Tab` (sans shift) sélectionne l'option sous le curseur SANS
   bloquer la tabulation (mains rapides : plus besoin d'Entrée avant Tab).
   `onPicked` (optionnel) est appelé APRÈS une sélection réussie (clic/Entrée/
   Tab) — l'appelant y avance le focus (ex. Qté de la même ligne) au lieu de
   subir le retour par défaut au bouton déclencheur. */
export default function ProduitPicker({ produits, value, onChange, invalid, typeFilter, onProduitCreated, onPicked }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  // T4-V1-002 — vrai dès que l'utilisateur a désigné un article (flèches,
  // survol) ; la frappe le remet à faux : seul un article TROUVÉ PAR SON NOM
  // est alors surligné d'office.
  const [navigue, setNavigue] = useState(false)
  const [quickCreateOpen, setQuickCreateOpen] = useState(false)
  // STKCAT13 — chargée paresseusement (jamais à l'ouverture du picker, qui
  // ligne-à-ligne serait bien trop de requêtes) SEULEMENT quand « Nouveau »
  // est cliqué ; sert à la fois à calculer `defaultCategorieId` ci-dessous et
  // à éviter à la modale de recharger la même liste (prop `categories`).
  const [categoriesForCreate, setCategoriesForCreate] = useState(null)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const canCreateProduit = useCanCreateProduit()
  // D-ACAL-152 — sans « voir les prix de vente » (Technicien), le serveur ne
  // sert aucun prix : aucun prix affiché, et l'absence de prix ne rend plus
  // un article inchoisissable (le technicien choisit un équipement, pas un prix).
  const prixMasques = !useVoitPrixVente(produits)
  const selected = useMemo(
    () => produits.find((p) => String(p.id) === String(value)) ?? null,
    [produits, value])

  // STKCAT12 — le nombre total de produits sélectionnables du catalogue,
  // INDÉPENDANT du typeFilter/de la recherche : c'est ce chiffre qu'annonce
  // l'indice « Tapez pour chercher dans N produits » (jamais un sous-compte
  // trompeur du seul type attendu).
  const totalSelectable = useMemo(
    () => produits.filter((p) => !p.is_archived && (prixMasques || !sansPrix(p))).length,
    [produits, prixMasques])

  const famille = typeFilter ? familleAttendue(typeFilter) : null
  // STKCAT13 — chargement paresseux des catégories, uniquement à l'ouverture
  // de la création rapide (jamais côté rendu normal du picker). Échec
  // silencieux (liste vide) : « + Nouveau » reste utilisable sans catégorie.
  useEffect(() => {
    if (!quickCreateOpen || categoriesForCreate !== null) return
    let cancelled = false
    stockApi.getCategories({ page_size: 200 })
      .then((r) => { if (!cancelled) setCategoriesForCreate(r.data?.results ?? r.data ?? []) })
      .catch(() => { if (!cancelled) setCategoriesForCreate([]) })
    return () => { cancelled = true }
  }, [quickCreateOpen, categoriesForCreate])

  // `defaultCategorieId` seulement quand la famille de la ligne désigne SANS
  // AMBIGÜITÉ une catégorie typée de la société (exactement une — 0 ou 2+
  // correspondances laissent l'utilisateur choisir lui-même).
  const defaultCategorieId = useMemo(() => {
    if (!famille || !categoriesForCreate) return undefined
    const typees = categoriesForCreate.filter((c) => c.type_equipement === famille)
    return typees.length === 1 ? typees[0].id : undefined
  }, [famille, categoriesForCreate])

  // Lignes à plat (en-têtes + articles) dans l'ordre délibéré de la taxonomie
  const { rows, selectables, nbForts } = useMemo(() => {
    const isRecommande = (p) => !!typeFilter && (
      classifyProduct(p.nom) === typeFilter
      || (famille !== null && typeOfProduit(p) === famille)
      || p.role_devis_effectif === typeFilter
      || (famille !== null && famille === familleAttendue(p.role_devis_effectif))
    )
    const actifs = produits.filter((p) => !p.is_archived)
    const matches = searchCatalogue(actifs, query)
    // T4-V1-002 — un article dont seule la FICHE (description) cite le mot
    // tapé (« parafoudre intégré » d'un onduleur) n'est qu'une piste : rangé
    // à part, en dernier, jamais surligné d'office.
    const parNom = query.trim()
      ? new Set(searchCatalogue(actifs.map((p) => ({ ...p, description: undefined })), query).map((p) => p.id))
      : null
    const forts = parNom ? matches.filter((p) => parNom.has(p.id)) : matches
    const faibles = parNom ? matches.filter((p) => !parNom.has(p.id)) : []
    const rows = []
    const selectables = []

    // Empile une grille CATÉGORIE → MARQUE → article pour `items` ; `sectionKey`
    // évite toute collision de clé React entre les deux sections (un même
    // article/catégorie peut apparaître groupé sous les deux en-têtes).
    const appendGroup = (items, sectionKey) => {
      for (const cat of groupCatalogue(items)) {
        rows.push({ kind: 'cat', label: cat.nom, key: `${sectionKey}-c-${cat.nom}` })
        for (const b of cat.brands) {
          rows.push({ kind: 'brand', label: b.marque, key: `${sectionKey}-b-${cat.nom}-${b.marque}` })
          for (const p of b.items) {
            const dispo = prixMasques || !sansPrix(p)
            rows.push({ kind: 'item', p, dispo, key: `${sectionKey}-p-${p.id}`,
                        index: dispo ? selectables.length : -1 })
            if (dispo) selectables.push(p)
          }
        }
      }
    }

    if (!typeFilter) {
      appendGroup(forts, 'all')
    } else {
      const recommandes = forts.filter(isRecommande)
      const reste = forts.filter((p) => !isRecommande(p))
      // Sans recherche tapée, seule la section Recommandé s'affiche (comme
      // avant STKCAT12) — l'indice au-dessus rappelle que taper cherche dans
      // TOUT le catalogue ; « reste » redevient visible dès la 1ʳᵉ frappe,
      // jamais un filtre permanent (UNION jamais substitution).
      if (recommandes.length) {
        rows.push({ kind: 'section', label: 'Recommandé pour cette ligne', key: 'sec-reco' })
        appendGroup(recommandes, 'reco')
      }
      if (query.trim() && reste.length) {
        rows.push({ kind: 'section', label: `Tout le catalogue (${reste.length})`, key: 'sec-reste' })
        appendGroup(reste, 'reste')
      }
    }
    const nbForts = selectables.length
    if (faibles.length) {
      rows.push({ kind: 'section', label: `Cités seulement dans la fiche produit (${faibles.length})`, key: 'sec-fiche' })
      appendGroup(faibles, 'fiche')
    }
    return { rows, selectables, nbForts }
  }, [produits, query, typeFilter, famille, prixMasques])

  // T4-V1-002 — l'article surligné : celui que l'utilisateur a désigné, sinon
  // le premier trouvé PAR SON NOM après une frappe, sinon aucun (-1) : Entrée
  // n'ajoute alors rien.
  const curseur = navigue ? cursor : (query.trim() && nbForts > 0 ? 0 : -1)
  // VX191 — `aria-activedescendant` : flécher au clavier annonce enfin
  // l'article visé (ProduitPicker n'avait aucun id d'option jusqu'ici).
  const { listId, getOptionId, activeId } = useActiveDescendant(curseur)

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus())
  }, [open])

  // Réinitialise la recherche à la fermeture (hors effet → pas de cascade).
  const handleOpenChange = (next) => {
    setOpen(next)
    if (!next) { setQuery(''); setCursor(0); setNavigue(false) }
  }

  // L'élément sous le curseur reste visible pendant la navigation clavier
  useEffect(() => {
    listRef.current
      ?.querySelector('[data-cursor="true"]')
      ?.scrollIntoView({ block: 'nearest' })
  }, [curseur, open])

  const pick = (p) => {
    onChange(p ? String(p.id) : '')
    setOpen(false)
    // VX238(c) — n'avance le focus qu'après une VRAIE sélection (jamais sur
    // « Aucun produit », p == null), sinon on court-circuiterait un simple
    // effacement en un saut de focus surprenant.
    if (p) onPicked?.(p)
  }

  const onKeyDown = (e) => {
    if (e.key === 'Escape') { setOpen(false); return }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setNavigue(true)
      setCursor(Math.min(curseur + 1, selectables.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setNavigue(true)
      setCursor(Math.max(curseur - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (selectables[curseur]) pick(selectables[curseur])
    } else if (e.key === 'Tab' && !e.shiftKey) {
      // VX238(b) — Tab sélectionne l'article sous le curseur SANS
      // preventDefault : la tabulation continue naturellement vers le champ
      // suivant (Qté, via onPicked) au lieu de blur à vide.
      if (selectables[curseur]) pick(selectables[curseur])
    }
  }

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={handleOpenChange}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          aria-invalid={invalid || undefined}
          className={cn(
            'flex h-[var(--control-h-sm)] w-full items-center justify-between gap-2 rounded-md border border-input bg-card px-2.5 text-sm text-foreground shadow-ui-xs transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-ring',
            'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30',
          )}
        >
          {selected
            ? <span className="truncate">{selected.nom}</span>
            : <span className="text-muted-foreground">— Produit —</span>}
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="start"
          sideOffset={4}
          onOpenAutoFocus={(e) => e.preventDefault()}
          // VX238(c) — quand `onPicked` gère la suite du focus (Qté de la
          // ligne), on empêche Radix de reprendre la main en refocalisant le
          // bouton déclencheur à la fermeture (comportement par défaut).
          onCloseAutoFocus={(e) => { if (onPicked) e.preventDefault() }}
          // T4-U3-005 — assez large pour un nom de pompe ET sa raison (bornée à l'écran).
          className="z-[var(--z-popover)] w-[max(var(--radix-popover-trigger-width),min(30rem,calc(100vw-2rem)))] overflow-hidden rounded-lg border border-border bg-popover p-0 text-popover-foreground shadow-ui-lg data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none"
        >
          <div className="flex items-center gap-1 border-b border-border p-1.5">
            <input
              ref={inputRef}
              role="combobox"
              aria-expanded={open}
              aria-autocomplete="list"
              aria-controls={listId}
              aria-activedescendant={activeId}
              className="h-8 w-full rounded-md bg-transparent px-2 text-base outline-none placeholder:text-muted-foreground sm:text-sm"
              placeholder="Chercher un produit… (Entrée = premier résultat)"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setCursor(0); setNavigue(false) }}
              onKeyDown={onKeyDown}
            />
            {canCreateProduit && (
              <button
                type="button"
                title="Nouveau produit"
                onClick={() => { setOpen(false); setQuickCreateOpen(true) }}
                className="flex h-8 shrink-0 items-center gap-1 whitespace-nowrap rounded-md px-2 text-xs font-medium text-primary outline-none hover:bg-accent"
              >
                <Plus className="size-3.5" /> Nouveau
              </button>
            )}
          </div>
          <div className="max-h-72 overflow-y-auto p-1" ref={listRef} role="listbox" id={listId}>
            {/* STKCAT12 — indice honnête : sans recherche, seule la section
                Recommandé s'affiche ; ce rappel dit qu'il y a plus à chercher,
                jamais un compte qui prétend que le catalogue s'arrête là. */}
            {!query && (
              <div className="px-2 pb-1.5 pt-1 text-xs text-muted-foreground">
                Tapez pour chercher dans {totalSelectable} produits
              </div>
            )}
            {value && (
              <button
                type="button"
                onClick={() => pick(null)}
                className="flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm text-muted-foreground outline-none hover:bg-accent"
              >
                ✕ Aucun produit (ligne libre)
              </button>
            )}
            {rows.map((r) => {
              if (r.kind === 'section') {
                return (
                  <div key={r.key}
                       className="mt-1 border-t border-border px-2 pb-1 pt-2 text-[11px] font-bold uppercase tracking-wider text-primary first:mt-0 first:border-t-0">
                    {r.label}
                  </div>
                )
              }
              if (r.kind === 'cat') {
                return (
                  <div key={r.key} className="px-2 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {r.label}
                  </div>
                )
              }
              if (r.kind === 'brand') {
                return (
                  <div key={r.key} className="px-2 py-0.5 text-xs font-medium text-foreground/70">
                    {r.label}
                  </div>
                )
              }
              const { p, dispo, index } = r
              const spec = keySpec(p)
              const isCur = index === curseur
              return (
                <button
                  type="button"
                  key={r.key}
                  id={dispo ? getOptionId(index) : undefined}
                  role="option"
                  aria-selected={String(p.id) === String(value)}
                  aria-disabled={!dispo || undefined}
                  disabled={!dispo}
                  data-cursor={dispo && isCur ? 'true' : undefined}
                  onMouseEnter={() => { if (dispo) { setNavigue(true); setCursor(index) } }}
                  onClick={() => dispo && pick(p)}
                  // T4-U3-005 — une option désactivée DIT pourquoi (title + texte).
                  title={dispo ? undefined
                    : 'Produit sans prix de vente : il ne peut pas être choisi tant que son prix n’est pas saisi dans Stock.'}
                  className={cn(
                    'flex w-full flex-col items-stretch gap-0.5 rounded-md px-2 py-1.5 text-left text-sm outline-none',
                    dispo && isCur && 'bg-accent text-accent-foreground',
                    !dispo && 'cursor-not-allowed opacity-70',
                  )}
                >
                  {/* T4-U3-005 — le nom a sa propre ligne et passe à la ligne
                      (jamais écrasé par la spec) ; le prix (ou sa raison) reste
                      visible à droite. */}
                  <span className="flex w-full items-start gap-2">
                    <span className="min-w-0 flex-1 break-words">{p.nom}</span>
                    <span className={cn('shrink-0 text-xs tabular-nums', dispo ? 'font-medium text-foreground' : 'italic text-muted-foreground')}>
                      {prixMasques ? null : dispo ? `${formatMAD(prixTtc(p), { withSymbol: false })} DH` : 'prix à renseigner'}
                    </span>
                  </span>
                  {/* STKCAT12 — puce du type de catégorie (categorie_type_display,
                      quand le backend l'a renseigné) EN PLUS de la spec clé
                      existante (keySpec) : deux informations différentes, ni
                      l'une ne remplace l'autre. */}
                  {(p.categorie_type_display || spec || !dispo) && (
                    <span className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                      {p.categorie_type_display && (
                        <span className="rounded-full border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                          {p.categorie_type_display}
                        </span>
                      )}
                      {spec && <span className="min-w-0 break-words">{spec}</span>}
                      {!dispo && <span className="italic">sans prix de vente : non sélectionnable</span>}
                    </span>
                  )}
                </button>
              )
            })}
            {/* STKCAT12 — jamais « Aucun produit pour «  » » : cette phrase ne
                s'affiche que quand une recherche a réellement été tapée. */}
            {rows.length === 0 && query.trim() && (
              <div className="px-2 py-6 text-center text-sm text-muted-foreground">
                Aucun produit pour «&nbsp;{query}&nbsp;»
              </div>
            )}
          </div>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
      {canCreateProduit && (
        <ProduitQuickCreateModal
          open={quickCreateOpen}
          onClose={() => setQuickCreateOpen(false)}
          categories={categoriesForCreate ?? undefined}
          defaultCategorieId={defaultCategorieId}
          onCreated={(p) => {
            setQuickCreateOpen(false)
            onProduitCreated?.(p)
            onChange(String(p.id))
          }}
        />
      )}
    </PopoverPrimitive.Root>
  )
}

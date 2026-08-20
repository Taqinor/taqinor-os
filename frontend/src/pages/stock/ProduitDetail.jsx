import { createElement, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { History, PackageSearch, Pencil } from 'lucide-react'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import stockApi from '../../api/stockApi'
import {
  ChartFrame, ChartTooltip, CHART_GRID_STYLE, CHART_TOKENS,
  CHART_ANIM_EASING, animationDuration, resolveColor,
} from '../../ui/charts'
import {
  categorieIcone, estPompage, pointsCourbePompe,
} from '../../features/stock/catalogue'
import { useHasPermission } from '../../hooks/useHasPermission'
import {
  Spinner, Badge, RelationCounters,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button, Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
// PACT128 — onglet « Options » (groupes d'options NTCPQ1) sur la fiche
// produit, en AJOUT au système d'onglets existant.
import ProduitOptionsTab from './ProduitOptionsTab.jsx'
// PV8 — badge de complétude datasheet, même règle que CatalogueTable (grille
// catalogue) : un seul calcul, réutilisé sur les deux écrans.
import { BadgeCompletudeFiche } from './CatalogueTable.jsx'
// PVFCH — libellés et mise en forme des champs de fiche : logique PURE
// partagée avec ProduitForm (mêmes intitulés d'un écran à l'autre).
import { groupeFicheAffichage } from './pvondFicheTechnique.js'

// ZPUR10 / ZSTK3 — Fiche produit (au-delà du catalogue) : quantité « en
// commande » (BCF brouillon/envoyé, jamais annulé/reçu) + rapport
// prévisionnel (disponible + entrées/sorties attendues → solde projeté
// daté). Donnée INTERNE (prix d'achat jamais client-facing) — la fiche ne
// modifie jamais aucun stock/mouvement, lecture seule.

const fmtDateFR = (iso) => {
  if (!iso) return 'Date inconnue'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? 'Date inconnue' : d.toLocaleDateString('fr-FR')
}

function Chargement() {
  return (
    <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner /> Chargement…
    </div>
  )
}

/* APX18 — En-tête visuel de la fiche : la photo du produit quand il en a une.
   Sans photo, AUCUNE boîte vide n'est rendue (l'icône de catégorie suffit déjà
   dans le titre du dialogue) — on ne montre pas un cadre gris pour rien.
   INTERNE : cette image ne part dans aucun PDF ni document client, et n'est
   jamais rendue à côté d'une donnée d'achat. */
function EnTetePhoto({ produit }) {
  if (!produit.image_url) return null
  return (
    <img
      className="pdet-photo mb-3"
      data-testid="pdet-photo"
      src={produit.image_url}
      alt={`Photo de ${produit.nom}`}
    />
  )
}

/* ── APX20 — Onglet « Fiche technique » ────────────────────────────────────
   Les champs `marque`, `garantie` (texte) et `description` alimentent depuis
   toujours les fiches produits des PDF de devis, mais AUCUN écran ne les
   MONTRAIT : on ne pouvait pas vérifier ce qui allait partir chez le client.
   Ici, lecture seule et honnête — un champ vide dit « non renseigné » plutôt
   que de disparaître, sinon on ne saurait pas qu'il manque.
   Les caractéristiques de pompage (kW, tension) ne s'affichent QUE pour un
   produit qui en porte : pas de ligne vide pour un panneau. */
const CHAMP_VIDE = 'Non renseigné'

function Ligne({ label, valeur }) {
  const rempli = valeur !== null && valeur !== undefined && String(valeur).trim() !== ''
  return (
    <div className="flex flex-col gap-0.5 border-b border-border py-2 last:border-b-0 sm:flex-row sm:gap-4">
      <span className="w-full shrink-0 text-xs uppercase tracking-wide text-muted-foreground sm:w-48">
        {label}
      </span>
      <span className={rempli ? 'text-sm text-foreground' : 'text-sm italic text-muted-foreground'}>
        {rempli ? String(valeur) : CHAMP_VIDE}
      </span>
    </div>
  )
}

/* ── APX21 — La courbe constructeur, enfin TRACÉE ───────────────────────────
   Les 11 pompes OSP 30 embarquent leur courbe débit→HMT du constructeur
   (`Produit.courbe_pompe`). Elle servait UNIQUEMENT au dimensionnement
   (`solar.js debitAtHmt`) et n'apparaissait à l'écran que sous forme d'un
   badge TEXTE « courbe constructeur » : personne ne l'a jamais vue.
   La lecture de la courbe (`pointsCourbePompe`) vit avec les autres règles de
   catalogue ; ce fichier-ci ne contient que des composants. */
function CourbePompe({ produit }) {
  const points = useMemo(
    () => pointsCourbePompe(produit?.courbe_pompe), [produit?.courbe_pompe])
  // Pas de courbe → RIEN. Une carte « aucune donnée » sur les dizaines de
  // produits sans courbe serait du bruit pur.
  if (!points) return null

  const couleur = resolveColor('info')
  const duree = animationDuration()   // 0 sous prefers-reduced-motion

  return (
    <div className="rounded-lg border border-border p-3" data-testid="pdet-courbe-pompe">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        Courbe constructeur
      </p>
      <p className="mb-2 text-xs text-muted-foreground">
        Débit délivré (m³/h) selon la hauteur manométrique totale (m).
      </p>
      <ChartFrame
        label={`Courbe de pompe de ${produit.nom} : débit en m³/h selon la HMT en m`}
        caption="Points de la courbe constructeur"
        columns={[
          { key: 'debit', header: 'Débit (m³/h)', align: 'right' },
          { key: 'hmt', header: 'HMT (m)', align: 'right' },
        ]}
        rows={points}
        getRowKey={(r, i) => i}
      >
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={points} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
            <CartesianGrid {...CHART_GRID_STYLE} />
            <XAxis
              dataKey="debit"
              type="number"
              domain={[0, 'auto']}
              tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
              tickLine={false}
              axisLine={false}
              label={{ value: 'm³/h', position: 'insideBottomRight',
                       offset: -2, fontSize: 10, fill: CHART_TOKENS.axis }}
            />
            <YAxis
              dataKey="hmt"
              type="number"
              domain={[0, 'auto']}
              width={38}
              tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
              tickLine={false}
              axisLine={false}
              label={{ value: 'm', position: 'insideTopLeft',
                       offset: 0, fontSize: 10, fill: CHART_TOKENS.axis }}
            />
            <Tooltip
              cursor={{ stroke: CHART_TOKENS.grid }}
              content={<ChartTooltip
                labelFormatter={(v) => `${v} m³/h`}
                format={(v) => `${v} m`} />}
            />
            <Line
              type="monotone"
              dataKey="hmt"
              name="HMT"
              stroke={couleur}
              strokeWidth={2}
              dot={{ r: 2, strokeWidth: 0, fill: couleur }}
              activeDot={{ r: 4, strokeWidth: 0 }}
              isAnimationActive={duree > 0}
              animationDuration={duree}
              animationEasing={CHART_ANIM_EASING}
            />
          </LineChart>
        </ResponsiveContainer>
      </ChartFrame>
    </div>
  )
}

// PV8 — fiche technique (PV5, datasheet du produit) : complet/partiel/absent
// selon `type_fiche`. UN appel réseau, filtré serveur par `?produit=` (jamais
// la liste entière) — cohérent avec le reste de l'écran (fiche = 1 produit).
function useFicheTechnique(produitId) {
  // L'état est CLÉ PAR PRODUIT : un changement d'id rend `undefined` (en cours)
  // par dérivation, sans setState synchrone dans l'effet (règle
  // react-hooks/set-state-in-effect — les rendus en cascade).
  const [etat, setEtat] = useState({ id: null, fiche: undefined })
  useEffect(() => {
    let active = true
    stockApi.getFichesTechniques(produitId)
      .then((r) => {
        if (!active) return
        const liste = r.data?.results ?? r.data ?? []
        setEtat({ id: produitId, fiche: liste[0] ?? null })
      })
      .catch(() => { if (active) setEtat({ id: produitId, fiche: null }) })
    return () => { active = false }
  }, [produitId])
  return etat.id === produitId ? etat.fiche : undefined
}

/* ── PVFCH (fondateur 20/08/2026) — la fiche STRUCTURÉE, enfin visible ──────
   « i am expecting a fiche produit that includes all the data separately,
   that I can change — number of MPPT, range of each MPPT, battery voltage… »

   Ces champs existaient (FicheTechnique, PV5/PVOND-H) et étaient éditables
   dans ProduitForm, mais cet onglet ne montrait que marque/garantie/
   description en PROSE : le fondateur regardait la fiche et n'y voyait aucune
   donnée séparée — il en a conclu qu'elle n'existait pas.

   Un champ vide s'affiche « — à renseigner », JAMAIS un défaut ni un zéro :
   c'est la règle « never invent numbers » côté écran, le pendant du refus
   explicite du calcul (apps/ventes/electrical_service.py). Un trou doit se
   VOIR comme un trou, parce que c'est lui qui bloque le chiffrage. */
function FicheStructuree({ fiche }) {
  const groupe = useMemo(() => groupeFicheAffichage(fiche), [fiche])
  if (!groupe) return null
  return (
    <div className="rounded-lg border border-border" data-testid="pdet-fiche-structuree">
      <p className="border-b border-border px-3 py-2 text-xs uppercase tracking-wide text-muted-foreground">
        {groupe.titre} — caractéristiques constructeur
      </p>
      <div className="px-3 py-1">
        {groupe.lignes.map(({ cle, libelle, valeur, absente }) => (
          <div
            key={cle}
            data-testid={`pdet-ft-${cle}`}
            className="flex flex-col gap-0.5 border-b border-border py-2 last:border-b-0 sm:flex-row sm:gap-4"
          >
            <span className="w-full shrink-0 text-xs uppercase tracking-wide text-muted-foreground sm:w-64">
              {libelle}
            </span>
            <span className={absente
              ? 'text-sm italic text-muted-foreground'
              : 'text-sm font-medium tabular-nums text-foreground'}>
              {valeur}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function OngletFicheTechnique({ produit, onEdit }) {
  const fiche = useFicheTechnique(produit.id)
  return (
    <div className="flex flex-col gap-3" data-testid="pdet-fiche-technique">
      {/* PV8 — badge de complétude, même règle que la grille catalogue.
          `fiche === undefined` (chargement) → rien, pour ne pas afficher
          « Fiche absente » une fraction de seconde avant la vraie réponse. */}
      {fiche !== undefined && (
        <div className="flex flex-wrap items-center gap-2" data-testid="pdet-fiche-completude">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            Fiche technique (PV5)
          </span>
          <BadgeCompletudeFiche fiche={fiche} />
          {/* PVFCH — « data … that I can change » : modifier la fiche part de
              LÀ OÙ on la regarde. Le bouton n'existe que si l'appelant sait
              ouvrir l'édition (et donc que l'utilisateur a le droit d'écrire :
              StockList ne passe `onEdit` que dans ce cas). */}
          {onEdit && (
            <Button
              type="button" variant="outline" size="sm" className="ml-auto"
              data-testid="pdet-modifier-fiche"
              onClick={() => onEdit(produit)}
            >
              <Pencil className="size-4" aria-hidden="true" /> Modifier la fiche
            </Button>
          )}
        </div>
      )}

      {/* Les caractéristiques SÉPARÉES, une ligne par variable. */}
      <FicheStructuree fiche={fiche} />

      <div className="rounded-lg border border-border">
        <div className="px-3 py-1">
          <Ligne label="Marque" valeur={produit.marque} />
          <Ligne label="Garantie" valeur={produit.garantie} />
          <Ligne label="Description" valeur={produit.description} />
          {estPompage(produit) && (
            <>
              <Ligne label="Puissance pompe (kW)" valeur={produit.pompe_kw} />
              <Ligne label="Tension (V)" valeur={produit.tension_v} />
            </>
          )}
        </div>
      </div>
      {/* APX21 — la courbe constructeur, quand le produit en porte une. */}
      <CourbePompe produit={produit} />
      <p className="text-xs text-muted-foreground">
        Ces caractéristiques alimentent le chiffrage, le schéma unifilaire et le
        tableau AC/DC : une valeur « à renseigner » n&apos;est jamais remplacée
        par une valeur par défaut — le calcul refuse et dit ce qui manque.
      </p>
    </div>
  )
}

// ── Onglet « En commande » — BCF sources contribuant à la quantité engagée ──
function OngletEnCommande({ produit }) {
  const enCommande = produit.quantite_en_commande ?? 0
  const sources = produit.bcf_sources_en_commande ?? []
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-lg border border-border bg-muted/30 p-3">
        <p className="text-xs text-muted-foreground">Quantité en commande</p>
        <p className="mt-1 text-lg font-semibold tabular-nums">{enCommande}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Somme des restants sur les BCF brouillon/envoyé (jamais annulé/reçu).
        </p>
      </div>
      {sources.length === 0 ? (
        <p className="py-2 text-sm text-muted-foreground">Aucun bon de commande ouvert pour ce produit.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[28rem] text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Bon de commande</th>
                <th className="px-3 py-2 text-left font-semibold">Fournisseur</th>
                <th className="px-3 py-2 text-left font-semibold">Livraison prévue</th>
                <th className="px-3 py-2 text-right font-semibold">Reste à recevoir</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.bon_commande_id} className="border-t border-border">
                  <td className="px-3 py-2 font-mono text-xs">{s.reference}</td>
                  <td className="px-3 py-2">{s.fournisseur_nom ?? <span className="text-muted-foreground">—</span>}</td>
                  <td className="px-3 py-2">{fmtDateFR(s.date_livraison_prevue)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.quantite_restante}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Onglet « Prévisionnel » — solde projeté daté (ZSTK3) ────────────────────
function OngletPrevisionnel({ produitId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.produitPrevisionnel(produitId)
      .then((r) => { if (active) setData(r.data ?? null) })
      .catch(() => { if (active) setError('Rapport prévisionnel indisponible.') })
    return () => { active = false }
  }, [produitId])

  if (error) return <p className="py-3 text-sm text-muted-foreground">{error}</p>
  if (!data) return <Chargement />

  const timeline = data.timeline ?? []

  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-border bg-muted/30 p-3">
          <p className="text-xs text-muted-foreground">Disponible</p>
          <p className="mt-1 text-lg font-semibold tabular-nums">{data.disponible}</p>
        </div>
        <div className="rounded-lg border border-border bg-muted/30 p-3">
          <p className="text-xs text-muted-foreground">Sorties attendues</p>
          <p className="mt-1 text-lg font-semibold tabular-nums">{data.sorties_attendues ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-muted/30 p-3">
          <p className="text-xs text-muted-foreground">Solde projeté</p>
          <p className="mt-1 text-lg font-semibold tabular-nums">{data.solde_projete}</p>
        </div>
      </div>
      {timeline.length === 0 ? (
        <p className="py-2 text-sm text-muted-foreground">Aucun mouvement attendu.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[28rem] text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left font-semibold">Date</th>
                <th className="px-3 py-2 text-left font-semibold">Type</th>
                <th className="px-3 py-2 text-left font-semibold">Référence</th>
                <th className="px-3 py-2 text-right font-semibold">Quantité</th>
                <th className="px-3 py-2 text-right font-semibold">Solde projeté</th>
              </tr>
            </thead>
            <tbody>
              {timeline.map((t, i) => (
                <tr key={i} className="border-t border-border">
                  <td className="px-3 py-2">{fmtDateFR(t.date)}</td>
                  <td className="px-3 py-2">
                    <Badge tone={t.type === 'entree' ? 'success' : 'warning'}>
                      {t.type === 'entree' ? 'Entrée attendue' : 'Sortie réservée'}
                    </Badge>
                  </td>
                  <td className="px-3 py-2">
                    {t.reference
                      ? <span className="font-mono text-xs">{t.reference}{t.fournisseur_nom ? ` · ${t.fournisseur_nom}` : ''}</span>
                      : <span className="text-muted-foreground">—</span>}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    <span className={t.quantite >= 0 ? 'text-success' : 'text-destructive'}>
                      {t.quantite >= 0 ? '+' : ''}{t.quantite}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right font-semibold tabular-nums">{t.solde_projete}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/* ── PVCOMPAT (fondateur 20/08/2026) — onglet « Compatibilités » ───────────
   « don't only show whether the fiche is complete — show COMPATIBILITIES and
   INSTALLABILITY ». Le calcul (apps/ventes/compatibilites.py, exposé via le
   selector stock côté backend) tourne SERVEUR ; cet onglet ne fait qu'AFFICHER
   son verdict — même règle « never invent numbers » que le reste de l'écran :
   les phrases de `bilan.problemes` et les `raison` sont des phrases françaises
   COMPLÈTES envoyées par le serveur, jamais réécrites ni tronquées ici.
   Même style de data-fetch que `useFicheTechnique` : état CLÉ PAR PRODUIT,
   pas de setState synchrone au début de l'effet (pas de flash d'un produit
   sur l'autre pendant un changement rapide d'onglet/produit). */
function useCompatibilites(produitId) {
  const [etat, setEtat] = useState({ id: null, data: undefined, error: false })
  useEffect(() => {
    let active = true
    stockApi.getCompatibilites(produitId)
      .then((r) => { if (active) setEtat({ id: produitId, data: r.data ?? null, error: false }) })
      .catch(() => { if (active) setEtat({ id: produitId, data: null, error: true }) })
    return () => { active = false }
  }, [produitId])
  return etat.id === produitId ? etat : { id: produitId, data: undefined, error: false }
}

// Libellés français par famille. Repli humanisé (underscores → espaces,
// première lettre en majuscule) pour toute famille future non encore
// mappée ici — le contrat dit « extensible … sans changer la forme ».
const FAMILLE_LABELS = {
  panneau: 'Panneaux',
  batterie: 'Batteries',
  onduleur: 'Onduleurs',
  onduleur_hybride: 'Onduleurs hybrides',
  onduleur_reseau: 'Onduleurs réseau',
}
function libelleFamille(famille) {
  if (FAMILLE_LABELS[famille]) return FAMILLE_LABELS[famille]
  const humain = String(famille).replace(/_/g, ' ')
  return humain.charAt(0).toUpperCase() + humain.slice(1)
}

// Une famille de produits potentiellement compatibles : ✓/✗ par produit,
// raison en texte atténué pour un ✗, en ton avertissement pour un ✓ « avec
// réserve » (raison non vide malgré `ok: true` — ex. donnée manquante qui
// n'empêche pas le verdict mais mérite d'être vue).
function FamilleCompat({ famille }) {
  const produits = famille.produits ?? []
  return (
    <div className="rounded-lg border border-border" data-testid={`pdet-compat-famille-${famille.famille}`}>
      <p className="border-b border-border px-3 py-2 text-xs uppercase tracking-wide text-muted-foreground">
        {libelleFamille(famille.famille)}
      </p>
      {produits.length === 0 ? (
        <p className="px-3 py-2 text-sm text-muted-foreground">
          Aucun produit de cette famille dans le stock.
        </p>
      ) : (
        <ul className="px-3 py-1">
          {produits.map((p) => (
            <li
              key={p.id}
              className="flex flex-col gap-0.5 border-b border-border py-2 last:border-b-0 sm:flex-row sm:items-baseline sm:gap-3"
            >
              <span className={p.ok ? 'text-sm text-success' : 'text-sm text-destructive'}>
                <span aria-hidden="true">{p.ok ? '✓' : '✗'}</span>{' '}
                <span className="sr-only">{p.ok ? 'Compatible : ' : 'Non compatible : '}</span>
                {p.nom}
              </span>
              {p.raison && (
                <span className={p.ok ? 'text-xs text-warning' : 'text-xs text-muted-foreground'}>
                  {p.raison}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function OngletCompatibilites({ produit }) {
  const { data, error } = useCompatibilites(produit.id)

  if (error) {
    return <p className="py-3 text-sm text-muted-foreground">Compatibilités indisponibles.</p>
  }
  if (data === undefined) return <Chargement />
  if (!data) {
    return <p className="py-3 text-sm text-muted-foreground">Compatibilités indisponibles.</p>
  }

  const ficheIncomplete = data.fiche_incomplete ?? []
  const { installable, bilan } = data
  const familles = data.familles ?? []

  return (
    <div className="flex flex-col gap-3" data-testid="pdet-compatibilites">
      {ficheIncomplete.length > 0 && (
        <div
          className="rounded-lg border border-warning/40 bg-warning/10 p-3"
          data-testid="pdet-compat-fiche-incomplete"
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-warning">
            Fiche technique incomplète
          </p>
          <ul className="mt-1 list-disc pl-5 text-sm text-foreground">
            {ficheIncomplete.map((label) => <li key={label}>{label}</li>)}
          </ul>
          <p className="mt-1 text-xs text-muted-foreground">
            Ces champs alimentent le chiffrage, le schéma unifilaire — et ce calcul de
            compatibilité : un verdict ci-dessous peut rester incertain tant qu&apos;ils
            manquent.
          </p>
        </div>
      )}

      {bilan && (
        <div className="rounded-lg border border-border" data-testid="pdet-compat-bilan">
          <div className="flex items-center gap-2 border-b border-border px-3 py-2">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              Installable avec le stock actuel
            </span>
            <Badge tone={installable ? 'success' : 'warning'} className="ml-auto">
              {bilan.verdict}
            </Badge>
          </div>
          <div className="flex flex-col gap-2 px-3 py-2">
            {bilan.composition.length > 0 && (
              <ul className="flex flex-col gap-2" data-testid="pdet-compat-composition">
                {bilan.composition.map((item) => (
                  <li
                    key={`${item.role}-${item.produit_id}`}
                    className="border-b border-border pb-2 last:border-b-0 last:pb-0"
                  >
                    <p className="text-sm font-medium text-foreground">
                      {item.nom} × {item.quantite}
                    </p>
                    {item.detail && <p className="text-xs text-muted-foreground">{item.detail}</p>}
                  </li>
                ))}
              </ul>
            )}
            {bilan.problemes.length > 0 && (
              <ul className="flex flex-col gap-1" data-testid="pdet-compat-problemes">
                {bilan.problemes.map((p) => (
                  <li key={p} className="text-sm text-warning">{p}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {familles.map((f) => <FamilleCompat key={f.famille} famille={f} />)}

      <p className="text-xs text-muted-foreground">
        Marque préférée par gamme :{' '}
        <Link to="/parametres/gammes" className="underline">Paramètres → Gammes &amp; marques</Link>.
      </p>
    </div>
  )
}

// Export nommé : testé directement.
export function ProduitDetail({ produit, onClose, onEdit }) {
  // VX98 — bouton « Historique » → Journal pré-filtré sur CE produit, visible
  // uniquement avec la permission journal_activite_voir (AuditLog couvre tous
  // les modèles ; le backend re-vérifie la permission).
  const canViewJournal = useHasPermission('journal_activite_voir')
  // APX18 — icône de catégorie en titre (repli visuel construit d'office) ;
  // repli générique `PackageSearch` si le produit n'a pas de catégorie.
  // Cf. CatalogueTable : resoudre l'icone en ligne via `createElement` plutot
  // que de la lier a une variable PascalCase pendant le rendu (le compilateur
  // React y voit une creation de composant au rendu).
  const iconeTitre = produit.categorie?.nom ? categorieIcone(produit) : PackageSearch
  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {createElement(iconeTitre, {
              className: 'size-4 text-muted-foreground', 'aria-hidden': 'true',
            })}
            {produit.nom}{produit.sku ? ` (${produit.sku})` : ''}
          </DialogTitle>
          <DialogDescription>
            Engagements d&apos;achat, rapport prévisionnel et fiche technique —
            donnée interne, lecture seule.
          </DialogDescription>
        </DialogHeader>

        <EnTetePhoto produit={produit} />

        {/* VX159/VX250 — RelationCounters : réutilise `produit.bcf_sources_en_commande`
            déjà chargé (prop, ZÉRO appel réseau nouveau). Pas de filtre par
            produit sur BonsCommandeFournisseur.jsx (hors périmètre de cette
            tâche) : lien vers la liste NUE, jamais un pré-filtre qui MENT.
            `prix_achat` ne transite jamais par ce composant (label/count
            purement quantitatifs). */}
        <RelationCounters
          className="mb-3"
          counters={[{
            label: 'bons de commande en cours',
            count: produit.bcf_sources_en_commande?.length ?? 0,
            to: '/stock/bons-commande-fournisseur',
          }]}
        />

        <Tabs defaultValue="en-commande">
          <TabsList>
            <TabsTrigger value="en-commande">En commande</TabsTrigger>
            <TabsTrigger value="previsionnel">Prévisionnel</TabsTrigger>
            {/* APX20 — 3ᵉ onglet, à côté des deux onglets achats. */}
            <TabsTrigger value="fiche">Fiche technique</TabsTrigger>
            {/* PVCOMPAT — 4ᵉ onglet : compatibilités + installabilité. */}
            <TabsTrigger value="compat">Compatibilités</TabsTrigger>
            {/* PACT128 — 5ᵉ onglet : groupes d'options de configuration. */}
            <TabsTrigger value="options">Options</TabsTrigger>
          </TabsList>
          <TabsContent value="en-commande">
            <OngletEnCommande produit={produit} />
          </TabsContent>
          <TabsContent value="previsionnel">
            <OngletPrevisionnel produitId={produit.id} />
          </TabsContent>
          <TabsContent value="fiche">
            <OngletFicheTechnique produit={produit} onEdit={onEdit} />
          </TabsContent>
          <TabsContent value="compat">
            <OngletCompatibilites produit={produit} />
          </TabsContent>
          <TabsContent value="options">
            <ProduitOptionsTab produitId={produit.id} />
          </TabsContent>
        </Tabs>

        <DialogFooter>
          {canViewJournal && (
            <Button asChild type="button" variant="outline">
              <Link to={`/journal?model=produit&object_id=${produit.id}`}>
                <History className="size-4" aria-hidden="true" /> Historique
              </Link>
            </Button>
          )}
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export default ProduitDetail

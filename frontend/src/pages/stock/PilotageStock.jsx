import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PieChart, Pie, Cell, Tooltip as RTooltip, ResponsiveContainer } from 'recharts'
import { ShoppingCart, RefreshCw, Download, FileText } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { store } from '../../store'
import { formatMAD } from '../../lib/format'
import { downloadBlob, stampedFilename } from '../../utils/downloadBlob'
import { ouvrirPdfBlob, estBlobPdf, messageErreurBlob } from '../../utils/pdfBlob'
import { ModuleDashboard } from '../../ui/module'
import { Button, Badge, Spinner, DataTable } from '../../ui'
import {
  BarArrondie, ChartEmpty, ChartTooltip, resolveColor, animationDuration, CHART_ANIM_EASING,
} from '../../ui/charts'
import useStockFlags from '../../features/parametres/useStockFlags'

/* ============================================================================
   WR3 — « Pilotage stock » : les analytics stock déjà prêtes côté backend
   (FG54/FG57/FG64/FG65) enfin câblées à l'écran :
     • suggestions de réapprovisionnement + génération d'un BCF brouillon en
       un clic (produits/a-reapprovisionner/ + generer-bcf-reappro/) ;
     • prévisions de demande (previsions-reappro/) ;
     • rotation / stock dormant (rotation/) ;
     • péremptions proches (expirant-bientot/).
   Panneau INTERNE : la valeur au prix d'achat peut s'afficher ici (écran
   fournisseur/admin) mais ne sort jamais vers un document client.
   Chaque rapport charge et échoue indépendamment (les rapports rotation /
   péremption / prévisions sont admin-only → message honnête si 403).

   VX33 — la tour de contrôle : les 4 rapports vivent maintenant sur le moteur
   mini-DataTable (au lieu du <table> HTML brut d'origine), complétés de deux
   graphiques du kit (top 5 à réapprovisionner en barres, donut de rotation
   actif/ralenti/immobile) ; la jauge « santé catalogue » vit dans le rail de
   catégories de StockList.jsx (au-dessus, pas ici).
   ========================================================================== */

// Message FR par section (403 = permission, sinon détail serveur ou repli).
function messageSection(err) {
  if (err?.response?.status === 403) return 'Réservé à l\'administrateur.'
  return err?.response?.data?.detail ?? 'Chargement impossible. Réessayez.'
}

const fmtMad = (v) => formatMAD(v)
const fmtDateFR = (iso) => {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('fr-FR')
}

const MAX_LIGNES = 8

// Tableau compact d'un rapport (état chargement / erreur / vide gérés ici),
// rendu sur le moteur mini-DataTable une fois les données prêtes.
function SectionRapport({ section, columns, getRowId, emptyLabel, footer = null, ariaLabel }) {
  if (section.loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
        <Spinner /> Chargement…
      </div>
    )
  }
  if (section.error) {
    return <p className="py-3 text-sm text-muted-foreground">{section.error}</p>
  }
  const rows = section.data ?? []
  if (rows.length === 0) {
    return <p className="py-3 text-sm text-muted-foreground">{emptyLabel}</p>
  }
  const visibles = rows.slice(0, MAX_LIGNES)
  return (
    <div className="flex flex-col gap-2">
      <DataTable
        data={visibles}
        columns={columns}
        getRowId={getRowId}
        hideToolbar
        hidePagination
        hideMobileCards
        searchable={false}
        aria-label={ariaLabel}
      />
      {rows.length > MAX_LIGNES && (
        <p className="text-xs text-muted-foreground">
          + {rows.length - MAX_LIGNES} autre(s) ligne(s)
        </p>
      )}
      {footer}
    </div>
  )
}

const BUCKET_META = {
  immobile: { label: 'Immobile', tone: 'danger' },
  ralenti: { label: 'Ralenti', tone: 'warning' },
  actif: { label: 'Actif', tone: 'success' },
}

// ---- Colonnes des 4 mini-tableaux (mêmes libellés/formats que le <table>
// HTML d'origine — tri désactivé, ce sont des synthèses, pas des grilles). ----
const REAPPRO_COLUMNS = [
  { id: 'produit', header: 'Produit', sortable: false,
    cell: (v, p) => <>{p.nom}{p.sku ? ` (${p.sku})` : ''}</> },
  { id: 'stock_seuil', header: 'Stock / seuil', sortable: false,
    cell: (v, p) => <span className="tabular-nums">{p.quantite_stock} / {p.seuil_alerte}</span> },
  { id: 'qte_suggeree', header: 'Qté suggérée', sortable: false,
    cell: (v, p) => <span className="font-semibold tabular-nums">{p.quantite_suggere}</span> },
  { id: 'fournisseur', header: 'Fournisseur le − cher', sortable: false,
    cell: (v, p) => p.fournisseur_nom ?? <span className="text-muted-foreground">—</span> },
  { id: 'prix_achat', header: 'Prix achat (interne)', sortable: false,
    cell: (v, p) => <span className="tabular-nums">{p.prix_achat != null ? fmtMad(p.prix_achat) : '—'}</span> },
]

const PREVISIONS_COLUMNS = [
  { id: 'produit', header: 'Produit', sortable: false,
    cell: (v, p) => <>{p.nom}{p.sku ? ` (${p.sku})` : ''}</> },
  { id: 'conso', header: 'Conso / mois', sortable: false,
    cell: (v, p) => <span className="tabular-nums">{p.consommation_mensuelle_moy}</span> },
  { id: 'stock', header: 'Stock', sortable: false,
    cell: (v, p) => <span className="tabular-nums">{p.quantite_stock}</span> },
  { id: 'qte_suggeree', header: 'Qté suggérée', sortable: false,
    cell: (v, p) => <span className="font-semibold tabular-nums">{p.quantite_suggeree}</span> },
]

const ROTATION_COLUMNS = [
  { id: 'produit', header: 'Produit', sortable: false,
    cell: (v, p) => <>{p.nom}{p.sku ? ` (${p.sku})` : ''}</> },
  { id: 'stock', header: 'Stock', sortable: false,
    cell: (v, p) => <span className="tabular-nums">{p.quantite_stock}</span> },
  { id: 'valeur', header: 'Valeur (interne)', sortable: false,
    cell: (v, p) => <span className="tabular-nums">{fmtMad(p.valeur_stock)}</span> },
  { id: 'derniere_sortie', header: 'Dernière sortie', sortable: false,
    cell: (v, p) => (p.derniere_sortie
      ? `${fmtDateFR(p.derniere_sortie)} (${p.jours_sans_mouvement} j)`
      : 'Jamais') },
  { id: 'rotation', header: 'Rotation', sortable: false,
    cell: (v, p) => {
      const meta = BUCKET_META[p.bucket] ?? BUCKET_META.actif
      return <Badge tone={meta.tone}>{meta.label}</Badge>
    } },
]

const EXPIRATIONS_COLUMNS = [
  { id: 'produit', header: 'Produit', sortable: false, cell: (v, l) => l.produit_nom },
  { id: 'lot', header: 'Lot', sortable: false,
    cell: (v, l) => <span className="font-mono text-xs">{l.numero_lot || '—'}</span> },
  { id: 'peremption', header: 'Péremption', sortable: false,
    cell: (v, l) => fmtDateFR(l.date_peremption) },
  { id: 'jours_restants', header: 'Jours restants', sortable: false,
    cell: (v, l) => (
      <span className={l.jours_restants <= 30 ? 'font-semibold tabular-nums text-destructive' : 'tabular-nums'}>
        {l.jours_restants} j
      </span>
    ) },
  { id: 'reception', header: 'Réception', sortable: false,
    cell: (v, l) => <span className="font-mono text-xs">{l.reception_ref || '—'}</span> },
]

// VX33 — donut « rotation » (actif/ralenti/immobile) sur les tokens du kit
// (mêmes tons que le Badge de la mini-table ci-dessus). Légende MAISON (au
// lieu du `<Legend>` recharts) : chaque puce combine libellé + effectif dans
// UN seul nœud texte (« Immobile : 1 »), pour ne jamais dupliquer le libellé
// nu déjà rendu par le Badge de la mini-table rotation.
function RotationDonut({ data }) {
  const dur = animationDuration()
  return (
    <div className="flex flex-col items-center gap-2">
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius={50}
            outerRadius={80}
            paddingAngle={2}
            isAnimationActive={dur > 0}
            animationDuration={dur}
            animationEasing={CHART_ANIM_EASING}
          >
            {data.map((d, i) => <Cell key={i} fill={resolveColor(d.tone)} />)}
          </Pie>
          <RTooltip content={<ChartTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap items-center justify-center gap-3 text-xs text-muted-foreground">
        {data.map((d) => (
          <span key={d.name} className="inline-flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block size-2 shrink-0 rounded-full"
              style={{ background: resolveColor(d.tone) }}
            />
            {d.name} : {d.value}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function PilotageStock({ onBcfGenere }) {
  const navigate = useNavigate()
  // ZSTK13 — masque la colonne « Lot » du registre de péremption quand la
  // société a désactivé les lots/séries (True par défaut = inchangé).
  const { stock_lots_series_actif: lotsSeriesActif } = useStockFlags()
  const expirationsColumns = useMemo(
    () => (lotsSeriesActif
      ? EXPIRATIONS_COLUMNS
      : EXPIRATIONS_COLUMNS.filter((c) => c.id !== 'lot')),
    [lotsSeriesActif],
  )
  const etatInitial = { loading: true, data: null, error: null }
  const [reappro, setReappro] = useState(etatInitial)
  const [previsions, setPrevisions] = useState(etatInitial)
  const [rotation, setRotation] = useState(etatInitial)
  const [expirations, setExpirations] = useState(etatInitial)
  const [genBusy, setGenBusy] = useState(false)
  const [genMsg, setGenMsg] = useState(null)
  const [genErr, setGenErr] = useState(null)
  // ZPUR9/XPUR24 — rapport « analyse d'achats » exportable (Excel + PDF
  // imprimable, au-delà du dashboard écran). Admin/Responsable uniquement.
  const [analyseBusy, setAnalyseBusy] = useState(null) // 'xlsx' | 'pdf' | null
  const [analyseErr, setAnalyseErr] = useState(null)

  const chargeSection = (promise, set) => promise
    .then((r) => set({ loading: false, data: r.data ?? [], error: null }))
    .catch((e) => set({ loading: false, data: null, error: messageSection(e) }))

  const chargerTout = () => {
    setReappro(etatInitial); setPrevisions(etatInitial)
    setRotation(etatInitial); setExpirations(etatInitial)
    chargeSection(stockApi.produitsAReapprovisionner(), setReappro)
    chargeSection(stockApi.previsionsReappro(), setPrevisions)
    chargeSection(stockApi.rotationStock(), setRotation)
    chargeSection(stockApi.expirantBientot(), setExpirations)
  }

  // Le 1er chargement des 4 rapports ne peut arriver que dans un effet ; les
  // setState initiaux (remise à « loading ») sont volontaires.
  // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/set-state-in-effect
  useEffect(() => { chargerTout() }, [])

  // WR3 — auto-PO : génère un BCF BROUILLON pour tous les produits sous seuil
  // (fournisseur le moins cher). Le brouillon reste modifiable avant envoi.
  const genererBcf = async () => {
    setGenBusy(true); setGenMsg(null); setGenErr(null)
    try {
      const r = await stockApi.genererBcfReappro()
      const d = r.data ?? {}
      setGenMsg(`BCF brouillon ${d.reference ?? ''} créé (${d.nb_lignes ?? 0} ligne(s)).`)
      onBcfGenere?.(d)
      chargeSection(stockApi.produitsAReapprovisionner(), setReappro)
    } catch (e) {
      setGenErr(e?.response?.status === 403
        ? 'Réservé aux responsables et administrateurs.'
        : (e?.response?.data?.detail ?? 'La génération du bon de commande a échoué.'))
    } finally { setGenBusy(false) }
  }

  // XPUR24 — export Excel du tableau de bord achats (dépenses, dérive de prix,
  // engagements ouverts, top produits, cycle DA→BCF→réception→facture).
  const exporterAnalyseXlsx = async () => {
    setAnalyseBusy('xlsx'); setAnalyseErr(null)
    try {
      const res = await stockApi.analyseAchatsXlsx()
      // VX81 — nom d'export horodaté, société incluse quand connue (lue au
      // clic, pas d'abonnement — le store singleton évite un useSelector qui
      // forcerait ce panneau interne à dépendre d'un <Provider> en test).
      const societe = store.getState().parametres?.profile?.nom
      downloadBlob(res.data, stampedFilename('analyse-achats', 'xlsx', societe))
    } catch (e) {
      setAnalyseErr(await messageErreurBlob(e, {
        fallback: "L'export Excel de l'analyse d'achats a échoué.",
      }))
    } finally { setAnalyseBusy(null) }
  }

  // ZPUR9 — rapport imprimable « analyse d'achats » (PDF, au-delà de l'export
  // Excel XPUR24) : dépenses par fournisseur/catégorie, top produits,
  // engagements ouverts, identité société. Admin/Responsable uniquement.
  const imprimerAnalysePdf = async () => {
    setAnalyseBusy('pdf'); setAnalyseErr(null)
    try {
      const res = await stockApi.analyseAchatsPdf()
      const blob = res.data
      if (!estBlobPdf(blob)) {
        setAnalyseErr('Le serveur n\'a pas renvoyé de PDF (réponse inattendue). Réessayez.')
        return
      }
      ouvrirPdfBlob(blob, 'analyse-achats.pdf')
    } catch (e) {
      setAnalyseErr(await messageErreurBlob(e, {
        fallback: "La génération du rapport PDF a échoué.",
      }))
    } finally { setAnalyseBusy(null) }
  }

  const nbDormants = (rotation.data ?? []).filter((r) => r.bucket === 'immobile').length

  // VX33 — top 5 à réapprovisionner (barres horizontales) : dérivé du même
  // rapport que la mini-table ci-dessus, zéro appel réseau supplémentaire.
  const top5Reappro = useMemo(() => {
    const rows = reappro.data ?? []
    return [...rows]
      .sort((a, b) => (b.quantite_suggere ?? 0) - (a.quantite_suggere ?? 0))
      .slice(0, 5)
      .map((p) => ({ label: p.sku ? `${p.nom} (${p.sku})` : p.nom, value: p.quantite_suggere ?? 0 }))
  }, [reappro.data])

  // VX33 — donut rotation actif/ralenti/immobile : mêmes compteurs que le KPI
  // « Stock dormant » et la mini-table rotation ci-dessous.
  const rotationBuckets = useMemo(() => {
    const rows = rotation.data ?? []
    const counts = { actif: 0, ralenti: 0, immobile: 0 }
    for (const r of rows) {
      counts[r.bucket] = (counts[r.bucket] ?? 0) + 1
    }
    return Object.entries(BUCKET_META)
      .map(([key, meta]) => ({ name: meta.label, value: counts[key] ?? 0, tone: meta.tone }))
      .filter((d) => d.value > 0)
  }, [rotation.data])

  const stats = [
    { label: 'À réapprovisionner',
      value: reappro.error ? '—' : String((reappro.data ?? []).length),
      hint: reappro.error ?? 'Produits sous leur seuil d\'alerte' },
    { label: 'Prévisions de réappro',
      value: previsions.error ? '—' : String((previsions.data ?? []).length),
      hint: previsions.error ?? 'SKU consommés sur 6 mois' },
    { label: 'Stock dormant',
      value: rotation.error ? '—' : String(nbDormants),
      hint: rotation.error ?? 'Produits sans aucune sortie' },
    { label: 'Péremptions ≤ 90 j',
      value: expirations.error ? '—' : String((expirations.data ?? []).length),
      hint: expirations.error ?? 'Lots reçus expirant bientôt' },
  ]

  const charts = [
    {
      title: 'Suggestions de réapprovisionnement',
      node: (
        <SectionRapport
          section={reappro}
          columns={REAPPRO_COLUMNS}
          getRowId={(p) => p.produit_id}
          ariaLabel="Suggestions de réapprovisionnement"
          emptyLabel="Aucun produit sous son seuil d'alerte."
          footer={(
            <div className="flex flex-wrap items-center gap-2">
              <Button type="button" size="sm" loading={genBusy} onClick={genererBcf}>
                <ShoppingCart /> Générer un BCF (brouillon)
              </Button>
              <Button type="button" size="sm" variant="ghost"
                      onClick={() => navigate('/stock/bons-commande-fournisseur')}>
                Voir les bons de commande
              </Button>
              {genMsg && <span className="text-sm text-success" role="status">{genMsg}</span>}
              {genErr && <span className="text-sm text-destructive" role="alert">{genErr}</span>}
            </div>
          )}
        />
      ),
    },
    {
      title: 'Prévisions de demande (6 derniers mois)',
      node: (
        <SectionRapport
          section={previsions}
          columns={PREVISIONS_COLUMNS}
          getRowId={(p) => p.produit_id}
          ariaLabel="Prévisions de demande"
          emptyLabel="Aucune sortie de stock sur la période."
        />
      ),
    },
    {
      title: 'Rotation / stock dormant',
      node: (
        <SectionRapport
          section={rotation}
          columns={ROTATION_COLUMNS}
          getRowId={(p) => p.produit_id}
          ariaLabel="Rotation et stock dormant"
          emptyLabel="Aucun produit en stock."
        />
      ),
    },
    {
      title: 'Péremptions proches (90 jours)',
      node: (
        <SectionRapport
          section={expirations}
          columns={expirationsColumns}
          getRowId={(l) => l.produit_id}
          ariaLabel="Péremptions proches"
          emptyLabel="Aucun lot n'expire dans les 90 prochains jours."
        />
      ),
    },
    {
      title: 'Top 5 à réapprovisionner',
      node: reappro.loading ? (
        <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
      ) : reappro.error ? (
        <p className="py-3 text-sm text-muted-foreground">{reappro.error}</p>
      ) : top5Reappro.length === 0 ? (
        <ChartEmpty title="Aucune suggestion" description="Aucun produit sous son seuil d'alerte." />
      ) : (
        <BarArrondie
          data={top5Reappro} categoryKey="label" dataKey="value"
          tone="warning" layout="vertical" height={200} name="Qté suggérée"
        />
      ),
    },
    {
      title: 'Rotation du catalogue',
      node: rotation.loading ? (
        <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
      ) : rotation.error ? (
        <p className="py-3 text-sm text-muted-foreground">{rotation.error}</p>
      ) : rotationBuckets.length === 0 ? (
        <ChartEmpty title="Aucune donnée" description="Aucun produit en stock." />
      ) : (
        <RotationDonut data={rotationBuckets} />
      ),
    },
  ]

  return (
    <section aria-label="Pilotage stock"
             className="flex flex-col gap-4 rounded-xl border border-border bg-muted/20 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-display text-base font-semibold tracking-tight">Pilotage stock</h3>
          <p className="text-xs text-muted-foreground">
            Réapprovisionnement, prévisions, rotation et péremptions — donnée interne.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* XPUR24 export Excel + ZPUR9 rapport PDF imprimable — même analyse,
              deux formats (écran/dashboard déjà couvert par les 4 rapports
              ci-dessus). */}
          <Button type="button" variant="outline" size="sm"
                  loading={analyseBusy === 'xlsx'} onClick={exporterAnalyseXlsx}
                  title="Exporter l'analyse d'achats en Excel (admin/responsable)">
            <Download /> Analyse d&apos;achats (Excel)
          </Button>
          <Button type="button" variant="outline" size="sm"
                  loading={analyseBusy === 'pdf'} onClick={imprimerAnalysePdf}
                  title="Rapport imprimable « analyse d'achats » (PDF, admin/responsable)">
            <FileText /> Analyse d&apos;achats (PDF)
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={chargerTout}>
            <RefreshCw /> Actualiser
          </Button>
        </div>
      </div>
      {analyseErr && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {analyseErr}
        </div>
      )}
      <ModuleDashboard stats={stats} charts={charts} />
    </section>
  )
}

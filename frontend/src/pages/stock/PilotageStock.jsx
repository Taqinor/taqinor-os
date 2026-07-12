import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShoppingCart, RefreshCw, Download, FileText } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { store } from '../../store'
import { formatMAD } from '../../lib/format'
import { downloadBlob, stampedFilename } from '../../utils/downloadBlob'
import { ouvrirPdfBlob, estBlobPdf, messageErreurBlob } from '../../utils/pdfBlob'
import { ModuleDashboard } from '../../ui/module'
import { Button, Badge, Spinner } from '../../ui'

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

// Tableau compact d'un rapport (état chargement / erreur / vide gérés ici).
function SectionRapport({ section, head, renderRow, emptyLabel, footer = null }) {
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
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[28rem] text-sm">
          <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>{head.map((h, i) => <th key={i} className="px-3 py-2 text-left font-semibold">{h}</th>)}</tr>
          </thead>
          <tbody>{visibles.map(renderRow)}</tbody>
        </table>
      </div>
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

export default function PilotageStock({ onBcfGenere }) {
  const navigate = useNavigate()
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
          head={['Produit', 'Stock / seuil', 'Qté suggérée', 'Fournisseur le − cher', 'Prix achat (interne)']}
          emptyLabel="Aucun produit sous son seuil d'alerte."
          renderRow={(p) => (
            <tr key={p.produit_id} className="border-t border-border">
              <td className="px-3 py-2">{p.nom}{p.sku ? ` (${p.sku})` : ''}</td>
              <td className="px-3 py-2 tabular-nums">{p.quantite_stock} / {p.seuil_alerte}</td>
              <td className="px-3 py-2 font-semibold tabular-nums">{p.quantite_suggere}</td>
              <td className="px-3 py-2">{p.fournisseur_nom ?? <span className="text-muted-foreground">—</span>}</td>
              <td className="px-3 py-2 tabular-nums">{p.prix_achat != null ? fmtMad(p.prix_achat) : '—'}</td>
            </tr>
          )}
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
          head={['Produit', 'Conso / mois', 'Stock', 'Qté suggérée']}
          emptyLabel="Aucune sortie de stock sur la période."
          renderRow={(p) => (
            <tr key={p.produit_id} className="border-t border-border">
              <td className="px-3 py-2">{p.nom}{p.sku ? ` (${p.sku})` : ''}</td>
              <td className="px-3 py-2 tabular-nums">{p.consommation_mensuelle_moy}</td>
              <td className="px-3 py-2 tabular-nums">{p.quantite_stock}</td>
              <td className="px-3 py-2 font-semibold tabular-nums">{p.quantite_suggeree}</td>
            </tr>
          )}
        />
      ),
    },
    {
      title: 'Rotation / stock dormant',
      node: (
        <SectionRapport
          section={rotation}
          head={['Produit', 'Stock', 'Valeur (interne)', 'Dernière sortie', 'Rotation']}
          emptyLabel="Aucun produit en stock."
          renderRow={(p) => {
            const meta = BUCKET_META[p.bucket] ?? BUCKET_META.actif
            return (
              <tr key={p.produit_id} className="border-t border-border">
                <td className="px-3 py-2">{p.nom}{p.sku ? ` (${p.sku})` : ''}</td>
                <td className="px-3 py-2 tabular-nums">{p.quantite_stock}</td>
                <td className="px-3 py-2 tabular-nums">{fmtMad(p.valeur_stock)}</td>
                <td className="px-3 py-2">
                  {p.derniere_sortie
                    ? `${fmtDateFR(p.derniere_sortie)} (${p.jours_sans_mouvement} j)`
                    : 'Jamais'}
                </td>
                <td className="px-3 py-2"><Badge tone={meta.tone}>{meta.label}</Badge></td>
              </tr>
            )
          }}
        />
      ),
    },
    {
      title: 'Péremptions proches (90 jours)',
      node: (
        <SectionRapport
          section={expirations}
          head={['Produit', 'Lot', 'Péremption', 'Jours restants', 'Réception']}
          emptyLabel="Aucun lot n'expire dans les 90 prochains jours."
          renderRow={(l) => (
            <tr key={l.produit_id} className="border-t border-border">
              <td className="px-3 py-2">{l.produit_nom}</td>
              <td className="px-3 py-2 font-mono text-xs">{l.numero_lot || '—'}</td>
              <td className="px-3 py-2">{fmtDateFR(l.date_peremption)}</td>
              <td className="px-3 py-2 tabular-nums">
                <span className={l.jours_restants <= 30 ? 'font-semibold text-destructive' : ''}>
                  {l.jours_restants} j
                </span>
              </td>
              <td className="px-3 py-2 font-mono text-xs">{l.reception_ref || '—'}</td>
            </tr>
          )}
        />
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

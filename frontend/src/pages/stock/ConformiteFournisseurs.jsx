import { useCallback, useEffect, useMemo, useState } from 'react'
import { ShieldCheck, Download, Clock } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import { downloadBlob, stampedFilename } from '../../utils/downloadBlob'
import { frErrDetail as frErr } from '../../lib/frErr'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import useVoitPrixAchat from '../../features/stock/useVoitPrixAchat'
import {
  Button, DataTable, Badge, Input, FormField,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { EnteteStock } from './EnteteStock'
import { AlerteErreurStock } from './BandeauxListeStock'

/* ENF15 (D-ENF15-STOCK-22) — conformité des fournisseurs : pièces d'onboarding
   qui expirent (NTP2P20), liste de conformité avec son export Excel
   (NTP2P19) et délai de livraison réel vs annoncé (NTSCM11). LECTURE SEULE.
   Le montant acheté est un montant d'achat : colonne absente sans le droit
   « prix d'achat » (le serveur retire aussi la clé). */

const fmtDate = (v) => {
  if (!v) return '—'
  try { return new Date(v).toLocaleDateString('fr-FR') } catch { return '—' }
}
const fmtJours = (v) => (v === null || v === undefined ? '—' : `${v} j`)

// ── Pièces qui expirent ─────────────────────────────────────────────────────
function DocumentsExpirants() {
  const [within, setWithin] = useState('30')
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)

  const charger = useCallback(() => {
    setError(null)
    return stockApi.getDocumentsFournisseurExpirants(Number(within) || 0)
      .then((r) => setRows(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])))
      .catch((err) => setError(frErr(err, 'Chargement des pièces impossible.')))
  }, [within])

  useEffect(() => { Promise.resolve().then(charger) }, [charger])

  const columns = useMemo(() => [
    { id: 'fournisseur_nom', header: 'Fournisseur', minWidth: 160, accessor: (d) => d.fournisseur_nom ?? '' },
    { id: 'type_document_display', header: 'Pièce', minWidth: 160, accessor: (d) => d.type_document_display ?? '' },
    { id: 'date_expiration', header: 'Expire le', width: 130, searchable: false,
      accessor: (d) => d.date_expiration ?? '', cell: (v) => fmtDate(v) },
    { id: 'jours_restants', header: 'Échéance', width: 130, searchable: false,
      accessor: (d) => d.jours_restants ?? 0,
      cell: (v) => (v < 0
        ? <Badge tone="danger">Expirée ({Math.abs(v)} j)</Badge>
        : <Badge tone={v <= 7 ? 'warning' : 'muted'}>Dans {v} j</Badge>) },
  ], [])

  return (
    <section className="flex flex-col gap-3" aria-labelledby="cf-docs-titre">
      <h2 id="cf-docs-titre" className="flex items-center gap-1.5 text-sm font-semibold">
        <Clock className="size-4" aria-hidden="true" /> Pièces qui expirent
      </h2>
      <div className="flex flex-wrap items-end gap-2">
        <FormField label="Horizon (jours)" htmlFor="cf-within">
          <Input id="cf-within" className="w-28" type="number" step="1" min="0" max="36500"
                 value={within} onChange={(e) => setWithin(e.target.value)} />
        </FormField>
      </div>
      <AlerteErreurStock error={error} />
      <DataTable
        data={rows ?? []}
        columns={columns}
        loading={rows === null && !error}
        getRowId={(d) => d.document_id}
        searchPlaceholder="Rechercher (fournisseur, pièce)…"
        globalColumns={['fournisseur_nom', 'type_document_display']}
        emptyTitle="Aucune pièce à renouveler"
        emptyDescription="Aucune pièce d'onboarding n'expire dans cet horizon."
        aria-label="Pièces fournisseur qui expirent"
      />
    </section>
  )
}

// ── Liste de conformité + export Excel ──────────────────────────────────────
function ListeConformite({ voitMontants }) {
  const [debut, setDebut] = useState('')
  const [fin, setFin] = useState('')
  const [rows, setRows] = useState(null)
  const [error, setError] = useState(null)
  const [export_, setExport] = useState(false)

  const params = useMemo(() => ({
    ...(debut ? { debut } : {}), ...(fin ? { fin } : {}),
  }), [debut, fin])

  useEffect(() => {
    let annule = false
    Promise.resolve().then(() => {
      setError(null)
      return stockApi.getConformiteFournisseurs(params)
        .then((r) => { if (!annule) setRows(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])) })
        .catch((err) => { if (!annule) setError(frErr(err, 'Chargement de la conformité impossible.')) })
    })
    return () => { annule = true }
  }, [params])

  const exporter = async () => {
    setExport(true)
    setError(null)
    try {
      const res = await stockApi.exportConformiteFournisseursXlsx(params)
      downloadBlob(res.data, stampedFilename('conformite-fournisseurs', 'xlsx'))
    } catch (err) {
      setError(frErr(err, "L'export a échoué."))
    } finally { setExport(false) }
  }

  // Colonne montant : seulement si le droit est là ET que le serveur l'a servie.
  const avecMontant = voitMontants && (rows ?? []).some((l) => 'montant_achete' in l)

  const columns = useMemo(() => {
    const cols = [
      { id: 'fournisseur', header: 'Fournisseur', minWidth: 160, accessor: (l) => l.fournisseur ?? '' },
      { id: 'statut_onboarding', header: 'Onboarding', minWidth: 130, accessor: (l) => l.statut_onboarding ?? '' },
      { id: 'score_risque', header: 'Risque', width: 130, searchable: false,
        accessor: (l) => l.score_risque ?? -1,
        cell: (_v, l) => (l.score_risque === null || l.score_risque === undefined
          ? <span className="text-muted-foreground">—</span>
          : <span>{l.score_risque}/100 {l.niveau_risque ? `· ${l.niveau_risque}` : ''}</span>) },
      { id: 'documents_expires', header: 'Pièces expirées', minWidth: 150, searchable: false,
        accessor: (l) => l.documents_expires ?? '', cell: (v) => v || <span className="text-muted-foreground">—</span> },
      { id: 'documents_manquants', header: 'Pièces manquantes', minWidth: 150, searchable: false,
        accessor: (l) => l.documents_manquants ?? '', cell: (v) => v || <span className="text-muted-foreground">—</span> },
      { id: 'dernier_retard_le', header: 'Dernier retard', width: 150, searchable: false,
        accessor: (l) => l.dernier_retard_le ?? '',
        cell: (_v, l) => (l.dernier_retard_le
          ? `${fmtDate(l.dernier_retard_le)} (${fmtJours(l.dernier_retard_jours)})`
          : <span className="text-muted-foreground">—</span>) },
    ]
    if (avecMontant) {
      cols.push({ id: 'montant_achete', header: 'Acheté (HT)', align: 'right', width: 140, searchable: false,
        accessor: (l) => Number(l.montant_achete ?? 0), cell: (_v, l) => formatMAD(l.montant_achete) })
    }
    return cols
  }, [avecMontant])

  return (
    <section className="flex flex-col gap-3" aria-labelledby="cf-liste-titre">
      <h2 id="cf-liste-titre" className="flex items-center gap-1.5 text-sm font-semibold">
        <ShieldCheck className="size-4" aria-hidden="true" /> Conformité par fournisseur
      </h2>
      <div className="flex flex-wrap items-end gap-2">
        <FormField label="Du" htmlFor="cf-debut">
          <Input id="cf-debut" type="date" value={debut} onChange={(e) => setDebut(e.target.value)} />
        </FormField>
        <FormField label="Au" htmlFor="cf-fin">
          <Input id="cf-fin" type="date" value={fin} onChange={(e) => setFin(e.target.value)} />
        </FormField>
        <Button type="button" variant="outline" loading={export_} onClick={exporter}>
          <Download className="size-4" aria-hidden="true" /> Exporter en Excel
        </Button>
      </div>
      <AlerteErreurStock error={error} />
      <DataTable
        data={rows ?? []}
        columns={columns}
        loading={rows === null && !error}
        getRowId={(l) => l.fournisseur_id}
        searchPlaceholder="Rechercher un fournisseur…"
        globalColumns={['fournisseur']}
        emptyTitle="Aucun fournisseur actif"
        emptyDescription="La conformité se calcule pour chaque fournisseur actif."
        aria-label="Conformité des fournisseurs"
      />
    </section>
  )
}

// ── Délai réel vs annoncé ───────────────────────────────────────────────────
function DelaiReelVsAnnonce() {
  const [fournisseurs, setFournisseurs] = useState([])
  const [fournisseurId, setFournisseurId] = useState('')
  const [fenetre, setFenetre] = useState('12')
  const [resultat, setResultat] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    stockApi.getAllFournisseurs({ ordering: 'nom' })
      .then((r) => setFournisseurs(r.data ?? []))
      .catch(() => {})
  }, [])

  const calculer = async () => {
    if (!fournisseurId) { setError('Choisissez un fournisseur.'); return }
    setLoading(true)
    setError(null)
    try {
      const r = await stockApi.getDelaiMesureFournisseur(fournisseurId, { fenetre_mois: Number(fenetre) || 12 })
      setResultat(r.data)
    } catch (err) {
      setResultat(null)
      setError(frErr(err, 'Mesure indisponible.'))
    } finally { setLoading(false) }
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-muted/30 p-3"
             aria-labelledby="cf-delai-titre">
      <h2 id="cf-delai-titre" className="flex items-center gap-1.5 text-sm font-semibold">
        <Clock className="size-4" aria-hidden="true" /> Délai de livraison réel et annoncé
      </h2>
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[14rem] flex-1">
          <Select value={fournisseurId} onValueChange={setFournisseurId}>
            <SelectTrigger aria-label="Fournisseur"><SelectValue placeholder="Choisir un fournisseur…" /></SelectTrigger>
            <SelectContent>
              {fournisseurs.map((f) => (
                <SelectItem key={f.id} value={String(f.id)}>{f.nom}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Input className="w-24" type="number" step="1" min="1" max="36" value={fenetre}
               onChange={(e) => setFenetre(e.target.value)} aria-label="Fenêtre (mois)" />
        <Button type="button" onClick={calculer} loading={loading}>Mesurer</Button>
      </div>
      <AlerteErreurStock error={error} />
      {resultat && (
        resultat.nb_mesures === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucune livraison confirmée sur {resultat.fenetre_mois} mois : rien à mesurer.
          </p>
        ) : (
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div><dt className="text-xs text-muted-foreground">Annoncé</dt><dd className="font-semibold tabular-nums">{fmtJours(resultat.delai_annonce_jours)}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Mesuré ({resultat.nb_mesures} livraison(s))</dt><dd className="font-semibold tabular-nums">{fmtJours(resultat.delai_mesure_jours)}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Écart</dt><dd className="font-semibold tabular-nums">{fmtJours(resultat.ecart_jours)}{resultat.ecart_pct ? ` (${resultat.ecart_pct} %)` : ''}</dd></div>
            <div><dt className="text-xs text-muted-foreground">Délai retenu</dt><dd className="font-semibold tabular-nums">{fmtJours(resultat.delai_retenu_jours)}</dd></div>
            {resultat.utiliser_delai_reel && (
              <p className="col-span-full text-xs text-muted-foreground">
                L&apos;écart dépasse {resultat.seuil_ecart_pct} % : le délai réel est retenu pour le point de commande.
              </p>
            )}
          </dl>
        )
      )}
    </section>
  )
}

export default function ConformiteFournisseurs() {
  const gestionnaire = useIsAdminOrResponsable()
  const voitMontants = useVoitPrixAchat()

  return (
    <div className="ui-root flex flex-col gap-6 px-4 py-5 sm:px-5">
      <EnteteStock
        icon={ShieldCheck}
        title="Conformité fournisseurs"
        subtitle="Pièces qui expirent, conformité de chaque fournisseur actif et fiabilité des délais de livraison."
      />
      <DocumentsExpirants />
      <ListeConformite voitMontants={voitMontants} />
      {gestionnaire && <DelaiReelVsAnnonce />}
    </div>
  )
}

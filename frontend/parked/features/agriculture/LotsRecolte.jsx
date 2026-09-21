// PACT79 — Écran Agriculture → Lots de récolte (NTAGR15 / NTAGR16).
//
// `agriculture.LotRecolte` porte le lot par CAMPAGNE (date, quantité en
// quintaux, calibre, grille de qualité libre) avec un rattachement OPTIONNEL à
// un lot de stock physique, en LECTURE SEULE. Le client agricole câblait ses 11
// autres ressources et n'avait aucune entrée pour celle-ci.
//
// Deux garanties reprises telles quelles du serveur, jamais réimplémentées ici :
//   • le NUMÉRO DE LOT est généré côté serveur (`core.numbering`, anti-collision
//     par société) — le formulaire ne le propose donc jamais à la saisie ;
//   • le lot stock physique n'est PAS un second système de traçabilité : le
//     champ `stock_lot_id` référence le `numero_lot` public d'un lot d'entrepôt
//     existant, et la traçabilité amont-aval est calculée par le serveur
//     (`…/lots-recolte/{id}/tracabilite/`, qui lit `apps.stock` par ses
//     selectors). Un lot sans rattachement s'arrête proprement à l'amont — ce
//     n'est pas une erreur, et l'écran le dit.
//
// Multi-tenant : `company` n'est JAMAIS envoyée — imposée côté serveur.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Wheat, Plus, Search, Link2 } from 'lucide-react'
import api from '../../api/axios'
import { toast } from '../../ui/confirm'
import { frenchError } from '../../lib/frenchError'
import {
  Button, Input, Badge, Spinner, EmptyState, Card, CardContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

const VIDE = {
  campagne: '', date_recolte: '', quantite_qtl: '',
  calibre: '', qualite: '', stock_lot_id: '',
}

// Date stockée en YYYY-MM-DD : affichée telle quelle, jamais reconvertie via un
// fuseau (une date de récolte glisserait d'un jour).
const fmtDate = (valeur) => {
  if (!valeur) return '—'
  const m = String(valeur).match(/^(\d{4})-(\d{2})-(\d{2})/)
  return m ? `${m[3]}/${m[2]}/${m[1]}` : String(valeur)
}

const libelleCampagne = (c) => (c
  ? `${c.culture}${c.variete ? ` (${c.variete})` : ''}${c.date_semis ? ` — semis ${fmtDate(c.date_semis)}` : ''}`
  : '')

export default function LotsRecolte() {
  const [lots, setLots] = useState([])
  const [campagnes, setCampagnes] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busy, setBusy] = useState(false)
  const [recherche, setRecherche] = useState('')
  const [draft, setDraft] = useState(VIDE)
  const [trace, setTrace] = useState(null)

  const charger = useCallback(() => api.get('/agriculture/lots-recolte/')
    .then((res) => {
      setLots(res.data?.results ?? res.data ?? [])
      setLoadError(false)
    })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false)), [])

  useEffect(() => { charger() }, [charger])

  // Campagnes disponibles pour le rattachement (un lot appartient toujours à
  // une campagne). Leur absence n'empêche pas de consulter les lots existants.
  useEffect(() => {
    let annule = false
    api.get('/agriculture/campagnes/')
      .then((res) => {
        if (annule) return
        const rows = res.data?.results ?? res.data ?? []
        setCampagnes(Array.isArray(rows) ? rows : [])
      })
      .catch(() => { if (!annule) setCampagnes([]) })
    return () => { annule = true }
  }, [])

  const campagneLabel = useCallback((id) => {
    const c = campagnes.find((x) => String(x.id) === String(id))
    return c ? libelleCampagne(c) : `Campagne #${id}`
  }, [campagnes])

  // Recherche locale sur le numéro de lot, le calibre, la qualité et le lot
  // stock rattaché — c'est par là qu'on « retrouve » un lot depuis sa
  // traçabilité stock.
  const visibles = useMemo(() => {
    const q = recherche.trim().toLowerCase()
    if (!q) return lots
    return lots.filter((l) => [l.numero_lot, l.calibre, l.qualite, l.stock_lot_id]
      .some((v) => String(v || '').toLowerCase().includes(q)))
  }, [lots, recherche])

  const creer = async () => {
    if (!draft.campagne || !draft.date_recolte || !(Number(draft.quantite_qtl) > 0)) return
    setBusy(true)
    try {
      const res = await api.post('/agriculture/lots-recolte/', {
        campagne: Number(draft.campagne),
        date_recolte: draft.date_recolte,
        quantite_qtl: draft.quantite_qtl,
        calibre: draft.calibre.trim(),
        qualite: draft.qualite.trim(),
        stock_lot_id: draft.stock_lot_id.trim(),
      })
      const numero = res.data?.numero_lot
      if (numero) toast.success(`Lot ${numero} créé.`)
      setDraft(VIDE)
      charger()
    } catch (e) {
      toast.error(frenchError(e, 'Création du lot impossible.'))
    } finally { setBusy(false) }
  }

  const tracer = async (lot) => {
    setTrace(null)
    try {
      const res = await api.get(`/agriculture/lots-recolte/${lot.id}/tracabilite/`)
      setTrace(res.data ?? null)
    } catch (e) {
      toast.error(frenchError(e, 'Traçabilité indisponible.'))
    }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-[1100px] p-6">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4 text-primary" /> Chargement…
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-[1100px] flex-col gap-4 p-6">
      <div>
        <h2 className="font-display text-xl font-bold tracking-tight text-foreground">
          Lots de récolte
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Un lot par campagne : date, quantité en quintaux, calibre et grille de
          qualité. Le numéro de lot est attribué par le serveur. Quand le
          produit récolté est aussi suivi en stock, indiquez le numéro du lot
          d'entrepôt : la traçabilité amont-aval devient consultable.
        </p>
      </div>

      {/* ── Recherche + liste ───────────────────────────────────────────── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <div className="mb-3 w-full max-w-[420px]">
            <Input value={recherche} aria-label="Rechercher un lot"
              leading={<Search className="size-4" aria-hidden="true" />}
              placeholder="N° de lot, calibre, qualité ou lot d'entrepôt…"
              onChange={(e) => setRecherche(e.target.value)} />
          </div>

          {loadError ? (
            <EmptyState title="Impossible de charger les lots de récolte"
              description="Une erreur est survenue lors du chargement." className="py-6" />
          ) : visibles.length === 0 ? (
            <EmptyState icon={Wheat} title="Aucun lot de récolte"
              description="Enregistrez votre premier lot ci-dessous."
              className="py-6" />
          ) : (
            <div className="flex flex-col gap-1.5">
              {visibles.map((lot) => (
                <div key={lot.id} data-testid={`lot-${lot.id}`}
                  className="flex flex-wrap items-center gap-1.5 rounded-lg border border-border p-3">
                  <span className="min-w-[120px] flex-[1_1_120px] text-sm font-medium">
                    {lot.numero_lot || `Lot #${lot.id}`}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {campagneLabel(lot.campagne)}
                  </span>
                  <Badge tone="neutral">{fmtDate(lot.date_recolte)}</Badge>
                  <Badge tone="info">{lot.quantite_qtl} qx</Badge>
                  {lot.calibre && <Badge tone="neutral">Calibre {lot.calibre}</Badge>}
                  {lot.qualite && <Badge tone="neutral">Qualité {lot.qualite}</Badge>}
                  {lot.stock_lot_id ? (
                    <Badge tone="success">
                      <Link2 className="mr-1 inline size-3" aria-hidden="true" />
                      Lot d'entrepôt {lot.stock_lot_id}
                    </Badge>
                  ) : (
                    <Badge tone="neutral">Sans lot d'entrepôt</Badge>
                  )}
                  <div className="ml-auto">
                    <Button type="button" size="sm" variant="outline"
                      onClick={() => tracer(lot)}>
                      Traçabilité
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Traçabilité du lot consulté ─────────────────────────────────── */}
      {trace && (
        <Card>
          <CardContent className="pt-4 sm:pt-5" data-testid="tracabilite-lot">
            <h3 className="mb-2 text-sm font-semibold tracking-tight text-foreground">
              Traçabilité du lot {trace.numero_lot}
            </h3>
            <p className="text-xs text-muted-foreground">
              Amont : parcelle {trace.amont?.parcelle_nom ?? '—'}
              {trace.amont?.culture ? ` — ${trace.amont.culture}` : ''}
              {' · '}
              {(trace.amont?.traitements?.length ?? 0)} traitement(s) enregistré(s).
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {trace.aval
                ? "Aval : le lot est rattaché à un lot d'entrepôt, sa chaîne stock est remontée."
                : "Aval : ce lot n'est rattaché à aucun lot d'entrepôt — la traçabilité s'arrête à l'amont."}
            </p>
          </CardContent>
        </Card>
      )}

      {/* ── Saisie d'un lot ─────────────────────────────────────────────── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <h3 className="mb-1 text-sm font-semibold tracking-tight text-foreground">
            Enregistrer un lot
          </h3>
          <p className="mb-3 text-[11.5px] text-muted-foreground">
            Le numéro de lot est généré par le serveur au moment de
            l'enregistrement — il n'est jamais saisi ici, ce qui évite toute
            collision entre deux saisies simultanées.
          </p>
          <div className="flex flex-wrap items-end gap-1.5">
            <div className="min-w-[220px] flex-[2_1_220px]">
              <Select value={draft.campagne}
                onValueChange={(v) => setDraft((d) => ({ ...d, campagne: v }))}>
                <SelectTrigger aria-label="Campagne">
                  <SelectValue placeholder="Campagne culturale" />
                </SelectTrigger>
                <SelectContent>
                  {campagnes.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {libelleCampagne(c)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Input className="w-[160px]" type="date" aria-label="Date de récolte"
              value={draft.date_recolte}
              onChange={(e) => setDraft((d) => ({ ...d, date_recolte: e.target.value }))} />
            <Input className="w-[140px]" type="number" step="any"
              aria-label="Quantité en quintaux" placeholder="Quintaux"
              value={draft.quantite_qtl}
              onChange={(e) => setDraft((d) => ({ ...d, quantite_qtl: e.target.value }))} />
            <Input className="w-[120px]" aria-label="Calibre" placeholder="Calibre"
              value={draft.calibre}
              onChange={(e) => setDraft((d) => ({ ...d, calibre: e.target.value }))} />
            <Input className="w-[120px]" aria-label="Qualité" placeholder="Qualité"
              value={draft.qualite}
              onChange={(e) => setDraft((d) => ({ ...d, qualite: e.target.value }))} />
            <Input className="w-[180px]" aria-label="Lot d'entrepôt (facultatif)"
              placeholder="Lot d'entrepôt (facultatif)"
              value={draft.stock_lot_id}
              onChange={(e) => setDraft((d) => ({ ...d, stock_lot_id: e.target.value }))} />
            <Button type="button" onClick={creer} disabled={busy}>
              <Plus className="size-4" aria-hidden="true" /> Enregistrer le lot
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

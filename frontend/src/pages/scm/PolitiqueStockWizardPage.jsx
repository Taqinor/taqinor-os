import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Check } from 'lucide-react'
import scmApi from '../../api/scmApi'
import stockApi from '../../api/stockApi'
import { Button, Badge, Skeleton } from '../../ui'
import { StateBlock } from '../../components/StateBlock'

/* ============================================================================
   NTSCM30 — Assistant guidé « Créer une politique de stock » : 1) sélection
   produit(s) — multi-sélection filtrable catégorie/classe ABC ; 2) niveau de
   service PRÉ-REMPLI selon la classe ABC dominante de la sélection ; 3)
   aperçu avant validation, appliquée en lot via
   `services.creer_politiques_en_lot` (NTSCM30, action `creer-en-lot`).
   ========================================================================== */

const NIVEAU_PAR_CLASSE = { A: 95, B: 90, C: 85 }

export default function PolitiqueStockWizardPage() {
  const navigate = useNavigate()
  const [etape, setEtape] = useState(1)

  const [produits, setProduits] = useState([])
  const [classes, setClasses] = useState({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)

  const [recherche, setRecherche] = useState('')
  const [classeFiltre, setClasseFiltre] = useState('')
  const [selection, setSelection] = useState(() => new Set())

  const [serviceLevel, setServiceLevel] = useState(95)

  const [creerBusy, setCreerBusy] = useState(false)
  const [creerErr, setCreerErr] = useState(null)
  const [resultat, setResultat] = useState(null)

  useEffect(() => {
    Promise.resolve().then(() => {
      setLoading(true)
      Promise.allSettled([
        stockApi.getProduits({ page_size: 500 }),
        scmApi.classificationAbc(),
      ]).then(([produitsRes, classesRes]) => {
        if (produitsRes.status === 'fulfilled') {
          const data = produitsRes.value.data
          setProduits(data?.results ?? data ?? [])
        } else {
          setLoadError("La liste des produits n'a pas pu être chargée.")
        }
        if (classesRes.status === 'fulfilled') {
          const data = classesRes.value.data
          const rows = data?.results ?? data ?? []
          const map = {}
          rows.forEach((r) => { map[r.produit] = r.classe })
          setClasses(map)
        }
      }).finally(() => setLoading(false))
    })
  }, [])

  const produitsFiltres = useMemo(() => {
    const q = recherche.trim().toLowerCase()
    return produits.filter((p) => {
      if (q && !(p.nom || '').toLowerCase().includes(q)) return false
      if (classeFiltre && classes[p.id] !== classeFiltre) return false
      return true
    })
  }, [produits, recherche, classeFiltre, classes])

  const toggleSelection = (id) => {
    setSelection((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const passerEtape2 = () => {
    // Niveau de service PRÉ-REMPLI selon la classe ABC DOMINANTE de la
    // sélection, calculée EN DIRECT au passage à l'étape 2.
    const compte = {}
    selection.forEach((id) => {
      const c = classes[id] || 'C'
      compte[c] = (compte[c] || 0) + 1
    })
    const dominante = Object.entries(compte).sort((a, b) => b[1] - a[1])[0]?.[0] || 'C'
    setServiceLevel(NIVEAU_PAR_CLASSE[dominante] || 95)
    setEtape(2)
  }

  const valider = async () => {
    setCreerBusy(true); setCreerErr(null)
    try {
      const r = await scmApi.creerPolitiquesEnLot({
        produit_ids: Array.from(selection), service_level_pct: serviceLevel,
      })
      setResultat(r.data)
      setEtape(4)
    } catch (e) {
      setCreerErr(e?.response?.data?.produit_ids
        ?? e?.response?.data?.service_level_pct
        ?? e?.response?.data?.detail
        ?? 'La création des politiques a échoué.')
    } finally {
      setCreerBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="ui-root page">
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="ui-root page">
        <StateBlock error={loadError} />
      </div>
    )
  }

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <Button type="button" variant="ghost" size="sm" onClick={() => navigate('/scm/reappro')}>
          <ArrowLeft /> Retour
        </Button>
        <h2>Assistant — Créer une politique de stock</h2>
        <p className="text-sm text-muted-foreground">
          Étape {Math.min(etape, 3)} sur 3
          {etape === 1 && ' — Sélection des produits'}
          {etape === 2 && ' — Paramètres'}
          {etape === 3 && ' — Aperçu et validation'}
        </p>
      </div>

      {etape === 1 && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="text" placeholder="Rechercher un produit…" value={recherche}
              onChange={(e) => setRecherche(e.target.value)}
              className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
              aria-label="Rechercher un produit"
            />
            <select
              value={classeFiltre} onChange={(e) => setClasseFiltre(e.target.value)}
              className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
              aria-label="Filtrer par classe ABC"
            >
              <option value="">Toutes les classes</option>
              <option value="A">Classe A</option>
              <option value="B">Classe B</option>
              <option value="C">Classe C</option>
            </select>
            <span className="text-sm text-muted-foreground">
              {selection.size} sélectionné(s)
            </span>
          </div>
          <div className="max-h-96 overflow-y-auto rounded-lg border border-border">
            {produitsFiltres.length === 0 ? (
              <div className="p-4 text-sm text-muted-foreground">
                Aucun produit ne correspond.
              </div>
            ) : produitsFiltres.map((p) => (
              <label
                key={p.id}
                className="flex items-center gap-2 border-b border-border p-2 text-sm last:border-b-0 hover:bg-muted/30"
              >
                <input
                  type="checkbox" checked={selection.has(p.id)}
                  onChange={() => toggleSelection(p.id)}
                />
                <span className="flex-1">{p.nom}</span>
                {classes[p.id] && <Badge tone="neutral">Classe {classes[p.id]}</Badge>}
              </label>
            ))}
          </div>
          <div>
            <Button type="button" disabled={selection.size === 0} onClick={passerEtape2}>
              Suivant <ArrowRight />
            </Button>
          </div>
        </div>
      )}

      {etape === 2 && (
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Niveau de service (%)
            <input
              type="number" min="1" max="99.99" step="0.1" value={serviceLevel}
              onChange={(e) => setServiceLevel(e.target.value)}
              className="w-40 rounded-md border border-border bg-background px-2 py-1.5"
            />
          </label>
          <p className="text-xs text-muted-foreground">
            Pré-rempli selon la classe ABC dominante de la sélection
            ({selection.size} produit(s)) — modifiable avant validation.
          </p>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => setEtape(1)}>
              <ArrowLeft /> Précédent
            </Button>
            <Button type="button" onClick={() => setEtape(3)}>
              Aperçu <ArrowRight />
            </Button>
          </div>
        </div>
      )}

      {etape === 3 && (
        <div className="flex flex-col gap-3">
          <p className="text-sm">
            {selection.size} politique(s) de stock seront créées/mises à jour
            avec un niveau de service de <strong>{serviceLevel}%</strong>. Le
            point de commande (ROP) sera calculé automatiquement à la
            validation.
          </p>
          <ul className="max-h-64 overflow-y-auto rounded-lg border border-border text-sm">
            {Array.from(selection).map((id) => {
              const p = produits.find((pr) => pr.id === id)
              return (
                <li key={id} className="border-b border-border p-2 last:border-b-0">
                  {p?.nom ?? id}
                </li>
              )
            })}
          </ul>
          {creerErr && <span className="text-sm text-destructive" role="alert">{creerErr}</span>}
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => setEtape(2)}>
              <ArrowLeft /> Précédent
            </Button>
            <Button type="button" loading={creerBusy} onClick={valider}>
              <Check /> Créer {selection.size} politique(s)
            </Button>
          </div>
        </div>
      )}

      {etape === 4 && resultat && (
        <div className="flex flex-col gap-3">
          <div role="status" className="rounded-lg border border-success/40 bg-success/10 p-3 text-sm">
            {resultat.nb_politiques} politique(s) de stock créée(s)/mise(s) à jour.
          </div>
          <Button type="button" onClick={() => navigate('/scm/reappro')}>
            Voir le tableau de bord réappro
          </Button>
        </div>
      )}
    </div>
  )
}

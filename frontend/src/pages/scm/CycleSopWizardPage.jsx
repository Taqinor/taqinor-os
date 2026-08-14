import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, ArrowRight, Sparkles, Check } from 'lucide-react'
import scmApi from '../../api/scmApi'
import stockApi from '../../api/stockApi'
import { Button, Skeleton } from '../../ui'

/* ============================================================================
   NTSCM31 — Assistant guidé « Lancer un cycle S&OP » : 1) période cible +
   rappel des produits actifs concernés ; 2) génère (rafraîchit) les
   prévisions de demande (NTSCM2) avant de geler la demande consensuelle ;
   3) confirme la création du cycle en statut brouillon (NTSCM12). Un second
   cycle sur la MÊME période/société affiche une erreur claire au lieu d'un
   500 (contrainte unique déjà en base, `CyclePlanificationSOPSerializer.
   validate_periode`).
   ========================================================================== */

const moisSuivant = () => {
  const d = new Date()
  d.setMonth(d.getMonth() + 1)
  return d.toISOString().slice(0, 7)
}

export default function CycleSopWizardPage() {
  const navigate = useNavigate()
  const [etape, setEtape] = useState(1)
  const [periode, setPeriode] = useState(moisSuivant())

  const [nbProduits, setNbProduits] = useState(null)
  const [loading, setLoading] = useState(true)

  const [genererBusy, setGenererBusy] = useState(false)
  const [nbGenerees, setNbGenerees] = useState(null)

  const [creerBusy, setCreerBusy] = useState(false)
  const [creerErr, setCreerErr] = useState(null)

  useEffect(() => {
    Promise.resolve().then(() => {
      setLoading(true)
      stockApi.getProduits({ page_size: 1 })
        .then((r) => setNbProduits(
          r.data?.count ?? (r.data?.results ?? r.data ?? []).length))
        .catch(() => setNbProduits(null))
        .finally(() => setLoading(false))
    })
  }, [])

  const genererPrevisionsManquantes = async () => {
    setGenererBusy(true)
    try {
      const r = await stockApi.getProduits({ page_size: 500 })
      const produits = r.data?.results ?? r.data ?? []
      const resultats = await Promise.allSettled(
        produits.map((p) => scmApi.genererPrevisions(
          { produit_id: p.id, horizon_mois: 3 })))
      setNbGenerees(resultats.filter((res) => res.status === 'fulfilled').length)
      setEtape(3)
    } finally {
      setGenererBusy(false)
    }
  }

  const creerCycle = async () => {
    setCreerBusy(true); setCreerErr(null)
    try {
      const r = await scmApi.creerCycleSop({ periode })
      navigate(`/scm/sop/${r.data.id}`)
    } catch (e) {
      setCreerErr(e?.response?.data?.periode?.[0]
        ?? e?.response?.data?.periode
        ?? e?.response?.data?.detail
        ?? 'La création du cycle a échoué.')
    } finally {
      setCreerBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="ui-root page">
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <Button type="button" variant="ghost" size="sm" onClick={() => navigate('/scm/sop')}>
          <ArrowLeft /> Retour aux cycles
        </Button>
        <h2>Assistant — Lancer un cycle S&amp;OP</h2>
        <p className="text-sm text-muted-foreground">Étape {etape} sur 3</p>
      </div>

      {etape === 1 && (
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Période cible (mois du cycle)
            <input
              type="month" value={periode} onChange={(e) => setPeriode(e.target.value)}
              className="w-48 rounded-md border border-border bg-background px-2 py-1.5"
              aria-label="Période cible"
            />
          </label>
          <p className="text-sm text-muted-foreground">
            {nbProduits != null
              ? `${nbProduits} produit(s) actif(s) concerné(s) par la planification.`
              : 'Nombre de produits actifs indisponible.'}
          </p>
          <div>
            <Button type="button" onClick={() => setEtape(2)}>
              Suivant <ArrowRight />
            </Button>
          </div>
        </div>
      )}

      {etape === 2 && (
        <div className="flex flex-col gap-3">
          <p className="text-sm">
            Génère (ou rafraîchit) les prévisions de demande de tous les
            produits actifs avant de geler la demande consensuelle du cycle.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="outline" onClick={() => setEtape(1)}>
              <ArrowLeft /> Précédent
            </Button>
            <Button type="button" loading={genererBusy} onClick={genererPrevisionsManquantes}>
              <Sparkles /> Générer les prévisions manquantes
            </Button>
            <Button type="button" variant="ghost" onClick={() => setEtape(3)}>
              Passer cette étape
            </Button>
          </div>
        </div>
      )}

      {etape === 3 && (
        <div className="flex flex-col gap-3">
          {nbGenerees != null && (
            <p className="text-sm text-success" role="status">
              {nbGenerees} prévision(s) générée(s)/rafraîchie(s).
            </p>
          )}
          <p className="text-sm">
            Créer le cycle S&amp;OP <strong>{periode}</strong> en statut brouillon ?
          </p>
          {creerErr && <span className="text-sm text-destructive" role="alert">{creerErr}</span>}
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => setEtape(2)}>
              <ArrowLeft /> Précédent
            </Button>
            <Button type="button" loading={creerBusy} onClick={creerCycle}>
              <Check /> Créer le cycle
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

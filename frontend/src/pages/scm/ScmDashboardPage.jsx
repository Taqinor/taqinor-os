import { useCallback, useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import scmApi from '../../api/scmApi'
import { formatMAD } from '../../lib/format'
import { Button, Skeleton } from '../../ui'
import { StateBlock } from '../../components/StateBlock'

/* ============================================================================
   NTSCM28 — Tableau de bord SCM exécutif : 4 KPI de synthèse (taux de
   service, OTIF fournisseur pondéré dépense, précision de prévision (MAPE),
   valeur de stock par classe ABC). Lecture seule — AUCUN prix d'achat/marge
   n'apparaît ici (règle #4).
   ========================================================================== */

function Carte({ titre, valeur, note }) {
  return (
    <div className="rounded-xl border border-border bg-muted/20 p-4">
      <div className="text-xs text-muted-foreground">{titre}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{valeur}</div>
      {note && <div className="mt-1 text-xs text-muted-foreground">{note}</div>}
    </div>
  )
}

const fmtPct = (v) => (v == null ? '—' : `${v}%`)

export default function ScmDashboardPage() {
  const [donnees, setDonnees] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)

  const charger = useCallback(() => {
    setLoading(true)
    setLoadError(null)
    return scmApi.tableauBordExecutif()
      .then((r) => setDonnees(r.data))
      .catch((e) => setLoadError(
        e?.response?.status === 403
          ? 'Réservé aux responsables et administrateurs.'
          : (e?.response?.data?.detail ?? "Le tableau de bord n'a pas pu être chargé.")))
      .finally(() => setLoading(false))
  }, [])

  // Différé d'un microtask : `charger` pose `loading`/l'erreur de façon
  // synchrone (react-hooks/set-state-in-effect). Comportement inchangé.
  useEffect(() => { Promise.resolve().then(charger) }, [charger])

  if (loading) {
    return (
      <div className="ui-root page">
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (loadError || !donnees) {
    return (
      <div className="ui-root page">
        <StateBlock error={loadError ?? 'Indisponible.'} onRetry={charger} />
      </div>
    )
  }

  const valeurParClasse = donnees.valeur_stock_par_classe_abc || {}

  return (
    <div className="ui-root page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Tableau de bord SCM exécutif</h2>
        <p className="text-sm text-muted-foreground">
          Synthèse pilotage supply chain — donnée interne, aucun prix
          d&apos;achat ni marge n&apos;apparaît ici.
        </p>
        <Button type="button" variant="outline" size="sm" onClick={charger}>
          <RefreshCw /> Actualiser
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Carte
          titre="Taux de service"
          valeur={fmtPct(donnees.taux_service_pct)}
          note="SKU sous politique de stock, hors rupture/à commander"
        />
        <Carte
          titre="OTIF fournisseur (pondéré dépense)"
          valeur={fmtPct(donnees.otif_pondere_pct)}
          note="Proxy taux de remplissage (FG59) en attendant l'OTIF réel (NTSCM8)"
        />
        <Carte
          titre="Précision de prévision (MAPE)"
          valeur={fmtPct(donnees.mape_global_pct)}
          note="Écart moyen prévision vs réel, 6 derniers mois"
        />
        <Carte
          titre="Valeur de stock — Classe A"
          valeur={valeurParClasse.A != null ? formatMAD(valeurParClasse.A) : '—'}
        />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Carte
          titre="Valeur de stock — Classe B"
          valeur={valeurParClasse.B != null ? formatMAD(valeurParClasse.B) : '—'}
        />
        <Carte
          titre="Valeur de stock — Classe C"
          valeur={valeurParClasse.C != null ? formatMAD(valeurParClasse.C) : '—'}
        />
      </div>
    </div>
  )
}

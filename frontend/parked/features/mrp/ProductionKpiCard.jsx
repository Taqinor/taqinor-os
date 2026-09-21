import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Factory } from 'lucide-react'
import mrpApi from '../../api/mrpApi'
import { Card, CardContent } from '../../ui'

/* ============================================================================
   NTMFG22 — Carte « Production » sur le cockpit direction : OF en retard,
   charge moyenne 7j, TRS moyen 7j, alerte maintenance de poste. Réservé
   responsable/admin côté API (`mrp/tableau-bord/`, IsResponsableOrAdmin) —
   un 403 (rôle limité classé « directeur » par erreur côté heuristique
   d'affichage) dégrade en silence, comme un flux vide. Drill-down : clic →
   /mrp/ordres-fabrication (« Atelier MRP »).
   ========================================================================== */

export default function ProductionKpiCard() {
  const navigate = useNavigate()
  const [donnees, setDonnees] = useState(null) // null = en cours/indisponible

  useEffect(() => {
    let alive = true
    mrpApi.getTableauBordProduction()
      .then((resp) => { if (alive) setDonnees(resp.data) })
      .catch(() => { if (alive) setDonnees(null) })
    return () => { alive = false }
  }, [])

  // Rien à afficher tant que le flux n'a pas répondu ou en cas d'échec
  // (403 rôle limité, société sans module mrp actif, etc.).
  if (!donnees) return null

  const goToAtelier = () => navigate('/mrp/ordres-fabrication')
  const onKeyGo = (e) => { if (e.key === 'Enter') goToAtelier() }

  const tuiles = [
    { label: 'OF en retard', valeur: donnees.of_en_retard },
    { label: 'Charge moyenne 7j', valeur: `${donnees.charge_moyenne_pct} %` },
    { label: 'TRS moyen 7j', valeur: `${donnees.trs_moyen_pct} %` },
    { label: 'Postes en alerte entretien', valeur: donnees.postes_en_alerte_maintenance },
  ]

  return (
    <div data-testid="mrp-production-kpi">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
        <Factory size={16} strokeWidth={1.75} aria-hidden="true" />
        Production (Atelier MRP)
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-4">
        {tuiles.map((t) => (
          <Card key={t.label} role="button" tabIndex={0} onClick={goToAtelier}
                onKeyDown={onKeyGo} className="cursor-pointer">
            <CardContent className="py-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">
                {t.label}
              </p>
              <p className="num mt-1 text-2xl font-semibold text-foreground">
                {t.valeur}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

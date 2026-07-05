import { useCallback, useEffect, useState } from 'react'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
  Tabs, TabsList, TabsTrigger, TabsContent,
  DefinitionList, Spinner, EmptyState,
} from '../../ui'
import flotteApi from '../../api/flotteApi'
import { formatMAD, formatNumber } from '../../lib/format'
import { ENERGIES } from './flotte'
import { VehiculeStatutPill } from './statusPills'

/* ============================================================================
   UX16 — Panneau détail d'un véhicule (tiroir latéral à onglets).
   ----------------------------------------------------------------------------
   Identité + carte grise (données déjà en ligne) et 4 fiches calculées chargées
   à la demande via les actions detail=True : TCO (coûts d'exploitation +
   coût/km), éco-conduite (CO₂), amortissement (VNC), TSAV (vignette). Chiffres
   d'exploitation INTERNES — jamais présentés comme prix client ; aucun prix
   d'achat/marge.
   ========================================================================== */

// Onglet générique qui charge une action `fetcher(id)` et rend son payload.
function ComputedTab({ id, fetcher, render, emptyLabel }) {
  const [state, setState] = useState({ loading: true, error: null, data: null })

  const load = useCallback(() => {
    let cancelled = false
    setState({ loading: true, error: null, data: null })
    fetcher(id)
      .then((res) => { if (!cancelled) setState({ loading: false, error: null, data: res?.data ?? null }) })
      .catch((err) => {
        if (!cancelled) {
          setState({
            loading: false,
            error: err?.response?.data?.detail || 'Donnée indisponible.',
            data: null,
          })
        }
      })
    return () => { cancelled = true }
  }, [id, fetcher])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  if (state.loading) {
    return (
      <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
        <Spinner className="size-4" /> Chargement…
      </div>
    )
  }
  if (state.error) {
    return <EmptyState title="Indisponible" description={state.error} />
  }
  if (!state.data) {
    return <EmptyState title={emptyLabel || 'Aucune donnée'} description="Rien à afficher." />
  }
  return render(state.data)
}

export default function VehiculeDetail({ vehicule, onClose }) {
  const v = vehicule
  const open = Boolean(v)

  const identite = [
    { term: 'Immatriculation', description: v?.immatriculation || '—' },
    { term: 'Marque / modèle', description: [v?.marque, v?.modele].filter(Boolean).join(' ') || '—' },
    { term: 'Énergie', description: v?.energie_display || ENERGIES[v?.energie] || '—' },
    { term: 'Puissance fiscale', description: v?.puissance_fiscale ? `${v.puissance_fiscale} CV` : '—' },
    { term: 'Kilométrage', description: v?.kilometrage != null ? `${formatNumber(v.kilometrage)} km` : '—' },
    { term: 'Catégorie de permis requise', description: v?.categorie_permis_requise || '— (aucune)' },
    { term: 'Emplacement de stock', description: v?.emplacement_stock_label || '—' },
    { term: 'Valeur (immobilisation)', description: v?.valeur != null ? formatMAD(v.valeur, { decimals: 0 }) : '—' },
    // ZCTR11 — carte mobilité affichée sur la fiche véhicule.
    { term: 'Carte mobilité', description: v?.carte_mobilite || '—' },
  ]

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose?.() }}>
      <SheetContent side="right" className="w-[min(40rem,calc(100%-2rem))]">
        <SheetHeader>
          <div className="flex flex-wrap items-center gap-2">
            <SheetTitle>{v?.immatriculation || 'Véhicule'}</SheetTitle>
            {v?.statut && <VehiculeStatutPill status={v.statut} />}
          </div>
          <p className="text-sm text-muted-foreground">
            {[v?.marque, v?.modele].filter(Boolean).join(' ')}
          </p>
        </SheetHeader>

        <Tabs defaultValue="identite">
          <TabsList className="flex-wrap">
            <TabsTrigger value="identite">Identité</TabsTrigger>
            <TabsTrigger value="tco">Coûts TCO</TabsTrigger>
            <TabsTrigger value="eco">Éco-conduite</TabsTrigger>
            <TabsTrigger value="amortissement">Amortissement</TabsTrigger>
            <TabsTrigger value="tsav">TSAV</TabsTrigger>
          </TabsList>

          <TabsContent value="identite">
            <DefinitionList items={identite} />
          </TabsContent>

          <TabsContent value="tco">
            <ComputedTab
              id={v?.id}
              fetcher={flotteApi.vehiculeTco}
              emptyLabel="Aucun coût enregistré"
              render={(d) => (
                <DefinitionList
                  items={[
                    { term: 'Carburant', description: formatMAD(d.carburant ?? d.carburant_total, { decimals: 0 }) },
                    { term: 'Réparations', description: formatMAD(d.reparations ?? d.reparations_total, { decimals: 0 }) },
                    { term: 'Pneus & pièces', description: formatMAD(d.pneus_pieces ?? d.pieces, { decimals: 0 }) },
                    { term: 'Infractions', description: formatMAD(d.infractions, { decimals: 0 }) },
                    { term: 'Sinistres', description: formatMAD(d.sinistres, { decimals: 0 }) },
                    { term: 'Coût total', description: formatMAD(d.cout_total ?? d.total, { decimals: 0 }) },
                    { term: 'Coût / km', description: d.cout_par_km != null ? `${formatNumber(d.cout_par_km, { decimals: 2 })} MAD/km` : '—' },
                  ]}
                />
              )}
            />
          </TabsContent>

          <TabsContent value="eco">
            <ComputedTab
              id={v?.id}
              fetcher={flotteApi.vehiculeEcoConduite}
              emptyLabel="Pas de données d’éco-conduite"
              render={(d) => (
                <DefinitionList
                  items={[
                    { term: 'Consommation moyenne', description: d.consommation_moyenne != null ? `${formatNumber(d.consommation_moyenne, { decimals: 1 })} L/100km` : '—' },
                    { term: 'CO₂ (g/km)', description: d.co2_g_km != null ? `${formatNumber(d.co2_g_km)} g/km` : '—' },
                    { term: 'CO₂ total', description: d.co2_total_kg != null ? `${formatNumber(d.co2_total_kg)} kg` : '—' },
                    { term: 'Score éco', description: d.eco_score != null ? formatNumber(d.eco_score) : '—' },
                  ]}
                />
              )}
            />
          </TabsContent>

          <TabsContent value="amortissement">
            <ComputedTab
              id={v?.id}
              fetcher={flotteApi.vehiculeAmortissement}
              emptyLabel="Aucune immobilisation liée"
              render={(d) => (
                <DefinitionList
                  items={[
                    { term: 'Valeur d’acquisition', description: d.valeur_acquisition != null ? formatMAD(d.valeur_acquisition, { decimals: 0 }) : '—' },
                    { term: 'Amortissement cumulé', description: d.amortissement_cumule != null ? formatMAD(d.amortissement_cumule, { decimals: 0 }) : '—' },
                    { term: 'Valeur nette comptable', description: d.vnc != null ? formatMAD(d.vnc, { decimals: 0 }) : '—' },
                  ]}
                />
              )}
            />
          </TabsContent>

          <TabsContent value="tsav">
            <ComputedTab
              id={v?.id}
              fetcher={flotteApi.vehiculeTsav}
              emptyLabel="Barème TSAV indisponible"
              render={(d) => (
                <DefinitionList
                  items={[
                    { term: 'Montant TSAV', description: d.exonere ? 'Exonéré' : (d.montant != null ? formatMAD(d.montant, { decimals: 0 }) : '—') },
                    { term: 'Note', description: d.note || '—' },
                  ]}
                />
              )}
            />
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  )
}

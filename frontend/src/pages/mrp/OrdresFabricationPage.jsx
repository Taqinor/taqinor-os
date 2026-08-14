// NTMFG9 — Écran de gestion des Ordres de Fabrication : liste + Kanban par
// statut + détail (opérations, réservations, dispo). Distinct de
// `/production` (monitoring photovoltaïque N51, module `installations`) —
// vit sous `/mrp/*`, appelé « Atelier MRP » dans le menu pour éviter toute
// confusion.
import { useEffect, useMemo, useState } from 'react'
import { Factory, Printer } from 'lucide-react'
import mrpApi from '../../api/mrpApi'
import {
  Card, CardContent, Badge, Spinner, EmptyState, Button,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { PageHeader } from '../../ui/PageHeader'
// NTMFG19 — ouverture/téléchargement du traveler PDF (même helper que le
// reste de l'app pour les blobs PDF, VX49/VX172 déjà gérés).
import { openPdfBlob } from '../../utils/pdfBlob'
// NTMFG20 — vue arbre de généalogie amont/aval, embarquée dans le détail OF.
import GenealogieOFPanel from './GenealogieOFPanel'

// Radix Select interdit une valeur vide (réservée à l'effacement) — même
// sentinelle que `pages/parametres/ApplicationsSection.jsx`.
const TOUS_LES_POSTES = '__tous'

const COLONNES = [
  { statut: 'brouillon', label: 'Brouillon' },
  { statut: 'planifie', label: 'Planifié' },
  { statut: 'lance', label: 'Lancé' },
  { statut: 'termine', label: 'Terminé' },
  { statut: 'annule', label: 'Annulé' },
]

function OfCard({ of, selected, onSelect }) {
  return (
    <Card
      className={`mb-2 cursor-pointer ${selected ? 'ring-2 ring-primary' : ''}`}
      onClick={() => onSelect(of.id)}
    >
      <CardContent className="p-3">
        <div className="font-medium">OF-{of.id}</div>
        <div className="text-sm text-muted-foreground">
          {of.produit_nom || `Produit #${of.produit}`} × {of.quantite}
        </div>
        <Badge tone="neutral">Priorité {of.priorite}</Badge>
      </CardContent>
    </Card>
  )
}

function OfDetail({ ofId }) {
  const [of, setOf] = useState(null)
  const [travelerBusy, setTravelerBusy] = useState(false)

  useEffect(() => {
    if (!ofId) return
    mrpApi.getOrdreFabrication(ofId).then((resp) => setOf(resp.data))
  }, [ofId])

  // NTMFG19 — fiche suiveuse (traveler) imprimable, aucun prix.
  const imprimerTraveler = async () => {
    if (!of) return
    setTravelerBusy(true)
    try {
      const resp = await mrpApi.getTravelerPdf(of.id)
      await openPdfBlob(resp.data, `traveler-of-${of.id}.pdf`)
    } finally {
      setTravelerBusy(false)
    }
  }

  if (!ofId) return <EmptyState title="Sélectionnez un OF pour voir le détail." />
  if (!of) return <Spinner />

  return (
    <Card>
      <CardContent>
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-medium mb-2">OF-{of.id}</h3>
          <Button variant="outline" size="sm" loading={travelerBusy}
                  onClick={imprimerTraveler}
                  title="Fiche suiveuse (traveler) imprimable — document interne, aucun prix">
            <Printer size={14} /> Traveler
          </Button>
        </div>
        <div className="text-sm mb-1">Statut : <Badge tone="info">{of.statut}</Badge></div>
        <div className="text-sm mb-3">Quantité : {of.quantite}</div>

        <h4 className="text-sm font-medium mt-3 mb-1">Opérations</h4>
        {(of.operations || []).length === 0 && (
          <div className="text-sm text-muted-foreground">Aucune opération.</div>
        )}
        {(of.operations || []).map((op) => (
          <div key={op.id} className="text-sm flex justify-between border-b py-1">
            <span>{op.ordre}. {op.libelle}</span>
            <Badge tone="neutral">{op.statut}</Badge>
          </div>
        ))}

        <h4 className="text-sm font-medium mt-3 mb-1">Réservations composants</h4>
        {(of.reservations || []).length === 0 && (
          <div className="text-sm text-muted-foreground">Aucune réservation.</div>
        )}
        {(of.reservations || []).map((r) => (
          <div key={r.id} className="text-sm flex justify-between border-b py-1">
            <span>Produit #{r.produit}</span>
            <span>{r.quantite}</span>
          </div>
        ))}

        {of.statut === 'brouillon' && (
          <Button className="mt-3" onClick={() => mrpApi.confirmerOrdreFabrication(of.id)}>
            Confirmer
          </Button>
        )}
        {(of.statut === 'planifie' || of.statut === 'lance') && (
          <Button className="mt-3" onClick={() => mrpApi.cloturerOrdreFabrication(of.id)}>
            Clôturer
          </Button>
        )}
        <GenealogieOFPanel ofId={of.id} />
      </CardContent>
    </Card>
  )
}

export default function OrdresFabricationPage() {
  const [ofs, setOfs] = useState([])
  const [postes, setPostes] = useState([])
  const [posteFiltre, setPosteFiltre] = useState(TOUS_LES_POSTES)
  const [selectionId, setSelectionId] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    mrpApi.getPostesCharge({ actif: true }).then((resp) => {
      setPostes(resp.data?.results || resp.data || [])
    })
  }, [])

  useEffect(() => {
    // Différé d'un microtask : évite un setState synchrone dans l'effet
    // (react-hooks/set-state-in-effect). Comportement inchangé.
    Promise.resolve().then(() => setLoading(true))
    const params = posteFiltre && posteFiltre !== TOUS_LES_POSTES ? { poste: posteFiltre } : {}
    mrpApi.getOrdresFabrication(params)
      .then((resp) => setOfs(resp.data?.results || resp.data || []))
      .finally(() => setLoading(false))
  }, [posteFiltre])

  const parStatut = useMemo(() => {
    const map = {}
    for (const col of COLONNES) map[col.statut] = []
    for (const of of ofs) {
      if (!map[of.statut]) map[of.statut] = []
      map[of.statut].push(of)
    }
    return map
  }, [ofs])

  return (
    <div>
      <PageHeader
        title="Atelier MRP — Ordres de fabrication"
        subtitle="Distinct du monitoring de production photovoltaïque (/production)."
        icon={Factory}
        filters={(
          <Select value={posteFiltre} onValueChange={setPosteFiltre}>
            <SelectTrigger className="w-56"><SelectValue placeholder="Tous les postes" /></SelectTrigger>
            <SelectContent>
              <SelectItem value={TOUS_LES_POSTES}>Tous les postes</SelectItem>
              {postes.map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>{p.nom}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      />
      {loading && <Spinner />}
      {!loading && (
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {COLONNES.map((col) => (
              <div key={col.statut}>
                <div className="text-sm font-medium mb-2">
                  {col.label} ({(parStatut[col.statut] || []).length})
                </div>
                {(parStatut[col.statut] || []).map((of) => (
                  <OfCard
                    key={of.id} of={of} selected={of.id === selectionId}
                    onSelect={setSelectionId}
                  />
                ))}
                {(parStatut[col.statut] || []).length === 0 && (
                  <div className="text-xs text-muted-foreground">—</div>
                )}
              </div>
            ))}
          </div>
          <OfDetail ofId={selectionId} />
        </div>
      )}
    </div>
  )
}

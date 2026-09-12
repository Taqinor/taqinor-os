import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, CalendarClock, FileWarning } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { Button, Card, CardContent, Spinner } from '../../ui'
import { toast } from '../../ui/confirm'

/* ============================================================================
   NTP2P30 — Wizard de clôture de fin de mois achats. Purement AGRÉGATEUR en
   lecture (`stock.selectors.checklist_cloture_achats`, aucune nouvelle
   donnée) : les 3 listes que le contrôleur achats doit traiter en fin de
   mois, chacune avec un lien direct vers son écran de résolution.
   ========================================================================== */

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

export default function ClotureAchatsWizardPage() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    stockApi.getChecklistClotureAchats()
      .then((r) => { if (active) setData(r.data) })
      .catch((err) => toast.error(frErr(err, 'Chargement de la checklist impossible.')))
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  if (loading) {
    return (
      <div className="page">
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </p>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Clôture de fin de mois — Achats</h1>
        <div className="page-subtitle">
          3 listes à traiter avant de clore le mois. Purement informatif —
          aucune donnée n&apos;est créée ici, chaque lien ouvre l&apos;écran de
          résolution.
        </div>
      </div>

      <div className="flex flex-col gap-4">
        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <AlertTriangle className="size-4 text-muted-foreground" aria-hidden="true" />
              Factures en exception 3-voies non résolues ({data.nb_factures_en_exception})
            </h2>
            {data.nb_factures_en_exception === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune facture en exception ce mois-ci.</p>
            ) : (
              <ul className="flex flex-col gap-1 text-sm">
                {data.factures_en_exception.map((f) => (
                  <li key={f.id} className="flex items-center justify-between gap-2">
                    <span>{f.reference} — {f.fournisseur_nom || '—'} ({f.montant_ttc} MAD)</span>
                    <Button variant="outline" size="sm"
                            onClick={() => navigate('/stock/factures-fournisseur', { state: { ouvrirFactureId: f.id } })}>
                      Résoudre
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <CalendarClock className="size-4 text-muted-foreground" aria-hidden="true" />
              Demandes d&apos;achat en attente trop anciennes ({data.nb_demandes_en_attente_anciennes})
            </h2>
            {data.nb_demandes_en_attente_anciennes === 0 ? (
              <p className="text-sm text-muted-foreground">
                Aucune demande en attente depuis plus de {data.seuil_jours} jours.
              </p>
            ) : (
              <ul className="flex flex-col gap-1 text-sm">
                {data.demandes_en_attente_anciennes.map((d) => (
                  <li key={d.id} className="flex items-center justify-between gap-2">
                    <span>{d.reference} — {d.objet} ({d.jours_en_attente} j)</span>
                    <Button variant="outline" size="sm"
                            onClick={() => navigate('/chantiers/demandes-achat', { state: { ouvrirDemandeId: d.id } })}>
                      Traiter
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex flex-col gap-3 pt-4 sm:pt-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <FileWarning className="size-4 text-muted-foreground" aria-hidden="true" />
              Documents fournisseur expirés ({data.nb_documents_expires})
            </h2>
            {data.nb_documents_expires === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun document fournisseur expiré.</p>
            ) : (
              <ul className="flex flex-col gap-1 text-sm">
                {data.documents_expires.map((doc) => (
                  <li key={doc.document_id} className="flex items-center justify-between gap-2">
                    <span>{doc.fournisseur_nom} — {doc.type_document_display}</span>
                    <Button variant="outline" size="sm"
                            onClick={() => navigate('/stock/fournisseurs', { state: { ouvrirFournisseurId: doc.fournisseur_id } })}>
                      Voir
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

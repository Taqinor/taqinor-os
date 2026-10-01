/**
 * Conception3DPage — fondateur 18/08 : « une vraie app pour ça » — la
 * conception 3D de toiture devient un item de nav de PLEIN DROIT de Ventes
 * (`/ventes/conception-3d`), plus seulement une action cachée dans un menu de
 * ligne de la liste des devis ou un geste lancé depuis une fiche lead.
 *
 * Ouverte depuis le nav, l'écran n'a AUCUN contexte de devis/lead — il ne
 * peut donc jamais deviner lequel calepiner. QJR636 — la liste vient du
 * SERVEUR (`?concevable=1`, toutes les pages) : brouillons ET envoyés, lus
 * dans la table de modifiabilité ; aucun filtre de statut ici. On réutilise
 * le MÊME chooser (`ChoisirDevisPourDesign`,
 * jamais dupliqué) pour que le commercial désigne lequel. Le choix navigue
 * vers le MÊME écran que le flux lead (`/ventes/devis/:id/design`) — aucune
 * seconde implémentation du builder 3D.
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Box } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { PageHeader } from '../../ui/PageHeader'
import { Button, EmptyState, Spinner } from '../../ui'
import { VENTES_ACCENT_STYLE } from '../../features/ventes/accent'
import ChoisirDevisPourDesign from '../../features/ventes/ChoisirDevisPourDesign'
import { fetchAllPages } from '../../utils/fetchAllPages'

export default function Conception3DPage() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [concevables, setConcevables] = useState([])
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    let annule = false
    // Borne basse : la liste devis coûte cher par page côté serveur.
    fetchAllPages(
      (page) => ventesApi.getDevis({ concevable: 1, page }).then((r) => r.data),
      { concurrency: 3 },
    )
      .then((rows) => {
        if (annule) return
        setConcevables(Array.isArray(rows) ? rows.filter(Boolean) : [])
      })
      .catch(() => { if (!annule) setErreur('Impossible de charger les devis.') })
      .finally(() => { if (!annule) setLoading(false) })
    return () => { annule = true }
  }, [])

  // Un devis choisi → le MÊME écran que le flux lead (PV20/ToitureDesign,
  // mode devis) ; aucune route parallèle.
  const choisir = (d) => { if (d?.id) navigate(`/ventes/devis/${d.id}/design`) }

  return (
    <div className="page" data-testid="conception-3d-page">
      <PageHeader
        style={VENTES_ACCENT_STYLE}
        className="app-accent-rail"
        icon={Box}
        title="Conception 3D"
        subtitle="Calepinez la toiture d'un devis en 3D."
      />
      <div className="mt-4">
        {loading && (
          <div className="flex min-h-[40vh] items-center justify-center gap-2 text-sm text-muted-foreground">
            <Spinner /> Chargement des devis…
          </div>
        )}
        {!loading && erreur && (
          <EmptyState
            icon={Box}
            tone="error"
            title="Devis indisponibles"
            description={erreur}
            className="mt-8"
          />
        )}
        {!loading && !erreur && concevables.length === 0 && (
          <EmptyState
            icon={Box}
            title="Aucun devis à calepiner"
            description="Créez d'abord un devis pour pouvoir en calepiner la toiture en 3D."
            action={(
              <Button onClick={() => navigate('/ventes/devis/nouveau')}>
                Créer un devis
              </Button>
            )}
            className="mt-8"
          />
        )}
        {!loading && !erreur && concevables.length > 0 && (
          <ChoisirDevisPourDesign
            open
            devis={concevables}
            description="Choisissez le devis dont la toiture doit être calepinée."
            onChoisir={choisir}
            onClose={() => navigate('/ventes/devis')}
          />
        )}
      </div>
    </div>
  )
}

/**
 * RoofViewerPage — QG12 : page autonome plein écran affichant le design 3D
 * (plan de toiture stocké, `roof_layout`) d'UN devis en LECTURE SEULE, montée
 * sur la route /ventes/devis/:id/3d.
 *
 * Cible de l'affordance « Ouvrir dans une fenêtre » de la liste / du détail des
 * devis : un clic ouvre cette page dans un nouvel onglet, où le plan occupe toute
 * la surface. Aucune édition — elle réutilise le composant RoofViewer (QG11) et
 * ne fait qu'un seul GET (le devis par id, borné à la société côté serveur).
 */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import ventesApi from '../../api/ventesApi'
import { Spinner, EmptyState } from '../../ui'
import { FileStack } from 'lucide-react'
import RoofViewer from './RoofViewer'

export default function RoofViewerPage() {
  const { id } = useParams()
  const [devis, setDevis] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    // `loading` démarre déjà à true et `error` à null (état initial) — on ne
    // les ré-assigne pas synchronement ici (le GET n'a lieu qu'une fois par id).
    let cancelled = false
    ventesApi.getDevisById(id)
      .then(res => { if (!cancelled) setDevis(res.data) })
      .catch(() => { if (!cancelled) setError('Devis introuvable ou accès refusé.') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [id])

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Chargement du design 3D…
      </div>
    )
  }

  if (error || !devis) {
    return (
      <EmptyState
        icon={FileStack}
        title="Design 3D indisponible"
        description={error || 'Aucune donnée pour ce devis.'}
        className="mt-8"
      />
    )
  }

  return (
    <div className="page" data-testid="roof-viewer-page">
      <div className="page-header">
        <h2>Design 3D — {devis.reference}</h2>
      </div>
      <div className="mt-4">
        <RoofViewer layout={devis.roof_layout} />
      </div>
    </div>
  )
}

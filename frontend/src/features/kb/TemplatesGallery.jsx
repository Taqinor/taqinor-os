import { useEffect, useState } from 'react'
import { LayoutTemplate, FileText } from 'lucide-react'
import { Card, Button, EmptyState, Spinner, toast } from '../../ui'
import kbApi from '../../api/kbApi'

/* ============================================================================
   XKB12 — Galerie des gabarits (articles marqués ``est_gabarit``). « Utiliser »
   crée un nouvel article BROUILLON pré-rempli depuis le gabarit choisi
   (``depuis-gabarit``), puis ouvre l'éditeur sur cette copie.
   ========================================================================== */

export default function TemplatesGallery({ onClose, onCreated }) {
  const [gabarits, setGabarits] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(null)

  useEffect(() => {
    kbApi.gabarits()
      .then((res) => setGabarits(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setGabarits([]))
      .finally(() => setLoading(false))
  }, [])

  const utiliser = async (gabarit) => {
    setCreating(gabarit.id)
    try {
      const res = await kbApi.depuisGabarit(gabarit.id)
      toast.success('Article créé depuis le gabarit (brouillon).')
      onCreated?.(res.data)
    } catch {
      toast.error('Création impossible.')
    } finally {
      setCreating(null)
    }
  }

  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-5">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-display text-lg font-semibold">
          <LayoutTemplate className="size-5" aria-hidden="true" /> Gabarits
        </h2>
        <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
      </div>
      {loading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4" /> Chargement…
        </div>
      )}
      {!loading && gabarits.length === 0 && (
        <EmptyState
          title="Aucun gabarit"
          description="Marquez un article comme gabarit depuis son détail pour le retrouver ici."
        />
      )}
      {!loading && gabarits.length > 0 && (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {gabarits.map((g) => (
            <li key={g.id} className="flex flex-col gap-2 rounded-lg border border-border p-3">
              <span className="flex items-center gap-2 font-medium">
                <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                {g.titre}
              </span>
              {g.categorie && (
                <span className="text-xs text-muted-foreground">{g.categorie}</span>
              )}
              <Button
                type="button" variant="outline" size="sm"
                disabled={creating === g.id}
                onClick={() => utiliser(g)}
              >
                {creating === g.id ? 'Création…' : 'Utiliser ce gabarit'}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

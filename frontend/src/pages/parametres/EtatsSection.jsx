import { AlertCircle, ChevronUp, ChevronDown, Trash2 } from 'lucide-react'
import { Badge, Button, IconButton, Spinner } from '../../ui'

/* Éléments d'écran PARTAGÉS des sections Paramètres « listes éditables »
   (Checklist, Kits, Sécurité & terrain, Shot list) : état de chargement /
   d'échec avec « Réessayer », et grappe d'actions d'une ligne (monter,
   descendre, actif, supprimer). Un seul endroit — jamais recopiés. */

/** Chargement, puis erreur + Réessayer ; `null` quand tout va bien. */
export function EtatChargementSection({ loading, loadError, message, onRetry }) {
  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner className="size-4 text-primary" /> Chargement…
      </p>
    )
  }
  if (loadError) {
    return (
      <div className="flex flex-col items-start gap-2">
        <p className="flex items-center gap-2 text-sm text-destructive">
          <AlertCircle className="size-4" aria-hidden="true" />
          {message}
        </p>
        <Button type="button" size="sm" variant="outline" onClick={onRetry}>Réessayer</Button>
      </div>
    )
  }
  return null
}

export function ActionsLigneParam({
  s, i, total, move, toggleActif, del, labelSupprimer, titreActif = false,
}) {
  return (
    <div className="ml-auto flex items-center gap-1">
      <IconButton size="sm" variant="ghost" label="Monter"
        disabled={i === 0} onClick={() => move(i, -1)}>
        <ChevronUp className="size-4" aria-hidden="true" />
      </IconButton>
      <IconButton size="sm" variant="ghost" label="Descendre"
        disabled={i === total - 1} onClick={() => move(i, 1)}>
        <ChevronDown className="size-4" aria-hidden="true" />
      </IconButton>
      <Button type="button" size="sm"
        variant={s.actif ? 'success' : 'secondary'}
        title={titreActif ? (s.actif ? 'Désactiver' : 'Activer') : undefined}
        onClick={() => toggleActif(s)}>
        {s.actif ? 'Actif' : 'Inactif'}
      </Button>
      {s.protege ? (
        <Badge tone="info">système</Badge>
      ) : (
        <IconButton size="sm" variant="outline" label={labelSupprimer}
          className="text-destructive hover:text-destructive"
          onClick={() => del(s)}>
          <Trash2 className="size-4" aria-hidden="true" />
        </IconButton>
      )}
    </div>
  )
}

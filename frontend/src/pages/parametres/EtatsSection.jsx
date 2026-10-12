import { AlertCircle, ChevronUp, ChevronDown, Trash2 } from 'lucide-react'
import { Badge, Button, EmptyState, IconButton, Spinner } from '../../ui'

/* Éléments d'écran PARTAGÉS des sections Paramètres « listes éditables »
   (Checklist, Kits, Sécurité & terrain, Shot list) : état de chargement /
   d'échec avec « Réessayer », et grappe d'actions d'une ligne (monter,
   descendre, actif, supprimer). Un seul endroit — jamais recopiés. */

/** Ligne « Chargement… » d'une section. */
export function ChargementTexte() {
  return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
}

/** Page entière en cours de chargement. */
export function PageChargement() {
  return (
    <div className="page">
      <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
        <Spinner /> Chargement…
      </p>
    </div>
  )
}

/** Page de réglages : en-tête (titre, sous-titre, actions) puis contenu. */
export function PageReglages({ titre, sousTitre, actions = null, children }) {
  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">{titre}</h1>
        <div className="page-subtitle">{sousTitre}</div>
        {actions}
      </div>
      {children}
    </div>
  )
}

/** Pied de formulaire de réglages : bouton « Enregistrer » à droite. */
export function PiedFormulaire({ saving, disabled }) {
  return (
    <div className="flex justify-end">
      <Button type="submit" loading={saving} disabled={disabled}>
        {saving ? 'Enregistrement…' : 'Enregistrer'}
      </Button>
    </div>
  )
}

/** Formulaire de réglages : cartes puis pied « Enregistrer ». */
export function FormulaireReglages({ onSubmit, saving, disabled, children }) {
  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      {children}
      <PiedFormulaire saving={saving} disabled={disabled} />
    </form>
  )
}

/** Chargement ou erreur d'une page de lecture seule (Fiabilité). */
export function EtatPageLecture({ loading, erreur }) {
  if (loading) {
    return <div className="flex items-center justify-center py-16"><Spinner /></div>
  }
  return <div className="p-6 text-sm text-destructive">{erreur}</div>
}

/** Échec de chargement d'une liste d'administration (état vide + message fixe). */
export function ErreurChargementListe({ title }) {
  return (
    <EmptyState title={title}
      description="Une erreur est survenue lors du chargement." className="py-6" />
  )
}

/** Bouton « supprimer » (icône corbeille) d'une ligne de liste. */
export function BoutonSupprimerLigne({ label, onClick, size = 'sm' }) {
  return (
    <IconButton size={size} variant="outline" label={label}
      className="text-destructive hover:text-destructive"
      onClick={onClick}>
      <Trash2 className="size-4" aria-hidden="true" />
    </IconButton>
  )
}

/** Bouton bascule « Actif / Inactif » d'une ligne de liste. */
export function BoutonActifInactif({ actif, onClick, avecTitre = true }) {
  return (
    <Button type="button" size="sm"
      variant={actif ? 'success' : 'secondary'}
      title={avecTitre ? (actif ? 'Désactiver' : 'Activer') : undefined}
      onClick={onClick}>
      {actif ? 'Actif' : 'Inactif'}
    </Button>
  )
}

/** Cadre en pointillés du formulaire de création en bas d'une liste. */
export function ZoneCreation({ visible = true, children }) {
  if (!visible) return null
  return (
    <div className="mt-3 rounded-lg border border-dashed border-border p-3">
      {children}
    </div>
  )
}

/** Rangée de champs d'un formulaire de création. */
export function LigneChamps({ children }) {
  return <div className="flex flex-wrap gap-1.5">{children}</div>
}

/** Chargement, puis erreur + Réessayer ; `null` quand tout va bien. */
export function EtatChargementSection({ loading, loadError, message, onRetry }) {
  if (loading) {
    return <ChargementTexte />
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
      <BoutonActifInactif actif={s.actif} avecTitre={titreActif}
        onClick={() => toggleActif(s)} />
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

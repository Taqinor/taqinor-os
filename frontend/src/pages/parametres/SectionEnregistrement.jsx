import { Save, CheckCircle2 } from 'lucide-react'
import { Button, Spinner } from '../../ui'

/* Éléments d'écran PARTAGÉS des sections Paramètres qui s'enregistrent d'un
   bloc (Statuts, Documents, Tarification) : bouton « Enregistrer / Enregistré ! »
   et état de chargement. Un seul endroit — jamais recopiés section par section. */

export function BoutonEnregistrer({ save, saving, saved, desactive = false }) {
  return (
    <Button type="button" size="sm" onClick={save} loading={saving}
      disabled={saving || desactive} variant={saved ? 'success' : 'default'}>
      {saved
        ? <><CheckCircle2 className="size-4" aria-hidden="true" /> Enregistré !</>
        : <><Save className="size-4" aria-hidden="true" /> Enregistrer</>}
    </Button>
  )
}

/* AERR56 — la lecture du réglage a échoué : on ne propose JAMAIS le formulaire
   (un formulaire vide ou par défaut, enregistré, écraserait la configuration
   serveur). Avis + « Réessayer » qui relance la lecture. */
export function LectureEchouee({ onRetry }) {
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm">
      <span>Réglages non chargés : rien n’a été modifié.</span>
      <Button type="button" size="sm" variant="outline" onClick={onRetry}>Réessayer</Button>
    </div>
  )
}

export function ChargementSection() {
  return (
    <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </div>
  )
}

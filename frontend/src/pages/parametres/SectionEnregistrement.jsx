import { Save, CheckCircle2 } from 'lucide-react'
import { Button, Spinner } from '../../ui'

/* Éléments d'écran PARTAGÉS des sections Paramètres qui s'enregistrent d'un
   bloc (Statuts, Documents, Tarification) : bouton « Enregistrer / Enregistré ! »
   et état de chargement. Un seul endroit — jamais recopiés section par section. */

export function BoutonEnregistrer({ save, saving, saved }) {
  return (
    <Button type="button" size="sm" onClick={save} loading={saving}
      disabled={saving} variant={saved ? 'success' : 'default'}>
      {saved
        ? <><CheckCircle2 className="size-4" aria-hidden="true" /> Enregistré !</>
        : <><Save className="size-4" aria-hidden="true" /> Enregistrer</>}
    </Button>
  )
}

export function ChargementSection() {
  return (
    <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </div>
  )
}

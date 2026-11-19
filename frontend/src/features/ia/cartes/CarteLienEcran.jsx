import { ExternalLink } from 'lucide-react'
import { Button } from '../../../ui'
import { cheminAutorise } from './ecrans'
import { useOuvrirEcran } from './useCarte'

/* Copilote vague 2 (FND10) — carte `lien_ecran` (action `erp.ouvrir`, contrat
   `apps/agent/contract_samples/assistant_ouvrir.json`) : UN bouton qui ouvre un
   écran de l'ERP pour un geste qui reste humain. Le chemin vient du SERVEUR ; il
   n'est suivi que s'il a la forme d'un écran du miroir `ecrans.js` — sinon, aucun
   bouton. Le tiroir du Copilote se referme à l'ouverture (`useOuvrirEcran`). */
export default function CarteLienEcran({ carte }) {
  const ouvrir = useOuvrirEcran()
  const d = carte.donnees ?? {}
  const chemin = cheminAutorise(d.chemin) ? d.chemin : ''
  return (
    <div className="min-w-0">
      {d.libelle && <p className="break-words text-sm font-medium">{d.libelle}</p>}
      {chemin ? (
        <Button
          variant="outline" size="sm" className="mt-2 min-h-10 w-full max-w-full sm:w-auto"
          onClick={() => ouvrir(chemin)}
        >
          <ExternalLink className="size-4 shrink-0" aria-hidden="true" />
          <span className="truncate">{d.titre || 'Ouvrir'}</span>
        </Button>
      ) : (
        <p className="mt-1 text-xs text-muted-foreground">
          Lien indisponible : ouvre l’écran depuis le menu.
        </p>
      )}
    </div>
  )
}

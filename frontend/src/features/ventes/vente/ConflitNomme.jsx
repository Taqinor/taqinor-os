// VNT80 (Groupe VNT) — un 409 qui NOMME un autre devis (`version_remplacee`
// → `successeur`, `vente_active_existante` → `vente_active`) : l'erreur reste
// visible SOUS la carte (role=alert, règle fondateur « erreurs → le champ
// fautif ») avec un bouton « Ouvrir <réf> » qui mène à ce devis. La forme
// `{conflit, code, message, successeur}` vient de `lireConflit` (reviserDevis.js).
import { Button } from '../../../ui'

export default function ConflitNomme({ conflit, onOuvrir, ...props }) {
  if (!conflit) return null
  const cible = conflit.successeur
  return (
    <div role="alert" className="vente-conflit" data-testid="vente-conflit" {...props}>
      <p>{conflit.message}</p>
      {cible?.reference && (
        <Button type="button" size="sm" variant="outline" onClick={() => onOuvrir?.(cible.id)}>
          Ouvrir {cible.reference}
        </Button>
      )}
    </div>
  )
}

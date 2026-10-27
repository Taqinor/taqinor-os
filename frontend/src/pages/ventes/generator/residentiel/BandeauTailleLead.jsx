// RGEN3 — LA TAILLE DEMANDÉE SUR LA FICHE DU LEAD, DITE AU VENDEUR.
// ---------------------------------------------------------------------------
// Quand la fiche porte « taille souhaitée (kWc) », le devis automatique la
// suit pour les deux options (`creation_auto_residentiel`, source
// « taille_demandee ») et l'écran aussi (`sizingReducer.tailleDemandeeParLead`).
// La facture ne dimensionne alors rien : ce bandeau le dit, sinon le vendeur
// voit un compte de panneaux qui ne correspond pas à la recommandation
// affichée plus bas, sans savoir pourquoi (rejeu lead 2141 : 16 kWc demandés,
// moteur 12,07 kWc).
import { tailleDemandeeParLead } from '../../../../features/ventes/quote/sizingReducer'

const fmtKwc = (kwc) => kwc.toLocaleString('fr-FR', { maximumFractionDigits: 2 })

export default function BandeauTailleLead({ sizing }) {
  const kwc = tailleDemandeeParLead(sizing)
  if (kwc == null) return null
  return (
    <div role="status" data-testid="gen-taille-lead"
         className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning">
      Taille demandée sur la fiche du lead : <strong>{fmtKwc(kwc)} kWc</strong>. Le nombre
      de panneaux la suit (avec et sans batterie, comme le devis automatique) : la facture
      ne sert pas au dimensionnement. Tapez un autre nombre de panneaux ou
      cliquez « Recalculer le dimensionnement » pour revenir à la recommandation.
    </div>
  )
}

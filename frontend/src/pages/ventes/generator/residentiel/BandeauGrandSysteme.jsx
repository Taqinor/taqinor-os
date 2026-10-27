// RGEN9 — UN GRAND SYSTÈME RÉSIDENTIEL EST SIGNALÉ, JAMAIS DÉTOURNÉ.
// ---------------------------------------------------------------------------
// Décision fondateur du 23/10/2026 (lead 1635, `dimensionnement-decisions-2310`) :
// les gros profils résidentiels (20 000 à 100 000+ MAD/mois) REÇOIVENT une
// taille ; au-dessus de 120 panneaux on recommande ET on signale « étude sur
// mesure conseillée ». L'écran disait l'inverse dès 36 kWc (≈ 51 panneaux) :
// « au-delà de l'échelle résidentielle — le mode Industriel ou Commercial
// produira un document plus adapté », poussant une villa vers le C&I.
import { formatNumber } from '../../../../lib/format'

// Même seuil que le dimensionnement serveur (SEUIL_PANNEAUX_RESIDENTIEL, balayage_adaptatif).
export const SEUIL_PANNEAUX_RESIDENTIEL = 120

export default function BandeauGrandSysteme({ modeInstallation, nbPanneaux, kwp }) {
  const n = Number(nbPanneaux) || 0
  if (modeInstallation !== 'residentiel' || n <= SEUIL_PANNEAUX_RESIDENTIEL) return null
  return (
    <div className="mt-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info"
         data-testid="gen-grand-systeme">
      Ce système compte {n} panneaux ({formatNumber(kwp, { decimals: 2 })} kWc) : au-delà de
      {' '}{SEUIL_PANNEAUX_RESIDENTIEL} panneaux, une étude sur mesure est conseillée. Le devis
      résidentiel reste possible.
    </div>
  )
}

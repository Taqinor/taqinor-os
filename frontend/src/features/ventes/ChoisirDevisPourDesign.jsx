/* PV22 — « Concevoir la toiture (3D) » depuis la fiche lead : les deux seuls
   moments où le geste ne peut pas aboutir tout seul.

   1. `ChoisirDevisPourDesign` — le lead a PLUSIEURS brouillons. On ne devine
      pas lequel calepiner : on les montre (référence · kWc · date) et le
      commercial choisit. Aucun devis n'est créé, aucun n'est modifié.
   2. `DevisAutoImpossibleDialog` — aucun brouillon et le serveur refuse d'en
      dimensionner un (422 : facture manquante, marché non résidentiel…). Le
      MESSAGE affiché est celui du serveur, mot pour mot — l'écran ne rédige
      jamais son propre diagnostic — et la seule sortie proposée est le
      générateur complet, où l'agent saisit ce qui manque.

   Aucun appel réseau ici : ces deux dialogues sont purement présentationnels,
   le shell (LeadWorkspace) possède la décision et la navigation. */
import { Button } from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDate, formatNumber } from '../../lib/format'

// kWc d'un devis : le serializer expose `etude_params.puissance_kwc` (le même
// chiffre que le PDF). Jamais recalculé ici — sans valeur, la colonne se tait.
function kwcDeDevis(devis) {
  const brut = devis?.etude_params?.puissance_kwc
  if (brut == null || brut === '') return null
  const valeur = Number(brut)
  return Number.isFinite(valeur) && valeur > 0 ? valeur : null
}

export default function ChoisirDevisPourDesign({ open, devis, onChoisir, onClose }) {
  const lignes = Array.isArray(devis) ? devis : []
  return (
    <ResponsiveDialog
      open={!!open}
      onOpenChange={(o) => { if (!o) onClose?.() }}
      title="Quel devis voulez-vous concevoir ?"
      description="Ce lead a plusieurs brouillons. Choisissez celui dont la toiture doit être calepinée."
    >
      <ul className="cdd-liste" data-testid="pv22-choix-devis">
        {lignes.map((d) => {
          const kwc = kwcDeDevis(d)
          return (
            <li key={d.id}>
              <Button
                type="button"
                variant="outline"
                className="cdd-ligne"
                onClick={() => onChoisir?.(d)}
              >
                <span className="cdd-ref">{d.reference}</span>
                {kwc != null && (
                  <span className="cdd-kwc num">
                    {` · ${formatNumber(kwc, { decimals: 2 })} kWc`}
                  </span>
                )}
                {d.date_creation && (
                  <span className="cdd-date">{` · ${formatDate(d.date_creation)}`}</span>
                )}
              </Button>
            </li>
          )
        })}
      </ul>
    </ResponsiveDialog>
  )
}

export function DevisAutoImpossibleDialog({ open, message, onGenerateur, onClose }) {
  return (
    <ResponsiveDialog
      open={!!open}
      onOpenChange={(o) => { if (!o) onClose?.() }}
      title="Impossible de créer le devis automatiquement"
      footer={(
        <Button type="button" onClick={() => onGenerateur?.()}>
          Ouvrir le générateur
        </Button>
      )}
    >
      {/* Le diagnostic vient du SERVEUR, jamais rédigé ici. */}
      <p className="cdd-message" role="alert" data-testid="pv22-devis-auto-impossible">
        {message}
      </p>
    </ResponsiveDialog>
  )
}

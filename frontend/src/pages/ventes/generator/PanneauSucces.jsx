// EZ3 — LE PANNEAU DE SUCCÈS de la création en pleine page, sorti de
// DevisGenerator.jsx (C20 : le fichier-mur ne grossit pas). Il offre l'action
// suivante évidente (envoyer, aperçu) sans re-chercher le devis. ALEA51 — un
// devis AUTOMATIQUE lancé d'ici (`?auto=1`) y montre aussi la phrase de succès
// (réf. · kWc · TTC · économie · retour · postes à chiffrer) et les alertes du
// serveur en avertissement, comme le panneau de la fiche lead.
import { Button, Card, CardContent } from '../../../ui'
import { Send, Eye } from 'lucide-react'
import { formatMoney } from '../../../features/ventes/solar'
import { libelleSuccesDevisAuto } from '../../../features/ventes/autoQuote'

export default function PanneauSucces({ succes, navigate }) {
  return (
    <div className="page gen-page">
      <Card className="mx-auto max-w-xl" data-testid="devis-succes">
        <CardContent className="flex flex-col gap-4 pt-6 text-center">
          <div>
            <p className="text-sm text-muted-foreground">Devis enregistré</p>
            <p className="font-display text-xl font-bold">{succes.reference || '—'}</p>
            {succes.total != null && (
              <p className="num mt-1 text-2xl font-semibold">{formatMoney(succes.total)}</p>
            )}
            {succes.resultat && (
              <p className="mt-2 text-sm" data-testid="succes-auto-resume">{libelleSuccesDevisAuto(succes.resultat)}</p>
            )}
          </div>
          {succes.alertes?.length > 0 && (
            <div className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-left text-sm"
                 role="status" data-testid="succes-auto-alertes">
              <strong>Alertes du devis automatique :</strong>
              <ul>
                {succes.alertes.map((a, i) => (
                  <li key={`${a.code || 'alerte'}-${i}`}>
                    {a.interne === true && <strong>Vendeur seulement — </strong>}
                    {a.message || a.code}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
            <Button
              onClick={() => navigate(`/ventes/devis?devis=${succes.id}&envoyer=1`)}
              data-testid="succes-whatsapp"
            >
              <Send /> Envoyer par WhatsApp
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate(`/ventes/devis?devis=${succes.id}&apercu=1`)}
              data-testid="succes-apercu"
            >
              <Eye /> Aperçu du PDF
            </Button>
            <Button
              variant="ghost"
              onClick={() => navigate(`/ventes/devis?devis=${succes.id}`)}
              data-testid="succes-liste"
            >
              Retour à la liste
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

import { Send } from 'lucide-react'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, Label, Input,
} from '../../../ui/index.js'
import { ResponsiveDialog } from '../../../ui/ResponsiveDialog'
import { buildRelanceMessage } from './devisListHelpers.js'

// SPL205 — dialogues d'envoi de la liste des devis (email + WhatsApp/relance),
// JSX déplacé VERBATIM de DevisList.jsx (move only). Tout l'état et les
// handlers viennent de useDevisEnvoi, passés en props NOMMÉES (le parent
// étale l'objet du hook ; seules les props ci-dessous sont lues).
export default function EnvoiDialogs({
  emailTarget, emailAddress, setEmailAddress, emailBusy, closeEmailModal, submitEmail,
  waTarget, waData, waSending, relanceMode, waGammeEnvoi, setWaGammeEnvoi,
  closeWaModal, openWhatsApp,
}) {
  return (
    <>
      {/* QJ14 — Modale « Envoyer par email » : PDF premium + lien de proposition
          (MB4 — ResponsiveDialog → tiroir bas plein écran sur mobile) */}
      <ResponsiveDialog
        open={!!emailTarget}
        onOpenChange={(o) => { if (!o) closeEmailModal() }}
        title={`Envoyer par email — ${emailTarget?.reference ?? ''}`}
        footer={(
          <>
            <Button variant="outline" onClick={closeEmailModal} disabled={emailBusy}>
              Annuler
            </Button>
            <Button onClick={submitEmail} loading={emailBusy}>
              <Send className="size-4 mr-1" aria-hidden="true" />
              Envoyer
            </Button>
          </>
        )}
      >
          <div className="flex flex-col gap-4">
            <div className="grid gap-1.5">
              <Label htmlFor="email-address">Adresse email du destinataire</Label>
              <Input
                id="email-address"
                type="email"
                placeholder="client@exemple.ma"
                value={emailAddress}
                onChange={e => setEmailAddress(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Laissez vide pour utiliser l'email du client enregistré.
                Le PDF de la proposition et le lien de signature seront joints.
              </p>
            </div>
          </div>
      </ResponsiveDialog>

      {/* QG8 — Aperçu du message WhatsApp avant ouverture. L'aperçu est une
          LECTURE (whatsapp-preview) : le devis n'est marqué « Envoyé » qu'au
          clic « Ouvrir WhatsApp » (action whatsapp). ERR-QAH-VENTES-ENVOYE-
          FAUX-STATUT — le texte ne prétend jamais un statut non encore posé. */}
      <Dialog open={!!waTarget} onOpenChange={(o) => { if (!o) closeWaModal() }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {relanceMode ? 'Relancer par WhatsApp' : 'Envoyer par WhatsApp'} — {waTarget?.reference}
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">
              {relanceMode
                ? 'Vérifiez le message de rappel ci-dessous puis ouvrez WhatsApp — vous appuierez vous-même sur Envoyer.'
                : 'Vérifiez le message ci-dessous puis ouvrez WhatsApp — vous appuierez vous-même sur Envoyer. Le devis passera « Envoyé » quand vous ouvrirez WhatsApp ; fermer cette fenêtre le laisse en brouillon.'}
            </p>
            <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm whitespace-pre-wrap">
              {relanceMode
                ? buildRelanceMessage(waData, waTarget?.reference)
                : (waData?.message || '…')}
            </div>
            {/* GAMMES — ENVOI À LA CARTE (fondateur 2026-08-18). Affiché
                uniquement quand ce devis appartient à une paire de gammes :
                envoyer CETTE gamme seule (le lien rend le devis comme
                aujourd'hui) ou LES DEUX (le client choisit, badge
                « Recommandé » sur celle désignée). Défaut : les deux. */}
            {waData?.gamme && !relanceMode && (
              <fieldset className="rounded-lg border border-border p-3">
                <legend className="px-1 text-sm font-medium">Gammes à envoyer</legend>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="gamme-envoi"
                    value="les_deux"
                    checked={waGammeEnvoi === 'les_deux'}
                    onChange={() => setWaGammeEnvoi('les_deux')}
                  />
                  <span>
                    Envoyer les deux
                    {waData.gamme.recommandee
                      ? ` (recommandée : ${waData.gamme.recommandee})`
                      : ''}
                  </span>
                </label>
                <label className="mt-2 flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="gamme-envoi"
                    value="seule"
                    checked={waGammeEnvoi === 'seule'}
                    onChange={() => setWaGammeEnvoi('seule')}
                  />
                  <span>
                    Envoyer cette gamme seule
                    {waData.gamme.nom ? ` (${waData.gamme.nom})` : ''}
                  </span>
                </label>
              </fieldset>
            )}
            {!waData?.wa_url && (
              <p className="text-sm text-destructive">
                Aucun numéro de téléphone : le message ne peut pas être ouvert
                dans WhatsApp.
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeWaModal} disabled={waSending}>Fermer</Button>
            <Button onClick={openWhatsApp} disabled={!waData?.wa_url} loading={waSending}>
              <Send className="size-4 mr-1" aria-hidden="true" />
              Ouvrir WhatsApp
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

import { MessageCircle } from 'lucide-react'
import {
  Button, Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter,
} from '../ui'

/* Aperçu d'un message WhatsApp avant ouverture de wa.me (jamais un envoi
   automatique) : titre, description, texte et lien public, puis pied
   Annuler [Passer] / Ouvrir WhatsApp. Un seul endroit pour les relances, la
   fiche client et les factures.
   - `apercu` : { reference, message, url, wa_url } (null = fermé) ;
   - `onFermer` : appelé à la fermeture (croix, Échap ou Annuler) ;
   - `libelleAnnuler` : « Annuler » (par défaut) ou « Arrêter » ;
   - `passer` : bouton « Passer » facultatif, entre Annuler et Ouvrir ;
   - `pied` / `piedProps` : conteneur du pied (DialogFooter par défaut). */
export default function ApercuWhatsAppDialog({
  apercu, titre, description, onFermer, onOuvrir,
  libelleAnnuler = 'Annuler', passer = null,
  pied = DialogFooter, piedProps,
}) {
  const Pied = pied
  return (
    <Dialog open={!!apercu} onOpenChange={(o) => { if (!o) onFermer() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{titre}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <pre className="m-0 whitespace-pre-wrap break-words rounded-lg bg-muted p-3 text-sm"
             style={{ fontFamily: 'inherit' }}>
          {apercu?.message}
        </pre>
        {apercu?.url && (
          <p className="mt-2 break-words text-xs text-muted-foreground">
            Lien public : {apercu.url}
          </p>
        )}
        <Pied {...piedProps}>
          <Button type="button" variant="ghost" onClick={onFermer}>{libelleAnnuler}</Button>
          {passer}
          <Button type="button" variant="success" disabled={!apercu?.wa_url}
                  onClick={onOuvrir}>
            <MessageCircle /> Ouvrir WhatsApp
          </Button>
        </Pied>
      </DialogContent>
    </Dialog>
  )
}

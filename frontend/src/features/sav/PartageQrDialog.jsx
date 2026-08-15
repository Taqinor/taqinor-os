// NTMOB23 — « Partager par QR » d'une fiche équipement.
// Affiche à l'écran le QR du lien de partage TOKENISÉ DÉJÀ EXISTANT
// (`/e/<public_token>`, le même que les étiquettes imprimées XSAV19) pour
// qu'un collègue sur site le scanne au lieu de taper une URL. Aucune nouvelle
// infrastructure de partage : ni jeton, ni route publique, ni modèle.
import { useEffect, useState } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../../ui/Dialog'
import { Spinner } from '../../ui'
import savApi from '../../api/savApi'

export default function PartageQrDialog({ equipementId, open, onOpenChange }) {
  const [partage, setPartage] = useState(null)
  const [erreur, setErreur] = useState(false)

  useEffect(() => {
    if (!open || !equipementId) return undefined
    let alive = true
    savApi.getEquipementPartageQr(equipementId)
      .then((r) => { if (alive) setPartage(r.data || null) })
      .catch(() => { if (alive) setErreur(true) })
    return () => { alive = false }
  }, [open, equipementId])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-label="Partager par QR">
        <DialogHeader>
          <DialogTitle>Partager par QR</DialogTitle>
          <DialogDescription>
            Faites scanner ce code par un collègue sur site : il ouvre la fiche
            partagée sans avoir à taper l'adresse.
          </DialogDescription>
        </DialogHeader>
        {erreur ? (
          <p role="alert" className="text-sm text-destructive">
            Lien de partage indisponible pour le moment.
          </p>
        ) : !partage ? (
          <Spinner />
        ) : (
          <div className="flex flex-col items-center gap-3">
            {/* Repli sans QR (lib absente côté serveur) : le lien reste
                lisible et copiable — jamais un écran vide. */}
            {partage.qr && (
              <img
                src={partage.qr}
                alt="QR du lien de partage"
                className="size-48 rounded-md border border-border bg-white p-2"
              />
            )}
            <code className="break-all text-center text-xs text-muted-foreground">
              {partage.url}
            </code>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

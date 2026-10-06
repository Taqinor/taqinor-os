import { Download } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import { Button, Card } from '../../../ui'

/* ============================================================================
   ADOC141 (D-ADOC-1) — « Mes données » : export (zip) des données du client.
   ----------------------------------------------------------------------------
   Le bouton est un lien direct vers `GET /portail/client/mes-donnees/export/` :
   le serveur répond un binaire avec son propre nom de fichier
   (Content-Disposition), jamais reconstruit côté écran.
   ========================================================================== */

export default function PortailClientMesDonnees() {
  return (
    <>
      <h1 className="font-display text-xl font-semibold tracking-tight">
        Mes données
      </h1>
      <Card className="flex flex-col gap-3 p-4">
        <p className="text-sm text-muted-foreground">
          Téléchargez une copie de vos données (devis, factures, demandes et
          documents) dans une archive ZIP.
        </p>
        <Button asChild className="self-start">
          <a href={portailApi.exportMesDonneesUrl()} download>
            <Download /> Exporter mes données
          </a>
        </Button>
      </Card>
    </>
  )
}

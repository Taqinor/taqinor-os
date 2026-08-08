// PACT96-101 — écran ERP interne « Portail client — Administration ».
// ----------------------------------------------------------------------------
// `apps/portail` a un backend entier et testé (comptes d'accès, preuve
// d'acceptation de devis, paiements en ligne, documents client, jalons de
// chantier, demandes de ticket SAV) mais aucun écran ERP ne l'exposait avant
// PACT96 : seul le client final voyait son propre espace self-service
// (`/portail/client`, hors de ce fichier). Une seule route/entrée de nav à
// onglets — chaque ressource est montée par sa propre tâche PACT (même
// patron que `pages/sav/SavParametresPage.jsx`) : chaque tâche suivante
// ajoute SON onglet ici, jamais un re-routage.
import { useState } from 'react'
import {
  TooltipProvider, Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../../ui'
import ComptesPortailAdmin from './ComptesPortailAdmin'
import AcceptationsDevisPortailAdmin from './AcceptationsDevisPortailAdmin'
import PaiementsFacturePortailAdmin from './PaiementsFacturePortailAdmin'

export default function PortailAdminPage() {
  const [tab, setTab] = useState('comptes')

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-6xl flex-col gap-5 p-1">
        <header>
          <h1 className="font-display text-2xl font-bold tracking-tight">
            Portail client — Administration
          </h1>
          <p className="text-sm text-muted-foreground">
            Comptes d'accès, preuves d'acceptation de devis, paiements en
            ligne, documents client, jalons de chantier et demandes de ticket
            SAV reçus depuis le portail self-service client.
          </p>
        </header>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="flex w-full flex-wrap justify-start">
            <TabsTrigger value="comptes">Comptes d'accès</TabsTrigger>
            <TabsTrigger value="acceptations-devis">Acceptations de devis</TabsTrigger>
            <TabsTrigger value="paiements-facture">Paiements de facture</TabsTrigger>
          </TabsList>

          <TabsContent value="comptes">
            <ComptesPortailAdmin />
          </TabsContent>
          <TabsContent value="acceptations-devis">
            <AcceptationsDevisPortailAdmin />
          </TabsContent>
          <TabsContent value="paiements-facture">
            <PaiementsFacturePortailAdmin />
          </TabsContent>
        </Tabs>
      </div>
    </TooltipProvider>
  )
}

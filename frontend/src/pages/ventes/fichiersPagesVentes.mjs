// Utilitaire de TEST : les fichiers de pages/ventes/ balayés par les gardes de
// source (APX11 en-tête legacy, APX12 glyphes de tendance), y compris les
// dossiers extraits devisList/ (SPL206, de DevisList.jsx) et factureList/
// (SPL211, de FactureList.jsx). Chemins relatifs à pages/ventes/. UNE seule
// liste partagée : un futur dossier extrait s'ajoute ici, pas dans chaque test.
import { readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const ICI = path.dirname(fileURLToPath(import.meta.url))
const DOSSIERS_EXTRAITS = ['devisList', 'factureList']

export function fichiersPagesVentes() {
  return [
    ...readdirSync(ICI),
    ...DOSSIERS_EXTRAITS.flatMap((d) =>
      readdirSync(path.join(ICI, d)).map((f) => path.join(d, f))),
  ]
}

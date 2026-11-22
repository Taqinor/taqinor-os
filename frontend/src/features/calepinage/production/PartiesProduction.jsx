import { formatNumber } from '../../../lib/format'
import { useModeExpert } from '../atelier/modeExpert'
import { kwh, nonCalculee } from './ResultatHeros.helpers'

/* ACAL848 — « Existant / Ajouté / Total » (niveau expert). Rendu seulement quand le serveur publie
   `production.parties` (ACAL843 : un pan du document est `existant`) ; sans lui, le panneau est
   inchangé. Tout est SERVI : kWc, P50 « avec l'âge » (la dégradation de la fiche du module appliquée
   à l'année de mise en service) et P50 neuf en petit, puis la mention du serveur, reprise telle
   quelle. Aucun calcul, aucun prix, aucune économie. */

const LIGNES = [['existant', 'Existant'], ['ajoute', 'Ajouté'], ['total', 'Total']]

const kwc = (v) => nonCalculee(v, (x) => `${formatNumber(x, { decimals: 2 })} kWc`)

export default function PartiesProduction({ parties }) {
  const [expert] = useModeExpert()
  if (!expert || !parties || typeof parties !== 'object') return null
  return (
    <details data-testid="acal848-parties" className="text-sm">
      <summary className="min-h-11 cursor-pointer text-muted-foreground">Existant et ajouté</summary>
      <table className="mt-2 w-full text-left">
        <thead>
          <tr className="text-xs text-muted-foreground">
            <th scope="col" className="font-medium">Partie</th>
            <th scope="col" className="font-medium">Puissance</th>
            <th scope="col" className="font-medium">Production P50 avec l’âge</th>
          </tr>
        </thead>
        <tbody>
          {LIGNES.map(([cle, libelle]) => {
            const ligne = parties[cle]
            if (!ligne) return null
            return (
              <tr key={cle} data-testid={`acal848-${cle}`}>
                <th scope="row" className="font-medium">{libelle}</th>
                <td className="tabular-nums">{kwc(ligne.kwc)}</td>
                <td className="tabular-nums">
                  {kwh(ligne.p50_kwh_avec_age)}
                  <span className="block text-xs text-muted-foreground">neuf : {kwh(ligne.p50_kwh_neuf)}</span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {parties.mention && (
        <p className="mt-1 text-xs text-muted-foreground" data-testid="acal848-mention">{parties.mention}</p>
      )}
    </details>
  )
}

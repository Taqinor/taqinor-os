// SPL46 — LE PANNEAU BRUT « Surcharges (registre) » (QJR215/QJR574), déplacé
// tel quel de DevisGenerator.jsx, condition d'affichage comprise (devis
// enregistré ET administrateur, verbatim).
import { FileText } from 'lucide-react'
import { Button, Card, CardContent, Input } from '../../../ui'
import { GenCardHeader } from './CarteMetrique'
import { CHEMINS_AUTORISES, cheminNonLu } from '../../../features/ventes/quote/overrides'

export default function PanneauSurcharges({
  editDevis, estAdmin, ovChemin, setOvChemin, ovValeur, setOvValeur, overridesBusy,
  poserOverride, overridesErreur, overridesReg, regenererOverride,
  // EDC9 — repliée par défaut en Édition complète (choix mémorisé).
  surchargesRepliees = false, basculerCarte = () => {},
}) {
  return (
    <>
      {/* QJR215 — registre de surcharges (QJR214/QJR216) : lecture à
          l'ouverture (au montage de ce panneau), pose EXPLICITE d'un
          chemin, retour à l'automatique par chemin. N'existe que sur un
          devis DÉJÀ enregistré (le registre vit sur `Devis.overrides`).
          QJR574 — administrateurs seulement. */}
      {editDevis?.id && estAdmin && (
        <Card data-testid="overrides-panel">
          {/* EDC9 — repliée par défaut (choix mémorisé), contenu monté. */}
          <GenCardHeader icon={FileText} title="Surcharges (registre)"
                         repliable replie={surchargesRepliees}
                         onBasculer={() => basculerCarte('surcharges')}
                         controle="gen-surcharges-contenu" />
          <CardContent id="gen-surcharges-contenu" hidden={surchargesRepliees}
                       className="pt-4 space-y-3">
            <div className="flex flex-wrap items-end gap-2">
              <select
                data-testid="overrides-chemin"
                className="rounded-md border border-input bg-background px-2 py-1.5 text-sm"
                value={ovChemin}
                onChange={(e) => setOvChemin(e.target.value)}
              >
                {/* QJR571 (D-QJR5-8) — un chemin que le moteur ne lit pas
                    est DIT tel quel : sa pose ne change pas le document. */}
                {CHEMINS_AUTORISES.map((c) => (
                  <option key={c} value={c}>
                    {cheminNonLu(c) ? `${c} — sans effet sur le document` : c}
                  </option>
                ))}
              </select>
              <Input
                data-testid="overrides-valeur"
                placeholder="Valeur (ex. 14, &quot;ONEE&quot;, [1,2,3])"
                value={ovValeur}
                onChange={(e) => setOvValeur(e.target.value)}
                className="max-w-xs"
              />
              <Button type="button" size="sm" data-testid="overrides-poser"
                      disabled={overridesBusy || !ovValeur}
                      onClick={poserOverride}>
                Poser
              </Button>
            </div>
            {/* Un refus 400 est affiché VERBATIM — jamais avalé. */}
            {overridesErreur && (
              <p className="rounded-md border border-destructive/30 bg-destructive/10 p-2 text-xs text-destructive"
                 data-testid="overrides-erreur">
                {overridesErreur}
              </p>
            )}
            {/* Bloc `effectif` : valeur AUTO vs valeur MANUELLE, côte à
                côte — la déclaration devient visible, jamais tacite. */}
            {overridesReg?.effectif && Object.keys(overridesReg.effectif).length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-xs" data-testid="overrides-effectif-table">
                  <thead>
                    <tr className="text-left text-muted-foreground">
                      <th className="pr-3 py-1">Chemin</th>
                      <th className="pr-3 py-1">Auto</th>
                      <th className="pr-3 py-1">Manuel</th>
                      <th className="pr-3 py-1">Effectif</th>
                      <th className="pr-3 py-1">Source</th>
                      <th className="py-1" />
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(overridesReg.effectif).map(([chemin, v]) => (
                      <tr key={chemin} className="border-t border-border"
                          data-testid={`overrides-effectif-row-${chemin}`}>
                        <td className="pr-3 py-1 font-mono">
                          {chemin}
                          {v.non_lu && (
                            <span className="ml-1 font-sans text-muted-foreground"
                                  data-testid={`overrides-non-lu-${chemin}`}>
                              — sans effet sur le document
                            </span>
                          )}
                        </td>
                        <td className="pr-3 py-1">{v.auto == null ? '—' : JSON.stringify(v.auto)}</td>
                        <td className="pr-3 py-1">{v.manuel == null ? '—' : JSON.stringify(v.manuel)}</td>
                        <td className="pr-3 py-1 font-medium">{v.effectif == null ? '—' : JSON.stringify(v.effectif)}</td>
                        <td className="pr-3 py-1">{v.source}</td>
                        <td className="py-1">
                          {v.source === 'manuel' && (
                            <Button type="button" size="sm" variant="ghost"
                                    data-testid={`overrides-regenerer-${chemin}`}
                                    disabled={overridesBusy}
                                    onClick={() => regenererOverride(chemin)}>
                              Régénérer
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </>
  )
}

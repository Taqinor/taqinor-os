// SPL52 — LA CARTE « Aperçu de la Simulation » DU GÉNÉRATEUR, déplacée
// telle quelle de DevisGenerator.jsx : étude horaire résidentielle (source,
// dimensionnement, falaise / impulsions / ventilation mensuelle), étude C&I,
// métriques QF5 / CJ2b signées (moteur / apercu / signerEcoOuRoi), comparateur
// VX138 et graphique recharts. La garde « masquée en agricole » reste dans la
// coquille. Props nommées une par une, jamais de spread.
import { Fragment } from 'react'
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { Link } from 'react-router-dom'
import { BarChart3 } from 'lucide-react'
import { Button, Card, CardContent, BarreDefilementCollante } from '../../../ui'
import { formatNumber, formatMAD } from '../../../lib/format'
import {
  balayageStockageAffichable, LIBELLES_MOIS,
} from '../../../features/ventes/etudeHorairePreview'
import { facturesRecaleesAffichables, motivationAffichable } from '../../../features/ventes/etudeHorairePreviewPur'
import { moteur } from '../../../features/ventes/quote/valeur'
import { SAISON_LABELS, fmtNum } from '../../../features/ventes/quote/ecranDefauts.js'
import CarteMetrique, { GenCardHeader } from './CarteMetrique'

//: Revue de l'écran (25/11) — UNE règle pour tout retour en années de l'aperçu (cartes,
//: tableau, falaise) : au dixième, virgule française (celle des cellules C&I voisines).
const ansFr = (v) => formatNumber(v, { decimals: 1 })
import { APERCU_INDISPONIBLE } from './hooks/useConceptionEcran'

export default function ApercuSimulation({
  setPreviewCollapsed, previewCollapsed, modeInstallation, etudeHoraireCorps,
  etudeHoraireSourceServeur, etudeHoraireSourceLabel, etudeHoraireChargement, etudeHoraireErreur,
  etudeHoraireDonnees, etudeHoraireLignes, ligneStockageOuverte, appliquerTailleDimensionnement,
  setLigneStockageOuverte, etudeHoraireFalaise, etudeHoraireGlitch, etudeHoraireEstimationConso,
  marcheCi, roi, etudeHoraireAnnuel, sansRec, showAvec,
  apercuProductionKwh, apercuProductionKwhAvec = null, showSans, signerEcoOuRoi, apercuEcoSans, apercuPaybackSansJamais,
  apercuPaybackSans, totals, avecRec, batterieInvendableServeur, verdictBatterieServeur,
  apercuEcoAvec, apercuPaybackAvecJamais, apercuPaybackAvec, capaciteBatterieInconnue,
  apercuPaybackSansAbsent = 'N/A', apercuPaybackAvecAbsent = 'N/A',
  facturesSaisies, chartData, apercuAvecAbsent = null, leadId = '',
  // EDC9 — repli en Édition complète (état tenu par l'écran, choix mémorisé).
  editDevis = null, simulationRepliee = false, basculerCarte = () => {},
}) {
  // Deux options montrées ET deux champs PV : une production par option.
  const productionParOption = apercuProductionKwhAvec != null && showSans && showAvec
  // R2-07 — une facture déclarée recalée par le barème (saut de tranche) est DITE.
  // Revue de l'écran (25/11) — la ligne sous le tableau, composée des valeurs servies.
  const motivation = motivationAffichable(etudeHoraireDonnees?.dimensionnement)
  const facturesRecalees = facturesRecaleesAffichables(
    etudeHoraireDonnees?.consommation?.detail, etudeHoraireCorps)
  return (
    <Card id="gen-sec-simulation" data-nav-libelle="Simulation">
      {/* EDC9 — repliable en Édition complète (repliée par défaut, jamais
          masquée) : le contenu reste MONTÉ (`hidden`), ses ancres
          `data-figure` restent lisibles (parité écran / PDF). */}
      <GenCardHeader icon={BarChart3} title="Aperçu de la Simulation"
                     repliable={Boolean(editDevis)}
                     replie={simulationRepliee}
                     onBasculer={() => basculerCarte('simulation')}
                     controle="gen-sec-simulation-contenu">
        {/* Repliable sur téléphone uniquement (bouton caché sur bureau) ;
            en Édition complète, le repli EDC9 le remplace. */}
        {!editDevis && (
          <Button type="button" size="sm" variant="outline" className="gen-preview-toggle"
                  onClick={() => setPreviewCollapsed(v => !v)}>
            {previewCollapsed ? 'Afficher' : 'Replier'}
          </Button>
        )}
      </GenCardHeader>
      <CardContent id="gen-sec-simulation-contenu" hidden={simulationRepliee}
                   className={`gen-preview-body pt-4${previewCollapsed ? ' m-collapsed' : ''}`}>
        {/* CJ2b — ORDRE FONDATEUR (20/08) : « on ne voit ni l'économie
            réelle calculée, ni les données PVGIS — cette donnée devrait
            être comparée à la courbe de consommation ». Résidentiel
            uniquement, sous le bandeau de source (serveur vs estimation
            locale, règle d'honnêteté #2/#4), le tableau de
            dimensionnement (paliers candidats du moteur horaire, chacun
            avec sa réalité batterie — règle #1) et le détail saisonnier
            production × consommation. */}
        {modeInstallation === 'residentiel' && etudeHoraireCorps && (
          <div className="mb-4" data-testid="etude-horaire-block">
            {etudeHoraireSourceServeur ? (
              <p className="mb-2 text-xs font-medium text-success" data-testid="etude-horaire-source">
                Chiffres du moteur horaire (serveur) — PVGIS réel × consommation réelle du client.
                {etudeHoraireSourceLabel?.estimation && (
                  <> {' '}Détail mensuel : {etudeHoraireSourceLabel.libelle}.</>
                )}
              </p>
            ) : roi?.modele === 'refus' && !etudeHoraireChargement ? null : (
              // Revue de l'écran (25/11) — un refus ou un échec est dit UNE fois, plus
              // bas (`apercu-conception-attente`), jamais répété ici.
              <p className="mb-2 text-xs text-muted-foreground" data-testid="etude-horaire-source">
                {etudeHoraireChargement
                  ? 'Calcul du moteur horaire en cours…'
                  : (etudeHoraireErreur
                      || (roi?.modele === 'conception' ? 'Détail horaire non servi pour cet aperçu.'
                        : 'Aucune conception servie pour l’instant.'))}
              </p>
            )}
            {/* E7d — les phrases du moteur sur la consommation retenue (imposée par le devis…), telles quelles. */}
            {etudeHoraireDonnees?.notes?.length > 0 && (
              <ul className="mb-3 list-disc pl-5 text-xs text-muted-foreground" data-testid="etude-horaire-notes">
                {etudeHoraireDonnees.notes.map((a) => <li key={a}>{a}</li>)}
              </ul>
            )}
            {etudeHoraireDonnees?.avertissements?.length > 0 && (
              <ul className="mb-3 list-disc pl-5 text-xs text-warning" data-testid="etude-horaire-avertissements">
                {etudeHoraireDonnees.avertissements.map((a) => <li key={a}>{a}</li>)}
              </ul>
            )}
            {facturesRecalees.length > 0 && (
              <ul className="mb-3 list-disc pl-5 text-xs text-warning" data-testid="etude-horaire-facture-recalee">
                {facturesRecalees.map((a) => <li key={a}>{a}</li>)}
              </ul>
            )}
            {etudeHoraireLignes.length > 0 && (
              // EDC3 — barre horizontale collante (même composant que la
              // table des lignes) : à chaque hauteur du tableau, jamais au pied.
              <BarreDefilementCollante>
                <table className="w-full border-collapse text-xs" data-testid="etude-horaire-dimensionnement">
                  <thead>
                    <tr className="border-b border-border text-left text-muted-foreground">
                      <th className="py-1 pr-3 font-medium">kWc</th>
                      <th className="py-1 pr-3 font-medium">Onduleur (règle 80 %)</th>
                      <th className="py-1 pr-3 font-medium">Autoconso.</th>
                      <th className="py-1 pr-3 font-medium">Couverture</th>
                      <th className="py-1 pr-3 font-medium">Éco. sans (MAD/an)</th>
                      <th className="py-1 pr-3 font-medium">Éco. avec (MAD/an, batterie du moteur)</th>
                      <th className="py-1 pr-3 font-medium">Payback sans (prix du moteur)</th>
                      <th className="py-1 pr-3 font-medium">Résiduel après (kWh/mois)</th>
                      <th className="py-1 pr-3 font-medium">Remplissage batterie</th>
                      <th className="py-1" />
                    </tr>
                  </thead>
                  <tbody>
                    {etudeHoraireLignes.map((ligne) => {
                      const estRecommandee = etudeHoraireDonnees?.dimensionnement
                        ?.recommandation?.panneaux === ligne.panneaux
                      // L-2OPT (fondateur 24/08) — second optimiseur, même
                      // patron : surligne DISTINCTEMENT le palier optimal
                      // AVEC batterie (recommandation_avec, moteur horaire
                      // serveur) — peut différer de `estRecommandee`
                      // ci-dessus (les deux optima peuvent diverger).
                      const estRecommandeeAvec = etudeHoraireDonnees?.dimensionnement
                        ?.recommandation_avec?.panneaux === ligne.panneaux
                      // L-FRONT lot 4 — résiduel/tranche après la meilleure option
                      // chiffrée (avec batterie si vendable, sinon sans), et
                      // remplissage moyen du stockage retenu pour cette taille.
                      // `null`/absent -> cellule vide, jamais un calcul de repli.
                      const residuelApres = ligne.batterieVendable
                        ? (ligne.residuel_avec_kwh_mois ?? ligne.residuel_kwh_mois)
                        : ligne.residuel_sans_kwh_mois
                      const trancheApres = ligne.batterieVendable
                        ? (ligne.tranche_apres_avec?.libelle ?? ligne.tranche_apres?.libelle)
                        : ligne.tranche_apres_sans?.libelle
                      const remplissageMoyen = ligne.remplissage?.moyen
                      const paliersStockage = balayageStockageAffichable(ligne)
                      const stockageOuvert = ligneStockageOuverte === ligne.panneaux
                      return (
                        <Fragment key={ligne.panneaux}>
                          <tr
                              className={`border-b border-border${estRecommandee ? ' bg-success/10' : ''}${estRecommandeeAvec ? ' bg-info/10' : ''}`}>
                            <td className="min-w-48 py-1.5 pr-3">
                              {formatNumber(ligne.kwc, { decimals: 2 })} kWc
                              {/* Revue de l'écran (25/11) — les badges sous le chiffre, un par ligne. */}
                              {(estRecommandee || estRecommandeeAvec || ligne.tailleDuDevis) && (
                                <div className="mt-0.5 flex flex-col items-start gap-0.5" data-testid="etude-horaire-badges">
                                  {estRecommandee && <span className="gen-rec-badge whitespace-nowrap">★ Recommandé (sans)</span>}
                                  {estRecommandeeAvec && <span className="gen-rec-badge whitespace-nowrap" data-testid="etude-horaire-reco-avec">★ Recommandé (avec)</span>}
                                  {ligne.tailleDuDevis && <span className="gen-rec-badge whitespace-nowrap" data-testid="etude-horaire-taille-devis">{ligne.tailleDuDevis}</span>}
                                </div>
                              )}
                            </td>
                            <td className="py-1.5 pr-3">
                              {ligne.onduleur} — {formatNumber(ligne.ratio_onduleur_kwc * 100, { decimals: 0 })} % du kWc
                              {!ligne.regle_80_pct_respectee && (
                                <span className="text-warning"> (sous 80 %)</span>
                              )}
                            </td>
                            <td className="py-1.5 pr-3">{formatNumber(ligne.taux_autoconso_sans * 100, { decimals: 0 })} %</td>
                            <td className="py-1.5 pr-3">{formatNumber(ligne.couverture_sans * 100, { decimals: 0 })} %</td>
                            <td className="py-1.5 pr-3">{fmtNum(Math.round(ligne.economie_sans_mad))}</td>
                            <td className="py-1.5 pr-3">
                              {ligne.batterieVendable
                                ? fmtNum(Math.round(ligne.economie_avec_mad))
                                : (
                                  <span className="text-muted-foreground" data-testid="etude-horaire-raison-batterie"
                                        title={ligne.raisonTechnique || undefined}>{ligne.raisonBatterie}</span>
                                )}
                            </td>
                            <td className="py-1.5 pr-3">{ligne.payback_sans_annees != null ? `${ansFr(ligne.payback_sans_annees)} ans` : 'N/A'}</td>
                            <td className="py-1.5 pr-3" data-testid="etude-horaire-residuel">
                              {residuelApres != null
                                ? <>{fmtNum(Math.round(residuelApres))} kWh{trancheApres && <> — {trancheApres}</>}</>
                                : '—'}
                            </td>
                            <td className="py-1.5 pr-3" data-testid="etude-horaire-remplissage">
                              {remplissageMoyen != null
                                ? `${formatNumber(remplissageMoyen * 100, { decimals: 0 })} %`
                                : '—'}
                            </td>
                            <td className="py-1.5">
                              <div style={{ display: 'flex', gap: '0.375rem' }}>
                                <Button type="button" size="sm" variant="outline"
                                        onClick={() => appliquerTailleDimensionnement(ligne)}>
                                  Appliquer cette taille
                                </Button>
                                {paliersStockage.length > 0 && (
                                  <Button type="button" size="sm" variant="ghost"
                                          data-testid="etude-horaire-stockage-toggle"
                                          onClick={() => setLigneStockageOuverte(
                                            stockageOuvert ? null : ligne.panneaux)}>
                                    {stockageOuvert ? 'Masquer stockage' : 'Détail stockage'}
                                  </Button>
                                )}
                              </div>
                            </td>
                          </tr>
                          {stockageOuvert && paliersStockage.length > 0 && (
                            <tr className="border-b border-border">
                              <td colSpan={9} className="bg-muted/30 py-2 pr-3">
                                {/* EDC3 — barre horizontale collante. */}
                                <BarreDefilementCollante>
                                  <table className="w-full border-collapse text-xs"
                                         data-testid="etude-horaire-balayage-stockage">
                                    <thead>
                                      <tr className="text-left text-muted-foreground">
                                        <th className="py-1 pr-3 font-medium">Batterie (kWh)</th>
                                        <th className="py-1 pr-3 font-medium">Coût TTC</th>
                                        <th className="py-1 pr-3 font-medium">Éco. (MAD/an)</th>
                                        <th className="py-1 pr-3 font-medium">Éco. marginale</th>
                                        <th className="py-1 pr-3 font-medium">Payback</th>
                                        <th className="py-1 pr-3 font-medium">Résiduel (kWh/mois)</th>
                                        <th className="py-1 pr-3 font-medium">Remplissage moyen</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {paliersStockage.map((p) => (
                                        <tr key={p.capaciteKwh}>
                                          <td className="py-1 pr-3">{fmtNum(p.capaciteKwh)} kWh</td>
                                          <td className="py-1 pr-3">{p.coutTtc != null ? `${fmtNum(Math.round(p.coutTtc))} MAD` : '—'}</td>
                                          <td className="py-1 pr-3">{p.economieMad != null ? fmtNum(Math.round(p.economieMad)) : '—'}</td>
                                          <td className="py-1 pr-3">{p.economieMarginaleMad != null ? fmtNum(Math.round(p.economieMarginaleMad)) : '—'}</td>
                                          <td className="py-1 pr-3">{p.paybackAnnees != null ? `${ansFr(p.paybackAnnees)} ans` : '—'}</td>
                                          <td className="py-1 pr-3">
                                            {p.residuelKwhMois != null
                                              ? <>{fmtNum(Math.round(p.residuelKwhMois))}{p.trancheApres && <> — {p.trancheApres}</>}</>
                                              : '—'}
                                          </td>
                                          <td className="py-1 pr-3">{p.remplissageMoyen != null ? `${formatNumber(p.remplissageMoyen * 100, { decimals: 0 })} %` : '—'}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </BarreDefilementCollante>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
                {motivation && (
                  <p className="mt-2 text-xs text-muted-foreground" data-testid="etude-horaire-motivation"
                     title={motivation.technique || undefined}>
                    {motivation.texte}
                  </p>
                )}
              </BarreDefilementCollante>
            )}
            {etudeHoraireDonnees?.etude?.saisons && (
              <div className="mt-3 grid gap-2 sm:grid-cols-3" data-testid="etude-horaire-saisons">
                {Object.entries(SAISON_LABELS).map(([cle, libelle]) => {
                  const s = etudeHoraireDonnees.etude.saisons[cle]
                  if (!s) return null
                  return (
                    <div key={cle} className="rounded-lg border border-border p-2">
                      <div className="text-xs font-medium">{libelle}</div>
                      <div className="text-xs text-muted-foreground">
                        Production {fmtNum(Math.round(s.production_kwh))} kWh
                        {' · '}Consommation {fmtNum(Math.round(s.consommation_kwh))} kWh
                        {' · '}Autoconsommé {fmtNum(Math.round(s.autoconsomme_sans_kwh))} kWh
                        {' '}({formatNumber(s.taux_autoconso_sans * 100, { decimals: 0 })} %)
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
            {/* L-FRONT lot 4 — falaise tarifaire : la marche du barème juste
                sous la consommation actuelle (« land frankly under the
                cliff »), + la meilleure combinaison du balayage qui y passe.
                Omis en bloc quand le moteur n'a rien calculé. */}
            {etudeHoraireFalaise && (
              <div className="mt-3 rounded-lg border border-border p-3" data-testid="etude-horaire-falaise">
                <div className="text-xs font-medium">Falaise tarifaire</div>
                <div className="text-xs text-muted-foreground">
                  Palier visé : {fmtNum(etudeHoraireFalaise.cibleKwhMois)} kWh/mois
                  {etudeHoraireFalaise.trancheActuelle && (
                    <> — actuellement en {etudeHoraireFalaise.trancheActuelle}</>
                  )}
                  {etudeHoraireFalaise.trancheVisee && (
                    <>, marche visée : {etudeHoraireFalaise.trancheVisee}</>
                  )}
                  .
                </div>
                {etudeHoraireFalaise.meilleure && (
                  <div className="mt-1 text-xs text-muted-foreground" data-testid="etude-horaire-meilleure-falaise">
                    Meilleure combinaison sous la marche : {etudeHoraireFalaise.meilleure.panneaux} panneaux
                    {etudeHoraireFalaise.meilleure.kwc != null && <> ({formatNumber(etudeHoraireFalaise.meilleure.kwc, { decimals: 2 })} kWc)</>}
                    {etudeHoraireFalaise.meilleure.batterieKwh
                      ? <> + {fmtNum(etudeHoraireFalaise.meilleure.batterieKwh)} kWh de batterie</>
                      : ''}
                    {etudeHoraireFalaise.meilleure.residuelKwhMois != null && (
                      <> — résiduel {fmtNum(Math.round(etudeHoraireFalaise.meilleure.residuelKwhMois))} kWh/mois
                        {etudeHoraireFalaise.meilleure.trancheApres && <> ({etudeHoraireFalaise.meilleure.trancheApres})</>}</>
                    )}
                    {etudeHoraireFalaise.meilleure.paybackAnnees != null && (
                      <> — payback {ansFr(etudeHoraireFalaise.meilleure.paybackAnnees)} ans (batterie et prix du moteur)</>
                    )}.
                  </div>
                )}
              </div>
            )}
            {/* L-FRONT lot 4 — résumé annuel des impulsions équipements
                (glitch) : n'apparaît que si le moteur a vraiment déclaré au
                moins un équipement concentrable (part_glitch additif). */}
            {etudeHoraireGlitch && (
              <div className="mt-3 rounded-lg border border-border p-3" data-testid="etude-horaire-glitch">
                <div className="text-xs font-medium">Pointes équipements ({etudeHoraireGlitch.couches.join(', ')})</div>
                <div className="text-xs text-muted-foreground">
                  {fmtNum(Math.round(etudeHoraireGlitch.sansKwh))} kWh/an partent au réseau sans batterie
                  {etudeHoraireGlitch.batterieKwh != null && (
                    <>, dont {fmtNum(Math.round(etudeHoraireGlitch.batterieKwh))} kWh/an rattrapés par le stockage</>
                  )}.
                </div>
              </div>
            )}
            {/* L-FRONT lot 4 — décomposition mensuelle de la consommation
                estimée (base + chaque équipement déclaré), pour que le
                commercial voie chaque ajout compté. Omise en bloc si la clé
                `estimation_conso` est absente du payload. */}
            {etudeHoraireEstimationConso && (
              // EDC3 — barre horizontale collante (12 mois + poste).
              <BarreDefilementCollante className="mt-3">
                <div className="mb-1 text-xs font-medium">Décomposition mensuelle de la consommation (kWh)</div>
                <table className="w-full border-collapse text-xs" data-testid="etude-horaire-estimation-conso">
                  <thead>
                    <tr className="border-b border-border text-left text-muted-foreground">
                      <th className="py-1 pr-3 font-medium">Poste</th>
                      {LIBELLES_MOIS.map((m) => <th key={m} className="py-1 pr-2 font-medium">{m}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-border">
                      <td className="py-1 pr-3">Base</td>
                      {etudeHoraireEstimationConso.base.map((v, i) => (
                        <td key={LIBELLES_MOIS[i]} className="py-1 pr-2">{fmtNum(Math.round(v))}</td>
                      ))}
                    </tr>
                    {etudeHoraireEstimationConso.ajouts.map((a) => (
                      <tr key={a.cle} className="border-b border-border">
                        <td className="py-1 pr-3">+ {a.libelle}</td>
                        {a.valeurs.map((v, i) => (
                          <td key={LIBELLES_MOIS[i]} className="py-1 pr-2">{fmtNum(Math.round(v))}</td>
                        ))}
                      </tr>
                    ))}
                    <tr className="font-medium">
                      <td className="py-1 pr-3">Total</td>
                      {etudeHoraireEstimationConso.total.map((v, i) => (
                        <td key={LIBELLES_MOIS[i]} className="py-1 pr-2">{fmtNum(Math.round(v))}</td>
                      ))}
                    </tr>
                  </tbody>
                </table>
              </BarreDefilementCollante>
            )}
          </div>
        )}
        {/* CIQ223 — en C&I, aucune simulation JS : les économies sont celles
            du moteur serveur (carte « Économies »). */}
        {marcheCi ? (
          <p className="text-center text-sm text-muted-foreground" data-testid="apercu-ci-serveur">
            Économies C&amp;I : voir la carte « Économies » (moteur serveur).
          </p>
        ) : !roi?.modele || roi.modele === 'refus' ? (
          // AGEN11 — rien de servi : l'attente du moteur, son refus dit tel quel,
          // ou l'invitation à saisir (aucun chiffre calculé dans le navigateur).
          <p className="text-center text-sm text-muted-foreground" data-testid="apercu-conception-attente"
             data-champ={roi?.champ || undefined}>
            {roi?.chargement ? 'Calcul en cours…' : roi?.reessayer && roi.message === APERCU_INDISPONIBLE ? (
              // E7d (M2) — échec sans phrase du serveur (5xx, réseau) : le dire et relancer.
              <>
                Aperçu indisponible —{' '}
                <Button type="button" size="sm" variant="outline" className="min-h-11 min-w-11"
                        onClick={roi.reessayer}>Réessayer</Button>
              </>
            ) : roi?.message ? (
              <>
                {roi.message}
                {/* Les cartes disent ce qui manque au lieu de disparaître en silence. */}
                <span className="mt-1 block text-xs">
                  Production, économies et retour sur investissement ne sont pas calculés tant que ce
                  point n’est pas réglé.
                </span>
              </>
            ) : (<>
              Renseignez le nombre de panneaux et les factures, puis la simulation
              s'actualise automatiquement.
            </>)}
          </p>
        ) : (
          <>
            {/* QF5 — quand une facture/consommation réelle est capturée
                (QF4), l'écran affiche le MÊME calcul « deux factures » par
                tranche que le PDF (facture sans vs avec solaire) au lieu
                d'une estimation moyenne. */}
            {/* AGEN11 / E7d — les cartes lisent la conception du moteur unique
                (l'ancien bandeau « Moteur horaire » de l'aperçu horaire, retiré
                avec lui, ne pouvait plus s'afficher). M2 : le bandeau dit d'où
                viennent les chiffres (aperçu de l'écran, ou dernière conception
                rangée du lead) — jamais « ceux du document », qu'il ne lit pas. */}
            <div className="mb-3 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success"
                 data-testid="bandeau-modele-conception">
              Conception du moteur unique{roi.chargement ? ' — calcul en cours…' : ''} :{' '}
              {roi.surApercu
                ? 'chiffres calculés sur les valeurs de l’écran (aperçu, rien n’est enregistré).'
                : 'chiffres de la dernière conception calculée pour ce lead.'}
            </div>
            <div className="gen-metrics-grid">
              {/* CJ2b — Production/Autoconso/Couverture : le serveur
                  horaire (PVGIS réel) gagne dès qu'il a répondu (résidentiel),
                  sinon la conception du moteur unique (AGEN11).
                  QJR426 — aucune puce ici avant comme après : cette carte
                  ne distingue déjà pas ses deux sources à l'écran (le
                  repli `roi` reste, comme aujourd'hui, non étiqueté) —
                  `moteur()` reproduit ce silence à l'octet, jamais un
                  nouveau badge introduit au passage. */}
              {/* QA-FIGURES — `figure` pose `data-figure` (clés :
                  apps/ventes/quote_engine/figures.py) : la parité écran /
                  PDF / page publique / API est vérifiée par
                  e2e/figures-parite.spec.js. */}
              {!productionParOption && (
                <CarteMetrique label="Production annuelle"
                               valeur={moteur(fmtNum(Math.round(apercuProductionKwh)))}
                               unit="kWh / an" accent
                               figure="production_annuelle_kwh" />
              )}
              {/* ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — champs PV
                  divergents (« Les deux », panneaux ajoutés pour la
                  batterie) : une production PAR OPTION, comme le document
                  (`prod_kwh_sans` / `prod_kwh_avec`), jamais celle de
                  l'option sans sous une étiquette commune. */}
              {productionParOption && (
                <>
                  <CarteMetrique label="Production annuelle (sans batterie)"
                                 valeur={moteur(fmtNum(Math.round(apercuProductionKwh)))}
                                 unit="kWh / an" accent
                                 figure="production_annuelle_kwh" figureOption="sans" />
                  <CarteMetrique label="Production annuelle (avec batterie)"
                                 valeur={moteur(fmtNum(Math.round(apercuProductionKwhAvec)))}
                                 unit="kWh / an" accent
                                 figure="production_annuelle_kwh" figureOption="avec" />
                </>
              )}
              {etudeHoraireSourceServeur && (
                <>
                  {/* QJR426 — ces deux cartes ne rendent QUE dans la
                      branche serveur (`etudeHoraireSourceServeur`) :
                      `moteur()` y est toujours exact, jamais un motif
                      inventé. */}
                  <CarteMetrique label="Taux d'autoconsommation (sans)"
                                 valeur={moteur(`${formatNumber(etudeHoraireAnnuel.taux_autoconso_sans * 100, { decimals: 0 })} %`)}
                                 unit="part de la production consommée" />
                  <CarteMetrique label="Taux de couverture (sans)"
                                 valeur={moteur(`${formatNumber(etudeHoraireAnnuel.couverture_sans * 100, { decimals: 0 })} %`)}
                                 unit="part de la conso couverte"
                                 figure="couverture_pct" figureOption="sans" />
                </>
              )}
            </div>
            {/* VX138 — comparateur Sans/Avec : 2 colonnes NOMMÉES au lieu
                d'une grille homogène de jusqu'à 6 cartes reliées par la
                seule étoile — la recommandation devient un liseré porté
                par TOUTE la colonne. */}
            <div className="gen-compare-grid">
              {showSans && (
                <div className={`gen-compare-col${sansRec ? ' gen-compare-col-rec' : ''}`}>
                  <div className="gen-compare-col-title">
                    Sans batterie
                    {sansRec && <span className="gen-rec-badge">★ Recommandé</span>}
                  </div>
                  {/* QJR426 — `signerEcoOuRoi` reproduit EXACTEMENT
                      l'ancien `badge={apercuEstimationExemple ? ... :
                      null}` : `apercu()` porte la même puce
                      `PUCE_APERCU` (« estimation d'exemple », le même
                      texte), `moteur()` n'en porte aucune. */}
                  <CarteMetrique label="Économies"
                                 valeur={signerEcoOuRoi(fmtNum(Math.round(apercuEcoSans)))}
                                 unit="MAD / an"
                                 figure="economie_annuelle" figureOption="sans" />
                  <CarteMetrique label="ROI"
                                 valeur={signerEcoOuRoi(
                                   apercuPaybackSansJamais ? 'Non rentabilisé sur 25 ans'
                                     : apercuPaybackSans != null ? apercuPaybackSans + ' ans' : apercuPaybackSansAbsent)}
                                 unit="retour sur invest." accent
                                 figure="payback_ans" figureOption="sans" />
                  {/* QJR426 — le coût est celui, certain, des lignes du
                      devis (`optionTotalsTTC`) : jamais de disclaimer
                      avant, `moteur()` en garde l'absence à l'octet. */}
                  <CarteMetrique label="Coût"
                                 valeur={moteur(fmtNum(Math.round(totals.totalSans)))}
                                 unit="MAD TTC"
                                 figure="total_ttc" figureOption="sans" />
                </div>
              )}
              {showAvec && (
                <div className={`gen-compare-col${avecRec ? ' gen-compare-col-rec' : ''}`}>
                  <div className="gen-compare-col-title">
                    Avec batterie
                    {avecRec && <span className="gen-rec-badge">★ Recommandé</span>}
                  </div>
                  {/* CJ2b — OMISSION HONNÊTE. Le moteur horaire dit que
                      l'option batterie n'est pas livrable à cette taille :
                      on affiche SA raison, jamais un montant — et surtout
                      jamais le « 0 MAD » que produirait un arrondi sur une
                      valeur absente. */}
                  {batterieInvendableServeur ? (
                    <p className="text-xs text-muted-foreground"
                       data-testid="etude-horaire-batterie-invendable">
                      Option batterie non livrable pour cette taille :{' '}
                      {verdictBatterieServeur.raison}
                    </p>
                  ) : (
                    <>
                      {/* E7d — option avec non chiffrée par la conception servie : la
                          raison à la place de l'économie et du ROI ; le coût (lignes) reste. */}
                      {apercuAvecAbsent ? (
                        <p className="text-xs text-muted-foreground" data-testid="apercu-avec-non-chiffree">
                          {apercuAvecAbsent}
                        </p>
                      ) : (
                        <>
                          <CarteMetrique label="Économies"
                                         valeur={signerEcoOuRoi(fmtNum(Math.round(apercuEcoAvec)))}
                                         unit="MAD / an"
                                         figure="economie_annuelle" figureOption="avec" />
                          <CarteMetrique label="ROI"
                                         valeur={signerEcoOuRoi(
                                           apercuPaybackAvecJamais ? 'Non rentabilisé sur 25 ans'
                                             : apercuPaybackAvec != null ? apercuPaybackAvec + ' ans' : apercuPaybackAvecAbsent)}
                                         unit="retour sur invest." accent
                                         figure="payback_ans" figureOption="avec" />
                        </>
                      )}
                      <CarteMetrique label="Coût"
                                     valeur={moteur(fmtNum(Math.round(totals.totalAvec)))}
                                     unit="MAD TTC"
                                     figure="total_ttc" figureOption="avec" />
                      {/* BAT5DEF — au moins une ligne batterie n'a pas de
                          kWh lisible : la capacité utilisée par le ROI et
                          l'étude horaire est SOUS-estimée (0 kWh pour
                          cette ligne, jamais un défaut inventé). Signalé
                          à l'écran, jamais caché — même patron que
                          gen-mt-manquant. */}
                      {capaciteBatterieInconnue && (
                        <p className="text-xs text-warning"
                           data-testid="gen-battery-capacite-inconnue">
                          Capacité batterie non lisible sur au moins une
                          ligne (désignation sans kWh) : les économies et
                          le payback « avec batterie » sont sous-estimés,
                          renseignez le kWh dans la désignation.
                        </p>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
            <div className="gen-chart-title">Économies mensuelles estimées (MAD / mois)</div>
            {/* N4 — tant qu'aucune facture RÉELLE n'a été saisie
                (facturesSaisies), `monthly` ne porte que les valeurs
                D'EXEMPLE du simulateur (DEFAULT_MONTHLY_BILLS) : le
                graphique « Facture ONEE » ne doit alors jamais se
                présenter comme une donnée du client — il est masqué au
                profit d'un message explicite. */}
            {facturesSaisies && chartData.length !== 12 ? (
              // E7d (M3) — le graphe ne sort que de la réponse des cartes : sans
              // ses douze mois, il le dit (jamais une courbe d'une autre source).
              <p className="py-6 text-center text-sm text-muted-foreground" data-testid="chart-indisponible">
                Graphique mensuel non disponible pour cet aperçu : le moteur n’a pas servi le détail
                mois par mois.
              </p>
            ) : facturesSaisies ? (
              <ResponsiveContainer width="100%" height={260}>
                <ComposedChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(0,0,0,0.07)" />
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }}
                         label={{ value: 'MAD / mois', angle: -90, position: 'insideLeft', fontSize: 11 }}
                         tickFormatter={(v) => formatNumber(v)} />
                  <Tooltip formatter={(v, name) => [`${formatMAD(v, { decimals: 0 })}`, name]} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="facture" name="Facture ONEE (MAD)"
                       fill="rgba(181,192,206,0.55)" stroke="rgba(181,192,206,0.8)" radius={[3, 3, 0, 0]} />
                  {showSans && (
                    <Line type="monotone" dataKey="ecoSans"
                          name={'Option 1 – Sans batterie' + (sansRec ? ' ⭐' : '')}
                          stroke="var(--gen-chart-sans)" strokeWidth={sansRec ? 3.5 : 2.2}
                          dot={{ r: sansRec ? 5 : 4 }} />
                  )}
                  {showAvec && (
                    <Line type="monotone" dataKey="ecoAvec"
                          name={'Option 2 – Avec batterie' + (avecRec ? ' ⭐' : '')}
                          stroke="var(--gen-chart-avec)" strokeWidth={avecRec ? 3.5 : 2.2}
                          dot={{ r: avecRec ? 5 : 4 }} />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            ) : (
              <p className="py-6 text-center text-sm text-muted-foreground" data-testid="chart-no-bills">
                Graphique masqué — exemple sans saisie réelle. Renseignez la Facture Hiver/Été (MAD/mois){' '}
                {leadId ? <Link to={`/crm/leads/${leadId}`} className="underline">de la fiche du lead</Link> : 'de la fiche du lead'}
                {' '}(ou le détail mensuel ci-dessus) pour voir vos économies mensuelles réelles.
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

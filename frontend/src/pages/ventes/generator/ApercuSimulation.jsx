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
import { BarChart3 } from 'lucide-react'
import { Button, Card, CardContent } from '../../../ui'
import { formatNumber, formatMAD } from '../../../lib/format'
import {
  balayageStockageAffichable, LIBELLES_MOIS,
} from '../../../features/ventes/etudeHorairePreview'
import { moteur } from '../../../features/ventes/quote/valeur'
import { SAISON_LABELS, fmtNum } from '../../../features/ventes/quote/ecranDefauts.js'
import CarteMetrique, { GenCardHeader } from './CarteMetrique'

export default function ApercuSimulation({
  setPreviewCollapsed, previewCollapsed, modeInstallation, etudeHoraireCorps,
  etudeHoraireSourceServeur, etudeHoraireSourceLabel, etudeHoraireChargement, etudeHoraireErreur,
  etudeHoraireDonnees, etudeHoraireLignes, ligneStockageOuverte, appliquerTailleDimensionnement,
  setLigneStockageOuverte, etudeHoraireFalaise, etudeHoraireGlitch, etudeHoraireEstimationConso,
  marcheCi, roi, etudeHoraireAnnuel, sansRec, showAvec, etudeHoraireAnnuelAvec, distributeur,
  apercuProductionKwh, showSans, signerEcoOuRoi, apercuEcoSans, apercuPaybackSansJamais,
  apercuPaybackSans, totals, avecRec, batterieInvendableServeur, verdictBatterieServeur,
  apercuEcoAvec, apercuPaybackAvecJamais, apercuPaybackAvec, capaciteBatterieInconnue,
  facturesSaisies, chartData,
}) {
  return (
    <Card>
      <GenCardHeader icon={BarChart3} title="Aperçu de la Simulation">
        {/* Repliable sur téléphone uniquement (bouton caché sur bureau) */}
        <Button type="button" size="sm" variant="outline" className="gen-preview-toggle"
                onClick={() => setPreviewCollapsed(v => !v)}>
          {previewCollapsed ? 'Afficher' : 'Replier'}
        </Button>
      </GenCardHeader>
      <CardContent className={`gen-preview-body pt-4${previewCollapsed ? ' m-collapsed' : ''}`}>
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
            ) : (
              <p className="mb-2 text-xs text-muted-foreground" data-testid="etude-horaire-source">
                {etudeHoraireChargement
                  ? 'Calcul du moteur horaire en cours…'
                  : (etudeHoraireErreur
                      || 'Estimation locale (hors ligne) — en attente du moteur horaire serveur.')}
              </p>
            )}
            {etudeHoraireDonnees?.avertissements?.length > 0 && (
              <ul className="mb-3 list-disc pl-5 text-xs text-warning" data-testid="etude-horaire-avertissements">
                {etudeHoraireDonnees.avertissements.map((a) => <li key={a}>{a}</li>)}
              </ul>
            )}
            {etudeHoraireLignes.length > 0 && (
              <div style={{ overflowX: 'auto' }}>
                <table className="w-full border-collapse text-xs" data-testid="etude-horaire-dimensionnement">
                  <thead>
                    <tr className="border-b border-border text-left text-muted-foreground">
                      <th className="py-1 pr-3 font-medium">kWc</th>
                      <th className="py-1 pr-3 font-medium">Onduleur (règle 80 %)</th>
                      <th className="py-1 pr-3 font-medium">Autoconso.</th>
                      <th className="py-1 pr-3 font-medium">Couverture</th>
                      <th className="py-1 pr-3 font-medium">Éco. sans (MAD/an)</th>
                      <th className="py-1 pr-3 font-medium">Éco. avec (MAD/an)</th>
                      <th className="py-1 pr-3 font-medium">Payback</th>
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
                            <td className="py-1.5 pr-3">
                              {formatNumber(ligne.kwc, { decimals: 2 })} kWc
                              {estRecommandee && <span className="gen-rec-badge"> ★ Recommandé (sans)</span>}
                              {estRecommandeeAvec && <span className="gen-rec-badge" data-testid="etude-horaire-reco-avec"> ★ Recommandé (avec)</span>}
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
                                : <span className="text-muted-foreground">{ligne.raisonBatterie}</span>}
                            </td>
                            <td className="py-1.5 pr-3">{ligne.payback_sans_annees != null ? `${ligne.payback_sans_annees} ans` : 'N/A'}</td>
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
                                <div style={{ overflowX: 'auto' }}>
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
                                          <td className="py-1 pr-3">{p.paybackAnnees != null ? `${p.paybackAnnees} ans` : '—'}</td>
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
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      )
                    })}
                  </tbody>
                </table>
                {etudeHoraireDonnees?.dimensionnement?.motivation && (
                  <p className="mt-2 text-xs text-muted-foreground" data-testid="etude-horaire-motivation">
                    {etudeHoraireDonnees.dimensionnement.motivation}
                  </p>
                )}
              </div>
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
                      <> — payback {etudeHoraireFalaise.meilleure.paybackAnnees} ans</>
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
              <div className="mt-3" style={{ overflowX: 'auto' }}>
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
              </div>
            )}
          </div>
        )}
        {/* CIQ223 — en C&I, aucune simulation JS : les économies sont celles
            du moteur serveur (carte « Économies »). */}
        {marcheCi ? (
          <p className="text-center text-sm text-muted-foreground" data-testid="apercu-ci-serveur">
            Économies C&amp;I : voir la carte « Économies » (moteur serveur).
          </p>
        ) : !roi ? (
          <p className="text-center text-sm text-muted-foreground">
            Renseignez le nombre de panneaux et les factures, puis la simulation
            s'actualise automatiquement.
          </p>
        ) : (
          <>
            {/* QF5 — quand une facture/consommation réelle est capturée
                (QF4), l'écran affiche le MÊME calcul « deux factures » par
                tranche que le PDF (facture sans vs avec solaire) au lieu
                d'une estimation moyenne. */}
            {etudeHoraireSourceServeur ? (
              // AGNR23 — le bandeau dit le modèle DES CARTES : l'étude
              // horaire du moteur quand elle répond.
              <div className="mb-3 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success"
                   data-testid="bandeau-modele-cartes">
                Moteur horaire : facture ≈ <strong>{fmtNum(Math.round(etudeHoraireAnnuel.facture_avant_mad))} MAD/an</strong>
                {' '}sans solaire → avec solaire ≈{' '}
                <strong>
                  {fmtNum(Math.round(sansRec || !showAvec
                    ? etudeHoraireAnnuel.facture_apres_sans_mad
                    : (etudeHoraireAnnuelAvec || etudeHoraireAnnuel).facture_apres_avec_mad))} MAD/an
                </strong>
                {' '}— chiffres des cartes (production horaire × consommation du client).
              </div>
            ) : roi.savings_model === 'factures' ? (
              <div className="mb-3 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success">
                Facture réelle {distributeur.toUpperCase()} ≈ <strong>{fmtNum(roi.facture_sans)} MAD/an</strong>
                {' '}sans solaire → avec solaire ≈{' '}
                <strong>
                  {fmtNum(sansRec || !showAvec ? roi.facture_avec_sans : roi.facture_avec_avec)} MAD/an
                </strong>
                {' '}— économie calculée par tranche (barème {distributeur.toUpperCase()}), pas une estimation.
              </div>
            ) : (
              <div className="mb-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
                Estimation (production × autoconsommation × tarif moyen) — renseignez la
                facture réelle du client ci-dessus pour un calcul par tranche exact.
              </div>
            )}
            <div className="gen-metrics-grid">
              {/* CJ2b — Production/Autoconso/Couverture : le serveur
                  horaire (PVGIS réel) gagne dès qu'il a répondu (résidentiel),
                  sinon repli sur `roi` (miroir local, inchangé).
                  QJR426 — aucune puce ici avant comme après : cette carte
                  ne distingue déjà pas ses deux sources à l'écran (le
                  repli `roi` reste, comme aujourd'hui, non étiqueté) —
                  `moteur()` reproduit ce silence à l'octet, jamais un
                  nouveau badge introduit au passage. */}
              {/* QA-FIGURES — `figure` pose `data-figure` (clés :
                  apps/ventes/quote_engine/figures.py) : la parité écran /
                  PDF / page publique / API est vérifiée par
                  e2e/figures-parite.spec.js. */}
              <CarteMetrique label="Production annuelle"
                             valeur={moteur(fmtNum(Math.round(apercuProductionKwh)))}
                             unit="kWh / an" accent
                             figure="production_annuelle_kwh" />
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
                                     : apercuPaybackSans != null ? apercuPaybackSans + ' ans' : 'N/A')}
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
                      <CarteMetrique label="Économies"
                                     valeur={signerEcoOuRoi(fmtNum(Math.round(apercuEcoAvec)))}
                                     unit="MAD / an"
                                     figure="economie_annuelle" figureOption="avec" />
                      <CarteMetrique label="ROI"
                                     valeur={signerEcoOuRoi(
                                       apercuPaybackAvecJamais ? 'Non rentabilisé sur 25 ans'
                                         : apercuPaybackAvec != null ? apercuPaybackAvec + ' ans' : 'N/A')}
                                     unit="retour sur invest." accent
                                     figure="payback_ans" figureOption="avec" />
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
            {facturesSaisies ? (
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
                Graphique masqué — exemple sans saisie réelle. Renseignez vos
                factures (hiver/été ou détail mensuel ci-dessus) pour voir vos
                économies mensuelles réelles.
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

// SPL55 — LA CARTE « Paramètres Techniques » DU GÉNÉRATEUR, déplacée telle
// quelle de DevisGenerator.jsx : puissance cible EZ5 (`gen-kwc-cible`),
// panneaux, puissance panneau, divergence QJR568, `StructureSelector`
// (STKCAT10), justification du palier, « deux valeurs » L-2OPT, refus U3-900,
// curseur de part diurne, Recalculer / Auto-remplir, `composition-erreur`
// (QJR577), `BandeauDeriveLead` (QJR589), onduleurs incomplets, confirmation
// pompage. Champs nombre en `step="any"` (garde `SURFACES_SAISIE` de
// solar.test.mjs). Props nommées une par une, jamais de spread.
import { RefreshCw, Zap } from 'lucide-react'
import { Button, Card, CardContent, Input, Label, Segmented } from '../../../ui'
import { formatNumber } from '../../../lib/format'
import { roleLabel } from '../../../features/ventes/solar'
import BandeauDeriveLead from '../../../features/ventes/quote/BandeauDeriveLead'
import StructureSelector from '../../../features/stock/StructureSelector'
import { GenCardHeader } from './CarteMetrique'

export default function CarteParametresTechniques({
  kwcCible, onKwcCibleChange, nbPanneaux, onNbPanneauxChange, panelW, dispatchSizing, kwp,
  panneauxLignes, produits, structureProduitId, structureType, sizingInfo, modeInstallation,
  showSans, deuxValeursDim, showAvec, sizingServeurMessage, dayUsage, errors,
  pompageManquants, autoFillLoading, marcheCi, apercuCi, fHiver, recalculerDimensionnement,
  avecQuantitesFigees, handleAutoFill, compositionErreur, editDevis, leadValeursModifiees,
  setLeadValeursModifiees, clear, setRechargeEdit, onduleursIncomplets, pompageAutoFilled,
  apercuPompage,
}) {
  return (
    <Card>
      <GenCardHeader icon={Zap} title="Paramètres Techniques" />
      <CardContent className="pt-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {/* EZ5 — on DIMENSIONNE en kWc, pas en nombre de panneaux : le
              client et le commercial disent « 3 kWc », jamais « 5 panneaux
              de 550 W ». Le champ est BIDIRECTIONNEL — taper une puissance
              cible remplit les panneaux, changer les panneaux remet la
              cible à jour. La conversion réutilise `panneauxPourKwc`
              (features/ventes/solar.js), déjà employée par le
              pré-remplissage depuis le lead : rien n'est réécrit. */}
          <div className="grid gap-1.5">
            <Label htmlFor="gen-kwc-cible">Puissance cible (kWc)</Label>
            <Input id="gen-kwc-cible" type="number" min="0" step="any"
                   placeholder="ex: 3" value={kwcCible}
                   data-testid="gen-kwc-cible"
                   onChange={e => onKwcCibleChange(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="gen-nbpanneaux" required>Nombre de panneaux</Label>
            <Input id="gen-nbpanneaux" type="number" min="1" max="500" step="any"
                   placeholder="ex: 14" value={nbPanneaux}
                   onChange={e => onNbPanneauxChange(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="gen-panelw">Puissance Panneau (W)</Label>
            <Input id="gen-panelw" type="number" min="100" max="1000" step="any"
                   value={panelW}
                   onChange={e => dispatchSizing({ type: 'SAISI', champ: 'panelW', valeur: e.target.value })} />
          </div>
          <div className="grid gap-1.5">
            <Label>Puissance PV (kWp) — calculée</Label>
            <div className="gen-kwp">{kwp > 0 ? formatNumber(kwp, { decimals: 2 }) + ' kWp' : '—'}</div>
          </div>
          {/* QJR568 — les lignes et la cible divergent (quantité panneau
              corrigée à la main) : on le DIT, sans recomposer d'office. */}
          {panneauxLignes > 0 && (parseInt(nbPanneaux) || 0) > 0
            && panneauxLignes !== (parseInt(nbPanneaux) || 0) && (
            <p className="text-xs text-warning sm:col-span-2" data-testid="gen-divergence-panneaux">
              Les lignes portent {formatNumber(panneauxLignes)} panneaux, la cible en
              vise {formatNumber(parseInt(nbPanneaux) || 0)} — recomposer ? (Auto-remplir)
            </p>
          )}
          {/* STKCAT10 (décision fondateur 16/09/2026) — le bouton
              acier/aluminium est remplacé par un sélecteur ouvert sur
              TOUTES les structures typées du catalogue (pergola, carport,
              bac lesté…). Le bouton d'hier reste le REPLI quand la société
              n'en a aucune : le sélecteur ne peut jamais naître vide. */}
          <StructureSelector
            id="gen-structure-produit"
            label="Type de Structure"
            produits={produits}
            value={structureProduitId}
            onChange={(v) => dispatchSizing({ type: 'SAISI', champ: 'structureProduit', valeur: v })}
            fallback={(
              <div className="grid gap-1.5">
                <Label>Type de Structure</Label>
                <Segmented
                  options={[
                    { value: 'acier', label: 'Acier galvanisé' },
                    { value: 'aluminium', label: 'Aluminium' },
                  ]}
                  value={structureType}
                  onChange={(v) => dispatchSizing({ type: 'SAISI', champ: 'structure', valeur: v })}
                />
              </div>
            )}
          />
        </div>
        {/* Règle fondateur du 18/08 — justifie la taille retenue par le
            dimensionnement facture → paliers : palier de 5 kWc, besoin lu
            sur la facture d'hiver, payback le plus court parmi les
            paliers testés (`sizingInfo.paliers`). */}
        {sizingInfo?.kwcOptimal > 0 && (() => {
          // PVMRQ — REPLI : une marque épinglée introuvable au stock ampute
          // CHAQUE palier (lignes placeholder à 0 MAD) ; leur payback serait
          // FABRIQUÉ, donc aucun n'est comparable et la taille retombe sur
          // le besoin lu sur la facture. On le DIT, jamais en silence — et
          // surtout on ne prétend pas avoir classé par retour sur
          // investissement.
          if (sizingInfo.repliMarqueManquante) {
            const mm = sizingInfo.marquesManquantes ?? []
            return (
              <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
                Taille retenue : palier de <strong>{sizingInfo.kwcOptimal} kWc</strong>
                {' '}— besoin lu sur la facture d'hiver ≈ {sizingInfo.besoinKwc} kWc.
                {' '}Le classement par retour sur investissement est <strong>suspendu</strong> :
                {' '}marque épinglée introuvable au stock
                {mm.length > 0 && (
                  <> ({mm.map(m => `${m.marque} (${roleLabel(m.role)})`).join(', ')})</>
                )}, les paliers chiffrés seraient incomplets.
                {' '}Ajoutez le produit ou changez la marque dans Paramètres → Gammes.
              </div>
            )
          }
          const retenu = sizingInfo.paliers?.find(p => p.kwc === sizingInfo.kwcOptimal)
          return (
            <div className="mt-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
              Taille retenue : palier de <strong>{sizingInfo.kwcOptimal} kWc</strong>
              {' '}— besoin lu sur la facture d'hiver ≈ {sizingInfo.besoinKwc} kWc,
              {' '}retour sur investissement le plus court parmi les paliers testés
              {Number.isFinite(retenu?.payback) && (
                <> (<strong>{retenu.payback} ans</strong>)</>
              )}.
            </div>
          )
        })()}
        {/* FOUNDER 26/08 — les DEUX valeurs de dimensionnement (L-2OPT),
            toujours dérivées d'un calcul réel (serveur horaire si
            disponible, sinon le même balayage local que ci-dessus —
            jamais un chiffre inventé, et jamais la paire mixée depuis
            deux sources différentes — voir deuxValeursDim/F3). Résidentiel
            uniquement : l'option batterie n'existe nulle part ailleurs
            (agricole = pompage, industriel/commercial ne la vendent
            jamais). Mono-option (`showSans`/`showAvec`, scénario déjà
            choisi) : seule la valeur réellement vendue sur CE devis
            s'affiche.
            F4 (revue adversariale 26/08) — le garde EXTÉRIEUR doit
            refléter EXACTEMENT ce que le contenu va rendre : l'ancien
            `(deuxValeursDim.sans || deuxValeursDim.avec)` pouvait être
            vrai (ex. `sans` calculable) alors que `showSans` est FAUX
            (scénario mono « Avec batterie ») ET `avec` encore `null` —
            un wrapper vide (marge + data-testid orphelins) s'affichait
            pour rien. Le garde reprend donc les DEUX conditions
            (source ET scénario) que le contenu vérifie déjà.
            F5 (revue adversariale 26/08) — « Recommandé » en tête : ce
            sont des RECOMMANDATIONS de l'optimiseur, pas une description
            des lignes composées — un nombre de panneaux TAPÉ À LA MAIN
            peut diverger du dimensionnement optimal affiché ici. */}
        {modeInstallation === 'residentiel'
          && ((showSans && deuxValeursDim.sans) || (showAvec && deuxValeursDim.avec)) && (
          <div className="mt-2 grid gap-0.5 text-sm text-foreground"
               data-testid="dimensionnement-deux-valeurs">
            {showSans && deuxValeursDim.sans && (
              <div>
                Recommandé sans batterie : <strong>{deuxValeursDim.sans.nbPanneaux} panneaux</strong>
                {' '}· {formatNumber(deuxValeursDim.sans.kwc, { decimals: 2 })} kWc
              </div>
            )}
            {showAvec && deuxValeursDim.avec && (
              <div>
                Recommandé avec batterie : <strong>{deuxValeursDim.avec.nbPanneaux} panneaux</strong>
                {' '}· {formatNumber(deuxValeursDim.avec.kwc, { decimals: 2 })} kWc
              </div>
            )}
          </div>
        )}
        {/* U3-900 — le moteur horaire serveur a décliné le dimensionnement
            (donnée nommée : ville, facture…) au lieu de deviner une
            taille : message FRANÇAIS EXACT, aucun panneau prérempli. */}
        {modeInstallation === 'residentiel' && sizingServeurMessage && (
          <div className="mt-2 text-xs text-warning" data-testid="sizing-serveur-refus">
            {sizingServeurMessage}
          </div>
        )}
        {/* AGNR44 / D-AGNR-2 (a) — plus de curseur : il ne changeait que
            l'aperçu local (ni enregistré, ni relu, ni imprimé). Le repli
            local prend la part diurne par défaut du marché et le DIT. */}
        {modeInstallation === 'residentiel' && (
          <div className="mt-2 text-xs text-muted-foreground" data-testid="part-diurne-defaut">
            Part de consommation diurne de l'aperçu : {dayUsage} % — hypothèse par défaut
            (non réglable, non imprimée sur le devis).
          </div>
        )}
        <div className="mt-3 flex flex-wrap items-center justify-end gap-3">
          {errors.recalcDim && <span className="text-xs text-destructive">{errors.recalcDim}</span>}
          {errors.autofill && <span className="text-xs text-destructive">{errors.autofill}</span>}
          {/* AGR128 — agricole : aucun devis plausible sans le besoin, la
              hauteur et le cas de pompe ; le message NOMME ce qui manque. */}
          {pompageManquants.length > 0 && (
            <span className="text-xs text-warning" data-testid="pompage-manquants">
              Auto-remplir indisponible — à renseigner : {pompageManquants.join(', ')}.
            </span>
          )}
          {errors.autofillKwc && <span className="text-xs text-warning">{errors.autofillKwc}</span>}
          {/* PVMRQ — même patron visuel que `errors.autofill` ci-dessus. */}
          {errors.marquesManquantes && <span className="text-xs text-destructive">{errors.marquesManquantes}</span>}
          {/* FOUNDER 26/08 — recalcule le dimensionnement (nombre de
              panneaux, sans ET avec batterie) depuis la facture ACTUELLE,
              puis recompose (même chemin qu'« Auto-remplir » ci-contre) :
              contrairement à ce dernier, qui recompose au nombre de
              panneaux COURANT sans jamais le redériver. Désactivé sans
              facture hiver exploitable, ou en agricole (dimensionnement
              pompage, aucune notion de facture → kWc). */}
          <Button type="button" variant="outline"
                  data-testid="btn-recalculer-dimensionnement"
                  loading={autoFillLoading}
                  disabled={modeInstallation === 'agricole' || (marcheCi
                    ? !(Number(apercuCi.donnees?.taille?.nb_panneaux) > 0)
                    : !(parseFloat(fHiver) > 0))}
                  onClick={recalculerDimensionnement}>
            <RefreshCw /> Recalculer le dimensionnement
          </Button>
          <Button type="button" className="bg-brass-400 text-nuit hover:bg-brass-500"
                  data-testid="btn-auto-remplir"
                  disabled={pompageManquants.length > 0}
                  loading={autoFillLoading} onClick={() => avecQuantitesFigees(handleAutoFill)}>
            <Zap /> Auto-remplir depuis le stock
          </Button>
        </div>
        {/* QJR577 (D-QJR5-9) — le dry-run serveur a échoué : AUCUNE
            composition de secours, l'erreur est dite et « Réessayer »
            rejoue le même dry-run. */}
        {compositionErreur && (
          <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
               data-testid="composition-erreur" role="alert">
            <span>{compositionErreur}</span>
            <Button type="button" size="sm" variant="outline"
                    data-testid="composition-reessayer"
                    loading={autoFillLoading}
                    onClick={() => avecQuantitesFigees(handleAutoFill)}>
              Réessayer
            </Button>
          </div>
        )}
        {/* QJR589 (contrat QJR505) — la dérive lead → devis, NOMMÉE et
            RÉSOLUBLE : « Reprendre les valeurs du lead » / « Garder les
            valeurs du devis ». Verdict serveur (`lead_valeurs_modifiees`)
            — l'écran ne compare rien. Après succès, l'écran relit le devis. */}
        <BandeauDeriveLead
          devisId={editDevis?.id}
          statut={editDevis?.statut}
          champs={leadValeursModifiees}
          onResolu={() => {
            setLeadValeursModifiees([])
            clear()
            setRechargeEdit(n => n + 1)
          }}
        />
        {onduleursIncomplets.length > 0 && (
          <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
            <strong>Onduleur(s) non chiffrable(s)</strong> — fiche technique
            incomplète, écartés de l'auto-remplissage (toujours
            sélectionnables à la main) :
            <ul className="mt-1 list-disc pl-5">
              {onduleursIncomplets.map(o => (
                <li key={o.id}>
                  {o.nom} — à renseigner : {o.manquantes.join(', ')}
                </li>
              ))}
            </ul>
            Complétez leur fiche technique dans Stock pour les rendre
            chiffrables.
          </div>
        )}
        {modeInstallation === 'agricole' && pompageAutoFilled && apercuPompage?.donnees && (
          <div className="mt-3 rounded-lg border border-success/30 bg-success/10 p-3 text-sm text-success"
               data-testid="pompage-auto-rempli">
            Auto-remplissage effectué (kit calculé par le serveur) —
            {' '}champ PV <strong>{apercuPompage.donnees.champ?.kwc ?? '—'} kWc</strong>
            {' '}({apercuPompage.donnees.champ?.nb_panneaux ?? '—'} panneaux).
          </div>
        )}
      </CardContent>
    </Card>
  )
}

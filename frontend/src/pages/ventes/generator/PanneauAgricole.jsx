// QJR101 — PANNEAU DE MARCHÉ : AGRICOLE (POMPAGE).
// ---------------------------------------------------------------------------
// Quatre panneaux sortent de `DevisGenerator.jsx` : chacun ne monte que les
// champs de SON marché. L'agricole ne montre AUCUNE facture électrique :
// il porte la pompe (CV, type, alimentation, HMT, débit, heures) et les
// données guidées de l'exploitation. Ni onduleur ni batterie n'existent ici.
//
// QJR241 — le panneau se retire lui-même hors de son marché via `CLE`
// (constante locale ; l'ex-module de stratégie `quote/marches/agricole.js`,
// devenu du code mort — aucun autre export que `cle` n'avait de consommateur
// de production — a été supprimé) — le même patron que `DevisOffresTailles`.
// `modeInstallation` ne vaut jamais qu'une des quatre clés (le reducer refuse
// toute autre valeur, `modeDepuisTypeInstallation`), donc exactement un
// panneau rend, à la place exacte qu'occupait la carte d'origine.
//
// AGR128 — les blocs suivent l'ordre des outils de référence : cas de pompe
// → besoin → point d'eau → hauteur (HMT) → équipement. Tous les champs
// démarrent VIDES (aucun défaut enregistré comme une saisie) ; la HMT
// calculée par le SERVEUR est affichée et surchargeable, la surcharge restant
// visible. Aucun calcul ici : l'aperçu vient de `useEtudePompagePreview`.
//
// AUCUNE LOGIQUE ICI : l'état et les gestes arrivent en props, tout le calcul
// reste dans l'écran porteur. Le balisage sort à l'octet — mêmes `id`, mêmes
// `placeholder`, mêmes classes, même ordre DOM. Chaque `<input type="number">`
// garde `step="any"` (règle fondateur : aucun champ ne snappe jamais) et le
// `noValidate` est resté sur le formulaire porteur.
import {
  Card, CardContent, Input, Label, Segmented,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import { Sprout } from 'lucide-react'
import { GenCardHeader } from './CarteMetrique'
import { formatNumber } from '../../../lib/format'

const fmtNum = (v) => (v !== null && v !== undefined) ? formatNumber(v) : 'N/A'

// AGR128 — un champ nombre des blocs nouveaux : `step="any"` (aucun champ ne
// snappe jamais), valeur tapée transmise telle quelle (jamais arrondie).
function ChampNombre({ id, label, valeur, onChange, placeholder }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="number" min="0" step="any"
             placeholder={placeholder} value={valeur ?? ''}
             onChange={e => onChange(e.target.value)} />
    </div>
  )
}

function ChampTexte({ id, label, valeur, onChange, type = 'text' }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type={type} value={valeur ?? ''}
             onChange={e => onChange(e.target.value)} />
    </div>
  )
}

function ChoixNatif({ id, label, valeur, onChange, options }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <select id={id} value={valeur ?? ''}
              onChange={e => onChange(e.target.value)}
              className="h-9 rounded-md border border-input bg-card px-2 text-sm">
        <option value="">Non renseigné</option>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  )
}

const MOIS = [['1', 'Janvier'], ['2', 'Février'], ['3', 'Mars'], ['4', 'Avril'],
  ['5', 'Mai'], ['6', 'Juin'], ['7', 'Juillet'], ['8', 'Août'],
  ['9', 'Septembre'], ['10', 'Octobre'], ['11', 'Novembre'], ['12', 'Décembre']]
// QJR241 — clé de marché de ce panneau (ex-`cle` de quote/marches/agricole.js,
// module supprimé faute de consommateur de production).
const CLE = 'agricole'

export default function PanneauAgricole({
  marche,
  // ── Pompe et forage ──
  pompeCv, setPompeCv, pompageSel, pompageDims, pompeType, setPompeType,
  pompeAlim, dispatchSizing, pompeHmt, setPompeHmt, pompeDebit, setPompeDebit,
  pompeHeures, setPompeHeures, pompeProfondeur, setPompeProfondeur,
  pompeDistance, setPompeDistance,
  // ── Votre exploitation (toutes optionnelles) ──
  farmSurfaceHa, setFarmSurfaceHa, farmCrop, setFarmCrop,
  farmRegion, setFarmRegion, farmIrrigation, setFarmIrrigation,
  farmFuel, setFarmFuel, farmFuelSpend, setFarmFuelSpend,
  farmFuelPeriod, setFarmFuelPeriod, farmFuelSpendAnnual,
  farmHmtStatic, setFarmHmtStatic, farmHmtDrawdown, setFarmHmtDrawdown,
  farmWaterDemand, pumpM3Day,
  // ── AGR128 — blocs nouveaux (cas de pompe, besoin, point d'eau, HMT) ──
  pompageSaisie, majPompage, apercuPompage,
}) {
  if (marche !== CLE) return null
  const sp = pompageSaisie || {}
  const plaque = sp.plaque || {}
  const besoin = sp.besoin || {}
  const source = sp.source || {}
  const hmt = sp.hmt || {}
  const conduite = hmt.conduite || {}
  const maj = (chemin) => (valeur) => majPompage?.(chemin, valeur)
  const existante = sp.mode_pompe === 'existante'
  const hmtServeur = apercuPompage?.donnees?.hmt || null
  return (
    <Card>
      <GenCardHeader icon={Sprout} title="Pompage solaire" />
      <CardContent className="pt-4">
        {/* ── (1) Cas de pompe : neuve ou existante (D-AGR-7) ── */}
        <div className="grid gap-1.5" data-testid="bloc-cas-pompe">
          <Label>Cas de pompe</Label>
          <Segmented
            options={[
              { value: 'neuve', label: 'Pompe neuve' },
              { value: 'existante', label: 'Pompe existante conservée' },
            ]}
            value={sp.mode_pompe || ''}
            onChange={maj('mode_pompe')}
          />
        </div>
        {existante ? (
          <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-5" data-testid="bloc-plaque">
            <ChampNombre id="gen-plaque-kw" label="Plaque : puissance (kW)"
                         valeur={plaque.kw} onChange={maj('plaque.kw')} />
            <div className="grid gap-1.5">
              <Label htmlFor="gen-pompecv">Plaque : puissance (CV)</Label>
              <Input id="gen-pompecv" type="number" min="0" step="any"
                     value={pompeCv} onChange={e => setPompeCv(e.target.value)} />
            </div>
            <ChampNombre id="gen-plaque-tension" label="Plaque : tension (V)"
                         valeur={plaque.tension_v} onChange={maj('plaque.tension_v')} />
            <ChoixNatif id="gen-plaque-phases" label="Plaque : phases"
                        valeur={plaque.phases} onChange={maj('plaque.phases')}
                        options={[['mono', 'Monophasé'], ['tri', 'Triphasé']]} />
            <ChampNombre id="gen-plaque-courant" label="Plaque : courant (A)"
                         valeur={plaque.courant_a} onChange={maj('plaque.courant_a')} />
          </div>
        ) : (pompeCv !== '' && pompeCv != null && (
          <p className="mt-2 text-xs text-muted-foreground" data-testid="pompe-actuelle-info">
            Pompe actuelle du client : {pompeCv} CV (information — une pompe neuve
            est dimensionnée par le serveur).
          </p>
        ))}
        {pompageDims && (
          <p className="mt-2 text-xs text-muted-foreground">
            ≈ {pompageSel?.kw ?? pompageDims.kw} kW · champ PV conseillé {pompageDims.champKw} kWc
            ({pompageDims.nbPanneaux} panneaux 710 W)
          </p>
        )}
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label>Type de pompe</Label>
            <Segmented
              options={[
                { value: 'immergee', label: 'Immergée' },
                { value: 'surface', label: 'Surface' },
              ]}
              value={pompeType}
              onChange={setPompeType}
            />
          </div>
          <div className="grid gap-1.5">
            <Label>Alimentation</Label>
            <Segmented
              options={[
                { value: 'mono', label: 'Mono 220V' },
                { value: 'tri', label: 'Tri 380V' },
              ]}
              value={pompeAlim}
              onChange={(v) => dispatchSizing({ type: 'SAISI', champ: 'pompeAlim', valeur: v })}
            />
          </div>
        </div>
        {/* ── (2) Besoin en eau : déclaré d'abord (D-AGR-3) ── */}
        <div className="mt-4 grid gap-1.5" data-testid="bloc-besoin">
          <Label>Besoin en eau</Label>
          <Segmented
            options={[
              { value: 'volume_declare', label: 'Volume déclaré' },
              { value: 'pompe_actuelle', label: 'Pompe actuelle' },
              { value: 'agronomique', label: 'Cultures' },
            ]}
            value={besoin.mode || ''}
            onChange={maj('besoin.mode')}
          />
        </div>
        {besoin.mode === 'volume_declare' && (
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <ChampNombre id="gen-besoin-volume" label="Volume par jour (m³/jour)"
                         valeur={besoin.volume_m3_jour} onChange={maj('besoin.volume_m3_jour')} />
            <ChoixNatif id="gen-besoin-mois-pointe" label="Mois de pointe"
                        valeur={besoin.mois_pointe} onChange={maj('besoin.mois_pointe')}
                        options={MOIS} />
          </div>
        )}
        {besoin.mode === 'pompe_actuelle' && (
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <ChampNombre id="gen-besoin-debit-actuel"
                         label="Débit de la pompe actuelle (m³/h) — déclaré par le client"
                         valeur={besoin.debit_actuel_m3h} onChange={maj('besoin.debit_actuel_m3h')} />
            <ChampNombre id="gen-besoin-heures-actuelles"
                         label="Heures de pompage actuelles / jour — déclaré par le client"
                         valeur={besoin.heures_actuelles_jour}
                         onChange={maj('besoin.heures_actuelles_jour')} />
          </div>
        )}

        {/* ── (3) Point d'eau ── */}
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="bloc-point-eau">
          <ChampNombre id="gen-source-debit" label="Débit d'exploitation du forage (m³/h)"
                       valeur={source.debit_exploitation_m3h}
                       onChange={maj('source.debit_exploitation_m3h')} />
          <ChoixNatif id="gen-source-debit-origine" label="Origine du débit"
                      valeur={source.debit_exploitation_origine}
                      onChange={maj('source.debit_exploitation_origine')}
                      options={[['essai', 'Essai de pompage'], ['foreur', 'Donné par le foreur'],
                        ['client', 'Estimation du client'], ['mesure_visite', 'Mesuré en visite']]} />
          <ChampTexte id="gen-source-debit-date" label="Date du débit" type="date"
                      valeur={source.debit_exploitation_date}
                      onChange={maj('source.debit_exploitation_date')} />
          <ChampNombre id="gen-source-debit-autorise" label="Débit autorisé ABH (m³/h)"
                       valeur={source.debit_autorise_m3h} onChange={maj('source.debit_autorise_m3h')} />
          <ChampNombre id="gen-source-volume-autorise" label="Volume annuel autorisé ABH (m³)"
                       valeur={source.volume_annuel_autorise_m3}
                       onChange={maj('source.volume_annuel_autorise_m3')} />
          <ChoixNatif id="gen-source-compteur" label="Compteur d'eau"
                      valeur={source.compteur} onChange={maj('source.compteur')}
                      options={[['oui', 'Oui'], ['non', 'Non']]} />
          <ChampNombre id="gen-source-niveau-dynamique" label="Niveau dynamique (m)"
                       valeur={source.niveau_dynamique_m} onChange={maj('source.niveau_dynamique_m')} />
          <ChampNombre id="gen-source-tubage" label="Diamètre de tubage (mm)"
                       valeur={source.diametre_tubage_mm} onChange={maj('source.diametre_tubage_mm')} />
          <ChampNombre id="gen-source-calage" label="Profondeur de calage (m)"
                       valeur={source.profondeur_calage_m} onChange={maj('source.profondeur_calage_m')} />
          <ChampNombre id="gen-source-reservoir" label="Réservoir (m³)"
                       valeur={source.volume_reservoir_m3} onChange={maj('source.volume_reservoir_m3')} />
        </div>

        {/* ── (4) Hauteur manométrique ── */}
        <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="grid gap-1.5">
            <Label htmlFor="gen-hmt">
              HMT saisie (m){hmtServeur?.source === 'calculee' && pompeHmt !== '' ? ' — surcharge' : ''}
            </Label>
            <Input id="gen-hmt" type="number" min="0" step="any"
                   placeholder="ex: 120" value={pompeHmt}
                   onChange={e => setPompeHmt(e.target.value)} />
            {hmtServeur?.valeur_m != null && (
              <p className="text-xs text-muted-foreground" data-testid="hmt-serveur">
                HMT retenue par le serveur : {fmtNum(hmtServeur.valeur_m)} m
                ({hmtServeur.source === 'saisie' ? 'saisie' : 'calculée'})
              </p>
            )}
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="gen-debit">Débit souhaité (m³/h)</Label>
            <Input id="gen-debit" type="number" min="0" step="any"
                   placeholder="ex: 30" value={pompeDebit}
                   onChange={e => setPompeDebit(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="gen-heures">Heures de pompage effectives / jour</Label>
            <Input id="gen-heures" type="number" min="0" step="any"
                   value={pompeHeures}
                   onChange={e => setPompeHeures(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="gen-profondeur">Profondeur forage (m) — optionnel</Label>
            <Input id="gen-profondeur" type="number" min="0" step="any"
                   value={pompeProfondeur}
                   onChange={e => setPompeProfondeur(e.target.value)} />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="gen-distance">Distance champ → coffret (m)</Label>
            <Input id="gen-distance" type="number" min="0" step="any"
                   value={pompeDistance}
                   onChange={e => setPompeDistance(e.target.value)} />
          </div>
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm">
          <input type="checkbox" data-testid="hmt-detail"
                 checked={Boolean(hmt.detail)}
                 onChange={e => majPompage?.('hmt.detail', e.target.checked)} />
          Détailler la HMT (dénivelé, conduite, pression)
        </label>
        {hmt.detail && (
          <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="bloc-hmt-detail">
            <ChampNombre id="gen-hmt-denivele" label="Dénivelé (m)"
                         valeur={hmt.denivele_m} onChange={maj('hmt.denivele_m')} />
            <ChoixNatif id="gen-hmt-materiau" label="Conduite : matériau"
                        valeur={conduite.materiau} onChange={maj('hmt.conduite.materiau')}
                        options={[['pehd', 'PEHD'], ['pvc', 'PVC'], ['acier', 'Acier'], ['autre', 'Autre']]} />
            <ChampNombre id="gen-hmt-diametre" label="Conduite : diamètre intérieur (mm)"
                         valeur={conduite.diametre_interieur_mm}
                         onChange={maj('hmt.conduite.diametre_interieur_mm')} />
            <ChampNombre id="gen-hmt-longueur" label="Conduite : longueur (m)"
                         valeur={conduite.longueur_m} onChange={maj('hmt.conduite.longueur_m')} />
            {conduite.materiau && !['pehd', 'pvc'].includes(conduite.materiau) && (
              <ChampNombre id="gen-hmt-c" label="Coefficient C de Hazen-Williams"
                           valeur={conduite.c_hazen_williams}
                           onChange={maj('hmt.conduite.c_hazen_williams')} />
            )}
            <ChampNombre id="gen-hmt-singulieres" label="Pertes singulières (m)"
                         valeur={hmt.pertes_singulieres_m} onChange={maj('hmt.pertes_singulieres_m')} />
            <ChampNombre id="gen-hmt-pression" label="Pression de service (bar)"
                         valeur={hmt.pression_service_bar} onChange={maj('hmt.pression_service_bar')} />
          </div>
        )}

        {/* ── Votre exploitation (données GUIDÉES, toutes optionnelles) ── */}
        {/* Encouragées : le besoin en eau FAO-56 qu'elles permettent d'estimer
            alimente bien le dimensionnement pompage du PDF (cartes HMT /
            Débit / Eau-par-jour du one-page). QJR428 (02/09/2026) — la
            donnée carburant (current_fuel / fuel_spend_current) reste
            conservée pour l'étude, mais aucune promesse de chiffre dans le
            PDF : le renderer agricole premium qui publiait un comparatif
            solaire-vs-carburant a été supprimé par QJR236, et le one-page
            qui sert aujourd'hui ce marché ne le lit pas (preuve exécutée :
            apps/ventes/tests/test_qjr428_promesse_carburant_agricole.py).
            Aucune donnée n'est obligatoire — chacune a un défaut. */}
        <div className="mt-4 rounded-lg border border-success/30 bg-success/5 p-3 sm:p-4">
          <div className="flex flex-wrap items-center gap-2">
            <Sprout className="size-4 text-success" aria-hidden="true" />
            <span className="font-display text-sm font-semibold tracking-tight">
              Votre exploitation
            </span>
            <span className="text-xs text-muted-foreground">
              recommandé — affine le devis avec les données réelles du fermier
            </span>
          </div>
          <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-surface">
                Surface irriguée (ha)
              </Label>
              <Input id="gen-farm-surface" type="number" min="0" step="any"
                     placeholder="ex: 5" value={farmSurfaceHa}
                     onChange={e => setFarmSurfaceHa(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-crop">Culture</Label>
              <Select value={farmCrop} onValueChange={setFarmCrop}>
                <SelectTrigger id="gen-farm-crop"><SelectValue placeholder="Non renseignée" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="agrumes">Agrumes</SelectItem>
                  <SelectItem value="maraichage">Maraîchage</SelectItem>
                  <SelectItem value="olivier">Olivier</SelectItem>
                  <SelectItem value="dattier">Dattier (palmier)</SelectItem>
                  <SelectItem value="cereales">Céréales</SelectItem>
                  <SelectItem value="luzerne">Luzerne / fourrage</SelectItem>
                  <SelectItem value="arganier">Arganier</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-region">Région</Label>
              <Select value={farmRegion} onValueChange={setFarmRegion}>
                <SelectTrigger id="gen-farm-region"><SelectValue placeholder="Non renseignée" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="souss-massa">Souss-Massa (Agadir)</SelectItem>
                  <SelectItem value="doukkala">Doukkala (El Jadida)</SelectItem>
                  <SelectItem value="tadla">Tadla (Béni Mellal)</SelectItem>
                  <SelectItem value="saiss">Saïss (Fès-Meknès)</SelectItem>
                  <SelectItem value="oriental">Oriental (Berkane)</SelectItem>
                  <SelectItem value="draa-tafilalet">Drâa-Tafilalet</SelectItem>
                  <SelectItem value="gharb-loukkos">Gharb-Loukkos</SelectItem>
                  <SelectItem value="haouz">Haouz (Marrakech)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-irrigation">Mode d'irrigation</Label>
              <Select value={farmIrrigation} onValueChange={setFarmIrrigation}>
                <SelectTrigger id="gen-farm-irrigation"><SelectValue placeholder="Non renseigné" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="goutte">Goutte-à-goutte</SelectItem>
                  <SelectItem value="aspersion">Aspersion</SelectItem>
                  <SelectItem value="gravitaire">Gravitaire</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-fuel">Énergie actuelle</Label>
              <Select value={farmFuel} onValueChange={setFarmFuel}>
                <SelectTrigger id="gen-farm-fuel"><SelectValue placeholder="Non renseignée" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="butane">Butane (gaz)</SelectItem>
                  <SelectItem value="diesel">Diesel (gasoil)</SelectItem>
                  <SelectItem value="none">Aucune / nouveau forage</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-fuelspend">
                Dépense carburant actuelle (MAD) — optionnel
              </Label>
              <div className="flex gap-2">
                <Input id="gen-farm-fuelspend" type="number" min="0" step="any"
                       className="flex-1"
                       placeholder="ex: 2000" value={farmFuelSpend}
                       onChange={e => setFarmFuelSpend(e.target.value)} />
                <Select value={farmFuelPeriod} onValueChange={setFarmFuelPeriod}>
                  <SelectTrigger id="gen-farm-fuelperiod" className="w-28">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="mois">/ mois</SelectItem>
                    <SelectItem value="an">/ an</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {farmFuelSpendAnnual !== '' && farmFuelPeriod === 'mois' && (
                <p className="text-xs text-muted-foreground">
                  ≈ {fmtNum(farmFuelSpendAnnual)} MAD / an
                </p>
              )}
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-static">
                Niveau statique de l'eau (m) — optionnel
              </Label>
              <Input id="gen-farm-static" type="number" min="0" step="any"
                     placeholder="ex: 40" value={farmHmtStatic}
                     onChange={e => setFarmHmtStatic(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-drawdown">
                Rabattement en pompage (m) — optionnel
              </Label>
              <Input id="gen-farm-drawdown" type="number" min="0" step="any"
                     placeholder="ex: 15" value={farmHmtDrawdown}
                     onChange={e => setFarmHmtDrawdown(e.target.value)} />
            </div>
          </div>

          {/* Readout FAO-56 : besoin estimé vs débit livré par la pompe.
              Purement informatif (le backend recalcule le besoin lui-même). */}
          {farmWaterDemand && (
            pumpM3Day != null ? (
              <div className={`mt-3 rounded-lg border p-3 text-sm ${
                pumpM3Day >= farmWaterDemand.m3DayPeak
                  ? 'border-success/30 bg-success/10 text-success'
                  : 'border-warning/40 bg-warning/10 text-warning'
              }`}>
                Besoin estimé ≈ <strong>{fmtNum(farmWaterDemand.m3DayPeak)} m³/jour</strong>
                {' '}(pointe estivale) — votre pompe livre{' '}
                <strong>{fmtNum(pumpM3Day)} m³/jour</strong>{' '}
                {pumpM3Day >= farmWaterDemand.m3DayPeak ? '✓' : '⚠ insuffisant'}
              </div>
            ) : (
              <div className="mt-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
                Besoin estimé ≈ <strong>{fmtNum(farmWaterDemand.m3DayPeak)} m³/jour</strong>
                {' '}(pointe estivale). Renseignez HMT + débit souhaité pour comparer
                au débit livré par la pompe.
              </div>
            )
          )}
        </div>

        {/* ── Résultat du dimensionnement (source des chiffres du PDF) ── */}
        {pompageSel?.mode === 'courbe' && (
          <div className="mt-3 rounded-lg border border-info/30 bg-info/10 p-3 text-sm text-info">
            <strong>Pompe sélectionnée : {pompageSel.pump.nom}</strong>
            <div className="mt-1">
              {pompageSel.cv} CV ({pompageSel.kw} kW) · débit à {pompeHmt} m
              de HMT : <strong>{pompageSel.debitHmt} m³/h</strong>
              {pompageSel.m3Jour != null && (
                <> · <strong>≈ {pompageSel.m3Jour} m³/jour</strong> sur {pompeHeures} h
                de pompage effectif</>
              )}
            </div>
          </div>
        )}
        {pompageSel?.sansPrix?.length > 0 && (
          <div className="mt-3 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
            Seules des pompes <strong>sans prix renseigné</strong> conviennent à cette
            HMT et ce débit ({pompageSel.sansPrix.join(', ')}). Renseignez leur prix
            dans Stock pour les chiffrer — aucune pompe ne sera ajoutée au devis.
          </div>
        )}
      </CardContent>
    </Card>
  )
}

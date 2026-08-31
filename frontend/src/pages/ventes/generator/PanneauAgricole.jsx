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
}) {
  if (marche !== CLE) return null
  return (
    <Card>
      <GenCardHeader icon={Sprout} title="Pompage solaire" />
      <CardContent className="pt-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="grid gap-1.5">
            <Label htmlFor="gen-pompecv">
              Puissance pompe (CV){pompageSel?.mode === 'courbe' && ' — auto (courbe)'}
            </Label>
            <Input id="gen-pompecv" type="number" min="0" step="any"
                   value={pompeCv} onChange={e => setPompeCv(e.target.value)} />
            {pompageDims && (
              <p className="text-xs text-muted-foreground">
                ≈ {pompageSel?.kw ?? pompageDims.kw} kW · champ PV conseillé {pompageDims.champKw} kWc
                ({pompageDims.nbPanneaux} panneaux 710 W)
              </p>
            )}
          </div>
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
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="grid gap-1.5">
            <Label htmlFor="gen-hmt">HMT (m)</Label>
            <Input id="gen-hmt" type="number" min="0" step="any"
                   placeholder="ex: 120" value={pompeHmt}
                   onChange={e => setPompeHmt(e.target.value)} />
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
            <Label htmlFor="gen-distance">Distance panneaux → coffret (m)</Label>
            <Input id="gen-distance" type="number" min="0" step="any"
                   value={pompeDistance}
                   onChange={e => setPompeDistance(e.target.value)} />
          </div>
        </div>

        {/* ── Votre exploitation (données GUIDÉES, toutes optionnelles) ── */}
        {/* Encouragées : elles permettent au PDF de dimensionner et chiffrer
            sur les données réelles du fermier (besoin en eau FAO-56, économies
            vs carburant). Aucune n'est obligatoire — chacune a un défaut. */}
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
                <SelectTrigger id="gen-farm-crop"><SelectValue /></SelectTrigger>
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
                <SelectTrigger id="gen-farm-region"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="souss-massa">Souss-Massa (Agadir)</SelectItem>
                  <SelectItem value="doukkala">Doukkala (El Jadida)</SelectItem>
                  <SelectItem value="tadla">Tadla (Béni Mellal)</SelectItem>
                  <SelectItem value="saiss">Saïss (Fès-Meknès)</SelectItem>
                  <SelectItem value="oriental">Oriental (Berkane)</SelectItem>
                  <SelectItem value="draa-tafilalet">Drâa-Tafilalet</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-farm-irrigation">Mode d'irrigation</Label>
              <Select value={farmIrrigation} onValueChange={setFarmIrrigation}>
                <SelectTrigger id="gen-farm-irrigation"><SelectValue /></SelectTrigger>
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
                <SelectTrigger id="gen-farm-fuel"><SelectValue /></SelectTrigger>
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

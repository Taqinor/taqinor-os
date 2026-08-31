// QJR101 — PANNEAU DE MARCHÉ : INDUSTRIEL.
// ---------------------------------------------------------------------------
// Quatre panneaux sortent de `DevisGenerator.jsx` : chacun ne monte que les
// champs de SON marché. L'industriel porte en propre la consommation
// mensuelle, l'injection du surplus (82-21) et le raccordement BT/MT ; il
// n'a ni catégorie commerciale ni pompage.
//
// QJR241 — le panneau se retire lui-même hors de son marché via `CLE`
// (constante locale ; l'ex-module de stratégie `quote/marches/industriel.js`,
// devenu du code mort — aucun autre export que `cle` n'avait de consommateur
// de production — a été supprimé) — le même patron que `DevisOffresTailles`.
// `modeInstallation` ne vaut jamais qu'une des quatre clés (le reducer refuse
// toute autre valeur, `modeDepuisTypeInstallation`), donc exactement un
// panneau rend, à la place exacte qu'occupait la carte d'origine.
//
// QJR244 — la carte « Factures Électriques » (factures hiver/été + grille des
// 12 mois + bloc facture réelle du client) est désormais PARTAGÉE
// (`CarteFacturesElectriques`, commune aux trois panneaux de marché réseau) :
// ce panneau lui passe son contenu propre (conso/injection/raccordement/MT)
// en `children`, rendu à L'INTÉRIEUR de la MÊME `CardContent` — le Fragment
// ne produit aucun nœud DOM, le rendu reste inchangé à l'octet.
//
// AUCUNE LOGIQUE ICI : l'état et les gestes arrivent en props, tout le calcul
// reste dans l'écran porteur. Le balisage sort à l'octet — mêmes `id`, mêmes
// `placeholder`, mêmes classes, même ordre DOM. Chaque `<input type="number">`
// garde `step="any"` (règle fondateur : aucun champ ne snappe jamais) et le
// `noValidate` est resté sur le formulaire porteur.
import { Input, Label, Segmented } from '../../../ui'
import { TARIF_MT_ONEE, tarifMtDisponible } from '../../../features/ventes/solar'
import { formatNumber } from '../../../lib/format'
import CarteFacturesElectriques from './CarteFacturesElectriques'

// QJR241 — clé de marché de ce panneau (ex-`cle` de quote/marches/
// industriel.js, module supprimé faute de consommateur de production).
const CLE = 'industriel'

export default function PanneauIndustriel({
  marche,
  // ── Factures mensuelles ──
  fHiver, setFHiver, fEte, setFEte, syncBillEstimator,
  onHiverPaste, onEtePaste, handleEstimerMois, errors, monthly, setMonth,
  // ── Facture réelle du client (QF4) ──
  distributeur, setDistributeur, realBillMode, setRealBillMode,
  realBillMad, setRealBillMad, realBillKwh, setRealBillKwh,
  onRealBillPaste, consoAnnuelleReelle,
  // ── Étude d'autoconsommation + raccordement (QX50 / QXMT) ──
  consoMensuelle, setConsoMensuelle, injectionEnabled, setInjectionEnabled,
  tensionRaccordement, dispatchSizing, estMt, repartitionMt, setPartMt,
  tarifMtApplique,
}) {
  if (marche !== CLE) return null
  return (
    <CarteFacturesElectriques
      fHiver={fHiver} setFHiver={setFHiver} fEte={fEte} setFEte={setFEte}
      syncBillEstimator={syncBillEstimator}
      onHiverPaste={onHiverPaste} onEtePaste={onEtePaste}
      handleEstimerMois={handleEstimerMois} errors={errors}
      monthly={monthly} setMonth={setMonth}
      distributeur={distributeur} setDistributeur={setDistributeur}
      realBillMode={realBillMode} setRealBillMode={setRealBillMode}
      realBillMad={realBillMad} setRealBillMad={setRealBillMad}
      realBillKwh={realBillKwh} setRealBillKwh={setRealBillKwh}
      onRealBillPaste={onRealBillPaste} consoAnnuelleReelle={consoAnnuelleReelle}
    >
      <div className="mt-3.5 grid gap-4 sm:grid-cols-2">
        <div className="grid gap-1.5">
          <Label htmlFor="gen-conso">Consommation mensuelle (kWh) — pour l'étude</Label>
          <Input id="gen-conso" type="number" min="0" step="any"
                 placeholder="ex: 12000" value={consoMensuelle}
                 onChange={e => setConsoMensuelle(e.target.value)} />
        </div>
        {/* QX50 — injection du surplus (loi 82-21), OFF par défaut */}
        <div className="grid gap-1.5">
          <Label>Injection du surplus (loi 82-21)</Label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={injectionEnabled}
                   onChange={e => setInjectionEnabled(e.target.checked)} />
            Valoriser le surplus injecté (plafond 20 %, tarif ANRE net)
          </label>
          <p className="text-xs text-muted-foreground">
            Tarif ANRE 03/2026-02/2027, plafond en révision.
          </p>
        </div>
        {/* QXMT — tension de raccordement : un site MT n'est pas
            facturé au barème BT. 'bt' par défaut → étude inchangée. */}
        <div className="grid gap-1.5">
          <Label>Raccordement du site</Label>
          <Segmented
            data-testid="gen-tension"
            options={[
              { value: 'bt', label: 'Basse tension (BT)' },
              { value: 'mt', label: 'Moyenne tension (MT)' },
            ]}
            value={tensionRaccordement}
            onChange={(v) => dispatchSizing({ type: 'SAISI', champ: 'tension', valeur: v })}
          />
          <p className="text-xs text-muted-foreground">
            Au-delà de ~50 kW le site est en général raccordé en MT :
            l'étude bascule alors sur le barème horaire ONEE MT.
          </p>
        </div>
      </div>

      {/* QXMT — répartition horaire du site MT. Aucune valeur par défaut :
          les plages horaires MT officielles ne sont pas publiées, donc
          aucune répartition n'est inventée. Sans saisie, l'étude OMET
          les économies plutôt que d'afficher un chiffre douteux. */}
      {estMt && (
        <div className="mt-3.5" data-testid="gen-mt-block">
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              ['pointe', 'Heures de pointe (%)', TARIF_MT_ONEE.POINTE],
              ['pleines', 'Heures pleines (%)', TARIF_MT_ONEE.PLEINES],
              ['creuses', 'Heures creuses (%)', TARIF_MT_ONEE.CREUSES],
            ].map(([key, label, prix]) => (
              <div className="grid gap-1.5" key={key}>
                <Label htmlFor={`gen-mt-${key}`}>{label}</Label>
                <Input id={`gen-mt-${key}`} type="number" min="0" step="any"
                       data-testid={`gen-mt-${key}`}
                       placeholder="ex: 20"
                       value={repartitionMt[key]}
                       onChange={e => setPartMt(key, e.target.value)} />
                <p className="text-xs text-muted-foreground">
                  {prix != null
                    ? `${formatNumber(prix, { decimals: 4 })} DH/kWh`
                    : 'tarif à fournir par le fondateur'}
                </p>
              </div>
            ))}
          </div>
          {tarifMtApplique != null ? (
            <p className="mt-2 text-xs text-muted-foreground" data-testid="gen-mt-tarif">
              Tarif MT moyen retenu ≈{' '}
              <strong>{formatNumber(tarifMtApplique, { decimals: 4 })} DH/kWh</strong>
              {' · '}{TARIF_MT_ONEE.MENTION}
            </p>
          ) : (
            <p className="mt-2 text-xs text-warning" data-testid="gen-mt-manquant">
              {tarifMtDisponible()
                ? 'Répartition horaire non renseignée : les économies et le '
                  + 'payback sont volontairement omis de l\'étude (les plages '
                  + 'horaires MT officielles ne sont pas publiées — aucun '
                  + 'chiffre n\'est supposé à votre place).'
                : 'Barème MT ONEE indisponible en source officielle : les '
                  + 'économies et le payback sont omis de l\'étude.'}
            </p>
          )}
        </div>
      )}
    </CarteFacturesElectriques>
  )
}

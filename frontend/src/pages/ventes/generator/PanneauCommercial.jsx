// QJR101 — PANNEAU DE MARCHÉ : COMMERCIAL.
// ---------------------------------------------------------------------------
// Quatre panneaux sortent de `DevisGenerator.jsx` : chacun ne monte que les
// champs de SON marché. Le commercial ajoute au socle industriel la
// CATÉGORIE (hôtel, bureau…) et ses questions par archétype, qui pilotent le
// taux de charge diurne de son étude ; il n'a pas de pompage.
//
// QJR241 — le panneau se retire lui-même hors de son marché via `CLE`
// (constante locale ; l'ex-module de stratégie `quote/marches/commercial.js`,
// devenu du code mort — aucun autre export que `cle` n'avait de consommateur
// de production — a été supprimé) — le même patron que `DevisOffresTailles`.
// `modeInstallation` ne vaut jamais qu'une des quatre clés (le reducer refuse
// toute autre valeur, `modeDepuisTypeInstallation`), donc exactement un
// panneau rend, à la place exacte qu'occupait la carte d'origine.
//
// QJR244 — la carte « Factures Électriques » (factures hiver/été + grille des
// 12 mois + bloc facture réelle du client) est désormais PARTAGÉE
// (`CarteFacturesElectriques`, commune aux trois panneaux de marché réseau) :
// ce panneau lui passe son contenu propre (conso/injection/raccordement/MT +
// catégorie commerciale) en `children`, rendu à L'INTÉRIEUR de la MÊME
// `CardContent` — le rendu reste inchangé à l'octet.
//
// AUCUNE LOGIQUE ICI : l'état et les gestes arrivent en props, tout le calcul
// reste dans l'écran porteur. Le balisage sort à l'octet — mêmes `id`, mêmes
// `placeholder`, mêmes classes, même ordre DOM. Chaque `<input type="number">`
// garde `step="any"` (règle fondateur : aucun champ ne snappe jamais) et le
// `noValidate` est resté sur le formulaire porteur.
import {
  Input, Label,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../../ui'
import {
  COMMERCIAL_CATEGORIES, COMMERCIAL_CATEGORY_QUESTIONS, commercialDayShare,
} from '../../../features/ventes/solar'
import CarteFacturesElectriques from './CarteFacturesElectriques'
// QJR637 — conso / injection / raccordement BT-MT / bloc MT : module partagé.
import BlocEtudeReseau from './BlocEtudeReseau'
// CIQ125 — le résultat du moteur serveur C&I, affiché tel quel.
import CarteResultatCi from './CarteResultatCi'

// QJR241 — clé de marché de ce panneau (ex-`cle` de quote/marches/
// commercial.js, module supprimé faute de consommateur de production).
const CLE = 'commercial'

// QJR575 — catégorie « Non précisée » : la valeur par défaut de l'écran (Radix
// refuse value=''), part diurne 80 % — la MÊME que le « Devis automatique »,
// qui ne connaît aucune catégorie — et persistée `null` (jamais « hôtel » par
// défaut : rouvrir puis enregistrer réécrivait taux / économies / payback).
export const CATEGORIE_NON_PRECISEE = 'non_precisee'

export default function PanneauCommercial({
  marche,
  // ── Factures mensuelles ──
  fHiver, setFHiver, fEte, setFEte, syncBillEstimator,
  onHiverPaste, onEtePaste, handleEstimerMois, errors, monthly, setMonth,
  // ── Facture réelle du client (QF4) ──
  distributeur, setDistributeur, realBillMode, setRealBillMode,
  realBillMad, setRealBillMad, realBillKwh, setRealBillKwh,
  onRealBillPaste, consoAnnuelleReelle,
  // ── CIQ125 — profil déclaré C&I + résultat du moteur serveur ──
  profilCi, setChampCi, apercuCi, repartitionMt, setPartMt, tarifMtApplique,
  // ── Catégorie commerciale et ses questions (QX44) ──
  categorieCommerciale, setCategorieCommerciale,
  commercialAnswers, setCommercialAnswer,
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
      marcheCi
    >
      <BlocEtudeReseau
        profil={profilCi} setChamp={setChampCi}
        resolues={apercuCi?.donnees?.entrees_resolues || null}
        erreurConso={errors?.conso}
        repartitionMt={repartitionMt} setPartMt={setPartMt}
        tarifMtApplique={tarifMtApplique}
      />
      <CarteResultatCi {...(apercuCi || {})} />

      {/* QX44 — étude commerciale par catégorie */}
      <div className="mt-3.5">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-1.5">
            <Label>Catégorie commerciale</Label>
            <Select value={categorieCommerciale} onValueChange={setCategorieCommerciale}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={CATEGORIE_NON_PRECISEE}>Non précisée</SelectItem>
                {COMMERCIAL_CATEGORIES.map(c => (
                  <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Profil de charge diurne ≈ {commercialDayShare(categorieCommerciale)} %
              (ajuste l'autoconsommation de l'étude).
            </p>
          </div>
        </div>
        {(COMMERCIAL_CATEGORY_QUESTIONS[categorieCommerciale] || []).length > 0 && (
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {(COMMERCIAL_CATEGORY_QUESTIONS[categorieCommerciale] || []).map(q => (
              <div className="grid gap-1.5" key={q.key}>
                <Label htmlFor={`gen-com-${q.key}`}>{q.label}</Label>
                {q.type === 'number' && (
                  <Input id={`gen-com-${q.key}`} type="number" min="0" step="any"
                         value={commercialAnswers[q.key] ?? ''}
                         onChange={e => setCommercialAnswer(q.key, e.target.value)} />
                )}
                {q.type === 'select' && (
                  <Select value={commercialAnswers[q.key] ?? ''}
                          onValueChange={v => setCommercialAnswer(q.key, v)}>
                    <SelectTrigger id={`gen-com-${q.key}`}><SelectValue placeholder="—" /></SelectTrigger>
                    <SelectContent>
                      {q.options.map(o => (
                        <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
                {q.type === 'bool' && (
                  <label className="flex items-center gap-2 text-sm cursor-pointer">
                    <input id={`gen-com-${q.key}`} type="checkbox"
                           checked={!!commercialAnswers[q.key]}
                           onChange={e => setCommercialAnswer(q.key, e.target.checked)} />
                    Oui
                  </label>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </CarteFacturesElectriques>
  )
}

// QJR101 — PANNEAU DE MARCHÉ : RÉSIDENTIEL.
// ---------------------------------------------------------------------------
// Quatre panneaux sortent de `DevisGenerator.jsx` : chacun ne monte que les
// champs de SON marché. Le résidentiel ne connaît ni la consommation
// industrielle, ni le raccordement MT, ni la catégorie commerciale, ni le
// pompage : ces champs ont quitté son arbre, il n'y a plus rien à y masquer.
//
// QJR241 — le panneau se retire lui-même hors de son marché via `CLE`
// (constante locale ; l'ex-module de stratégie `quote/marches/residentiel.js`,
// devenu du code mort — aucun autre export que `cle` n'avait de consommateur
// de production — a été supprimé) — le même patron que `DevisOffresTailles`.
// `modeInstallation` ne vaut jamais qu'une des quatre clés (le reducer refuse
// toute autre valeur, `modeDepuisTypeInstallation`), donc exactement un
// panneau rend, à la place exacte qu'occupait la carte d'origine.
//
// QJR244 — la carte « Factures Électriques » (factures hiver/été + grille des
// 12 mois + bloc facture réelle du client) est désormais PARTAGÉE
// (`CarteFacturesElectriques`, commune aux trois panneaux de marché réseau) :
// le résidentiel n'a AUCUN contenu à ajouter après elle (pas de `children`),
// contrairement à Industriel/Commercial. Rendu inchangé à l'octet.
//
// AUCUNE LOGIQUE ICI : l'état et les gestes arrivent en props, tout le calcul
// reste dans l'écran porteur. Le balisage sort à l'octet — mêmes `id`, mêmes
// `placeholder`, mêmes classes, même ordre DOM. Chaque `<input type="number">`
// garde `step="any"` (règle fondateur : aucun champ ne snappe jamais) et le
// `noValidate` est resté sur le formulaire porteur.
import CarteFacturesElectriques from './CarteFacturesElectriques'

// QJR241 — clé de marché de ce panneau (ex-`cle` de quote/marches/
// residentiel.js, module supprimé faute de consommateur de production).
const CLE = 'residentiel'

export default function PanneauResidentiel({
  marche,
  // ── Factures mensuelles ──
  fHiver, setFHiver, fEte, setFEte, syncBillEstimator,
  onHiverPaste, onEtePaste, handleEstimerMois, errors, monthly, setMonth,
  // ── Facture réelle du client (QF4) ──
  distributeur, setDistributeur, realBillMode, setRealBillMode,
  realBillMad, setRealBillMad, realBillKwh, setRealBillKwh,
  onRealBillPaste, consoAnnuelleReelle,
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
    />
  )
}

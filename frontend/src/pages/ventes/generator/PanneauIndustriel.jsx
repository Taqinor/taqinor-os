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
import CarteFacturesElectriques from './CarteFacturesElectriques'
// QJR637 — conso / injection / raccordement BT-MT / bloc MT : module partagé.
import BlocEtudeReseau from './BlocEtudeReseau'
// CIQ125 — le résultat du moteur serveur C&I, affiché tel quel.
import CarteResultatCi from './CarteResultatCi'

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
  // ── CIQ125 — profil déclaré C&I + résultat du moteur serveur ──
  profilCi, setChampCi, apercuCi, repartitionMt, setPartMt, tarifMtApplique,
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
    </CarteFacturesElectriques>
  )
}

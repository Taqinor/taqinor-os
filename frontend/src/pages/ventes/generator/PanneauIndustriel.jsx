// QJR101 — PANNEAU DE MARCHÉ : INDUSTRIEL.
// ---------------------------------------------------------------------------
// Quatre panneaux sortent de `DevisGenerator.jsx` : chacun ne monte que les
// champs de SON marché. L'industriel n'a ni catégorie commerciale ni pompage.
//
// QJR241 — le panneau se retire lui-même hors de son marché via `CLE`
// (constante locale) — le même patron que `DevisOffresTailles`.
// `modeInstallation` ne vaut jamais qu'une des quatre clés (le reducer refuse
// toute autre valeur, `modeDepuisTypeInstallation`), donc exactement un
// panneau rend.
//
// CIQ125/CIQ126 — UNE seule saisie de consommation : le profil déclaré C&I
// (`CarteProfilCi`, partagée avec le commercial) et le résultat du moteur
// serveur. Les factures hiver/été et la facture réelle résidentielles ne sont
// plus montées ici (elles ne dimensionnaient pas le C&I).
//
// AUCUNE LOGIQUE ICI : l'état et les gestes arrivent en props. Chaque
// `<input type="number">` garde `step="any"` (règle fondateur : aucun champ
// ne snappe jamais) et le `noValidate` est resté sur le formulaire porteur.
import { CarteProfilCi } from './BlocEtudeReseau'

const CLE = 'industriel'

// `carte` = les props de la carte C&I (profil, aperçu, tarif, erreurs).
export default function PanneauIndustriel({ marche, ...carte }) {
  if (marche !== CLE) return null
  return <CarteProfilCi {...carte} />
}

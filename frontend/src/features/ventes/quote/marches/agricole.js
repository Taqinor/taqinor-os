// QJR89 — STRATÉGIE DE MARCHÉ : AGRICOLE / POMPAGE (module PUR).
// ---------------------------------------------------------------------------
// Ce module HÉBERGE la moitié pompage : la sélection par courbe constructeur
// (HMT + débit souhaité) et la composition de l'équipement. Comme pour
// l'industriel, le calcul n'est pas recopié — il reste `pompageSelection` /
// `autoFillPompage` de `solar.js`, source UNIQUE écran / devis / PDF ; c'est
// le site d'appel de `DevisGenerator.jsx:2271-2277` et `:2501-2515` qui est
// recopié ici, à l'identique.
//
// RÈGLES DU MARCHÉ (repo, non négociables) :
//   · une composition pompage ne contient NI onduleur NI batterie — le
//     scénario batterie n'existe pas ici, donc `defautScenario` est `null`
//     (le scénario n'est jamais touché par ce marché) ;
//   · m³/jour n'est JAMAIS imprimé pour une pompe SANS courbe : `m3Jour` vaut
//     alors `null` et la clé est OMISE de l'étude (jamais un 0 déguisé) ;
//   · aucun produit « prix à renseigner » n'est jamais quoté (garde de
//     `autoFillPompage`, inchangée).
//
// Aucun moteur serveur pour l'agricole (chantier séparé QJR113, décision
// fondateur D10) : l'étude sort SIGNÉE `apercu` (QJR86).
//
// Module AJOUTÉ TESTÉ, IMPORTÉ PAR PERSONNE (vague M4).
import { pompageSelection, autoFillPompage } from '../../solar.js'
import { apercu, absent } from '../valeur.js'

export const cle = 'agricole'

/**
 * Pompage : ni batterie ni onduleur — le scénario n'est PAS touché par ce
 * marché (`DevisGenerator.jsx:1222-1225`).
 */
export const defautScenario = null

/** Soit la puissance pompe (CV), soit le couple HMT + débit souhaité. */
export const champsRequis = Object.freeze(['pompe_cv | (pompe_hmt_m + pompe_debit_m3h)'])

export const MOTIF_SANS_POMPE =
  'renseignez la puissance pompe (CV) ou HMT + débit souhaité'

const params = (etat) => ({
  cv: etat.pompeCv, alim: etat.pompeAlim, typePompe: etat.pompeType,
  hmt: etat.pompeHmt, debit: etat.pompeDebit, heures: etat.pompeHeures,
})

/**
 * DIMENSIONNEMENT — courbe constructeur si une pompe convient à cette HMT,
 * sinon sélection historique par CV (débit manuel, aucun m³/jour inventé).
 * Le catalogue arrive par `deps.produits` : le module ne va rien chercher.
 */
export function dimensionner(etat = {}, deps = {}) {
  const selection = pompageSelection(deps.produits ?? [], params(etat))
  return {
    mode: 'local',
    raison: 'aucun moteur de dimensionnement serveur pour le marché agricole '
      + '— sélection par courbe constructeur (HMT + débit)',
    selection,
    dims: selection?.dims ?? null,
  }
}

/**
 * COMPOSITION — équipement pompage (pompe + variateur assorti + afficheur +
 * champ PV + structures + câble). Locale : aucun dry-run serveur n'existe pour
 * ce marché. Une liste vide signifie « rien de quotable », jamais un
 * équipement de remplissage.
 */
export function composer(etat = {}, deps = {}) {
  const lignes = autoFillPompage(deps.produits ?? [], {
    ...params(etat),
    distance: etat.pompeDistance,
    structureType: etat.structure,
  })
  return {
    mode: 'local',
    raison: 'aucun dry-run serveur pour le marché agricole — composition pompage locale',
    lignes,
    ...(lignes.length ? {} : { motif: MOTIF_SANS_POMPE }),
  }
}

/**
 * ÉTUDE PERSISTÉE — les chiffres canoniques du pompage, calculés UNE fois et
 * rendus à l'identique à l'écran et sur le PDF. Rend une VALEUR SIGNÉE :
 * `absent(motif)` tant qu'aucune pompe n'est sélectionnable, sinon
 * `apercu(etude)`. `m3_jour` et `debit_hmt` ne sont présents QUE lorsque la
 * courbe constructeur les fournit — jamais reconstruits autrement.
 *
 * SEULE dérogation à l'interface commune : ce marché lit le CATALOGUE. La
 * sélection déjà faite par `dimensionner` peut être passée telle quelle
 * (`etat.selection`) pour que l'étude décrive EXACTEMENT la pompe retenue
 * — une seconde sélection ne doit jamais pouvoir diverger de la première.
 */
export function etudePersistee(etat = {}, deps = {}) {
  const sel = etat.selection ?? pompageSelection(deps.produits ?? [], params(etat))
  if (!sel || !(Number(sel.cv) > 0)) return absent(MOTIF_SANS_POMPE)
  const etude = {
    pompe_cv: String(sel.cv),
    pompe_kw: sel.kw,
    pompe_nom: sel.pump?.nom ?? null,
    mode_selection: sel.mode,          // 'courbe' | 'cv'
    champ_kwc: sel.dims?.champKwc ?? sel.dims?.champKw ?? null,
    nb_panneaux: sel.dims?.nbPanneaux ?? null,
    ...(sel.debitHmt != null ? { debit_hmt_m3h: sel.debitHmt } : {}),
    ...(sel.m3Jour != null ? { m3_jour: sel.m3Jour } : {}),
    ...(sel.warning ? { avertissement: sel.warning } : {}),
  }
  return apercu(etude)
}

export default {
  cle, defautScenario, champsRequis, dimensionner, composer, etudePersistee,
}

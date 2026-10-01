// QJR542 — LA projection « étude du marché → clés etude_params légales ».
//
// Déplacement PUR du corps de `blocEtudeMarche` (DevisGenerator.jsx) : une
// seule fonction, sans état React, qui ne laisse sortir QUE des clés ECRAN
// déclarées par `apps/ventes/domain/etude_schema.py` (le schéma refuse en 400
// toute autre clé de tête). Les objets BRUTS de `computeEtudeIndustrielle`
// (solar.js) et de `buildEtudePompage` (autoQuote.js) portent des clés hors
// schéma (kwc, prix_kwc, economies_annuelles…) : ils ne doivent jamais partir
// tels quels — ils passent par ici. Le générateur ET le devis automatique
// (QJR543) appellent cette même fonction : jamais une seconde liste de clés.
//
// Entrées :
//   mode               'industriel' | 'commercial' | 'agricole' | autre (résidentiel)
//   etude              l'étude I/C calculée par l'écran (industriel / commercial)
//   choix              les CHOIX de l'écran (scenario, recommended_option, nombre_proprietes)
//   entrees            fonction (consoDejaConnue) => entrées réelles, ou objet déjà calculé
//   partDiurne         part diurne du curseur industriel (%)
//   tensionRaccordement, repartitionMt   raccordement et répartition horaire TELLE QUE SAISIE
//   categorie, reponses                  catégorie commerciale + réponses du questionnaire
//   pompage            objet de `buildEtudePompage` (ou {} si aucune pompe retenue)
//   saisiePompage      { hmt, debit, heures, typePompe, alim, profondeur, distance }
//   exploitation       { irrigation, region, crop, surfaceHa, fuel, fuelSpend, hmtStatic, hmtDrawdown }
import { COMMERCIAL_CATEGORY_QUESTIONS } from '../solar.js'

const nombre = (v) => {
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : null
}

const resoudreEntrees = (entrees, consoDejaConnue) => (
  typeof entrees === 'function' ? entrees(consoDejaConnue) : (entrees || {})
)

// QXMT — la répartition horaire TELLE QUE SAISIE, ou `null` (règle Z2 : un
// site repassé en BT n'a plus de répartition MT, on la RETIRE au lieu de
// laisser traîner celle d'hier). Rien de rempli ⇒ `null` aussi : l'étude MT
// omet alors économies et payback plutôt que d'inventer un barème.
export const repartitionMtSaisie = (tensionRaccordement, repartitionMt) => {
  if (tensionRaccordement !== 'mt') return null
  const parts = {}
  for (const creneau of ['pointe', 'pleines', 'creuses']) {
    const n = parseFloat((repartitionMt || {})[creneau])
    if (Number.isFinite(n)) parts[creneau] = n
  }
  return Object.keys(parts).length ? parts : null
}

export function projeterEtudeMarche(mode, {
  etude, choix = {}, entrees, partDiurne,
  tensionRaccordement, repartitionMt,
  categorie, reponses = {},
  pompage, saisiePompage = {}, exploitation = {},
} = {}) {
  if (mode === 'industriel' || mode === 'commercial') {
    const e = etude || {}
    const bloc = {
      ...choix,
      ...resoudreEntrees(entrees, nombre(e.conso_annuelle)),
      taux_autoconso: nombre(e.taux_autoconso),
      taux_couverture: nombre(e.taux_couverture),
      payback: nombre(e.payback),
      injection_kwh_an: nombre(e.injection_kwh_an),
      injection_dh_an: nombre(e.injection_dh_an),
      // QJR528 — la part diurne du curseur INDUSTRIEL (entrée de l'étude) :
      // relue par `?edit=`, sinon la réouverture remettait le défaut et
      // réécrivait taux / payback. Commercial : dérivée de la catégorie
      // (`commercialDayShare`), rien à écrire.
      part_diurne_pct: mode === 'industriel' ? nombre(partDiurne) : undefined,
      // QXMT — raccordement du site + répartition horaire : le mappeur
      // `?edit=` les relit, donc elles doivent être PERSISTÉES, sinon un
      // devis MT rouvert repartait silencieusement au barème BT. On stocke
      // ce que le vendeur a TAPÉ (l'entrée), pas la répartition normalisée
      // par l'étude : c'est la forme que le formulaire réinjecte.
      tension_raccordement: tensionRaccordement || null,
      repartition_mt: repartitionMtSaisie(tensionRaccordement, repartitionMt),
    }
    if (mode === 'commercial') {
      // QX44 — la catégorie ET ses réponses (clés snake_case à plat, comme
      // le mappeur `?edit=` les relit : `e[q.key]`). Coercition de type
      // IDENTIQUE à celle d'avant, jamais de `prix_achat`.
      bloc.categorie_commerciale = categorie || null
      for (const q of (COMMERCIAL_CATEGORY_QUESTIONS[categorie] || [])) {
        const brut = reponses[q.key]
        if (brut === undefined || brut === '' || brut === null) continue
        bloc[q.key] = q.type === 'number'
          ? (parseFloat(brut) || 0)
          : q.type === 'bool' ? !!brut : String(brut)
      }
    }
    return bloc
  }
  if (mode === 'agricole') {
    // MÊME dérivation que l'aperçu écran et que le devis auto
    // (`buildEtudePompage`) : une seule formule, jamais deux chiffres qui
    // pourraient diverger. Seules les clés du schéma en sortent, typées.
    const p = pompage || {}
    const s = saisiePompage
    const x = exploitation
    return {
      ...choix,
      ...resoudreEntrees(entrees, null),
      // DÉRIVÉES du dimensionnement (propriétaire ECRAN au schéma).
      pompe_cv: nombre(p.pompe_cv),
      pompe_kw: nombre(p.pompe_kw),
      debit_hmt_m3h: nombre(p.debit_hmt_m3h),
      m3_jour: nombre(p.m3_jour),
      champ_kwc: nombre(p.champ_kwc),
      // ENTRÉES du vendeur, prises à l'ÉTAT de l'écran (pas au
      // dimensionnement) : ce sont elles que le mappeur `?edit=` réinjecte
      // dans le formulaire, et elles existent même quand aucune pompe à
      // courbe ne peut être retenue.
      hmt_m: nombre(s.hmt),
      debit_souhaite_m3h: nombre(s.debit),
      heures_pompage: nombre(s.heures),
      type_pompe: s.typePompe || null,
      alim: s.alim || null,
      profondeur_m: nombre(s.profondeur),
      distance_m: nombre(s.distance),
      // Exploitation guidée (toutes optionnelles, toutes relues par `?edit=`).
      irrigation_method: x.irrigation || null,
      region: x.region || null,
      crop: x.crop || null,
      surface_ha: nombre(x.surfaceHa),
      current_fuel: x.fuel || null,
      fuel_spend_current: nombre(x.fuelSpend),
      hmt_static: nombre(x.hmtStatic),
      hmt_drawdown: nombre(x.hmtDrawdown),
    }
  }
  // Résidentiel : le serveur est propriétaire de son ÉTUDE — mais pas des
  // CHOIX du vendeur ni des entrées réelles qu'il vient de taper (arbitrage
  // « zéro perte »). Objet vide ⇒ `null` (aucun appel du tout).
  const res = { ...choix, ...resoudreEntrees(entrees, null) }
  return Object.keys(res).length ? res : null
}

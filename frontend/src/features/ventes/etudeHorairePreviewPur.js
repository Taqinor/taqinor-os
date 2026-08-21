// CJ2b — LE CŒUR PUR du pont « écran générateur ↔ moteur horaire » (CJ2a).
//
// POURQUOI CE FICHIER EXISTE À PART. Ces fonctions n'importent RIEN : ni React,
// ni le client API. C'est ce qui les rend exécutables sous `node --test` — la
// convention du dépôt pour la logique pure. Le module voisin
// `etudeHorairePreview.js` (le hook) importe `../../api/ventesApi`, qui lit
// `import.meta.env` AU CHARGEMENT (`src/api/axios.js`) : hors de Vite, cette
// lecture jette, et un test qui importerait cette chaîne échouerait à
// l'import — sans rien dire des fonctions qu'il prétend vérifier.
//
// RÈGLES D'HONNÊTETÉ (fondateur, absolues — voir CLAUDE.md règle #4) :
//   1. Quand `batterie_disponible` est faux, AUCUN chiffre « avec batterie »
//      n'est affiché — jamais un 0, jamais un tiret qui se ferait passer pour
//      une mesure. `lignesAffichables` les efface elle-même en défense de
//      profondeur, même si le serveur les avait déjà mis à `null`.
//   2. Tout chiffre dérivé d'une consommation ESTIMÉE (une ou deux factures
//      répétées sur 12 mois) porte l'étiquette « estimation » —
//      `etiquetteSource` le décide depuis `etude.source_consommation`.
//   3. Les `avertissements` du serveur sont montrés tels quels.
//   4. Une donnée manquante est OMISE avec une explication FR courte, jamais
//      comblée par une valeur inventée.

/**
 * Corps de la requête POST /ventes/etude-horaire/preview/, ou `null` quand
 * rien n'ancre un calcul réel (ni facture d'hiver saisie, ni devis existant
 * dont le lead porte un profil) — l'écran n'appelle alors même pas le
 * serveur : on omet, on n'approxime pas (règle d'honnêteté #4). Résidentiel
 * uniquement (CJ2b) : tout autre mode renvoie `null`.
 */
export function construireCorpsPreview({
  modeInstallation, editId, fHiver, fEte, eteDifferente, ville, raccordement,
  kwp, batterieKwh, occupation, equipements,
} = {}) {
  if (modeInstallation !== 'residentiel') return null

  const hiver = Number(fHiver) || 0
  const hasDevis = editId !== null && editId !== undefined && String(editId).trim() !== ''
  if (hiver <= 0 && !hasDevis) return null

  const corps = { dimensionner: true }
  if (hasDevis) corps.devis = Number(editId)
  if (hiver > 0) corps.facture_hiver = hiver
  const ete = Number(fEte) || 0
  // eteDifferente non fourni explicitement : on le déduit d'une facture été
  // réellement saisie et distincte (même heuristique que l'écran ailleurs).
  const eteDiff = eteDifferente == null ? ete > 0 : !!eteDifferente
  if (eteDiff && ete > 0) {
    corps.facture_ete = ete
    corps.ete_differente = true
  }
  if (ville) corps.ville = ville
  if (raccordement) corps.raccordement = raccordement
  if (Number(kwp) > 0) corps.kwc = Number(kwp)
  if (Number(batterieKwh) > 0) corps.batterie_kwh = Number(batterieKwh)
  if (occupation) corps.occupation = occupation
  if (equipements && Object.keys(equipements).length) corps.equipements = equipements
  return corps
}

// Sources où le détail MENSUEL est une répétition de 1-2 factures réelles
// (donc une vraie estimation de la VARIATION mois à mois, même si l'ancrage
// annuel est réel) — honnêteté rule #2.
const SOURCES_ESTIMATION = new Set(['facture_hiver', 'facture_hiver_ete'])

const LIBELLES_SOURCE = {
  kwh_mensuels_saisis: 'Consommation mensuelle réelle saisie par le client',
  factures_mensuelles_reelles: 'Factures mensuelles réelles du client',
  facture_hiver: "Estimation — une seule facture (hiver) répétée sur 12 mois",
  facture_hiver_ete: "Estimation — deux factures (hiver/été) répétées sur 12 mois",
  absente: 'Aucune facture exploitable — aucune étude possible',
  inconnue: 'Source de consommation inconnue',
}

/**
 * `{ estimation, libelle }` — `estimation: true` quand le détail MENSUEL
 * vient de factures répétées (hiver seule, ou hiver/été) plutôt que d'une
 * vraie variation mois par mois. `kwh_mensuels_saisis`/
 * `factures_mensuelles_reelles` valent `false` (vraie variation réelle).
 */
export function etiquetteSource(sourceConsommation) {
  return {
    estimation: SOURCES_ESTIMATION.has(sourceConsommation),
    libelle: LIBELLES_SOURCE[sourceConsommation] || LIBELLES_SOURCE.inconnue,
  }
}

/**
 * Lignes du tableau de dimensionnement prêtes à l'affichage : chaque ligne
 * porte `batterieVendable` (bool) + `raisonBatterie` (FR, jointe depuis
 * `verdicts_bloquants_avec`). Honnêteté rule #1 — quand `batterie_disponible`
 * est faux, TOUS les champs `_avec` sont effacés ici même si le serveur en
 * avait laissé passer un (défense en profondeur, jamais un 0 ni un chiffre
 * d'une installation qu'on ne peut pas livrer).
 */
export function lignesAffichables(dimensionnement) {
  const tableau = dimensionnement?.tableau
  if (!Array.isArray(tableau)) return []
  return tableau.map((ligne) => {
    const batterieVendable = ligne?.batterie_disponible === true
    const raisonBatterie = batterieVendable
      ? ''
      : ((Array.isArray(ligne.verdicts_bloquants_avec) && ligne.verdicts_bloquants_avec.length)
          ? ligne.verdicts_bloquants_avec.join(' ')
          : 'Option batterie non livrable pour cette taille (catalogue).')
    return {
      ...ligne,
      batterieVendable,
      raisonBatterie,
      economie_avec_mad: batterieVendable ? ligne.economie_avec_mad : null,
      cout_avec_ttc: batterieVendable ? ligne.cout_avec_ttc : null,
      payback_avec_annees: batterieVendable ? ligne.payback_avec_annees : null,
      couverture_avec: batterieVendable ? ligne.couverture_avec : null,
      taux_autoconso_avec: batterieVendable ? ligne.taux_autoconso_avec : null,
    }
  })
}

/**
 * CJ2b — verdict batterie du moteur POUR LA TAILLE RÉELLEMENT CHIFFRÉE.
 *
 * Le tableau de dimensionnement dit, taille par taille, si l'option batterie
 * est électriquement livrable. Le vendeur, lui, chiffre UNE taille : c'est
 * SON verdict qu'il faut appliquer aux cartes de comparaison en haut de
 * l'écran, sinon elles continuent d'annoncer une économie « avec batterie »
 * pour une installation que le catalogue ne peut pas livrer (le trou réel
 * exhumé par CJ2a : panneau 710 Wc + hybride 5 kW mono, Isc 18,6 A > 17,0 A).
 *
 * `null` quand le moteur ne dit rien sur cette taille (aucun tableau, ou
 * aucune ligne assez proche) : l'écran garde alors son comportement d'avant —
 * on ne fabrique pas un verdict par défaut, ni dans un sens ni dans l'autre.
 *
 * `tolerance` en kWc : le vendeur peut avoir tapé une puissance qui ne tombe
 * pas exactement sur un palier du catalogue.
 */
export function verdictBatteriePourTaille(lignes, kwc, tolerance = 0.4) {
  const cible = Number(kwc)
  if (!Array.isArray(lignes) || !lignes.length || !(cible > 0)) return null
  let meilleure = null
  let ecartMin = Infinity
  for (const ligne of lignes) {
    const ecart = Math.abs(Number(ligne?.kwc) - cible)
    if (Number.isFinite(ecart) && ecart < ecartMin) {
      ecartMin = ecart
      meilleure = ligne
    }
  }
  if (!meilleure || ecartMin > tolerance) return null
  return {
    vendable: meilleure.batterieVendable === true,
    raison: meilleure.raisonBatterie || '',
    kwc: meilleure.kwc,
  }
}


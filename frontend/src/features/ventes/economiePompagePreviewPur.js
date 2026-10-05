// AGR213 — fonctions PURES de la carte « Économie déclarée » (pompage).
// Aucun import : elles tournent sous `node --test` comme sous Vitest.
//
// Contrat partagé : `backend/django_core/apps/ventes/contract_samples/
// economie_pompage.json` (AGR3). L'écran ne CALCULE RIEN : il construit le
// corps de `POST /ventes/economie-pompage/preview/` (AGR206) et met en mots
// la réponse du serveur, chiffre pour chiffre.
//
// RÈGLES :
//   1. aucun chiffre recalculé ici — on lit, on étiquette, on omet ;
//   2. une grandeur absente est OMISE avec son motif, jamais un zéro ;
//   3. la clé `vue_interne` n'est JAMAIS lue par la vue client de la carte
//      (elle n'entre que dans le volet interne, AGR214).

const ETIQUETTE = 'estimation — calculée sur les chiffres déclarés'

const UNITES = {
  bouteille_12kg: 'bouteille(s) de 12 kg',
  litre: 'litre(s)',
}

const COMPOSANTS = { pompe: 'Pompe', variateur: 'Variateur' }

const LIBELLES_CHAMPS = {
  'saisies_economie_pompage.energie_actuelle': 'Énergie actuelle',
  'saisies_economie_pompage.consommation': 'Consommation',
  'saisies_economie_pompage.depense_unitaire_payee': 'Prix payé',
  'saisies_economie_pompage.mois_irrigation': "Mois d'irrigation",
  'saisies_economie_pompage.entretien_paye_mad_an': 'Entretien payé',
  'saisies_economie_pompage.facture_reseau': 'Facture réseau',
}

/** `AAAA-MM-JJ` → `JJ/MM` (texte tel quel sinon). */
export function jourMois(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ''))
  return m ? `${m[3]}/${m[2]}` : (iso || '')
}

const nombreLu = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

/**
 * Le corps de l'aperçu, ou `null` tant qu'il manque l'essentiel (aucune
 * saisie déclarée, ou aucune sortie d'étude pompage servie) : aucun appel.
 */
export function construireCorpsEconomiePompage({ saisies, sortieEtude, lignes } = {}) {
  if (!saisies || !sortieEtude) return null
  const propres = (Array.isArray(lignes) ? lignes : [])
    .filter((l) => l && l.produit)
    .map((l) => ({
      produit: l.produit,
      quantite: l.quantite ?? null,
      prix_unitaire: l.prix_unitaire ?? null,
      remise: l.remise ?? null,
      taux_tva: l.taux_tva ?? null,
    }))
  return { saisies, sortie_etude_pompage: sortieEtude, lignes: propres }
}

/** « N bouteilles × P DH × M mois, déclaré le JJ/MM » — lu des entrées DÉCLARÉES. */
export function detailDeclare(reponse) {
  const entrees = Array.isArray(reponse?.entrees_declarees) ? reponse.entrees_declarees : []
  const par = Object.fromEntries(entrees.map((e) => [e.cle, e]))
  const conso = par.consommation
  const prix = par.depense_unitaire_payee
  const mois = par.mois_irrigation
  if (!conso || !prix) return null
  const morceaux = [`${conso.valeur} ${conso.unite || ''}`.trim(),
    `${prix.valeur} ${prix.unite || 'MAD'}`]
  if (Array.isArray(mois?.valeur)) morceaux.push(`${mois.valeur.length} mois`)
  const date = conso.saisi_le || prix.saisi_le
  return `${morceaux.join(' × ')}${date ? `, déclaré le ${jourMois(date)}` : ''}`
}

/** L'économie NETTE de l'année 1 servie (flux de l'année 1 : économie −
 *  charges), ou `null`. */
function economieNetteAnnee1(economie) {
  const flux = Array.isArray(economie?.flux) ? economie.flux : []
  const an1 = flux.find((f) => f && f.annee === 1)
  return an1 ? nombreLu(an1.flux_mad) : null
}

/**
 * Le modèle d'affichage CLIENT de la carte (aucune clé de `vue_interne`).
 * Chaque chiffre porte l'étiquette d'estimation ; chaque omission son motif.
 */
export function vueCarteEconomie(reponse) {
  if (!reponse || typeof reponse !== 'object') return null
  const economie = reponse.economie || {}
  const omissions = [
    ...(Array.isArray(reponse.omissions) ? reponse.omissions : []),
    ...(Array.isArray(economie.omissions) ? economie.omissions : []),
  ].map((o) => ({ cle: o?.cle || null, motif: o?.motif || o?.cle || '' }))
  const coherenceParChamp = {}
  for (const c of Array.isArray(reponse.coherence) ? reponse.coherence : []) {
    const champ = c?.champ || 'general'
    coherenceParChamp[champ] = coherenceParChamp[champ] || {
      libelle: LIBELLES_CHAMPS[champ] || champ, messages: [],
    }
    coherenceParChamp[champ].messages.push(c?.message || c?.code || '')
  }
  const depense = reponse.depense_actuelle
  return {
    etiquette: ETIQUETTE,
    statut: reponse.statut || null,
    cas: reponse.cas || null,
    depenseAnnuelle: depense ? nombreLu(depense.annuelle_mad) : null,
    depenseFormule: depense?.formule || null,
    detailDeclare: detailDeclare(reponse),
    charges: reponse.charges_solaires ? {
      total: nombreLu(reponse.charges_solaires.total_mad_an),
      lignes: (reponse.charges_solaires.lignes || []).map((l) => ({
        libelle: l.libelle, montant: nombreLu(l.montant_mad_an), source: l.source || null,
      })),
    } : null,
    remplacements: (Array.isArray(reponse.remplacements) ? reponse.remplacements : [])
      .map((r) => ({
        composant: COMPOSANTS[r.composant] || r.composant,
        annee: r.annee ?? null,
        montant: nombreLu(r.montant_ttc_mad),
        source: r.source || null,
        motif: r.motif || null,
      })),
    economieNette: economieNetteAnnee1(economie),
    retourAns: nombreLu(economie.retour_ans),
    madParM3: reponse.mad_par_m3 ? {
      actuel: nombreLu(reponse.mad_par_m3.actuel),
      solaire: nombreLu(reponse.mad_par_m3.solaire),
      formule: reponse.mad_par_m3.formule || null,
    } : null,
    sensibilite: (Array.isArray(reponse.sensibilite_carburant) ? reponse.sensibilite_carburant : [])
      .map((s) => ({ libelle: s.libelle, economie: nombreLu(s.economie_nette_mad_an),
        retourAns: nombreLu(s.retour_ans) })),
    seuil: reponse.seuil_rentabilite_carburant ? {
      valeur: nombreLu(reponse.seuil_rentabilite_carburant.valeur_unitaire_mad),
      unite: reponse.seuil_rentabilite_carburant.unite || null,
    } : null,
    omissions,
    coherenceParChamp,
    couvertureNonVerifiee: reponse.couverture && reponse.couverture.verifiee === false
      ? (reponse.couverture.motif || 'couverture du besoin non vérifiable (pompe sans courbe)')
      : null,
    motifsNonPubliable: reponse.publiable_client === false
      ? (Array.isArray(reponse.motifs_non_publiable) ? reponse.motifs_non_publiable : [])
      : [],
  }
}

export const libelleUnite = (u) => UNITES[u] || u || ''

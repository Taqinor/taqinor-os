// AGEN11 (D-ACAL-97, contrôle C4-E7) — L'ÉCRAN DEVIS LIT LE MOTEUR UNIQUE.
//
// Plus aucun calcul de production, d'économie ni de payback dans le
// navigateur : avec un lead, l'écran montre d'abord la conception RANGÉE
// (`GET conception/<lead>/`) ; dès qu'une valeur est tapée (facture, kWh,
// nombre de panneaux), l'aperçu SANS écriture du même moteur
// (`POST conception/apercu/`, ADEV152) est demandé — un devis sans lead
// l'obtient sur ses seules valeurs tapées. « Calcul en cours » pendant l'appel.
// Forme : `apps/ventes/contract_samples/conception_lead.json`. Les nombres
// partent TELS QUE TAPÉS (jamais arrondis, jamais corrigés ici).
import { useEffect, useState } from 'react'
import ventesApi from '../../../../api/ventesApi'
import {
  appartientAuPanierAvec, appartientAuPanierSans, isBattery, isHybridInverter,
  isOffgridInverter, isPanel, isReseauInverter, texteClassement, _produitDeLigne,
} from '../../../../features/ventes/calc/classification.js'
import { batteryKwhFromLines } from '../../../../features/ventes/solar'

//: Délai avant l'appel d'aperçu (la frappe reste instantanée).
export const DELAI_APERCU_MS = 500
//: E7d (M2) — l'échec sans phrase du serveur (5xx, réseau) ; l'écran offre « Réessayer ».
export const APERCU_INDISPONIBLE = 'Aperçu indisponible — Réessayer'

const tape = (v) => (v === null || v === undefined ? '' : String(v).trim())

/** Le corps de `POST conception/apercu/` pour ce que l'écran a TAPÉ, ou `null`
 *  (rien de tapé, ou marché agricole : son aperçu est celui du pompage).
 *  E7d (revue lot 4, B2) — `consommation` : celle que le devis ENREGISTRE
 *  (`etatDevis.consommationImposeeDeEtat`, le sélecteur de l'enregistrement),
 *  imposée au moteur (`imposes.consommation`) ; `null` ⇒ celle du lead. */
export function corpsApercuConception({
  leadId, modeInstallation, fHiver, fEte, nbPanneaux = 0, consommation = null, investissement = null,
}) {
  if (!modeInstallation || modeInstallation === 'agricole') return null
  const entrees = {}
  if (tape(fHiver)) entrees.facture_hiver = tape(fHiver)
  if (modeInstallation === 'residentiel' && tape(fEte) && Number(fEte) > 0) {
    entrees.facture_ete = tape(fEte)
    entrees.ete_differente = true
  }
  const lead = leadId ? Number(leadId) : null
  const imposes = modeInstallation === 'residentiel' && nbPanneaux > 0 ? { nb_panneaux: nbPanneaux } : {}
  if (consommation) imposes.consommation = consommation
  // E7d (M1) — le TTC de vente des lignes de chaque option (> 0 seulement) : le
  // prix du payback servi ; avec un lead, des lignes chiffrées suffisent à demander
  // l'aperçu (le payback de CE devis), jamais sans porteur.
  const prix = Object.fromEntries(Object.entries(investissement || {})
    .filter(([, v]) => Number.isFinite(Number(v)) && Number(v) > 0).map(([k, v]) => [k, Number(v)]))
  if (!lead && !Object.keys(entrees).length && !consommation) return null
  if (lead && !Object.keys(entrees).length && !Object.keys(imposes).length && !Object.keys(prix).length) return null
  // Sans lead, le marché du devis est une valeur tapée de l'écran.
  if (!lead) entrees.type_installation = modeInstallation
  return { lead, calepinage: null, entrees, imposes, ...(Object.keys(prix).length ? { investissement: prix } : {}) }
}

const valeur = (table, cle) => table?.[cle]?.valeur ?? null

const idProduit = (l) => (l?.produit ? Number(l.produit) : null)

/** E7d (revue de l'écran, 25/11) — la composition IMPOSABLE des lignes d'une option
 *  (`composition_imposee.CHAMPS_IMPOSES`) : `nb_panneaux`, le produit panneau, le produit
 *  onduleur (réseau / hors réseau pour « sans », hybride / hors réseau pour « avec ») et,
 *  pour « avec », la batterie — son produit pour UNE batterie, sinon sa capacité totale
 *  (`batterie_kwh` : le moteur impose une batterie par produit). Une ligne sans produit
 *  du catalogue n'impose rien (le moteur choisit) ; jamais un produit absent des lignes.
 *  `null` sans panneau. */
export function compositionDesLignes(lines, option, produits = []) {
  const panier = option === 'avec' ? appartientAuPanierAvec : appartientAuPanierSans
  const lignes = (lines || []).filter((l) => panier(l, produits))
  const texte = (l) => texteClassement(l, produits)
  const panneaux = lignes.filter((l) => isPanel(l?.designation || '', _produitDeLigne(l, produits)?.nom || ''))
  const nb = panneaux.reduce((n, l) => n + (parseFloat(l.quantite) || 0), 0)
  if (!(nb > 0)) return null
  const famille = option === 'avec' ? isHybridInverter : isReseauInverter
  const onduleur = lignes.find((l) => famille(texte(l)) || isOffgridInverter(texte(l)))
  const imposes = { nb_panneaux: nb }
  const panneau = panneaux.find(idProduit)
  if (panneau) imposes.panneau_produit_id = idProduit(panneau)
  if (idProduit(onduleur)) imposes.onduleur_produit_id = idProduit(onduleur)
  if (option === 'avec') {
    const batteries = lignes.filter((l) => isBattery(texte(l)) && l.variante !== 'sans')
    const unique = batteries.length === 1 && (parseFloat(batteries[0].quantite) || 0) === 1
    const kwh = batteryKwhFromLines(batteries, produits)
    if (unique && idProduit(batteries[0])) imposes.batterie_produit_id = idProduit(batteries[0])
    else if (kwh > 0) imposes.batterie_kwh = kwh
  }
  return imposes
}

/** E7d — la conception décrit-elle les LIGNES ? `composition` = `{ sans, avec, deux }`
 *  (`compositionDesLignes` par option, `deux` : les deux options montrées). Vrai si chaque
 *  option servie porte le compte de panneaux ET les produits panneau / onduleur que les
 *  lignes imposent, et, l'écran montrant les deux, si les deux sont servies. Un refus : vrai. */
export function concordeAvecLesLignes(conception, composition) {
  if (!conception || conception.etat !== 'complet' || !composition) return true
  const valeurs = conception.valeurs || {}
  if (composition.deux && !(valeurs.sans && valeurs.avec)) return false
  const memes = (table, lignes) => !lignes
    || (valeur(table, 'nb_panneaux') === lignes.nb_panneaux
      && (!lignes.panneau_produit_id || valeur(table, 'module_produit') === lignes.panneau_produit_id)
      && (!lignes.onduleur_produit_id || valeur(table, 'onduleur_produit') === lignes.onduleur_produit_id))
  return Object.entries(valeurs).every(([opt, table]) => memes(table, composition[opt]))
}

/** Revue finale du lot — le tableau des tailles des DEUX aperçus imposés : chaque
 *  taille (panneaux) une fois — la ligne du premier aperçu qui la porte —, les
 *  options `taille_du_devis` des deux réunies, triées par taille. `null` sans
 *  tableau dans l'un ni l'autre (le bloc reste celui de l'aperçu « sans »). */
function reunirTableaux(tSans, tAvec) {
  if (!Array.isArray(tSans) && !Array.isArray(tAvec)) return null
  const parTaille = new Map()
  for (const ligne of [...(tSans || []), ...(tAvec || [])]) {
    const deja = parTaille.get(ligne?.panneaux)
    if (!deja) { parTaille.set(ligne?.panneaux, ligne); continue }
    const options = [...(deja.taille_du_devis || []), ...(ligne.taille_du_devis || [])]
      .filter((o, i, liste) => liste.indexOf(o) === i)
    if (options.length) parTaille.set(ligne.panneaux, { ...deja, taille_du_devis: options })
  }
  return [...parTaille.values()].sort((a, b) => (Number(a?.panneaux) || 0) - (Number(b?.panneaux) || 0))
}

/** E7d — une composition imposée est UNE option chez le moteur : les deux options d'un
 *  écran « Les deux » viennent de deux aperçus imposés, réunis ici par option (valeurs,
 *  étude horaire de chacune, dimensionnement du premier) ; un refus l'emporte (le premier). */
export function reunirOptions(sans, avec) {
  if (!avec) return sans
  if (!sans || sans.etat !== 'complet') return sans
  if (avec.etat !== 'complet') return avec
  const premiere = (c) => c.valeurs?.[Object.keys(c.valeurs || {})[0]]
  const messages = new Set()
  const dimSans = sans.blocs?.dimensionnement
  const tableau = reunirTableaux(dimSans?.tableau, avec.blocs?.dimensionnement?.tableau)
  return {
    ...sans,
    option_retenue: avec.option_retenue === 'avec' ? 'avec' : sans.option_retenue,
    valeurs: { sans: sans.valeurs?.sans || premiere(sans), avec: avec.valeurs?.avec || premiere(avec) },
    blocs: { ...(sans.blocs || {}), etude_horaire_sans: sans.blocs?.etude_horaire,
      etude_horaire: avec.blocs?.etude_horaire,
      ...(tableau ? { dimensionnement: { ...dimSans, tableau } } : {}) },
    suppositions: [...(sans.suppositions || []), ...(avec.suppositions || [])]
      .filter((x) => !messages.has(x?.message) && messages.add(x?.message)),
  }
}

/** Les chiffres AFFICHÉS d'une conception servie (aucun calcul : des lectures).
 *  `null` tant qu'elle n'est pas complète. */
export function chiffresConception(conception) {
  if (!conception || conception.etat !== 'complet') return null
  const valeurs = conception.valeurs || {}
  const cles = Object.keys(valeurs)
  if (!cles.length) return null
  const sans = valeurs.sans || valeurs[cles[0]]
  const avec = valeurs.avec || sans
  return {
    productionSans: valeur(sans, 'production_annuelle'),
    productionAvec: valeur(avec, 'production_annuelle'),
    ecoSans: valeur(sans, 'economies_annuelles'),
    ecoAvec: valeur(avec, 'economies_annuelles'),
    paybackSans: valeur(sans, 'payback'),
    paybackAvec: valeur(avec, 'payback'),
  }
}

/** La conception de l'écran : `conception` (l'aperçu dès qu'il a répondu,
 *  sinon la version rangée du lead), `servie` (la version rangée seule : son
 *  payback est celui du devis de référence, comme le PDF), `chargement`,
 *  `erreur` (message du serveur, en français).
 *  E7d (M3) — les clés de la garde de péremption du dimensionnement
 *  (`decisionSizing`) : `cleCourante` (ce qui est à l'écran), `cleServie` /
 *  `cleErreur` (ce qui a produit la réponse ou l'échec) ; un lead SANS version
 *  rangée (404) est prévisualisé sur ses seules colonnes (corps vide). */
export function useConceptionEcran({ leadId, corps, composition = null }) {
  const [rangee, setRangee] = useState({ lead: null, donnees: null })
  const [apercu, setApercu] = useState({ donnees: null, chargement: false, erreur: null, cle: '' })
  const [essai, setEssai] = useState(0)  // E7d (M2) — « Réessayer » relance le même corps

  useEffect(() => {
    let vivant = true
    const lire = async () => {
      if (!leadId) { setRangee({ lead: null, donnees: null }); return }
      try {
        const { data } = await ventesApi.getConceptionLead(leadId)
        if (vivant) setRangee({ lead: leadId, donnees: data?.etat && data.etat !== 'aucune' ? data : null })
      } catch {
        if (vivant) setRangee({ lead: leadId, donnees: null })  // 404 « conception_absente » : rien de rangé
      }
    }
    lire()
    return () => { vivant = false }
  }, [leadId])

  const servie = rangee.lead === leadId ? rangee.donnees : null
  const sansVersion = Boolean(leadId) && rangee.lead === leadId && !rangee.donnees
  const corpsEffectif = corps
    ?? (sansVersion ? { lead: Number(leadId), calepinage: null, entrees: {}, imposes: {} } : null)
  const cleLibre = corpsEffectif ? JSON.stringify(corpsEffectif) : ''
  // E7d (CI e2e figures-parite) — d'abord la conception sur les valeurs du porteur
  // (aucun nombre de panneaux imposé : le moteur sert ses deux options, comme au
  // devis automatique) ; SEULEMENT si elle ne porte pas les panneaux des lignes,
  // l'aperçu est redemandé au compte de l'écran (`imposes.nb_panneaux`, une option).
  // Imposé : la composition des LIGNES (compte, panneau, onduleur, batterie), une option
  // par aperçu ; « Les deux » : deux aperçus, réunis par `reunirOptions`.
  const libre = apercu.libre?.cle === cleLibre ? apercu.libre.donnees : null
  const imposer = (lignes) => (lignes ? { ...corpsEffectif, imposes: { ...corpsEffectif.imposes, ...lignes } } : null)
  const premiere = composition?.sans || composition?.avec
  const impose = corpsEffectif && premiere && libre && !concordeAvecLesLignes(libre, composition)
    ? [imposer(premiere), composition.deux && composition.sans ? imposer(composition.avec) : null].filter(Boolean)
    : null
  const cle = impose ? JSON.stringify(impose) : cleLibre
  useEffect(() => {
    const ctrl = new AbortController()
    let minuterie = null
    const demander = async () => {
      try {
        const lu = JSON.parse(cle)
        const reponses = await Promise.all((Array.isArray(lu) ? lu : [lu])
          .map((corpsLu) => ventesApi.apercuConception(corpsLu, { signal: ctrl.signal })))
        const [premier, second] = reponses.map((r) => (r?.data?.etat ? r.data : null))
        const donnees = premier && second ? reunirOptions(premier, second) : premier
        if (!ctrl.signal.aborted) {
          setApercu((a) => ({ donnees, chargement: false, erreur: null, cle,
            libre: cle === cleLibre ? { cle, donnees } : a.libre }))
        }
      } catch (err) {
        if (ctrl.signal.aborted) return
        const detail = err?.response?.data?.detail
        setApercu((a) => ({ donnees: null, chargement: false, cle, champ: err?.response?.data?.champ || null,
          erreur: typeof detail === 'string' ? detail : APERCU_INDISPONIBLE, libre: a.libre }))
      }
    }
    const lancer = async () => {
      if (!cle) { setApercu({ donnees: null, chargement: false, erreur: null, cle: '', libre: null }); return }
      setApercu((a) => ({ ...a, chargement: true, erreur: null }))
      minuterie = setTimeout(demander, DELAI_APERCU_MS)
    }
    lancer()
    return () => { if (minuterie) clearTimeout(minuterie); ctrl.abort() }
  }, [cle, essai]) // eslint-disable-line react-hooks/exhaustive-deps -- cleLibre : dérivée du même corps que `cle`

  const surRangee = !cle && Boolean(servie)
  // E7d (revue lot 4, M2) — une saisie dont l'aperçu a ÉCHOUÉ ne retombe jamais sur la
  // version rangée comme si elle était à jour : aucune conception, l'erreur est dite.
  const echec = Boolean(cle) && Boolean(apercu.erreur) && apercu.cle === cle
  return {
    conception: echec ? null : (apercu.donnees ?? servie), servie, chargement: apercu.chargement,
    apercuServi: !echec && Boolean(cle) && Boolean(apercu.donnees),
    erreur: apercu.erreur, champErreur: echec ? (apercu.champ || null) : null, compteImpose: Boolean(impose),
    reessayer: echec ? () => setEssai((n) => n + 1) : null,
    cleCourante: cle || (surRangee ? 'rangee' : null),
    cleServie: apercu.donnees ? apercu.cle : (surRangee ? 'rangee' : null),
    cleErreur: apercu.erreur ? apercu.cle : null,
  }
}

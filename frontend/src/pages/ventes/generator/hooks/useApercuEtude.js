// SPL51 — LES DÉRIVATIONS D'APERÇU, déplacées de DevisGenerator.jsx :
// valeurs différées, conso réelle / écran, lead prioritaire (bandeau de
// segment, rappel ICE), conception servie (AGEN11) et, depuis E7d (M3), TOUS
// les blocs de l'aperçu lus sur cette même conception (graphe, falaise,
// verdict batterie, tableau, décision de dimensionnement), `apercu*` /
// `payback*`, `signerEcoOuRoi`, `chartData`. `ctx` porte, nom par nom, ce que
// le corps lit du composant. Appelé à la MÊME position (ordre des hooks inchangé).
import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import crmApi from '../../../../api/crmApi'
import { toast } from '../../../../ui/confirm'
import { formatNumber } from '../../../../lib/format'
import {
  CHART_MONTHS, batteryCapaciteInconnue, comptePanneauxOption,
} from '../../../../features/ventes/solar'
import { consoAnnuelleDepuisFactures } from '../../../../features/ventes/calc/tarifs.js'
import {
  lignesAffichables, verdictBatteriePourTaille, falaiseAffichable, glitchAnnuel,
  donneesHorairesDeConception, serieEconomiesMensuelles,
} from '../../../../features/ventes/etudeHorairePreviewPur'
import { toucheNbPanneauxPourComposition } from '../../../../features/ventes/quote/sizingReducer'
import { decisionSizing } from '../../../../features/ventes/quote/hooks/useSizingMoteurPur'
import { moteur, apercu } from '../../../../features/ventes/quote/valeur'
import { villeEffectiveLead } from '../../../../features/ventes/quote/ecranDefauts.js'
import { consommationImposeeDeEtat } from '../../../../features/ventes/quote/etatDevis.js'
import {
  chiffresConception, compositionDesLignes, corpsApercuConception, useConceptionEcran,
} from './useConceptionEcran'

export function useApercuEtude(ctx) {
  const {
    lines, realBillMode, realBillKwh,
    realBillMad, distributeur, baremeSociete, provenanceMois, leadDuDevis, leads,
    leadId, modeInstallation, clientsConnus, clientId, confirm, fHiver, fEte,
    sizing, dispatchSizing, produits, monthly, realBillSaisi, distributeurChoisi, consoStockee, totals,
    showSans, showAvec,
  } = ctx

  // La capacité batterie se juge sur des lignes DIFFÉRÉES (la frappe reste instantanée).
  const dLines = useDeferredValue(lines)

  // BAT5DEF (26/08/2026) — au moins une ligne batterie n'a pas de kWh lisible
  // dans sa désignation : `batteryKwhFromLines` ne lui compte plus un défaut
  // fabriqué de 5 kWh (RÈGLE FONDATEUR « zéro chiffre inventé »), donc la
  // capacité utilisée en aval (ROI, étude horaire) peut être SOUS-estimée.
  // Signalé à l'écran plutôt que tu — jamais un chiffre qu'on tairait.
  const capaciteBatterieInconnue = useMemo(
    () => batteryCapaciteInconnue(dLines, produits), [dLines, produits])

  // QF4/QF5 — consommation annuelle RÉELLE dérivée de la facture/kWh du
  // client (barème par tranche du distributeur choisi). Alimente à la fois
  // etude_params (à l'enregistrement) et l'étude horaire servie —
  // UNE seule dérivation, jamais deux chiffres qui pourraient diverger.
  const consoAnnuelleReelle = (() => {
    if (realBillMode === 'kwh') {
      const kwh = parseFloat(realBillKwh) || 0
      return kwh > 0 ? Math.round(kwh * 12) : null
    }
    const mad = parseFloat(realBillMad) || 0
    if (mad <= 0) return null
    // AGNR14 — la « Facture réelle » est un montant de facture TOTALE
    // (énergie + lignes fixes + TPPAN) : inversée au barème COMPLET, comme
    // les 12 factures et le serveur (`kwh_from_bill(..., facture_totale=True)`),
    // jamais par l'énergie seule (`kwhFromBill`, +40 % sur les petites factures).
    const kwhAn = consoAnnuelleDepuisFactures(Array(12).fill(mad), distributeur,
      baremeSociete?.tranches, baremeSociete?.chargesFixes)
    return kwhAn > 0 ? kwhAn : null
  })()

  // N1/N4 — `monthly` démarre avec les valeurs D'EXEMPLE du simulateur
  // (DEFAULT_MONTHLY_BILLS) : tant qu'aucune n'a été touchée (hiver/été,
  // « Estimer 12 mois », ou une case du détail mensuel éditée à la main),
  // AUCUNE vraie facture client n'existe encore. Sert à la fois à décider si
  // le graphique écran peut se présenter comme un fait (N4) et si
  // `etude_params.factures_mensuelles_reelles` doit être semé à
  // l'enregistrement (N1) — jamais les valeurs d'exemple.
  // AGNR13 — case par case : une seule case d'EXEMPLE suffit à bloquer
  // l'envoi (taper Janvier seul n'envoie plus 11 mois d'exemple).
  const facturesSaisies = provenanceMois.every(p => p !== 'exemple')
  const moisNonSaisis = provenanceMois.some(p => p !== 'exemple')
    ? CHART_MONTHS.filter((_, i) => provenanceMois[i] === 'exemple') : []

  // Lead prioritaire résolu tôt (bandeau de segment, rappel ICE, ville de calcul).
  const leadsListe = (leadDuDevis
    && !leads.some(l => String(l.id) === String(leadDuDevis.id)))
    ? [leadDuDevis, ...leads] : leads
  const selectedLead = leadsListe.find(l => String(l.id) === String(leadId))

  // AGR421 / CIQ423 (D-AGR-9) — devis agricole, commercial ou industriel sur un
  // lead d'un autre type : le bandeau PROPOSE, le commercial change le type à la
  // main (jamais à l'enregistrement ni à l'envoi). C&I : seul l'écart que le
  // serveur signale (`incoherence_segment`) ou un lead d'une autre famille.
  const [typeLeadMisAJour, setTypeLeadMisAJour] = useState({})
  const incoherenceSegment = selectedLead?.incoherence_segment || null
  const typeLeadEffectif = selectedLead
    ? (typeLeadMisAJour[selectedLead.id]
      ?? incoherenceSegment?.segment_lead
      ?? selectedLead.type_installation ?? '')
    : ''
  const marcheSegment = ['agricole', 'commercial', 'industriel'].includes(modeInstallation)
    ? modeInstallation : ''
  const bandeauSegment = Boolean(selectedLead) && Boolean(marcheSegment)
    && typeLeadEffectif !== marcheSegment
    && (marcheSegment === 'agricole'
      || Boolean(incoherenceSegment)
      || (typeLeadEffectif !== '' && !['commercial', 'industriel'].includes(typeLeadEffectif)))
  // CIQ423 (D-CIQ-11) — rappel NON bloquant : l'ICE d'un client entreprise.
  const clientDuDevis = clientsConnus.find(c => String(c.id) === String(clientId))
  const identiteEntreprise = clientDuDevis?.identite_entreprise
    ?? selectedLead?.identite_entreprise ?? null
  const manquantsIdentite = Array.isArray(identiteEntreprise?.manquants)
    ? identiteEntreprise.manquants : []
  const marchePro = ['commercial', 'industriel'].includes(modeInstallation)
  // Hors commercial/industriel (résidentiel, agricole) : le rappel ne vaut que
  // pour un client ENTREPRISE sans ICE — l'ICE n'y est exigé qu'à la facture.
  const rappelIce = marchePro
    ? manquantsIdentite.some(m => m === 'ice' || m === 'raison_sociale')
    : identiteEntreprise?.type_client === 'entreprise' && manquantsIdentite.includes('ice')
  const rappelIceAcceptation = marchePro
  const changerTypeLead = async () => {
    if (!selectedLead) return
    const ok = await confirm({
      title: 'Changer le type du lead ?',
      description: `Le lead passera en « ${marcheSegment} » : le script d'appel, le score et le suivi le traiteront comme un lead ${marcheSegment}.`,
      confirmLabel: `Passer en ${marcheSegment}`,
    })
    if (!ok) return
    try {
      await crmApi.updateLead(selectedLead.id, { type_installation: marcheSegment })
      setTypeLeadMisAJour(m => ({ ...m, [selectedLead.id]: marcheSegment }))
    } catch {
      toast.error('Le type du lead n’a pas pu être modifié.')
    }
  }

  // QJR586 — la ville de CALCUL du lead sélectionné (servie par le serveur).
  const villeCalculLead = villeEffectiveLead(selectedLead)


  // AGEN11 (D-ACAL-97) — LE moteur unique : la conception rangée du lead, puis
  // l'aperçu SANS écriture de ce qui est tapé (`useConceptionEcran`). Aucun
  // calcul local de production, d'économie ni de payback ne subsiste ici.
  // E7d (revue lot 4, B2) — la consommation de l'aperçu = celle que le devis
  // ENREGISTRE : le même état, le même sélecteur (`etatDevis.consoDeEtat`).
  const consommationImposee = consommationImposeeDeEtat({
    monthly, provenanceMois, facturesSaisies, fHiver, fEte, realBillSaisi, realBillMode,
    consoAnnuelleReelle, distributeur, distributeurChoisi, consoStockee: consoStockee?.current ?? null,
    bareme: baremeSociete,
  })
  // E7d (revue lot 4, M1) — le prix du payback : le TTC de VENTE des lignes de
  // chaque option à l'écran (jamais un prix d'achat), envoyé avec l'aperçu.
  const corpsConception = corpsApercuConception({
    leadId, modeInstallation, fHiver, fEte, consommation: consommationImposee,
    investissement: { sans: totals?.totalSans, avec: totals?.totalAvec },
  })
  // E7d — la composition des LIGNES par option montrée (compte, panneau, onduleur,
  // batterie) : la conception servie doit la porter ; sinon l'aperçu est redemandé en
  // l'imposant (une option par aperçu chez le moteur).
  const composition = modeInstallation === 'residentiel' ? {
    sans: showSans ? compositionDesLignes(lines, 'sans', produits) : null,
    avec: showAvec ? compositionDesLignes(lines, 'avec', produits) : null,
    deux: Boolean(showSans && showAvec),
  } : null
  const conceptionEcran = useConceptionEcran({ leadId, corps: corpsConception, composition })
  const chiffres = chiffresConception(conceptionEcran.conception)
  // La conception affichée est-elle l'APERÇU de cet écran (payback sur ses lignes) ?
  // La version rangée porte le payback d'un devis de RÉFÉRENCE : jamais affiché ici.
  const surApercu = conceptionEcran.apercuServi

  // E7d (revue lot 4, M3) — UNE SOURCE PAR BLOC. Le graphe mensuel, la falaise,
  // le verdict batterie, le tableau de dimensionnement ET la recommandation de
  // taille (U3-900) se lisent sur la MÊME réponse que les cartes : la conception
  // servie (`blocs` = l'étude que le moteur unique a calculée,
  // `donneesHorairesDeConception`). L'aperçu horaire (`etude-horaire/preview/`)
  // n'est plus appelé par cet écran : un bloc dont la donnée manque le dit.
  const horaires = useMemo(
    () => donneesHorairesDeConception(modeInstallation === 'residentiel' ? conceptionEcran.conception : null),
    [modeInstallation, conceptionEcran.conception])
  const etudeHoraireDonnees = horaires?.sans ?? null
  const etudeHoraireDonneesPourAvec = horaires?.avec ?? etudeHoraireDonnees
  const etudeHoraireChargement = conceptionEcran.chargement
  const refusDesigne = conceptionEcran.conception?.etat === 'refus' ? conceptionEcran.conception.refus : null
  const etudeHoraireErreur = conceptionEcran.erreur || refusDesigne?.message || null
  // Corps « présent » = l'écran a demandé ou reçu une conception résidentielle.
  const etudeHoraireCorps = modeInstallation === 'residentiel'
    && (corpsConception || conceptionEcran.conception || conceptionEcran.chargement)
    ? (corpsConception || {}) : null
  // La garde de péremption du dimensionnement (QJR90) sur les clés de la conception.
  const decisionMoteur = decisionSizing({
    attente: sizing.attenteMoteur,
    toucheNbPanneaux: toucheNbPanneauxPourComposition(sizing),
    chargement: conceptionEcran.chargement,
    donnees: etudeHoraireDonnees
      ?? (refusDesigne ? { dimensionnement: null, avertissements: [refusDesigne.message].filter(Boolean) } : null),
    erreur: conceptionEcran.erreur,
    cleServie: conceptionEcran.cleServie,
    cleErreur: conceptionEcran.cleErreur,
    cleCourante: conceptionEcran.cleCourante,
  })
  // U3-900 (fondateur 29/08/2026, « ALL sizing goes through the new sizing
  // tool ») — l'attente (`sizing.attenteMoteur`) posée par applyLead /
  // applySiteProfile / syncBillEstimator est satisfaite par la recommandation
  // du moteur (`blocs.dimensionnement.recommandation` de la conception). Un
  // refus affiche son message FRANÇAIS EXACT et ne préremplit RIEN ; une frappe
  // manuelle gagne toujours. La DÉCISION est prise par la moitié pure
  // (`decisionSizing`) ; il ne reste ici que sa traduction en transition.
  const actionMoteur = decisionMoteur.action
  const recoMoteur = decisionMoteur.recommandation ?? null
  const motifMoteurServeur = decisionMoteur.motif ?? null
  useEffect(() => {
    // dispatch SYNCHRONE dans l'effet, idiome MAISON (ProductTour.jsx,
    // Avatar.jsx, FollowToggle.jsx…) : la valeur arrive d'un aller-retour
    // réseau DÉJÀ asynchrone, et la différer encore d'une microtâche
    // n'ajouterait qu'un tour de boucle. Aucune de ces valeurs n'est relue
    // dans le MÊME rendu.
    if (actionMoteur === 'appliquer') {
      dispatchSizing({ type: 'MOTEUR_A_REPONDU', recommandation: recoMoteur })
    } else if (actionMoteur === 'refuser') {
      dispatchSizing({ type: 'MOTEUR_A_REFUSE', motif: motifMoteurServeur })
    } else if (actionMoteur === 'abandonner') {
      // Une frappe manuelle a gagné : l'attente se referme sans rien appliquer.
      dispatchSizing({ type: 'MOTEUR_A_REPONDU' })
    }
  }, [actionMoteur, recoMoteur, motifMoteurServeur]) // eslint-disable-line react-hooks/exhaustive-deps -- dispatchSizing : dispatch de useReducer (stable), reçu du ctx (D-ENF22)
  const etudeHoraireAnnuel = etudeHoraireDonnees?.etude?.annuel || null
  const etudeHoraireSourceServeur = !!etudeHoraireAnnuel
  const etudeHoraireAnnuelAvec = etudeHoraireDonneesPourAvec?.etude?.annuel || null
  const etudeHoraireLignes = useMemo(
    () => lignesAffichables(etudeHoraireDonnees?.dimensionnement),
    [etudeHoraireDonnees])
  // La source de la consommation (« estimation ») est dite par les phrases du
  // moteur (`notes`), plus par l'étiquette de l'aperçu horaire.
  const etudeHoraireSourceLabel = null
  const etudeHoraireFalaise = useMemo(
    () => falaiseAffichable(etudeHoraireDonnees?.dimensionnement),
    [etudeHoraireDonnees])
  const etudeHoraireGlitch = useMemo(
    () => glitchAnnuel(etudeHoraireDonnees?.etude),
    [etudeHoraireDonnees])
  // La décomposition mensuelle de la consommation estimée n'est pas dans la
  // conception : le bloc ne s'affiche pas (jamais un chiffre d'une autre source).
  const etudeHoraireEstimationConso = null
  const [ligneStockageOuverte, setLigneStockageOuverte] = useState(null)

  // CJ2b / AGEN11 — chiffres AFFICHÉS dans le bloc « Aperçu de la Simulation »
  // (Production / Économies / ROI) : la conception du moteur unique seule.
  // Rien de servi ⇒ rien d'affiché.
  const valeursServies = conceptionEcran.conception?.valeurs || {}
  const apercuProductionKwh = chiffres?.productionSans ?? null
  // ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — deux options de productions
  // DIFFÉRENTES : l'option AVEC a SA production. `null` sinon : la carte unique.
  const apercuProductionKwhAvec = (chiffres && valeursServies.sans && valeursServies.avec
    && chiffres.productionAvec !== chiffres.productionSans) ? chiffres.productionAvec : null
  const apercuEcoSans = chiffres?.ecoSans ?? null
  // CJ2b — le moteur dit, POUR LA TAILLE CHIFFRÉE (le kWc de l'option avec de la
  // MÊME conception), si l'option batterie est électriquement livrable ; sinon
  // les cartes « Avec batterie » affichent la raison, aucun montant.
  const kwcAvecServi = (valeursServies.avec || valeursServies.sans)?.puissance_kwc?.valeur ?? null
  const verdictBatterieServeur = etudeHoraireAnnuelAvec
    ? verdictBatteriePourTaille(lignesAffichables(etudeHoraireDonneesPourAvec?.dimensionnement), kwcAvecServi)
    : null
  const batterieInvendableServeur = verdictBatterieServeur
    ? !verdictBatterieServeur.vendable : false
  // E7d (CI e2e figures-parite) — les deux options montrées, la conception n'en sert
  // qu'une (nombre de panneaux imposé : le moteur chiffre une option) : l'option avec
  // batterie n'est pas chiffrée — l'écran le DIT, jamais les chiffres de l'option sans.
  const apercuAvecAbsent = chiffres && showSans && showAvec && !valeursServies.avec
    ? 'Option avec batterie non chiffrée pour ce nombre de panneaux : le moteur chiffre une seule option '
      + 'quand le nombre de panneaux est imposé. Enregistrez le devis pour recalculer les deux options.'
    : null
  const apercuEcoAvec = batterieInvendableServeur || apercuAvecAbsent ? null : (chiffres?.ecoAvec ?? null)
  // AGEN11 — le payback SERVI par option (celui du PDF, sur le devis de
  // référence de la conception rangée) ; absent ⇒ « N/A », jamais recalculé.
  // E7d (M1) — le payback de l'APERÇU, calculé sur le TTC des lignes de l'écran ;
  // sans prix sur les lignes : « après enregistrement » ; jamais celui d'un autre devis.
  // Au dixième, virgule française (règle unique de l'aperçu, `ApercuSimulation.ansFr`).
  // ACAL1204 — aucune ligne panneau (quantité > 0) dans l'option : jamais de retour
  // chiffré sur les lignes par défaut (onduleur seul) ; « à chiffrer ».
  const panneauxSans = comptePanneauxOption(lines, 'sans', produits)
  const panneauxAvec = comptePanneauxOption(lines, 'avec', produits)
  const chiffre = (total, v, panneaux) => (surApercu && panneaux > 0 && Number(total) > 0 && v != null
    ? formatNumber(v, { decimals: 1 }) : null)
  const apercuPaybackSans = chiffre(totals?.totalSans, chiffres?.paybackSans, panneauxSans)
  const apercuPaybackAvec = chiffre(totals?.totalAvec, chiffres?.paybackAvec, panneauxAvec)
  const paybackAbsent = (total, panneaux) => (!(panneaux > 0) ? 'à chiffrer : ajoutez les panneaux'
    : !(Number(total) > 0) ? 'après enregistrement'
      : conceptionEcran.chargement ? 'calcul en cours…' : 'N/A')
  const apercuPaybackSansAbsent = paybackAbsent(totals?.totalSans, panneauxSans)
  const apercuPaybackAvecAbsent = paybackAbsent(totals?.totalAvec, panneauxAvec)
  const apercuPaybackSansJamais = false
  const apercuPaybackAvecJamais = false
  // L'état de l'aperçu servi, lu par la carte : `modele` (« conception »,
  // « refus » avec son message), `chargement` (« Calcul en cours »). Un refus
  // est TOUJOURS dit (sa phrase et son champ), jamais remplacé par un autre calcul.
  const refusConception = refusDesigne
    ? (refusDesigne.message || 'Le moteur n’a pas pu calculer la conception.')
    : conceptionEcran.erreur
  const modeleServi = refusDesigne ? 'refus' : chiffres ? 'conception' : refusConception ? 'refus' : null
  const roi = (modeleServi || conceptionEcran.chargement)
    ? { modele: modeleServi, chargement: conceptionEcran.chargement, message: refusConception || null,
        champ: refusDesigne?.champ || conceptionEcran.champErreur || null, reessayer: conceptionEcran.reessayer,
        surApercu }
    : null

  // QJR35 — sans facture réelle ni chiffre servi, un chiffre affiché est étiqueté « exemple ».
  const apercuEstimationExemple = !facturesSaisies && !etudeHoraireSourceServeur && !chiffres
  // QJR426 (DR5) — même discriminant que la puce ci-dessus, porté sur la
  // VALEUR SIGNÉE des quatre cartes Économies/ROI : `apercu()` (puce
  // `PUCE_APERCU`) quand aucune donnée réelle n'appuie le chiffre, `moteur()`
  // (aucune puce) dès qu'une facture réelle ou un chiffre servi est là.
  const signerEcoOuRoi = (v) => (apercuEstimationExemple ? apercu(v) : moteur(v))

  // AGNR23 / E7d — le graphe sort de la MÊME réponse que les cartes : les 12
  // mois de l'étude de la conception (Σ = la carte) ; sinon aucun graphe.
  const chartData = useMemo(
    () => serieEconomiesMensuelles(etudeHoraireDonnees, etudeHoraireDonneesPourAvec, CHART_MONTHS),
    [etudeHoraireDonnees, etudeHoraireDonneesPourAvec])

  return {
    capaciteBatterieInconnue, consoAnnuelleReelle, facturesSaisies, moisNonSaisis, leadsListe,
    selectedLead, typeLeadEffectif, marcheSegment, bandeauSegment, rappelIce, rappelIceAcceptation, changerTypeLead, roi,
    villeCalculLead, etudeHoraireCorps, etudeHoraireDonnees, etudeHoraireChargement,
    etudeHoraireErreur, etudeHoraireAnnuel, etudeHoraireSourceServeur, etudeHoraireAnnuelAvec,
    etudeHoraireLignes, etudeHoraireSourceLabel, etudeHoraireFalaise, etudeHoraireGlitch,
    etudeHoraireEstimationConso, ligneStockageOuverte, setLigneStockageOuverte,
    apercuProductionKwh, apercuProductionKwhAvec, apercuEcoSans, verdictBatterieServeur,
    batterieInvendableServeur, apercuEcoAvec, apercuPaybackSans, apercuPaybackAvec, apercuPaybackSansJamais,
    apercuPaybackAvecJamais, signerEcoOuRoi, chartData, apercuPaybackSansAbsent, apercuPaybackAvecAbsent,
    apercuAvecAbsent,
  }
}

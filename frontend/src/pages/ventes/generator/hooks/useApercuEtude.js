// SPL51 — LES DÉRIVATIONS D'APERÇU ET D'ÉTUDE HORAIRE, déplacées telles
// quelles de DevisGenerator.jsx : valeurs différées, conso réelle / écran,
// lead prioritaire (bandeau de segment, rappel ICE), conception servie (AGEN11), corps
// et données de l'étude horaire (`useSizingMoteur`, effet de décision),
// `etudeHoraire*`, `apercu*` / `payback*`, `signerEcoOuRoi`, `chartData`.
// Corps verbatim ; `ctx` porte, nom par nom, ce que le corps lit du
// composant. Appelé à la MÊME position (ordre des hooks inchangé).
import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import crmApi from '../../../../api/crmApi'
import { toast } from '../../../../ui/confirm'
import {
  CHART_MONTHS, comptePanneauxOption,
  batteryKwhFromLines, batteryCapaciteInconnue,
} from '../../../../features/ventes/solar'
import {
  appartientAuPanierAvec, isBattery, texteClassement,
} from '../../../../features/ventes/calc/classification.js'
import { consoAnnuelleDepuisFactures } from '../../../../features/ventes/calc/tarifs.js'
import {
  construireCorpsPreview, etiquetteSource, lignesAffichables,
  useEtudeHorairePreview, verdictBatteriePourTaille,
  falaiseAffichable, glitchAnnuel,
  estimationConsoAffichable,
} from '../../../../features/ventes/etudeHorairePreview'
import { batteriesDesLignes } from '../../../../features/ventes/etudeHorairePreviewPur'
import { toucheNbPanneauxPourComposition } from '../../../../features/ventes/quote/sizingReducer'
import { useSizingMoteur } from '../../../../features/ventes/quote/hooks/useSizingMoteur'
import { moteur, apercu } from '../../../../features/ventes/quote/valeur'
import { villeEffectiveLead } from '../../../../features/ventes/quote/ecranDefauts.js'
import { consommationImposeeDeEtat } from '../../../../features/ventes/quote/etatDevis.js'
import { chiffresConception, corpsApercuConception, useConceptionEcran } from './useConceptionEcran'

export function useApercuEtude(ctx) {
  const {
    lines, kwpLignes, kwpAvec, realBillMode, realBillKwh,
    realBillMad, distributeur, baremeSociete, provenanceMois, leadDuDevis, leads,
    leadId, modeInstallation, clientsConnus, clientId, confirm, editId, fHiver, fEte,
    sizing, dispatchSizing, produits, monthly, realBillSaisi, distributeurChoisi, consoStockee,
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
  const corpsConception = corpsApercuConception({
    leadId, modeInstallation, fHiver, fEte, consommation: consommationImposee,
    nbPanneaux: comptePanneauxOption(lines, 'sans', produits),
  })
  const conceptionEcran = useConceptionEcran({ leadId, corps: corpsConception })
  const chiffres = chiffresConception(conceptionEcran.conception)
  // Le payback est celui SERVI avec la version rangée (devis de référence, la
  // fonction du PDF) : un aperçu n'en porte aucun (rien n'est encore chiffré).
  const paybackServi = chiffresConception(conceptionEcran.servie)

  // CJ2b — ORDRE FONDATEUR : « on ne voit ni l'économie réelle calculée, ni
  // les données PVGIS — cette donnée devrait être comparée à la courbe de
  // consommation ». Résidentiel UNIQUEMENT : appelle le moteur horaire
  // serveur (intégration PVGIS réelle × consommation réelle, mois par mois)
  // (jumeau serveur de la conception, survivant tant que l'écran le lit). `null` = rien à ancrer (aucune facture,
  // aucun devis) : aucun appel réseau (règle d'honnêteté — on omet, on
  // n'invente pas).
  // RGEN7 — batteries des lignes « avec » liées à un produit : le serveur lit leur fiche (capacité utile, rendement).
  const batteriesAvec = batteriesDesLignes(lines,
    l => isBattery(texteClassement(l, produits)) && appartientAuPanierAvec(l, produits))
  const etudeHoraireCorps = modeInstallation === 'residentiel'
    ? construireCorpsPreview({
        modeInstallation,
        editId,
        leadId,
        fHiver,
        fEte,
        eteDifferente: !!fEte && Number(fEte) > 0,
        ville: villeCalculLead,
        raccordement: selectedLead?.raccordement || '',
        // QJR568 — le kWc FACTURÉ par les lignes, pas la seule cible.
        kwp: kwpLignes,
        batterieKwh: batteryKwhFromLines(lines, produits),
        batteries: batteriesAvec,
      })
    : null
  // L-2OPT — l'étude horaire de la branche AVEC porte SON PROPRE kWc. Le corps
  // ci-dessus décrit la branche SANS (`kwp`) ; l'interroger avec les batteries
  // de la composition AVEC produisait une chimère (kWc sans + batteries avec).
  // `null` tant que rien ne diverge ⇒ AUCUN second appel réseau et l'écran lit
  // le corps unique comme hier.
  const etudeHoraireCorpsAvec = (modeInstallation === 'residentiel'
      && kwpAvec !== kwpLignes)
    ? construireCorpsPreview({
        modeInstallation,
        editId,
        leadId,
        fHiver,
        fEte,
        eteDifferente: !!fEte && Number(fEte) > 0,
        ville: villeCalculLead,
        raccordement: selectedLead?.raccordement || '',
        kwp: kwpAvec,
        batterieKwh: batteryKwhFromLines(lines, produits),
        batteries: batteriesAvec,
      })
    : null
  // QJR99 — `useSizingMoteur` (QJR90) enrobe `useEtudeHorairePreview` : il rend
  // les mêmes données réseau (aucun appel supplémentaire) PLUS une `decision`
  // déjà prise par sa moitié pure. La garde de réponse PÉRIMÉE y couvre les
  // DEUX branches : l'ancienne comparaison de clé en ligne ne valait que pour
  // `donnees`, si bien que la branche d'ÉCHEC refermait l'attente et épinglait
  // le refus d'une facture qu'on venait de remplacer (correctif intentionnel).
  const {
    decision: decisionMoteur,
    donnees: etudeHoraireDonnees,
    chargement: etudeHoraireChargement,
    erreur: etudeHoraireErreur,
  } = useSizingMoteur(etudeHoraireCorps, {
    attente: sizing.attenteMoteur,
    toucheNbPanneaux: toucheNbPanneauxPourComposition(sizing),
  })
  const { donnees: etudeHoraireDonneesAvec } =
    useEtudeHorairePreview(etudeHoraireCorpsAvec)
  // U3-900 (fondateur 29/08/2026, « ALL sizing goes through the new sizing
  // tool ») — LE SEUL remplaçant du repli `estimerPanneaux` (panneaux/900 MAD,
  // supprimé du backend le même jour, cf. apps/ventes/dimensionnement.py).
  // L'attente (`sizing.attenteMoteur`) est posée par applyLead /
  // applySiteProfile / syncBillEstimator quand le résidentiel ne se dimensionne
  // plus à l'écran : la recommandation du moteur horaire SERVEUR
  // (`etudeHoraireDonnees`, déjà interrogé dès que fHiver/lead est posé — AUCUN
  // appel réseau supplémentaire) la satisfait dès qu'elle répond. Un dry-run qui
  // décline (ville manquante, catalogue incomplet…) affiche son message
  // FRANÇAIS EXACT et ne préremplit RIEN — un vide honnête plutôt qu'une
  // supposition sur 900 DH (règle #4 CLAUDE.md). Une frappe manuelle gagne
  // toujours, comme partout ailleurs sur ce champ.
  //
  // QJR99 — la DÉCISION (appliquer / refuser / abandonner / attendre) est prise
  // par `useSizingMoteur` ; il ne reste ici que sa traduction en transition. La
  // garde de réponse périmée, les deux formes de motif (F4 :
  // `avertissements[0]` PUIS `dimensionnement.motivation`, rendues VERBATIM) et
  // la priorité de la frappe manuelle sont toutes dans la moitié pure, testée.
  const actionMoteur = decisionMoteur.action
  const recoMoteur = decisionMoteur.recommandation ?? null
  const motifMoteurServeur = decisionMoteur.motif ?? null
  useEffect(() => {
    // dispatch SYNCHRONE dans l'effet, idiome MAISON (ProductTour.jsx,
    // Avatar.jsx, FollowToggle.jsx…) : la valeur arrive d'un aller-retour
    // réseau DÉJÀ asynchrone (`useEtudeHorairePreview`), et la différer encore
    // d'une microtâche n'ajouterait qu'un tour de boucle entre la réponse et
    // l'affichage. Aucune de ces valeurs n'est relue dans le MÊME rendu.
     
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
  // Réponse serveur à lire pour l'option AVEC. DIVERGENT : uniquement la
  // sienne — jamais l'étude du kWc SANS, ce qui recréerait exactement le croisement corrigé ici. NON
  // divergent : le corps unique, comme hier.
  const etudeHoraireDonneesPourAvec = etudeHoraireCorpsAvec
    ? etudeHoraireDonneesAvec
    : etudeHoraireDonnees
  const etudeHoraireAnnuelAvec =
    etudeHoraireDonneesPourAvec?.etude?.annuel || null
  const etudeHoraireLignes = useMemo(
    () => lignesAffichables(etudeHoraireDonnees?.dimensionnement),
    [etudeHoraireDonnees])
  // Lignes de dimensionnement à interroger pour le VERDICT batterie : celles
  // de l'étude de la branche AVEC (son kWc), jamais celles du kWc SANS.
  const etudeHoraireLignesAvec = useMemo(
    () => lignesAffichables(etudeHoraireDonneesPourAvec?.dimensionnement),
    [etudeHoraireDonneesPourAvec])
  const etudeHoraireSourceLabel = etudeHoraireDonnees?.consommation
    ? etiquetteSource(etudeHoraireDonnees.consommation.source)
    : null
  // L-FRONT lot 4 — falaise tarifaire (palier visé + meilleure combinaison du
  // balayage qui y passe), résumé annuel des impulsions équipements (glitch)
  // et décomposition mensuelle de la consommation estimée : les trois `null`
  // quand le moteur n'a rien calculé (mode non résidentiel, Z2, aucun
  // équipement concentrable) — jamais un bloc affiché sur un chiffre absent.
  const etudeHoraireFalaise = useMemo(
    () => falaiseAffichable(etudeHoraireDonnees?.dimensionnement),
    [etudeHoraireDonnees])
  const etudeHoraireGlitch = useMemo(
    () => glitchAnnuel(etudeHoraireDonnees?.etude),
    [etudeHoraireDonnees])
  const etudeHoraireEstimationConso = useMemo(
    () => estimationConsoAffichable(etudeHoraireDonnees?.estimation_conso),
    [etudeHoraireDonnees])
  const [ligneStockageOuverte, setLigneStockageOuverte] = useState(null)

  // CJ2b / AGEN11 — chiffres AFFICHÉS dans le bloc « Aperçu de la Simulation »
  // (Production / Économies / ROI) : la conception du moteur unique d'abord,
  // l'étude horaire servie ensuite (jumeau serveur survivant, ADEV152) — jamais
  // un calcul du navigateur. Rien de servi ⇒ rien d'affiché.
  const apercuProductionKwh = chiffres?.productionSans
    ?? (etudeHoraireSourceServeur ? etudeHoraireAnnuel.production_kwh : null)
  // ERR-QAH-FIG-EDITION-ETUDE-LIVE-VS-DOCUMENT — champs PV DIVERGENTS : l'option
  // AVEC a SA production. `null` hors divergence : la carte unique d'hier.
  const apercuProductionKwhAvec = etudeHoraireCorpsAvec
    ? (chiffres?.productionAvec ?? etudeHoraireAnnuelAvec?.production_kwh ?? null)
    : null
  const apercuEcoSans = chiffres?.ecoSans
    ?? (etudeHoraireSourceServeur ? etudeHoraireAnnuel.economie_sans_mad : null)
  // CJ2b — ORDRE FONDATEUR (« l'omission honnête, jamais un zéro inventé ») :
  // le moteur dit, POUR LA TAILLE CHIFFRÉE, si l'option batterie est
  // électriquement livrable. Quand elle ne l'est pas, les cartes « Avec
  // batterie » n'affichent AUCUN montant — elles affichent la raison.
  // L-2OPT — verdict lu sur l'étude de la branche AVEC, à SON kWc (`kwpAvec`).
  const verdictBatterieServeur = etudeHoraireAnnuelAvec
    ? verdictBatteriePourTaille(etudeHoraireLignesAvec, kwpAvec)
    : null
  const batterieInvendableServeur = verdictBatterieServeur
    ? !verdictBatterieServeur.vendable : false
  const apercuEcoAvec = batterieInvendableServeur ? null
    : (chiffres?.ecoAvec ?? etudeHoraireAnnuelAvec?.economie_avec_mad ?? null)
  // AGEN11 — le payback SERVI par option (celui du PDF, sur le devis de
  // référence de la conception rangée) ; absent ⇒ « N/A », jamais recalculé.
  const apercuPaybackSans = paybackServi?.paybackSans ?? null
  const apercuPaybackAvec = paybackServi?.paybackAvec ?? null
  const apercuPaybackSansJamais = false
  const apercuPaybackAvecJamais = false
  // L'état de l'aperçu servi, lu par la carte : `modele` (« conception »,
  // « horaire », « refus » avec son message), `chargement` (« Calcul en cours »).
  const refusConception = conceptionEcran.conception?.etat === 'refus'
    ? (conceptionEcran.conception.refus?.message || 'Le moteur n’a pas pu calculer la conception.')
    : conceptionEcran.erreur
  const modeleServi = chiffres ? 'conception' : etudeHoraireSourceServeur ? 'horaire' : refusConception ? 'refus' : null
  const roi = (modeleServi || conceptionEcran.chargement)
    ? { modele: modeleServi, chargement: conceptionEcran.chargement, message: refusConception || null }
    : null

  // QJR35 — sans facture réelle ni chiffre servi, un chiffre affiché est étiqueté « exemple ».
  const apercuEstimationExemple = !facturesSaisies && !etudeHoraireSourceServeur && !chiffres
  // QJR426 (DR5) — même discriminant que la puce ci-dessus, porté sur la
  // VALEUR SIGNÉE des quatre cartes Économies/ROI : `apercu()` (puce
  // `PUCE_APERCU`, strictement le même texte que le `badge` littéral
  // remplacé) quand aucune donnée réelle n'appuie le chiffre, `moteur()`
  // (aucune puce, comme aujourd'hui) dès qu'une facture réelle ou l'étude
  // horaire serveur est là — rendu byte-identique à l'ancien `badge=`.
  const signerEcoOuRoi = (v) => (apercuEstimationExemple ? apercu(v) : moteur(v))

  const chartData = useMemo(() => {
    // AGNR23 — le graphe sort du MODÈLE QUI PORTE LES CARTES : quand l'étude
    // horaire serveur répond, ses 12 mois (Σ = la carte).
    const moisServeur = etudeHoraireDonnees?.etude?.mois
    if (etudeHoraireSourceServeur && Array.isArray(moisServeur) && moisServeur.length === 12) {
      const moisAvec = etudeHoraireDonneesPourAvec?.etude?.mois
      const avec = Array.isArray(moisAvec) && moisAvec.length === 12 ? moisAvec : moisServeur
      return moisServeur.map((m, i) => ({
        month: CHART_MONTHS[i],
        facture: Math.round(Number(m.facture_avant_mad) || 0),
        ecoSans: Math.round(Number(m.economie_sans_mad) || 0),
        ecoAvec: Math.round(Number(avec[i]?.economie_avec_mad) || 0),
      }))
    }
    // AGEN11 — plus de courbe du miroir local : sans étude servie, aucun graphe.
    return []
  }, [etudeHoraireSourceServeur, etudeHoraireDonnees, etudeHoraireDonneesPourAvec])

  return {
    capaciteBatterieInconnue, consoAnnuelleReelle, facturesSaisies, moisNonSaisis, leadsListe,
    selectedLead, typeLeadEffectif, marcheSegment, bandeauSegment, rappelIce, rappelIceAcceptation, changerTypeLead, roi,
    villeCalculLead, etudeHoraireCorps, etudeHoraireDonnees, etudeHoraireChargement,
    etudeHoraireErreur, etudeHoraireAnnuel, etudeHoraireSourceServeur, etudeHoraireAnnuelAvec,
    etudeHoraireLignes, etudeHoraireSourceLabel, etudeHoraireFalaise, etudeHoraireGlitch,
    etudeHoraireEstimationConso, ligneStockageOuverte, setLigneStockageOuverte,
    apercuProductionKwh, apercuProductionKwhAvec, apercuEcoSans, verdictBatterieServeur,
    batterieInvendableServeur, apercuEcoAvec, apercuPaybackSans, apercuPaybackAvec, apercuPaybackSansJamais,
    apercuPaybackAvecJamais, signerEcoOuRoi, chartData, paybackServi,
  }
}

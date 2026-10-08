// SPL51 — LES DÉRIVATIONS D'APERÇU ET D'ÉTUDE HORAIRE, déplacées telles
// quelles de DevisGenerator.jsx : valeurs différées, conso réelle / écran,
// lead prioritaire (bandeau de segment, rappel ICE), `roi` / `roiAvec`, corps
// et données de l'étude horaire (`useSizingMoteur`, effet de décision),
// `etudeHoraire*`, `apercu*` / `payback*`, `signerEcoOuRoi`, `chartData`.
// Corps verbatim ; `ctx` porte, nom par nom, ce que le corps lit du
// composant. Appelé à la MÊME position (ordre des hooks inchangé).
import { useDeferredValue, useEffect, useMemo, useState } from 'react'
import crmApi from '../../../../api/crmApi'
import { toast } from '../../../../ui/confirm'
import {
  CHART_MONTHS, computeROI,
  paybackMoteurHoraire, inverterCostFromLines, appartientAuPanierSans,
  appartientAuPanierAvec,
  batteryKwhFromLines, batteryCapaciteInconnue,
  consoAnnuelleDepuisFactures,
  productibleForCity,
} from '../../../../features/ventes/solar'
import {
  construireCorpsPreview, etiquetteSource, lignesAffichables,
  useEtudeHorairePreview, verdictBatteriePourTaille,
  falaiseAffichable, glitchAnnuel,
  estimationConsoAffichable,
} from '../../../../features/ventes/etudeHorairePreview'
import { toucheNbPanneauxPourComposition } from '../../../../features/ventes/quote/sizingReducer'
import { useSizingMoteur } from '../../../../features/ventes/quote/hooks/useSizingMoteur'
import { moteur, apercu } from '../../../../features/ventes/quote/valeur'
import { villeEffectiveLead } from '../../../../features/ventes/quote/ecranDefauts.js'

export function useApercuEtude(ctx) {
  const {
    monthly, lines, totals, kwp, kwpLignes, kwpAvec, dayUsage, realBillMode, realBillKwh,
    realBillMad, distributeur, baremeSociete, provenanceMois, realBillSaisi, leadDuDevis, leads,
    leadId, modeInstallation, clientsConnus, clientId, confirm, quoteLogic, editId, fHiver, fEte,
    sizing, dispatchSizing,
  } = ctx

  // Simulation/graphique en VALEURS DIFFÉRÉES : la frappe et les bascules
  // restent instantanées (les champs gardent leurs valeurs exactes — rien
  // n'est perdu ni arrondi), le recalcul lourd + recharts suit d'un souffle.
  const dMonthly = useDeferredValue(monthly)
  const dLines = useDeferredValue(lines)
  const dTotals = useDeferredValue(totals)
  const dKwp = useDeferredValue(kwp)
  const dKwpLignes = useDeferredValue(kwpLignes)
  const dKwpAvec = useDeferredValue(kwpAvec)
  const dDayUsage = useDeferredValue(dayUsage)

  // BAT5DEF (26/08/2026) — au moins une ligne batterie n'a pas de kWh lisible
  // dans sa désignation : `batteryKwhFromLines` ne lui compte plus un défaut
  // fabriqué de 5 kWh (RÈGLE FONDATEUR « zéro chiffre inventé »), donc la
  // capacité utilisée en aval (ROI, étude horaire) peut être SOUS-estimée.
  // Signalé à l'écran plutôt que tu — jamais un chiffre qu'on tairait.
  const capaciteBatterieInconnue = useMemo(
    () => batteryCapaciteInconnue(dLines), [dLines])

  // QF4/QF5 — consommation annuelle RÉELLE dérivée de la facture/kWh du
  // client (barème par tranche du distributeur choisi). Alimente à la fois
  // etude_params (à l'enregistrement) et l'aperçu écran (roi ci-dessous) —
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

  // AGNR24 — LA consommation que l'écran ENREGISTRE, un seul sélecteur :
  // même cascade que `entreesReellesEcran` (usePersistanceDevis) — saisie
  // réelle de la session → conso stockée relue (`?edit=` : mode kWh non
  // retouché) → 12 factures réelles au barème → facture réelle. L'aperçu
  // (`computeROI`) la reçoit : jamais « estimation » quand le corps
  // enregistré porte une conso.
  const consoEcran = (() => {
    if (realBillSaisi && consoAnnuelleReelle > 0) return consoAnnuelleReelle
    if (!realBillSaisi && realBillMode === 'kwh' && consoAnnuelleReelle > 0) return consoAnnuelleReelle
    if (facturesSaisies) {
      const derivee = consoAnnuelleDepuisFactures(monthly.map(v => parseFloat(v) || 0), distributeur,
        baremeSociete?.tranches, baremeSociete?.chargesFixes)
      if (derivee > 0) return derivee
    }
    return consoAnnuelleReelle > 0 ? consoAnnuelleReelle : null
  })()

  // Lead prioritaire résolu tôt : le calcul ROI ci-dessous lit sa ville
  // (productible par ville) — doit être déclaré avant le useMemo (pas de TDZ).
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
  const rappelIce = ['commercial', 'industriel'].includes(modeInstallation)
    && Array.isArray(identiteEntreprise?.manquants)
    && identiteEntreprise.manquants.some(m => m === 'ice' || m === 'raison_sociale')
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

  const roi = useMemo(() => {
    if (dKwp <= 0 || !dMonthly.some(v => v > 0)) return null
    return computeROI({
      kwp: dKwp,
      factures: dMonthly.map(v => parseFloat(v) || 0),
      dayUsagePct: parseInt(dDayUsage) || 50,
      totalSans: dTotals.totalSans,
      totalAvec: dTotals.totalAvec,
      batteryKwh: batteryKwhFromLines(dLines),
      // Q1 (fondateur 20/08/2026) — lignes RÉELLES pour la provision de
      // remplacement onduleur (prix TTC de la ligne, jamais 8 % forfaitaires).
      lines: dLines,
      kwhPrice: quoteLogic.kwhPrice,
      efficiency: quoteLogic.efficiency,
      // QF5 — bascule sur le modèle « deux factures » par tranche (parité
      // PDF) dès qu'une consommation réelle + un distributeur sont connus.
      // AGNR24 — la conso ENREGISTRÉE (`consoEcran`), jamais la seule saisie.
      consoAnnuelleKwh: consoEcran,
      utility: distributeur,
      bareme: baremeSociete,
      // QX38 — productible CANONIQUE PVGIS par ville (source unique alignée
      // avec le PDF/web) ; override société si renseigné ≠ 1600.
      productible: productibleForCity(
        (selectedLead?.ville_effective ?? selectedLead?.ville) || '', quoteLogic.productible),
    })
  }, [dKwp, dMonthly, dDayUsage, dTotals, dLines, quoteLogic,
    consoEcran, distributeur, selectedLead, baremeSociete])

  // L-2OPT — miroir local de `roi` recalculé AU kWc DE LA BRANCHE AVEC. `null`
  // dès que rien ne diverge (`kwpAvec === kwp`) : l'écran retombe alors mot
  // pour mot sur `roi`, aucun second calcul, comportement d'hier. Quand les
  // deux optimiseurs ont réellement rendu deux tailles, seuls les champs
  // « avec » de CE résultat sont lus (l'option sans garde `roi`).
  const roiAvec = useMemo(() => {
    // QJR568 — « non divergent » se juge contre le kWc FACTURÉ des lignes
    // (`kwpAvec` y retombe quand les options ne divergent pas).
    if (dKwpAvec === dKwp || dKwpAvec === dKwpLignes) return null
    if (dKwpAvec <= 0 || !dMonthly.some(v => v > 0)) return null
    return computeROI({
      kwp: dKwpAvec,
      factures: dMonthly.map(v => parseFloat(v) || 0),
      dayUsagePct: parseInt(dDayUsage) || 50,
      totalSans: dTotals.totalSans,
      totalAvec: dTotals.totalAvec,
      batteryKwh: batteryKwhFromLines(dLines),
      lines: dLines,
      kwhPrice: quoteLogic.kwhPrice,
      efficiency: quoteLogic.efficiency,
      consoAnnuelleKwh: consoEcran,
      utility: distributeur,
      bareme: baremeSociete,
      productible: productibleForCity(
        (selectedLead?.ville_effective ?? selectedLead?.ville) || '', quoteLogic.productible),
    })
  }, [dKwpAvec, dKwp, dKwpLignes, dMonthly, dDayUsage, dTotals, dLines, quoteLogic,
    consoEcran, distributeur, selectedLead, baremeSociete])

  // QJR586 — la ville de CALCUL du lead sélectionné (servie par le serveur).
  const villeCalculLead = villeEffectiveLead(selectedLead)


  // Source des chiffres « avec batterie » du miroir local : `roiAvec` quand
  // les deux optimiseurs divergent, sinon `roi` (identique par construction).
  const roiPourAvec = roiAvec || roi

  // CJ2b — ORDRE FONDATEUR : « on ne voit ni l'économie réelle calculée, ni
  // les données PVGIS — cette donnée devrait être comparée à la courbe de
  // consommation ». Résidentiel UNIQUEMENT : appelle le moteur horaire
  // serveur (intégration PVGIS réelle × consommation réelle, mois par mois)
  // au lieu de ne montrer QUE le miroir local `roi` ci-dessus (conservé
  // intact comme repli hors-ligne). `null` = rien à ancrer (aucune facture,
  // aucun devis) : aucun appel réseau (règle d'honnêteté — on omet, on
  // n'invente pas).
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
        batterieKwh: batteryKwhFromLines(lines),
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
        batterieKwh: batteryKwhFromLines(lines),
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
  }, [actionMoteur, recoMoteur, motifMoteurServeur]) // eslint-disable-line react-hooks/exhaustive-deps -- dispatchSizing : dispatch de useReducer (stable), reçu du ctx
  // Le serveur GAGNE dès qu'il a répondu (etude non nul) : `roi` reste le
  // seul chiffre affiché tant que la réponse n'est pas là (ou a échoué).
  const etudeHoraireAnnuel = etudeHoraireDonnees?.etude?.annuel || null
  const etudeHoraireSourceServeur = !!etudeHoraireAnnuel
  // Réponse serveur à lire pour l'option AVEC. DIVERGENT : uniquement la
  // sienne — tant qu'elle n'est pas revenue, l'écran retombe sur le miroir
  // local `roiAvec` (au bon kWc) plutôt que de ré-afficher l'étude du kWc
  // SANS, ce qui recréerait exactement le croisement corrigé ici. NON
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

  // CJ2b — chiffres AFFICHÉS dans le bloc « Aperçu de la Simulation »
  // (Production / Économies / ROI) : le serveur horaire gagne dès qu'il a
  // répondu, sinon repli SUR `roi` tel quel (miroir local inchangé — c'est
  // uniquement la SOURCE de ce qui est montré à l'écran qui bascule). Le
  // payback affiché en mode serveur est une simple division coût réel des
  // lignes / économie réelle serveur — jamais un chiffre inventé.
  const apercuProductionKwh = etudeHoraireSourceServeur
    ? etudeHoraireAnnuel.production_kwh : roi?.production_annuelle_kwh
  const apercuEcoSans = etudeHoraireSourceServeur
    ? etudeHoraireAnnuel.economie_sans_mad : roi?.eco_annuelle_sans
  // CJ2b — ORDRE FONDATEUR (« l'omission honnête, jamais un zéro inventé ») :
  // le moteur dit, POUR LA TAILLE CHIFFRÉE, si l'option batterie est
  // électriquement livrable. Quand elle ne l'est pas, les cartes « Avec
  // batterie » n'affichent AUCUN montant — elles affichent la raison. C'est le
  // trou catalogue RÉEL exhumé par CJ2a (panneau 710 Wc + hybride 5 kW
  // monophasé : Isc 18,6 A > 17,0 A) : sans cette garde, l'écran promettait au
  // vendeur l'économie d'une installation qu'on ne peut pas livrer.
  // `null` (le moteur ne dit rien sur cette taille) ⇒ comportement d'avant.
  // L-2OPT — verdict + économie « avec » lus sur l'étude de la branche AVEC,
  // à SON kWc (`kwpAvec`). Non divergent : mêmes lignes, même taille, même
  // résultat qu'hier.
  const verdictBatterieServeur = etudeHoraireAnnuelAvec
    ? verdictBatteriePourTaille(etudeHoraireLignesAvec, kwpAvec)
    : null
  const batterieInvendableServeur = verdictBatterieServeur
    ? !verdictBatterieServeur.vendable : false
  const apercuEcoAvec = etudeHoraireAnnuelAvec
    ? (batterieInvendableServeur ? null : etudeHoraireAnnuelAvec.economie_avec_mad)
    : roiPourAvec?.eco_annuelle_avec
  // ERR-QAH-FIG-PAYBACK-FORMULE-ECRAN — branche serveur : le payback du
  // MOTEUR (cashflow 25 ans QX39, `paybackMoteurHoraire`) sur l'économie
  // servie, jamais une division coût ÷ économie. Un cumul qui ne croise jamais
  // zéro s'affiche « Non rentabilisé sur 25 ans », jamais « 25 ans ».
  const paybackServeurSans = etudeHoraireSourceServeur
    ? paybackMoteurHoraire(totals.totalSans, apercuEcoSans, {
        annuel: etudeHoraireAnnuel,
        inverterReplaceCost: inverterCostFromLines(lines.filter(appartientAuPanierSans)),
      })
    : null
  const paybackServeurAvec = etudeHoraireAnnuelAvec
    ? paybackMoteurHoraire(totals.totalAvec, apercuEcoAvec, {
        annuel: etudeHoraireAnnuelAvec,
        rendementBatterie: etudeHoraireDonneesPourAvec?.etude?.rendement_batterie ?? null,
        stockage: batteryKwhFromLines(lines) > 0,
        inverterReplaceCost: inverterCostFromLines(lines.filter(appartientAuPanierAvec)),
      })
    : null
  const apercuPaybackSans = etudeHoraireSourceServeur
    ? (paybackServeurSans?.paybackYears ?? null)
    : roi?.payback_sans
  const apercuPaybackAvec = etudeHoraireAnnuelAvec
    ? (paybackServeurAvec?.paybackYears ?? null)
    : roiPourAvec?.payback_avec
  const apercuPaybackSansJamais = etudeHoraireSourceServeur
    ? !!paybackServeurSans?.jamaisRembourse : !!roi?.payback_sans_jamais
  const apercuPaybackAvecJamais = etudeHoraireAnnuelAvec
    ? !!paybackServeurAvec?.jamaisRembourse : !!roiPourAvec?.payback_avec_jamais

  // QJR35 — au montage (roi tourne dès dKwp>0 && dMonthly.some(v=>v>0), vrai
  // avec DEFAULT_MONTHLY_BILLS), les cartes Économies/ROI peuvent afficher un
  // chiffre dérivé du MIROIR LOCAL sans qu'aucune facture réelle ni étude
  // horaire serveur n'existe encore. Ni caché (le vendeur s'en sert comme
  // repère) ni remplacé par un autre chiffre — étiqueté. QJR89/QJR90 rendent
  // cette règle structurelle ; ceci est l'intérim minimal.
  const apercuEstimationExemple = !facturesSaisies && !etudeHoraireSourceServeur
  // QJR426 (DR5) — même discriminant que la puce ci-dessus, porté sur la
  // VALEUR SIGNÉE des quatre cartes Économies/ROI : `apercu()` (puce
  // `PUCE_APERCU`, strictement le même texte que le `badge` littéral
  // remplacé) quand aucune donnée réelle n'appuie le chiffre, `moteur()`
  // (aucune puce, comme aujourd'hui) dès qu'une facture réelle ou l'étude
  // horaire serveur est là — rendu byte-identique à l'ancien `badge=`.
  const signerEcoOuRoi = (v) => (apercuEstimationExemple ? apercu(v) : moteur(v))

  const chartData = useMemo(() => {
    // AGNR23 — le graphe sort du MODÈLE QUI PORTE LES CARTES : quand l'étude
    // horaire serveur répond, ses 12 mois (Σ = la carte) ; sinon `roi`.
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
    if (!roi) return []
    // L-2OPT — la courbe « avec batterie » suit le kWc de SA branche quand les
    // deux optimiseurs divergent (`roiAvec`), sinon `roi` (identique).
    const detailAvec = (roiAvec || roi).monthly_detail
    return roi.monthly_detail.map((d, i) => ({
      month: CHART_MONTHS[i],
      facture: d.facture,
      ecoSans: Math.round(d.eco_sans),
      ecoAvec: Math.round((detailAvec[i] ?? d).eco_avec),
    }))
  }, [roi, roiAvec, etudeHoraireSourceServeur, etudeHoraireDonnees, etudeHoraireDonneesPourAvec])

  return {
    capaciteBatterieInconnue, consoAnnuelleReelle, facturesSaisies, moisNonSaisis, leadsListe,
    selectedLead, typeLeadEffectif, marcheSegment, bandeauSegment, rappelIce, changerTypeLead, roi,
    villeCalculLead, etudeHoraireCorps, etudeHoraireDonnees, etudeHoraireChargement,
    etudeHoraireErreur, etudeHoraireAnnuel, etudeHoraireSourceServeur, etudeHoraireAnnuelAvec,
    etudeHoraireLignes, etudeHoraireSourceLabel, etudeHoraireFalaise, etudeHoraireGlitch,
    etudeHoraireEstimationConso, ligneStockageOuverte, setLigneStockageOuverte,
    apercuProductionKwh, apercuEcoSans, verdictBatterieServeur, batterieInvendableServeur,
    apercuEcoAvec, apercuPaybackSans, apercuPaybackAvec, apercuPaybackSansJamais,
    apercuPaybackAvecJamais, signerEcoOuRoi, chartData,
  }
}

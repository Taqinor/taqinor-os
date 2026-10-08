// SPL54 — LE BROUILLON LOCAL ET LA GARDE DE SORTIE, déplacés tels quels de
// DevisGenerator.jsx : `draftKey`, `draftSnapshot`, le prédicat `dirty`
// (EZ4, QJR581 : référence d'écran), `useDraftAutosave`, `useDirtyGuard`,
// brouillon périmé / proposable, `marquerEnregistre`, `handleRestoreDraft`.
// Corps verbatim ; `ctx` porte, nom par nom, ce que le corps lit du
// composant. Appelé à la MÊME position (ordre des hooks inchangé).
import { useEffect, useMemo, useState } from 'react'
import { toast } from '../../../../ui/confirm'
import { useDirtyGuard } from '../../../../ui/useDirtyGuard'
import { useDraftAutosave } from '../../../../ui/useDraftAutosave'
import { DEFAULT_MONTHLY_BILLS, TVA_STANDARD_DEFAUT } from '../../../../features/ventes/solar'
import { withKeys } from '../../../../features/ventes/quote/ligneFabrique.js'
import { profilCiVide } from '../../../../features/ventes/quote/profilCi'

export function useBrouillonEcran(ctx) {
  const {
    editId, leadId, clientId, dateValidite, scenario, recommendedChoice, note, fHiver, fEte,
    monthly, provenanceMois, distributeur, realBillMode, realBillMad, realBillKwh, realBillSaisi,
    distributeurChoisi, nbPanneaux, panelW, structureType, structureProduitId, dayUsage, lines,
    tauxTva, discountPct, multiMode, nombreProprietes, villaGroups, modeInstallation,
    consoMensuelle, categorieCommerciale, commercialAnswers, tensionRaccordement, profilCi,
    prixCible, remiseMax, accessoiresOnly, horsReseau, horsReseauTouched, pompeCv, pompeType,
    pompeAlim, pompeHmt, pompeDebit, pompeProfondeur, pompeDistance, farmRegion, farmCrop,
    farmSurfaceHa, farmIrrigation, ecoPompage, attestationAgricole, farmHmtStatic, farmHmtDrawdown,
    pompageSaisie, conditions, echeancierSaisie, tarifSaisie, ecoCi, captureReferenceJusqua,
    editDevis, setLeadId, setClientId, setDateValidite, dispatchSizing, setRecommendedChoice,
    setNote, setFHiver, setFEte, setMonthly, setConditions, setEcheancierSaisie, setTarifSaisie,
    setEcoCi, setProvenanceMois, setDistributeur, setRealBillMode, setRealBillMad, setRealBillKwh,
    setRealBillSaisi, setDistributeurChoisi, setDayUsage, setLines, linesInitialized, setTauxTva,
    setDiscountPct, setMultiMode, setNombreProprietes, setVillaGroups, setConsoMensuelle,
    setCategorieCommerciale, setCommercialAnswers, setProfilCi, setPrixCible, setRemiseMax,
    setAccessoiresOnly, setHorsReseau, setHorsReseauTouched, setPompeCv, setPompeType, setPompeHmt,
    setPompeDebit, setPompeProfondeur, setPompeDistance, setFarmRegion, setFarmCrop,
    setFarmSurfaceHa, setFarmIrrigation, setEcoPompage, setAttestationAgricole, setFarmHmtStatic,
    setFarmHmtDrawdown, setPompageSaisie,
  } = ctx

  // ── VX62 — Brouillon auto + garde de sortie ──
  // Le formulaire (2 300+ lignes, ~20 min de saisie) n'avait NI brouillon NI
  // garde : un onglet fermé/un swipe retour = tout perdu. On sauvegarde un
  // snapshot débouncé dans localStorage (clé scopée lead/client/édition), on
  // propose « Reprendre le brouillon » au montage, on purge au succès, et on
  // pose useDirtyGuard pour la fermeture d'onglet.
  const draftKey = editId
    ? `devis:edit:${editId}`
    : (leadId ? `devis:lead:${leadId}` : (clientId ? `devis:client:${clientId}` : 'devis:new'))
  // Snapshot des champs éditables saillants (les référentiels leads/clients/
  // produits ne sont jamais persistés — seulement la saisie de l'utilisateur).
  const draftSnapshot = useMemo(() => ({
    leadId, clientId, dateValidite, scenario, recommendedChoice, note,
    fHiver, fEte, monthly, provenanceMois, distributeur, realBillMode, realBillMad, realBillKwh,
    realBillSaisi, distributeurChoisi,
    nbPanneaux, panelW, structureType, structureProduitId, dayUsage, lines, tauxTva, discountPct,
    multiMode, nombreProprietes, villaGroups, modeInstallation, consoMensuelle,
    categorieCommerciale, commercialAnswers,
    tensionRaccordement, profilCi,
    prixCible, remiseMax, accessoiresOnly, horsReseau, horsReseauTouched,
    pompeCv, pompeType, pompeAlim, pompeHmt, pompeDebit, pompeProfondeur,
    pompeDistance, farmRegion, farmCrop, farmSurfaceHa,
    farmIrrigation, ecoPompage, attestationAgricole, farmHmtStatic,
    farmHmtDrawdown, pompageSaisie,
    // AGNR30 — conditions, échéancier, tarif déclaré et éco C&I : les
    // modifier arme la garde de sortie et crée un brouillon local.
    conditions, echeancierSaisie, tarifSaisie, ecoCi,
  }), [
    leadId, clientId, dateValidite, scenario, recommendedChoice, note,
    fHiver, fEte, monthly, provenanceMois, distributeur, realBillMode, realBillMad, realBillKwh,
    realBillSaisi, distributeurChoisi,
    nbPanneaux, panelW, structureType, structureProduitId, dayUsage, lines, tauxTva, discountPct,
    multiMode, nombreProprietes, villaGroups, modeInstallation, consoMensuelle,
    categorieCommerciale, commercialAnswers,
    tensionRaccordement, profilCi,
    prixCible, remiseMax, accessoiresOnly, horsReseau, horsReseauTouched,
    pompeCv, pompeType, pompeAlim, pompeHmt, pompeDebit, pompeProfondeur,
    pompeDistance, farmRegion, farmCrop, farmSurfaceHa,
    farmIrrigation, ecoPompage, attestationAgricole, farmHmtStatic,
    farmHmtDrawdown, pompageSaisie,
    conditions, echeancierSaisie, tarifSaisie, ecoCi,
  ])
  // « Dirty » = l'utilisateur a réellement saisi quelque chose de significatif
  // (au moins un identifiant de cible OU une note OU des factures OU des
  // paramètres techniques). Tant que le formulaire est vierge, ni brouillon ni
  // garde ne s'activent (évite un bandeau/blocage sur un simple montage).
  // EZ4 — L'ANGLE MORT DU BROUILLON : `dirty` ignorait `lines`, `discountPct`,
  // `tauxTva` et `villaGroups` — or ces quatre champs sont DÉJÀ dans
  // `draftSnapshot` ci-dessus. Un utilisateur qui n'avait fait qu'ajouter des
  // LIGNES (le cœur du devis) n'était donc ni sauvegardé ni protégé par la
  // garde de fermeture d'onglet. Seul ce prédicat était à corriger.
  const lignesSaisies = lines.some(
    (l) => l.produit || (l.designation || '').trim() || parseFloat(l.prix_unit_ttc) > 0,
  )
  const remiseSaisie = parseFloat(discountPct) > 0
  const tvaModifiee = String(tauxTva ?? '') !== '' && parseFloat(tauxTva) !== TVA_STANDARD_DEFAUT
  // `villaGroups` a des libellés PAR DÉFAUT : le signal utile est le mode
  // multi-propriétés lui-même (défaut 'none'), pas la présence de libellés.
  const villasSaisies = multiMode !== 'none'
  const formulaireNonVierge = Boolean(
    leadId || clientId || note || fHiver || fEte || nbPanneaux
    || consoMensuelle || prixCible || pompeHmt || pompeDebit || farmSurfaceHa
    || lignesSaisies || remiseSaisie || tvaModifiee || villasSaisies,
  )
  // QJR581 — « dirty » veut dire « DIFFÉRENT de la référence » : l'état que le
  // mappeur `?edit=` vient de poser (édition) ou le dernier enregistrement
  // réussi. Sans référence : non-vacuité en création, jamais en édition (le
  // devis n'est pas encore chargé). Avant, ouvrir un devis sans rien toucher
  // écrivait un « brouillon non enregistré » et armait la garde de sortie,
  // même après un enregistrement réussi.
  const snapshotJson = useMemo(() => JSON.stringify(draftSnapshot), [draftSnapshot])
  const [referenceEcran, setReferenceEcran] = useState(null)
  useEffect(() => {
    if (Date.now() < captureReferenceJusqua.current) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- captureReferenceJusqua : useRef de la coquille reçu du ctx (même effet qu'avant SPL54)
      setReferenceEcran(snapshotJson)
    }
  }, [snapshotJson]) // eslint-disable-line react-hooks/exhaustive-deps -- captureReferenceJusqua est un ref (stable)
  const dirty = referenceEcran != null
    ? snapshotJson !== referenceEcran
    : (editId ? false : formulaireNonVierge)
  const { restored, restore, discard, clear, savedAt } = useDraftAutosave(draftKey, draftSnapshot, {
    enabled: dirty,
    version: editId ? (editDevis?.updated_at ?? null) : undefined,
  })
  useDirtyGuard(dirty)
  // QJR581 — un brouillon local d'édition n'est repris que s'il porte la
  // version COURANTE du devis ; sinon (devis modifié depuis, ou brouillon
  // d'avant QJR581 sans version) il est purgé, avec une notice.
  const brouillonPerime = Boolean(editId && restored && editDevis
    && restored.version !== editDevis.updated_at)
  const brouillonProposable = Boolean(restored
    && (!editId || (editDevis && restored.version === editDevis.updated_at)))
  useEffect(() => {
    if (!brouillonPerime) return
    discard()
    toast.info('Brouillon local ignoré : ce devis a été modifié depuis.')
  }, [brouillonPerime, discard])
  // Après un enregistrement réussi, l'état courant DEVIENT la référence.
  const marquerEnregistre = () => setReferenceEcran(snapshotJson)

  // Restauration : réinjecte le snapshot sauvegardé dans tous les setters.
  const handleRestoreDraft = () => {
    const d = restore()
    if (!d) return
    if (d.leadId != null) setLeadId(d.leadId)
    if (d.clientId != null) setClientId(d.clientId)
    if (d.dateValidite != null) setDateValidite(d.dateValidite)
    // QJR641 — un vieux brouillon qui porte encore `instType` : clé ignorée.
    // Le scénario du brouillon local est lui aussi un choix déjà posé : un lead
    // sélectionné après restauration ne le réécrit pas. QJR99 — même effet
    // qu'avant (`scenarioTouched.current = true` + `setScenario`), en UNE
    // transition. Il DOIT précéder le marché ci-dessous : c'est ce qui empêche
    // `MARCHE_CHANGE` de reposer le défaut du marché par-dessus.
    if (d.scenario != null) dispatchSizing({ type: 'SAISI', champ: 'scenario', valeur: d.scenario })
    if (d.recommendedChoice != null) setRecommendedChoice(d.recommendedChoice)
    if (d.note != null) setNote(d.note)
    if (d.fHiver != null) setFHiver(d.fHiver)
    if (d.fEte != null) setFEte(d.fEte)
    if (d.monthly != null) setMonthly(d.monthly)
    // AGNR30 — conditions, échéancier, tarif déclaré, éco C&I.
    if (d.conditions != null) setConditions(d.conditions)
    if (d.echeancierSaisie != null) setEcheancierSaisie(d.echeancierSaisie)
    if (d.tarifSaisie != null) setTarifSaisie(d.tarifSaisie)
    if (d.ecoCi != null) setEcoCi(d.ecoCi)
    // AGNR13 — la provenance revient avec le brouillon ; un brouillon ancien
    // (sans elle) garde la règle d'avant : une série modifiée = saisie.
    if (Array.isArray(d.provenanceMois) && d.provenanceMois.length === 12) {
      setProvenanceMois(d.provenanceMois)
    } else if (Array.isArray(d.monthly)
      && d.monthly.some((v, i) => Number(v) !== DEFAULT_MONTHLY_BILLS[i])) {
      setProvenanceMois(Array(12).fill('tapee'))
    }
    if (d.distributeur != null) setDistributeur(d.distributeur)
    if (d.realBillMode != null) setRealBillMode(d.realBillMode)
    if (d.realBillMad != null) setRealBillMad(d.realBillMad)
    if (d.realBillKwh != null) setRealBillKwh(d.realBillKwh)
    if (d.realBillSaisi != null) setRealBillSaisi(!!d.realBillSaisi)
    if (d.distributeurChoisi != null) setDistributeurChoisi(!!d.distributeurChoisi)
    // QJR99 — les champs du reducer se restaurent par dispatch. `REOUVERTURE`
    // pose le compte de panneaux SANS le marquer « touché » (comportement
    // historique : un brouillon restauré n'est pas une frappe) ; `SAISI panelW`
    // n'a jamais eu de drapeau propre. `MARCHE_CHANGE` en origine
    // `programme` ne marque pas le marché non plus — le lead peut encore le
    // pré-régler, exactement comme avant.
    if (d.panelW != null) dispatchSizing({ type: 'SAISI', champ: 'panelW', valeur: d.panelW })
    if (d.nbPanneaux != null) dispatchSizing({ type: 'REOUVERTURE', devis: { panneaux: d.nbPanneaux } })
    if (d.structureType != null) dispatchSizing({ type: 'SAISI', champ: 'structure', valeur: d.structureType })
    // STKCAT10 — le PRODUIT de structure se restaure comme le reste du
    // brouillon : sans ça, reprendre un brouillon reperdait la pergola
    // choisie et recomposait en acier, en silence.
    if (d.structureProduitId != null) {
      dispatchSizing({ type: 'SAISI', champ: 'structureProduit', valeur: d.structureProduitId })
    }
    if (d.dayUsage != null) setDayUsage(d.dayUsage)
    // eslint-disable-next-line react-hooks/immutability -- linesInitialized : useRef de la coquille reçu du ctx
    if (Array.isArray(d.lines)) { setLines(withKeys(d.lines)); linesInitialized.current = true }
    if (d.tauxTva != null) setTauxTva(d.tauxTva)
    if (d.discountPct != null) setDiscountPct(d.discountPct)
    if (d.multiMode != null) setMultiMode(d.multiMode)
    if (d.nombreProprietes != null) setNombreProprietes(d.nombreProprietes)
    if (Array.isArray(d.villaGroups)) setVillaGroups(d.villaGroups)
    if (d.modeInstallation != null) {
      dispatchSizing({ type: 'MARCHE_CHANGE', mode: d.modeInstallation, origine: 'programme' })
    }
    if (d.consoMensuelle != null) setConsoMensuelle(d.consoMensuelle)
    if (d.categorieCommerciale != null) setCategorieCommerciale(d.categorieCommerciale)
    if (d.commercialAnswers && typeof d.commercialAnswers === 'object') setCommercialAnswers(d.commercialAnswers)
    if (d.tensionRaccordement != null) {
      dispatchSizing({ type: 'SAISI', champ: 'tension', valeur: d.tensionRaccordement })
    }
    if (d.profilCi && typeof d.profilCi === 'object') setProfilCi({ ...profilCiVide(), ...d.profilCi })
    if (d.prixCible != null) setPrixCible(d.prixCible)
    if (d.remiseMax != null) setRemiseMax(d.remiseMax)
    if (d.accessoiresOnly != null) setAccessoiresOnly(d.accessoiresOnly)
    // OFFGRID — un choix déjà posé (brouillon local) est un choix EXPLICITE :
    // il ferme `horsReseauTouched`, sinon un lead appliqué après restauration
    // écraserait le raccordement que le vendeur avait retenu.
    if (d.horsReseau != null) { setHorsReseau(d.horsReseau); setHorsReseauTouched(true) }
    if (d.pompeCv != null) setPompeCv(d.pompeCv)
    if (d.pompeType != null) setPompeType(d.pompeType)
    if (d.pompeAlim != null) dispatchSizing({ type: 'SAISI', champ: 'pompeAlim', valeur: d.pompeAlim })
    if (d.pompeHmt != null) setPompeHmt(d.pompeHmt)
    if (d.pompeDebit != null) setPompeDebit(d.pompeDebit)
    if (d.pompeProfondeur != null) setPompeProfondeur(d.pompeProfondeur)
    if (d.pompeDistance != null) setPompeDistance(d.pompeDistance)
    // AGNR26 — `pompeHeures` d'un brouillon ancien est ignoré (champ retiré).
    if (d.farmRegion != null) setFarmRegion(d.farmRegion)
    if (d.farmCrop != null) setFarmCrop(d.farmCrop)
    if (d.farmSurfaceHa != null) setFarmSurfaceHa(d.farmSurfaceHa)
    if (d.farmIrrigation != null) setFarmIrrigation(d.farmIrrigation)
    if (d.ecoPompage && typeof d.ecoPompage === 'object') setEcoPompage(d.ecoPompage)
    if (d.attestationAgricole && typeof d.attestationAgricole === 'object') {
      setAttestationAgricole(d.attestationAgricole)
    }
    if (d.farmHmtStatic != null) setFarmHmtStatic(d.farmHmtStatic)
    if (d.farmHmtDrawdown != null) setFarmHmtDrawdown(d.farmHmtDrawdown)
    if (d.pompageSaisie && typeof d.pompageSaisie === 'object') setPompageSaisie(d.pompageSaisie)
  }

  return {
    restored, discard, clear, savedAt, brouillonProposable, marquerEnregistre, handleRestoreDraft,
  }
}

// SPL45 — LE CHARGEUR `?edit=` DU GÉNÉRATEUR (réouverture d'un devis),
// déplacé tel quel de DevisGenerator.jsx : l'effet `getDevisById` → garde
// `peutEditerDevis` → `devisVersEtat` → pose des setters → hydratation du lead
// → transition REOUVERTURE, et `rechargerDevisRecompose`. Corps verbatim ;
// `editLoaded` (écrit en synchrone dans l'effet) vit DANS le hook (règle
// react-hooks/immutability). `ctx` porte, nom par nom, ce que le corps lit.
import { useEffect, useRef } from 'react'
import ventesApi from '../../../../api/ventesApi'
import { peutEditerDevis } from '../../devisStatuts'
import { toast } from '../../../../ui/confirm'
import { FENETRE_REFERENCE_MS } from '../ecranDefauts.js'
import { devisVersEtat } from '../etatDevis'
import crmApi from '../../../../api/crmApi'
import { withKeys } from '../ligneFabrique.js'
import { ATTESTATION_VIDE, ECO_CI_VIDE, TARIF_SAISIE_VIDE, ecoDepuisSaisies } from '../etudeMarcheBloc'

export function useChargeurEdition(ctx) {
  const {
    setLeadDuDevis, setErrors, dispatchSizing, cancel, editId, setEditDevis, jetonRef,
    captureReferenceJusqua, rechargeEdit, setRechargeEdit, setRecommendedChoice, setLeadId,
    setClientId, setDateValidite, setNote, setEcheancierSaisieBrut, echeancierAEnvoyer,
    setConditions, conditionsServies, setFHiver, setFEte, setMonthly, setDistributeur,
    setRealBillMode, setRealBillKwh, setDistributeurChoisi, consoStockee, modeInstallation,
    setDayUsage, setLines, setLeadValeursModifiees, setTauxTva, setDiscountPct, linesInitialized,
    setMultiMode, setNombreProprietes, setVillaGroups, setConsoMensuelle, setProfilCi,
    setTarifSaisie, setEcoCi, setCategorieCommerciale, setCommercialAnswers, setPrixCible,
    setAccessoiresOnly, setHorsReseau, setHorsReseauTouched, setPompeCv, setPompeType, setPompeHmt,
    setPompeDebit, setPompeProfondeur, setPompeDistance, setFarmRegion, setFarmCrop,
    setFarmSurfaceHa, setFarmIrrigation, setEcoPompage, setAttestationAgricole, setFarmHmtStatic,
    setFarmHmtDrawdown, setPompageSaisie, clear, appliquerPartDiurneDuMarche,
  } = ctx

  // QJR548 — le chargeur `?edit=` se relance quand le devis a été recomposé
  // côté serveur (taille d'offre appliquée) : `editLoaded` retient le numéro
  // de chargement déjà servi, `rechargeEdit` en demande un nouveau.
  const editLoaded = useRef(null)

// ── Édition d'un brouillon (?edit=ID) : préremplissage complet ──
  useEffect(() => {
    if (!editId || editLoaded.current === rechargeEdit) return
    editLoaded.current = rechargeEdit
    ventesApi.getDevisById(editId).then(({ data: d }) => {
      // QJR532 (D-QJR5-1) — le refus vient du SERVEUR (`modifiable`, QJR516),
      // plus d'une garde « statut !== brouillon » : un envoyé se corrige sur
      // place ; un accepté / remplacé dit pourquoi (raison_non_modifiable).
      if (!peutEditerDevis(d)) {
        // APX17 — plus de popup du système : un toast d'erreur français,
        // dans le seul Toaster de l'app.
        toast.error(d.raison_non_modifiable
          || 'Ce devis ne peut plus être modifié — révisez-le pour créer une nouvelle version.')
        cancel()
        return
      }
      // QJR581 — la RÉFÉRENCE « rien n'a changé » se capture sur l'état que
      // ce mappeur (et ses relectures immédiates : lead, réouverture) pose.
      captureReferenceJusqua.current = Date.now() + FENETRE_REFERENCE_MS
      // QJR549 — le jeton de fraîcheur du devis CHARGÉ (et rechargé).
      jetonRef.current = d.updated_at ?? null
      setEditDevis({ id: d.id, reference: d.reference,
                     statut: d.statut, date_envoi: d.date_envoi ?? null,
                     // QJR548 — verdict SERVI (QJR516), relu par les gestes
                     // de l'écran qui disent AVANT le clic s'ils sont permis.
                     modifiable: d.modifiable,
                     raison_non_modifiable: d.raison_non_modifiable || '',
                     // QJR580 — le lead / client DU DEVIS, lus par leurs noms
                     // servis (jamais `leads.find` : lead hors page 1).
                     lead_nom: d.lead_nom || '', client_nom: d.client_nom || '',
                     // QJR581 — version du devis : un brouillon local d'une
                     // AUTRE version n'est jamais proposé.
                     updated_at: d.updated_at ?? null,
                     // QJR540 — relations et état du calepinage, déjà servis
                     // par DevisSerializer : lus tels quels (zéro appel réseau).
                     factures_liees: d.factures_liees ?? [],
                     bon_commande_etat: d.bon_commande_etat ?? null,
                     chantier: d.chantier ?? null,
                     layout_stale: d.layout_stale ?? null,
                     layout_nb_panneaux: d.layout_nb_panneaux ?? null,
                     lineIds: (d.lignes ?? []).map(l => l.id) })
      // QJR658 — LE MAPPEUR EST UN MODULE PUR (`quote/etatDevis.js`,
      // aller-retour exécuté par `etatDevis.test.mjs`) : il lit le devis
      // servi et rend l'état d'écran ; ici on ne fait que le POSER.
      const etat = devisVersEtat(d)
      const pose = (valeur, setter) => { if (valeur !== undefined) setter(valeur) }
      // Défaut de part diurne du marché (QJR641), avant la valeur persistée.
      if (etat.mode && etat.mode !== modeInstallation) appliquerPartDiurneDuMarche(etat.mode)
      if (d.lead) {
        setLeadId(etat.leadId)
        // ERR-QAH-VENTES-EDITION-PERD-LEAD — relit le lead par son id et repose
        // ses factures hiver/été SANS redimensionner ; une valeur déjà présente
        // n'est jamais écrasée ; une panne reste ISOLÉE.
        Promise.resolve().then(() => crmApi.getLead(d.lead)).then(({ data: lead }) => {
          if (!lead || lead.id == null) return
          // QJR581 — hydratation serveur tardive : re-capture de la référence.
          captureReferenceJusqua.current = Date.now() + FENETRE_REFERENCE_MS
          setLeadDuDevis(lead)
          if (parseFloat(lead.facture_hiver) > 0) {
            setFHiver(prev => prev || String(lead.facture_hiver))
            setFEte(prev => prev || (lead.ete_differente && lead.facture_ete
              ? String(lead.facture_ete) : ''))
          }
        }).catch(() => {})
      } else pose(etat.clientId, setClientId)
      // DC11 / QJR106 — verdict de dérive du serveur (liste vide = aucune bannière).
      setLeadValeursModifiees(etat.leadValeursModifiees)
      setDiscountPct(etat.discountPct)
      setTauxTva(etat.tauxTva)
      pose(etat.dateValidite, setDateValidite)
      pose(etat.note, setNote)
      // QJR624 — l'échéancier DU DEVIS.
      echeancierAEnvoyer.current = etat.echeancierAEnvoyer
      setEcheancierSaisieBrut(etat.echeancier)
      // CIQ226 — les conditions contractuelles du devis, telles que saisies.
      pose(etat.conditions, setConditions)
      conditionsServies.current = etat.conditionsServies || []
      setPrixCible(etat.prixCible)
      setLines(withKeys(etat.lignes))
      linesInitialized.current = true
      // QJR99 / QJR526 — la RÉOUVERTURE est UNE transition du reducer : mode,
      // compte de panneaux (branche SANS), scénario, wattage et structure.
      dispatchSizing({
        type: 'REOUVERTURE',
        devis: {
          mode_installation: etat.mode,
          panneaux: etat.panneaux,
          scenario: etat.scenario,
          panel_watt: etat.reouverture.panelW,
          structure: etat.reouverture.structure,
          structureProduitId: etat.reouverture.structureProduitId,
        },
      })
      setHorsReseau(etat.reouverture.horsReseau)
      setHorsReseauTouched(true)
      setAccessoiresOnly(etat.reouverture.accessoiresOnly)
      pose(etat.recommendedChoice, setRecommendedChoice)
      pose(etat.multiMode, setMultiMode)
      pose(etat.nombreProprietes, setNombreProprietes)
      pose(etat.villaGroups, setVillaGroups)
      if (etat.tension === 'mt') dispatchSizing({ type: 'SAISI', champ: 'tension', valeur: 'mt' })
      pose(etat.partDiurne, setDayUsage)
      pose(etat.categorieCommerciale, setCategorieCommerciale)
      pose(etat.commercialAnswers, setCommercialAnswers)
      pose(etat.pompe.cv, setPompeCv)
      pose(etat.pompe.hmt, setPompeHmt)
      pose(etat.pompe.debit, setPompeDebit)
      if (etat.pompageSaisie) setPompageSaisie(etat.pompageSaisie)
      pose(etat.consoMensuelle, setConsoMensuelle)
      // CIQ125 — le profil déclaré C&I se relit de ses ENTRÉES v2.
      pose(etat.profilCi, setProfilCi)
      // CIQ222 — le tarif déclaré se relit tel que saisi.
      setTarifSaisie(etat.tarifSaisie || TARIF_SAISIE_VIDE)
      // CIQ223 — les saisies de l'économie C&I se relisent telles que saisies.
      setEcoCi(etat.ecoCi || ECO_CI_VIDE)
      pose(etat.distributeur, setDistributeur)
      pose(etat.distributeurChoisi, setDistributeurChoisi)
      pose(etat.monthly, setMonthly)
      consoStockee.current = etat.consoStockee
      pose(etat.realBillMode, setRealBillMode)
      pose(etat.realBillKwh, setRealBillKwh)
      pose(etat.farm.region, setFarmRegion)
      pose(etat.farm.crop, setFarmCrop)
      pose(etat.farm.surfaceHa, setFarmSurfaceHa)
      pose(etat.farm.irrigation, setFarmIrrigation)
      // AGR212 — l'économie déclarée se relit telle qu'enregistrée.
      setEcoPompage(etat.saisiesEco || ecoDepuisSaisies(null))
      // AGR218 — l'attestation d'usage agricole se relit telle que saisie.
      setAttestationAgricole(etat.farm.attestation || ATTESTATION_VIDE)
      pose(etat.farm.hmtStatic, setFarmHmtStatic)
      pose(etat.farm.hmtDrawdown, setFarmHmtDrawdown)
      pose(etat.pompe.profondeur, setPompeProfondeur)
      // QJR66 — `alim` restaurée est un choix humain (drapeau « touché »).
      pose(etat.pompe.type, setPompeType)
      if (etat.pompe.alim) dispatchSizing({ type: 'SAISI', champ: 'pompeAlim', valeur: etat.pompe.alim })
      pose(etat.pompe.distance, setPompeDistance)
    }).catch(() => {
      setErrors(prev => ({
        ...prev,
        submit: 'Impossible de charger ce devis — il a peut-être été supprimé.',
      }))
    })
  }, [editId, rechargeEdit]) // eslint-disable-line react-hooks/exhaustive-deps

  // QJR548 — une taille d'offre appliquée RECOMPOSE le devis côté serveur
  // (lignes, totaux, études) : l'écran relit ce devis par LE chargeur
  // `?edit=` ci-dessus et efface son brouillon local — sinon le prochain
  // « Enregistrer » renverrait les anciennes lignes et annulerait la taille
  // appliquée en silence. La confirmation est posée par DevisOffresTailles.
  const rechargerDevisRecompose = () => {
    clear()
    setRechargeEdit(n => n + 1)
  }

  return {
    rechargerDevisRecompose,
  }
}

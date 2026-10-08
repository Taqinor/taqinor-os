// SPL44 — LA PERSISTANCE ET LA VALIDATION DU GÉNÉRATEUR (déplacées telles
// quelles de DevisGenerator.jsx : `usableLines` … `ouvrirConception3D`, corps
// verbatim). `ctx` porte, nom par nom, ce que ces fonctions lisent du
// composant ; seules exceptions au verbatim : les refs écrites passent sous
// les noms `facturesEcartConfirmeRef` / `forcerSansJetonRef` (règle
// react-hooks/immutability).
import { erreursConditions } from '../../echeancierEdition'
import {
  controlerFacturesSaisies,
  isHybridInverter, isReseauInverter, isOffgridInverter, isPanel, isPompe,
  consoAnnuelleDepuisFactures,
  controlerKwhDeclare, MESSAGE_KWH_INCOHERENT,
} from '../../solar'
import { CATEGORIE_NON_PRECISEE } from '../../../../pages/ventes/generator/PanneauCommercial'
import { etatVersEcritures } from '../etatDevis'
import ventesApi from '../../../../api/ventesApi'
import { erreursTarifDeclare } from '../etudeMarcheBloc'
import { toast } from '../../../../ui/confirm'
import { ecartsAuRegistre } from '../overrides'
import crmApi from '../../../../api/crmApi'
import { erreursBaseLegaleServeur, lignesServeurVersEcran } from '../lignesEcran'
import { useState } from 'react'
import { withKeys } from '../ligneFabrique.js'

export function usePersistanceDevis(ctx) {
  const {
    navigate, confirm, setClients, setLeads, setSaving, setErrors, setWarnings,
    facturesEcartConfirmeRef, finish, editId, editDevis, jetonRef, forcerSansJetonRef,
    setConflitVerrou, armerJeton, setRechargeEdit, recommendedChoice, overridesReg,
    setOverridesReg, setOverridesErreur, messageErreurOverrides, leadId, setLeadId, clientId,
    setClientId, dateValidite, note, echeancierSaisie, echeancierAEnvoyer, conditions,
    conditionsServies, monthly, distributeur, realBillMode, realBillSaisi, distributeurChoisi,
    consoStockee, nbPanneaux, scenario, modeInstallation, pompeAlim, lines, setLines, tauxTva,
    discountPct, setDiscountPct, multiMode, nombreProprietes, profilCi, tarifSaisie, ecoCi,
    categorieCommerciale, commercialAnswers, prixCible, accessoiresOnly, pompeCv, pompeType,
    pompeHmt, pompeDebit, pompeProfondeur, pompeDistance, farmRegion, farmCrop, farmSurfaceHa,
    farmIrrigation, attestationAgricole, farmHmtStatic, farmHmtDrawdown, pompageSaisie, clear,
    marquerEnregistre, recommended, consoAnnuelleReelle, facturesSaisies, selectedLead, marcheCi,
    ctxProfilCi, consoCiConnue, aujourdhuiIso, ecoAvecCalendrier,
  } = ctx

  // ── Sauvegarde ──
  // Une ligne est enregistrée si elle a un produit et une quantité > 0 ;
  // les lignes placeholder (sans produit, prix 0) sont ignorées silencieusement.
  const usableLines = () =>
    lines.filter(l => l.produit && parseFloat(l.quantite) > 0)

  const validate = () => {
    const e = {}
    // QJR580 — en édition, le devis a déjà son client (lecture seule).
    if (!editId && !clientId && !leadId) e.client = 'Sélectionnez un lead ou un client'
    // CIQ226 — pénalités = taux ET plafond ; retenue = son taux (sous le champ).
    if (editId && Object.keys(erreursConditions(conditions)).length) {
      e.conditions = 'Conditions du client incomplètes : voir sous les champs.'
    }
    // CIQ125 — commercial ET industriel : sans consommation (saisie, ou
    // reprise de la fiche lead par le serveur) ni taille explicite,
    // l'enregistrement est refusé SOUS le champ.
    if (marcheCi && !consoCiConnue) {
      e.conso = 'Renseignez la consommation du site (12 mois, total annuel ou '
        + 'factures) ou une taille explicite — l\'étude en dépend.'
    }
    // ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES (décision fondateur 30/09/2026) —
    // le kWh mensuel DÉCLARÉ sur la fiche du lead (celui que le serveur chiffre
    // en priorité, Q14) contredit ses factures (barème ÷ facture hors
    // [0,5 ; 2]) ⇒ enregistrement REFUSÉ, jamais un chiffrage silencieux. Le
    // serveur (`/atomic`, `replace-lines`) applique la même garde.
    if (!e.conso && selectedLead) {
      const ctlKwh = controlerKwhDeclare(selectedLead.conso_mensuelle_kwh, {
        factureHiver: selectedLead.facture_hiver,
        factureEte: selectedLead.facture_ete,
        eteDifferente: selectedLead.ete_differente,
      })
      if (ctlKwh && !ctlKwh.coherent) e.conso = MESSAGE_KWH_INCOHERENT
    }
    const orphan = lines.find(l =>
      !l.produit && parseFloat(l.quantite) > 0 && parseFloat(l.prix_unit_ttc) > 0)
    if (orphan) {
      e.lines = `Sélectionnez un produit du stock pour la ligne « ${orphan.designation || '—'} »`
    } else if (!usableLines().length) {
      e.lines = 'Au moins une ligne avec un produit et une quantité > 0'
    } else if (!accessoiresOnly) {
      // QX20 — un devis solaire DOIT contenir de l'équipement solaire cohérent
      // avec le marché. Résidentiel/industriel : ≥ 1 panneau ET ≥ 1 onduleur ;
      // agricole : ≥ 1 pompe. Échappatoire DOCUMENTÉE : cocher « Composition
      // libre » (accessoiresOnly, relabellée — incident fondateur 01/09 round
      // 2) désactive la garde pour un devis composé à la main (accessoires/
      // main-d'œuvre seuls, ou toute composition hors calculateur), MÊME sur
      // un devis « Hors réseau » — cette garde ne dépend jamais de `horsReseau`.
      const usable = usableLines()
      const has = (pred) => usable.some(l => pred(l.designation))
      if (modeInstallation === 'agricole') {
        // AGR130 — une pompe EXISTANTE n'a pas de ligne pompe (le kit n'en
        // pose pas) ; une pompe NEUVE exige une pompe ou son placeholder
        // « prix à renseigner » (ligne sans produit, jamais chiffrée à 0).
        const existante = pompageSaisie.mode_pompe === 'existante'
        const placeholderPompe = lines.some(l => !l.produit && isPompe(l.designation))
        if (!existante && !has(isPompe) && !placeholderPompe) {
          e.lines = 'Un devis de pompage doit contenir au moins une pompe. '
            + 'Utilisez « Auto-remplir » ou ajoutez une pompe, ou cochez '
            + '« Composition libre ».'
        }
      } else {
        const hasPanel = has(isPanel)
        // OFFGRID — un onduleur hors réseau compte comme onduleur : un devis
        // hors réseau qui ne porte QUE cette ligne (jamais réseau/hybride)
        // doit pouvoir s'enregistrer, sans obliger le vendeur à garder une
        // ligne hybride « pour passer la garde ».
        const hasInverter = has(d => isReseauInverter(d) || isHybridInverter(d) || isOffgridInverter(d))
        if (!hasPanel || !hasInverter) {
          const manque = [
            !hasPanel ? 'un panneau' : null,
            !hasInverter ? 'un onduleur' : null,
          ].filter(Boolean).join(' et ')
          e.lines = `Un devis solaire doit contenir au moins ${manque}. `
            + 'Utilisez « Auto-remplir » ou ajoutez ces lignes, ou cochez '
            + '« Composition libre ».'
        }
      }
    }
    // ERR-QAC-FACTURES-ECRAN-INVRAISEMBLABLES — les 12 factures partent comme
    // « réelles » (`entreesReellesEcran`) : une facture sous les lignes fixes
    // du compteur est REFUSÉE (le serveur la refuserait aussi, après
    // l'enregistrement des lignes) ; un écart avec la facture d'hiver du lead
    // se fait CONFIRMER une fois (second clic), jamais corrigé en silence.
    if (facturesSaisies) {
      const ctl = controlerFacturesSaisies(monthly, {
        factureHiverLead: selectedLead?.facture_hiver,
      })
      if (ctl.sousPlancher.length) {
        e.factures = `Facture(s) mensuelle(s) inférieure(s) aux lignes fixes du `
          + `compteur (${ctl.plancher.toFixed(2)} MAD TTC/mois) — mois `
          + `${ctl.sousPlancher.join(', ')}. Une facture réelle ne peut pas être `
          + 'aussi basse : corrigez la saisie (hiver/été ou détail mensuel).'
      } else if (ctl.ecartLead) {
        const signature = monthly.map(v => Number(v) || 0).join('|')
          + `#${ctl.ecartLead.lead}`
        if (facturesEcartConfirmeRef.current !== signature) {
          facturesEcartConfirmeRef.current = signature
          e.factures = `La facture d'hiver enregistrée (${Math.round(ctl.ecartLead.serie)} MAD) `
            + `s'écarte de celle du lead (${Math.round(ctl.ecartLead.lead)} MAD). `
            + 'Vérifiez la saisie, puis cliquez à nouveau pour confirmer.'
        }
      }
    }
    // Avertissement NON bloquant : le lead choisi est perdu et/ou archivé.
    // On le signale avant l'enregistrement sans jamais l'empêcher.
    const w = {}
    if (selectedLead && (selectedLead.perdu || selectedLead.is_archived)) {
      const flags = [
        selectedLead.perdu ? 'perdu' : null,
        selectedLead.is_archived ? 'archivé' : null,
      ].filter(Boolean).join(' et ')
      const nom = `${selectedLead.nom}${selectedLead.prenom ? ` ${selectedLead.prenom}` : ''}`.trim()
      w.lead = `Attention : le lead « ${nom} » est ${flags}. `
        + 'Vous pouvez tout de même créer ce devis.'
    }
    setWarnings(w)
    setErrors(e)
    return Object.keys(e).length === 0
  }

  // QJR66 (audit L3 du 29/08/2026) — LA SOUS-CLÉ D'ÉTUDE DU MARCHÉ COURANT,
  // et RIEN D'AUTRE.
  //
  // CE QUI SE PASSAIT. `persisterDevis` reconstruisait `etude_params` DE ZÉRO
  // et le posait en bloc dans le corps du devis : toute clé que l'écran ne
  // recompose pas lui-même — `factures_mensuelles_reelles`, `gamme`, et les
  // quatre blocs écrits par les rafraîchisseurs serveur (`etude_horaire`,
  // `dimensionnement`, `profils_comparatifs`, `simulation`) — DISPARAISSAIT à
  // la sauvegarde suivante du vendeur.
  //
  // CE QUI SE PASSE MAINTENANT. Le corps du devis ne porte plus d'étude du
  // tout ; l'écran écrit UNIQUEMENT la sous-clé de SON marché, par l'endpoint
  // de FUSION `PATCH /ventes/devis/<id>/etude-params/` (QJR62) — seules les
  // clés envoyées bougent, les autres restent intouchées bit à bit.
  //   • TOUS LES MARCHÉS — les ENTRÉES RÉELLES tapées par le vendeur sur CET
  //     écran, et elles seules : les 12 factures du client, la consommation
  //     annuelle et le distributeur (voir `entreesReellesEcran` ci-dessous).
  //     ARBITRAGE ORCHESTRATEUR (QJR66, 29/08/2026) : « zéro perte ». Une
  //     première version de cette tâche n'écrivait RIEN en résidentiel, ce qui
  //     re-rouvrait le trou N1 — un devis créé À LA MAIN (hors devis auto d'un
  //     lead) n'avait plus AUCUN moyen d'alimenter
  //     `factures_mensuelles_reelles`, la donnée la plus précieuse du dossier,
  //     et le moteur PDF retombait sur une facture « avant » reconstruite
  //     depuis l'économie SUPPOSÉE (proxy circulaire). Ces trois clés sont des
  //     ENTRÉES déclarées `ECRAN` dans le schéma : c'est leur chemin.
  //     Le RESTE des entrées résidentielles (scénario, option recommandée)
  //     passe, lui, par le REGISTRE DE SURCHARGES D12 — pas par ici.
  //   • industriel / commercial — les cinq dérivées de leur étude
  //     d'autoconsommation (+ la catégorie commerciale, qui EST l'entrée de
  //     cette étude : elle choisit l'archétype de part diurne).
  //   • agricole — le bloc pompage (pompe, HMT, débit à la HMT, m³/jour,
  //     champ kWc, méthode d'irrigation).
  //   • résidentiel — RIEN DE PLUS que les entrées réelles ci-dessus : le
  //     serveur est propriétaire de son étude (dimensionnement, bloc horaire,
  //     profils, calepinage).
  // Le schéma serveur (`apps/ventes/domain/etude_schema.py`) est la SEULE
  // porte : une clé hors schéma ou une clé DÉRIVÉE dont l'écran n'est pas
  // propriétaire (`puissance_kwc`, `production_annuelle`,
  // `economies_annuelles`, `etude_horaire`…) est refusée en 400 français.
  // C'est voulu : ces chiffres-là appartiennent à l'étape qui les CALCULE.
  //
  // `null` RETIRE la clé (règle Z2) : une étude qui n'est plus calculable est
  // retirée, jamais laissée périmée — on envoie donc le bloc du marché même
  // quand l'étude est indisponible, pour effacer un chiffre devenu faux.
  //
  // LES ENTRÉES RÉELLES DE L'ÉCRAN — tous marchés (arbitrage « zéro perte »).
  // Reprend MOT POUR MOT les deux règles d'avant, sans en inventer une
  // troisième : le seed N1 (`facturesSaisies` — jamais les valeurs D'EXEMPLE
  // de `DEFAULT_MONTHLY_BILLS`) et la règle QF4 de `buildEtudeParamsChoice`
  // (une conso annuelle déjà connue ⇒ on n'envoie que le distributeur ; une
  // facture réelle saisie ⇒ les deux ; sinon le distributeur seulement s'il
  // n'est pas le défaut ONEE).
  //
  // AUCUNE CLÉ N'EST ENVOYÉE À `null` ICI : `null` SUPPRIME (règle Z2), et
  // supprimer les factures semées par le devis auto parce que CE vendeur n'a
  // rien retapé serait exactement la perte que cette tâche referme. Une clé
  // que l'écran ne connaît pas est simplement ABSENTE du corps — la fusion la
  // laisse alors intacte, bit à bit.
  // QF7 / QJR66 — LES CHOIX DU COMMERCIAL, tous marchés. L'ancien
  // `buildEtudeParamsChoice`, à la sémantique près : le scénario et l'option
  // recommandée AFFICHÉS À L'ÉCRAN sont persistés pour TOUS les modes
  // (résidentiel / industriel / commercial / agricole), pas seulement quand
  // une étude existe.
  //
  // POURQUOI C'EST BLOQUANT. `etude_params['scenario']` est LU par
  // `quote_engine/builder.py` (`_stored_choice`) et par `utils/options.py`
  // pour décider quelles lignes composent l'option vendue. Absent, le moteur
  // prend la branche « artefact » et TOTALISE TOUTES les lignes — les deux
  // onduleurs ET la batterie d'un devis « Les deux » — pendant que le total
  // d'affichage montre, lui, l'option choisie : DEUX chiffres contradictoires
  // sous les yeux du client. Le retirer du corps du devis (QJR66) sans le
  // remettre sur le canal de fusion ouvrait exactement ce trou.
  //
  // JAMAIS `null` : ces deux clés ne valent que quand l'écran les possède
  // réellement — et il les possède toujours (un défaut de mode, ou le choix
  // explicite du vendeur). Le câblage vers le REGISTRE D12 (`scenario`,
  // `recommended_option` sont des chemins surchargeables) est un chantier M5 :
  // en attendant, l'écran reste leur écrivain, par le canal validé.
  //
  // QJ31 (mode A) — ×N VILLAS IDENTIQUES. `selectors.py` multiplie le total du
  // devis par `etude_params['nombre_proprietes']` (défaut 1) : sans écrivain,
  // un devis ×4 rendait le total d'UNE villa. C'est le SEUL choix de ce bloc
  // qui s'envoie à `null` — et c'est VOULU : le sélecteur multi-villa est
  // toujours dans un état défini, donc « pas de ×N à l'écran » signifie
  // vraiment « ce devis est mono-système », et `null` RETIRE la clé (règle Z2)
  // au lieu de laisser traîner le ×4 d'hier. Contraste avec les factures
  // réelles, où « rien de retapé » ne veut PAS dire « pas de factures » — d'où
  // l'absence de clé là-bas. Le mappeur `?edit=` repose le mode depuis cette
  // même clé (plus bas), sans quoi rouvrir un devis ×4 l'aurait remis à 1.
  const choixEcran = () => {
    const choix = {}
    if (scenario) choix.scenario = scenario
    if (recommended) choix.recommended_option = recommended
    const n = multiMode === 'multiplier' ? parseInt(nombreProprietes, 10) : 1
    choix.nombre_proprietes = (Number.isFinite(n) && n > 1) ? n : null
    return choix
  }

  const entreesReellesEcran = (consoDejaConnue) => {
    const entrees = {}
    if (facturesSaisies) {
      entrees.factures_mensuelles_reelles = monthly.map(v => parseFloat(v) || 0)
    }
    // Conso annuelle : la source la plus DIRECTE d'abord (l'étude du marché,
    // qui descend de la saisie « consommation »), puis la facture réelle QF4,
    // puis la dérivation depuis les 12 factures (kwhFromBill au barème réel du
    // distributeur choisi — même patron que `autoQuote.js`, jamais un chiffre
    // supposé).
    //
    // COUV-HOR (29/09/2026) — une facture/kWh TAPÉE dans cette session reste
    // souveraine ; une conso STOCKÉE qui était une saisie repart telle quelle
    // (exacte, sans la dérive ×12 de l'aller-retour kWh/mois) ; sinon les
    // factures (celles de l'écran, à défaut celles du devis) sont RE-DÉRIVÉES
    // au barème — jamais la valeur réaffichée par `?edit=` réécrite à
    // l'identique (DEV-202609-0113 : 198 000 MAD ÷ 1,20 = 165 000 kWh revenait
    // à chaque enregistrement, étiqueté 'onee').
    const stockee = consoStockee.current
    let conso = consoDejaConnue ?? null
    let auBareme = false   // conso calculée ICI au barème de `distributeur`
    if (conso == null && realBillSaisi && consoAnnuelleReelle > 0) {
      conso = consoAnnuelleReelle
      auBareme = realBillMode === 'mad'
    }
    if (conso == null && stockee && !stockee.descendDesFactures) conso = stockee.valeur
    const factures = entrees.factures_mensuelles_reelles || stockee?.factures || null
    if (conso == null && factures) {
      const derivee = consoAnnuelleDepuisFactures(factures, distributeur)
      if (derivee > 0) { conso = derivee; auBareme = true }
    }
    if (conso == null && consoAnnuelleReelle > 0) {
      conso = consoAnnuelleReelle
      auBareme = realBillMode === 'mad'
    }
    if (conso != null) {
      entrees.conso_annuelle = conso
      // Jamais un distributeur que personne n'a choisi sur une conso que
      // l'écran n'a pas calculée à son barème.
      if (auBareme || distributeurChoisi) entrees.distributeur = distributeur
    } else if (distributeur && distributeur !== 'onee') {
      entrees.distributeur = distributeur
    }
    return entrees
  }

  // QJR542 — la projection « étude du marché → clés etude_params légales »
  // vit dans UNE fonction pure partagée avec le devis automatique
  // (`features/ventes/quote/etudeMarcheBloc.js`) ; ici on ne fait que lui
  // passer l'état de l'écran. Résidentiel ⇒ `null` si rien à écrire (aucun
  // appel, voir `persisterDevis`).
  // QJR658 — l'état d'écran à enregistrer, dans la forme de `etatDevis.js`.
  const etatEcran = () => ({
    mode: modeInstallation, dateValidite, tauxTva, discountPct, note, prixCible,
    echeancier: echeancierSaisie, echeancierAEnvoyer: echeancierAEnvoyer.current,
    conditions, conditionsServies: conditionsServies.current,
    lignes: lines, multiMode, nombreProprietes, scenario, recommendedChoice,
    profilCi, ctxCi: ctxProfilCi, tarifSaisie, aujourdhui: aujourdhuiIso,
    ecoCi: { ...ecoCi, revente_demandee: profilCi.tension === 'mt' && Boolean(profilCi.revente) },
    // QJR575 — la sentinelle « Non précisée » se persiste null.
    categorieCommerciale: categorieCommerciale === CATEGORIE_NON_PRECISEE ? null : categorieCommerciale,
    commercialAnswers,
    pompe: {
      cv: pompeCv, hmt: pompeHmt, debit: pompeDebit, type: pompeType,
      alim: pompeAlim, profondeur: pompeProfondeur, distance: pompeDistance,
    },
    pompageSaisie,
    farm: {
      irrigation: farmIrrigation, region: farmRegion, crop: farmCrop,
      surfaceHa: farmSurfaceHa,
      hmtStatic: farmHmtStatic, hmtDrawdown: farmHmtDrawdown,
      attestation: attestationAgricole,
    },
    saisiesEco: ecoAvecCalendrier,
  })
  const blocEtudeMarche = () => etatVersEcritures(etatEcran(), {
    etude: null,
    recommended,
    entrees: entreesReellesEcran,
  }).etude

  // Cœur de persistance extrait de `handleSubmit` (aucun changement de
  // comportement) : construit le payload + les lignes, écrit le devis (édition
  // atomique ou création atomique), attache l'étude du marché par l'endpoint de
  // fusion (QJR66 ci-dessus), et RENVOIE {devisId, devisCree} en cas de succès
  // — null sinon (le message HUMAIN est déjà posé dans `errors.submit`).
  // PV23bis (fondateur 20/08) — `ouvrirConception3D` ci-dessous réutilise
  // EXACTEMENT ce même chemin d'écriture pour le bouton « Concevoir en 3D » :
  // un seul endroit qui sait enregistrer un devis, jamais une seconde logique
  // dupliquée.
  // QJR553 — `surcharge` (optionnelle, « Revenir à cette version ») :
  // `{ lignes, entete, etude_params }` d'un instantané rejoués par CE MÊME
  // chemin d'écriture (replace-lines + jeton) — jamais un second chemin.
  const persisterDevis = async (surcharge = null) => {
    setSaving(true)
    try {
      // QJR515 — `statut` n'est JAMAIS dans l'en-tête d'édition (un envoyé ne
      // repasse jamais en brouillon) : posé seulement à la création ci-dessous.
      // QJR658 — en-tête et lignes construits par le module pur
      // (`etatVersEcritures`), le même que l'aller-retour testé.
      const ecritures = etatVersEcritures(etatEcran())
      const payload = { ...ecritures.entete }
      // QX21 — lignes construites UNE fois (mêmes champs qu'avant : HT dérivé du
      // TTC saisi au taux DE LA LIGNE, groupe villa en mode « villas »).
      // XSAL14 — lignes retenues : produits utilisables + lignes de section/note
      // (intitulé non vide). L'ordre visuel est conservé (ordre = index) pour
      // intercaler les intertitres au bon endroit. Une ligne section/note ne
      // porte ni produit ni prix.
      // QJR523 — payload construit par le mappeur UNIQUE (lignesEcran.js) :
      // prix HT dérivé du TTC au taux DE LA LIGNE, groupe villa en mode
      // « villas », option / type / ordre / variante / verrous manuels
      // (QJR65 / D12, QJR218) et rôle stocké.
      const lignesPayload = ecritures.lignes

      let devisId
      let devisCree = null
      if (editDevis) {
        // QJR544 — ÉDITION ATOMIQUE : en-tête + lignes + choix d'écran en UN
        // appel, UNE transaction serveur (replace-lines). Un échec ne change
        // RIEN (ni en-tête, ni lignes) ; plus de PATCH d'en-tête séparé.
        // QJR624 — l'échéancier part dans `entete` (contrat QJR504) : posé
        // par `etatVersEcritures` quand il est propre au devis ou touché.
        const extra = {
          entete: surcharge?.entete ? { ...payload, ...surcharge.entete } : payload,
          etude_params: surcharge?.etude_params ?? choixEcran(),
        }
        // QJR549 — le jeton part avec l'édition ; « Enregistrer quand même »
        // (après un 409) renvoie UNE fois sans jeton.
        if (jetonRef.current && !forcerSansJetonRef.current) {
          extra.expected_updated_at = jetonRef.current
        }
        forcerSansJetonRef.current = false
        const reponse = await ventesApi.replaceLignesDevis(
          editDevis.id, surcharge?.lignes ?? lignesPayload, extra)
        armerJeton(reponse?.data?.updated_at)
        setConflitVerrou(null)
        devisId = editDevis.id
        devisCree = { reference: editDevis.reference }
      } else {
        // QX21 — CRÉATION ATOMIQUE : devis + lignes en UN commit serveur → plus
        // de brouillon orphelin/partiel si la connexion est coupée en cours de
        // sauvegarde. Lead prioritaire : le client est résolu côté serveur.
        payload.statut = 'brouillon'
        if (leadId) payload.lead = parseInt(leadId)
        else payload.client = parseInt(clientId)
        // ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — les CHOIX de l'écran
        // (scénario, option recommandée, ×N) partent AVEC la création : ils
        // décident de l'option que suit l'argent, donc du total que renvoie le
        // serveur. Envoyés seulement après (PATCH `etude-params` ci-dessous),
        // la réponse de création totalisait TOUTES les lignes — les deux
        // onduleurs compris — et l'écran « Devis enregistré » affichait un prix
        // qu'aucun document ne porte. Le PATCH qui suit reste inchangé (il
        // repose les mêmes choix + les entrées réelles, sans bouger le total).
        const { data } = await ventesApi.createDevisAtomic({
          ...payload, etude_params: choixEcran(), lignes: lignesPayload,
        })
        devisId = data.id
        devisCree = data
      }

      // QJR66 — l'étude du marché courant part par l'endpoint de FUSION, APRÈS
      // les lignes : le serveur vient d'y recalculer ses propres blocs
      // (`rafraichir_etudes_du_devis`), et cette fusion ne touche QUE les clés
      // qu'elle envoie. Résidentiel ⇒ aucun appel.
      // QJR553 — une version restaurée porte SA propre étude (déjà rejouée
      // ci-dessus) : l'étude de l'écran courant ne la recouvre pas.
      const etudeMarche = surcharge ? null : blocEtudeMarche()
      if (etudeMarche) {
        try {
          const reponseEtude = await ventesApi.patchEtudeParams(devisId, etudeMarche)
          // QJR549 — cette écriture avance aussi le jeton : ré-armé.
          armerJeton(reponseEtude?.data?.updated_at)
        } catch (errEtude) {
          // Le devis EST enregistré : une étude refusée ne doit jamais faire
          // croire à un échec d'enregistrement (ni pousser à un second POST
          // qui créerait un doublon). On le DIT, en français, et on continue.
          const detail = errEtude?.response?.data?.detail
          // CIQ222 — un 400 qui nomme un champ du tarif déclaré s'affiche SOUS ce champ.
          const erreursTarif = erreursTarifDeclare(detail)
          if (Object.keys(erreursTarif).length) setErrors((e) => ({ ...e, tarifDeclare: erreursTarif }))
          toast.error(typeof detail === 'string'
            ? `Devis enregistré, étude non attachée : ${detail}`
            : "Devis enregistré, mais l'étude n'a pas pu être attachée.")
        }
      }

      // QJR572 — le registre suit l'écran : APRÈS l'enregistrement réussi
      // (lignes + choix d'écran), un chemin DÉJÀ surchargé dont la valeur
      // affichée a changé est reposé (ou rendu à l'automatique sur « Auto »).
      // Rien à la création, rien sans surcharge. `etude_params` reste écrit
      // (repli du moteur). Une erreur est DITE, l'enregistrement reste fait.
      if (editDevis && !surcharge) {
        const { patch, regenerer } = ecartsAuRegistre({
          scenario,
          recommended_option: recommendedChoice,
          'taille.nb_panneaux': nbPanneaux,
        }, overridesReg)
        try {
          if (Object.keys(patch).length) {
            const { data } = await ventesApi.poserOverrides(devisId, patch)
            setOverridesReg(data)
            armerJeton(data?.updated_at)
          }
          for (const chemin of regenerer) {
            const { data } = await ventesApi.regenererOverride(devisId, chemin)
            setOverridesReg(data)
            armerJeton(data?.updated_at)
          }
        } catch (errOv) {
          const msg = messageErreurOverrides(errOv)
          setOverridesErreur(msg)
          toast.error(`Devis enregistré, registre non mis à jour : ${msg}`)
        }
      }

      return { devisId, devisCree }
    } catch (err) {
      // QJR549 — 409 `devis_modifie` : quelqu'un (ou le catalogue) a écrit ce
      // devis depuis l'ouverture. Bannière NON bloquante, rien d'autre écrit.
      if (err?.response?.status === 409 && err?.response?.data?.code === 'devis_modifie') {
        setConflitVerrou({ par: err.response.data.updated_by_nom || '' })
        return null
      }
      // Message HUMAIN, jamais de JSON brut — et le formulaire reste vivant.
      const raw = err?.response?.data ?? err
      let msg
      if (raw?.lead) {
        msg = 'Ce lead n\'existe plus (supprimé entre-temps ?). '
          + 'La liste des leads a été rechargée — choisissez-en un autre.'
        setLeadId('')
        crmApi.getLeads()
          .then(r => setLeads(r.data.results ?? r.data)).catch(() => {})
      } else if (raw?.client) {
        msg = 'Ce client n\'existe plus. Choisissez un autre client ou un lead.'
        setClientId('')
        crmApi.getClients().then(r => setClients(r.data.results ?? r.data)).catch(() => {})
      } else if (raw?.code === 'kwh_incoherent_factures') {
        // ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES — refus serveur : sous le champ.
        msg = typeof raw.detail === 'string' ? raw.detail : MESSAGE_KWH_INCOHERENT
        setErrors(prev => ({ ...prev, conso: msg }))
      } else if (Object.keys(erreursBaseLegaleServeur(raw, lines)).length) {
        // AGR218 — refus « base légale obligatoire à 0 % » : le message du
        // serveur s'affiche SOUS le champ de la ligne visée.
        const parLigne = erreursBaseLegaleServeur(raw, lines)
        setLines(ls => ls.map(l => (parLigne[l._key]
          ? { ...l, _erreurBaseLegale: parLigne[l._key] } : l)))
        msg = raw.detail
      } else if (typeof raw?.detail === 'string') {
        msg = raw.detail
      } else {
        msg = 'L\'enregistrement a échoué — vérifiez les champs et réessayez.'
      }
      setErrors(prev => ({ ...prev, submit: msg }))
      return null
    } finally {
      setSaving(false)
    }
  }

  // QJR547 — « Enregistrer comme modèle » photographie l'ÉCRAN : le devis
  // est d'abord enregistré par le chemin unique (`persisterDevis`), sans
  // quitter l'écran ; un échec (validation ou serveur) → aucun modèle.
  const enregistrerAvantModele = async () => {
    if (!validate()) return false
    const res = await persisterDevis()
    if (!res) return false
    clear(); marquerEnregistre()
    return true
  }

  // QJR553 (D-QJR5-7) — « Revenir à cette version » : l'écran est rechargé
  // depuis le contenu de l'instantané (lignes, remise) puis enregistré par le
  // chemin NORMAL (replace-lines avec entete + etude_params + jeton) ; sur un
  // envoyé, c'est une correction sur place tracée (QJR518). Puis l'écran
  // relit le devis enregistré.
  const [versionHistorique, setVersionHistorique] = useState(0)
  const revenirAVersion = async (snap) => {
    const contenu = snap?.contenu || {}
    // Le lot (propre à UN devis) ne voyage pas : l'écran ne gère pas les lots.
    const lignesSnap = (contenu.lignes || []).map((l) => {
      const copie = { ...l }
      delete copie.lot
      return copie
    })
    if (!lignesSnap.length) return
    const ok = await confirm({
      title: 'Revenir à cette version ?',
      description: 'Le devis reprend les lignes, la remise et l\'échéancier de cette '
        + 'version, puis il est enregistré. La version actuelle reste dans l\'historique.',
      confirmLabel: 'Revenir à cette version',
    })
    if (!ok) return
    setLines(withKeys(lignesServeurVersEcran(lignesSnap, tauxTva)))
    if (contenu.remise_globale != null) {
      setDiscountPct(String(parseFloat(contenu.remise_globale) || 0))
    }
    const entete = {}
    if (contenu.remise_globale != null) entete.remise_globale = contenu.remise_globale
    if (Array.isArray(contenu.echeancier)) entete.echeancier = contenu.echeancier
    const etude = contenu.etude && Object.keys(contenu.etude).length ? contenu.etude : undefined
    const res = await persisterDevis({ lignes: lignesSnap, entete, etude_params: etude })
    if (res) {
      toast.success('Version restaurée et enregistrée.')
      clear()
      setVersionHistorique(n => n + 1)
      setRechargeEdit(n => n + 1)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    const res = await persisterDevis()
    if (res) { clear(); marquerEnregistre(); finish(res.devisId, res.devisCree) }
  }

  // PV23bis (fondateur 20/08) — « Concevoir en 3D » depuis l'écran de devis :
  // l'outil 3D travaille désormais TOUJOURS SUR LE DEVIS (jamais un aller-
  // retour lead déconnecté qui en créerait un second, cf. le bouton
  // ci-dessous). Le formulaire est d'abord enregistré (création ou édition,
  // via `persisterDevis` ci-dessus) pour que l'outil s'ouvre attaché à un
  // devis réel et resynchronise ses lignes (PV21) ; le chemin lead ne
  // survit que comme repli « conception avant devis valide », quand le
  // formulaire n'est pas encore un devis enregistrable.
  const ouvrirConception3D = async () => {
    if (!validate()) {
      if (leadId && selectedLead) navigate(`/devis-design/${selectedLead.id}`)
      return
    }
    const res = await persisterDevis()
    if (!res) return
    clear()
    marquerEnregistre()
    navigate(`/ventes/devis/${res.devisId}/design`)
  }

  return {
    usableLines, enregistrerAvantModele, versionHistorique, revenirAVersion, handleSubmit,
    ouvrirConception3D,
  }
}

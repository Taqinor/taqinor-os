// SPL48 — LA COMPOSITION DU GÉNÉRATEUR, déplacée telle quelle de
// DevisGenerator.jsx : `buildDimensionnementAvec`,
// `appliquerCompositionServeur`, `handleAutoFill` (jamais d'`await confirm()`
// dedans : invariant gardé par le verbatim), `appliquerTailleDimensionnement`,
// `recalculerDimensionnement` et l'effet de recalcul. Corps verbatim ; `ctx`
// porte, nom par nom, ce que le corps lit du composant.
import { roleLabel, tauxTvaOf, tauxTvaOuDefaut, ttcFromHt } from '../../../../features/ventes/solar'
import { lignesDepuisKit } from '../../../../features/ventes/quote/etudeMarcheBloc'
import { SCENARIO_AVEC, SCENARIO_LES_DEUX } from '../../../../features/ventes/quote/sizingReducer'
import ventesApi from '../../../../api/ventesApi'
import { corpsCiDepuisProfil, lignesDepuisCompositionCi } from '../../../../features/ventes/quote/profilCi'
import { useEffect } from 'react'

export function useCompositionEcran(ctx) {
  const {
    produits, setErrors, dispatchSizing, panelW, scenario, modeInstallation, structureType,
    structureProduitId, recalcDimTick, setPompageAutoFilled, setOnduleursIncomplets,
    setAutoFillLoading, setCompositionErreur, profilCi, horsReseau, kwp, selectedLead,
    etudeHoraireDonnees, etudeHoraireChargement, marcheCi, ctxProfilCi, apercuCi, resolveKwcAvec,
    recomposerLignes, avecQuantitesFigees, apercuPompage,
  } = ctx

  // U3COMPOSE — l'optimum AXE BATTERIE envoyé au dry-run serveur : même
  // précédence que `resolveKwcAvec` ci-dessus (le moteur horaire serveur
  // prime), sans jamais inventer un nombre de panneaux hors d'une dérivation
  // réelle (repli sur la conversion kWc→panneaux du wattage saisi).
  const buildDimensionnementAvec = (kwpAvec) => {
    const backendAvec = etudeHoraireDonnees?.dimensionnement?.recommandation_avec
    const panelWNum = parseFloat(panelW) || 710
    // QJR37 — le moteur horaire (recommandation/recommandation_avec) émet la
    // clé `panneaux` (vérifié contre apps/ventes/contract_samples/
    // etude_horaire.json : "recommandation_avec": {"panneaux": 17, …}), jamais
    // `nb_panneaux` — cette dernière n'existe QUE côté REQUÊTE de
    // POST /ventes/devis/composition/ (contract_samples/devis_composition.json,
    // champ d'entrée `dimensionnement_avec: {nb_panneaux?, kwc?, …}`), une
    // forme différente qu'on continue de PRODUIRE ci-dessous inchangée.
    const nbPanneauxAvec = Number(backendAvec?.panneaux) > 0
      ? Math.round(Number(backendAvec.panneaux))
      : Math.round((kwpAvec * 1000) / panelWNum)
    const dims = { nb_panneaux: nbPanneauxAvec, kwc: kwpAvec }
    const battKwh = Number(backendAvec?.batterie_kwh)
    if (battKwh > 0) dims.batterie_kwh = battKwh
    return dims
  }

  // U3COMPOSE — mappe la réponse du dry-run serveur (contract_samples/
  // devis_composition.json) vers les lignes éditables de l'écran. Le HT
  // (`prix_unitaire_ht`) fait foi — c'est le prix RÉEL en base — mais le TTC
  // affiché est RE-DÉRIVÉ ici avec `tauxTvaOf`/`ttcFromHt` (le taux RÉEL par
  // produit — 10 % panneaux, 20 % le reste, DC7) plutôt que le
  // `prix_unitaire_ttc`/`taux_tva` renvoyés par le dry-run, qui appliquent un
  // taux UNIQUE à toute la composition (simplification de prévisualisation
  // côté serveur, `taux_tva` de la requête, 20 % par défaut) : sans ce
  // ré-alignement une ligne panneau afficherait un TTC calculé à 20 % au lieu
  // de 10 % — un écart de PRIX réel, pas un simple arrondi.
  const appliquerCompositionServeur = (data) => {
    const generated = (data.lignes || []).map(li => {
      const produit = produits.find(p => String(p.id) === String(li.produit))
      const taux = produit ? tauxTvaOf(produit) : tauxTvaOuDefaut(li.taux_tva, 20)
      const prixTtc = produit
        ? ttcFromHt(li.prix_unitaire_ht, taux)
        : (li.prix_unitaire_ttc ?? 0)
      return {
        produit: li.produit ?? '',
        designation: li.designation,
        quantite: li.quantite,
        prix_unit_ttc: prixTtc,
        taux_tva: taux,
        variante: li.variante || '',
      }
    })
    if (!generated.length) {
      setErrors(e => ({ ...e, autofill: 'Aucun produit solaire reconnu dans le stock.' }))
      return
    }
    // Même message que la composition locale (mêmes clés d'erreur, même bandeau).
    const manquants = generated
      .filter(r => !r.produit && parseFloat(r.quantite) > 0)
      .map(r => r.designation || 'ligne sans produit')
    const askedW = parseFloat(panelW) || 710
    const realW = data.panel_watt
    let mismatch = null
    if (realW && Math.abs(realW - askedW) > 1) {
      mismatch = `Attention : le stock ne propose pas de panneau ${askedW} W ; `
        + `un panneau ${realW} W a été retenu. La puissance réelle du système est `
        + `${data.kwc_reel} kWc (et non ${kwp} kWc). Ajustez le nombre de panneaux ou le `
        + 'wattage pour la cible voulue.'
    }
    const marquesManquantes = data.marques_manquantes || []
    const marquesMsg = marquesManquantes.length
      ? `Marque épinglée introuvable au stock : ${marquesManquantes
          .map(m => `${m.marque} (${roleLabel(m.role)})`).join(', ')}. `
        + 'Ajoutez le produit ou changez la marque dans Paramètres → Gammes.'
      : null
    const manquantsMsg = manquants.length
      ? `Aucun produit du stock ne correspond à : ${[...new Set(manquants)].join(', ')}. `
        + 'Complétez le catalogue ou choisissez ces produits à la main dans les lignes.'
      : null
    // `avertissements` (dry-run serveur) : mêmes messages que ceux que PVOND
    // affichait localement pour un onduleur incomplet, un rôle absent, etc. —
    // rendus tels quels dans le même bandeau, jamais tus.
    const avertissementsMsg = (data.avertissements || []).join(' ') || null
    setErrors(e => ({
      ...e,
      autofill: [manquantsMsg, avertissementsMsg].filter(Boolean).join(' ') || null,
      autofillKwc: mismatch,
      marquesManquantes: marquesMsg,
    }))
    recomposerLignes(generated)
  }

  const handleAutoFill = async () => {
    // PVOND — le bandeau des onduleurs grisés appartient au DERNIER
    // auto-remplissage : on le vide d'abord, sinon un message du run précédent
    // survivrait à un changement de mode (le pompage n'a pas d'onduleur).
    setOnduleursIncomplets([])
    // Mode agricole : équipement pompage (pompe + variateur + champ PV)
    if (modeInstallation === 'agricole') {
      // AGR130 — Auto-remplir pose les lignes du KIT de la taille choisie,
      // telles que le serveur les a composées (aperçu AGR127) : aucune
      // composition JavaScript. Sans aperçu, rien n'est inventé.
      const kit = apercuPompage?.donnees?.kit
      const generated = lignesDepuisKit(kit, produits)
      if (!generated.length) {
        setErrors(e => ({ ...e, autofill: 'Le dimensionnement du serveur n\'est pas encore disponible : '
          + 'renseignez le besoin, la hauteur et le cas de pompe, puis patientez un instant.' }))
        return
      }
      setErrors(e => ({ ...e, autofill: null, marquesManquantes: null }))
      recomposerLignes(generated)
      // Succès sur le marché agricole : une erreur de composition
      // résidentielle antérieure ne décrit plus rien (QJR577).
      setCompositionErreur(null)
      // QJR99 — le dimensionnement POSE une taille calculée : la même
      // transition que la réouverture d'un devis (`REOUVERTURE`) la pose SANS
      // marquer le champ « touché » (ce n'est pas une frappe).
      const nb = apercuPompage?.donnees?.champ?.nb_panneaux
      if (Number.isFinite(Number(nb)) && Number(nb) > 0) {
        dispatchSizing({ type: 'REOUVERTURE', devis: { panneaux: Number(nb) } })
      }
      setPompageAutoFilled(true)
      return
    }
    // U3COMPOSE (26/08/2026) — RÉSIDENTIEL SEULEMENT : le dry-run serveur
    // (POST /ventes/devis/composition/, U3) devient la source de vérité de
    // l'aperçu écran au lieu de la recomposition locale (deux implémentations
    // divergeaient déjà avant U3, incident du 20/08 — câbles, marques,
    // ordre, arrondi panneaux). Un échec réseau/serveur retombe SANS
    // EXCEPTION sur `composeLocalement` (ex-corps de cette fonction) :
    // l'écran ne doit jamais se retrouver sans Auto-remplir. Agricole
    // (ci-dessus) / industriel / commercial : AUCUN dry-run serveur n'existe
    // pour ces marchés — comportement local strictement inchangé.
    if (modeInstallation === 'residentiel') {
      if (kwp <= 0) {
        setErrors(e => ({ ...e, autofill: 'Entrez le nombre de panneaux' }))
        return
      }
      setAutoFillLoading(true)
      try {
        const body = {
          kwc: kwp,
          panel_watt: parseFloat(panelW) || 710,
          // STKCAT1/STKCAT7 — `structure_type` reste envoyé comme ALIAS
          // DÉPRÉCIÉ (compatibilité descendante ET repli quand aucun produit
          // n'est choisi) ; `structure_produit_id`, quand il est là, est
          // PRIORITAIRE côté serveur et les deux ne se combinent jamais.
          structure_type: structureType,
          ...(structureProduitId
            ? { structure_produit_id: Number(structureProduitId) }
            : {}),
        }
        // BARÈME TRANSPORT — QJR604 : l'écran envoie l'ID du lead ; le serveur
        // en résout la ville (lead de la société) et reprice la ligne
        // Transport dans l'étape composer. Sans lead : prix catalogue.
        if (selectedLead?.id) body.lead = selectedLead.id
        // OFFGRID — champ additif optionnel (contrat backend) : absent quand
        // `horsReseau` est faux, le serveur dérive alors de
        // `lead.raccordement == 'aucun'` lui-même. Envoyé explicitement ici
        // pour couvrir le cas où le vendeur bascule le contrôle à la main sans
        // que le lead porte ce raccordement.
        if (horsReseau) body.hors_reseau = true
        // Même déclenchement que la fusion locale ci-dessus (composeLocalement) :
        // seuls « Les deux » et « Avec batterie » servent réellement l'axe
        // batterie, et seulement quand il diverge du champ sans stockage.
        // OFFGRID — jamais cette branche : une composition hors réseau ne
        // connaît qu'une option, le serveur ne reçoit pas `dimensionnement_avec`.
        if (!horsReseau && (scenario === SCENARIO_LES_DEUX || scenario === SCENARIO_AVEC)) {
          const kwpAvec = resolveKwcAvec()
          if (Math.abs(kwpAvec - kwp) > 1e-9) {
            if (scenario === SCENARIO_AVEC) {
              // mono avec : compose l'optimum AVEC seul, aucune fusion —
              // MIROIR EXACT de `composeAvec()` du repli local, qui compose
              // UNE fois à `kwpAvec`. Envoyer `dimensionnement_avec` ici
              // ferait composer au serveur DEUX champs fusionnés (variantes
              // 'sans'/'avec') alors que l'écran n'affiche même pas l'option
              // sans batterie dans ce scénario : le kWc AVEC devient donc la
              // puissance UNIQUE de la requête.
              body.kwc = kwpAvec
            } else {
              body.dimensionnement_avec = buildDimensionnementAvec(kwpAvec)
            }
          }
        }
        const { data } = await ventesApi.composerDevis(body)
        setCompositionErreur(null)
        appliquerCompositionServeur(data)
      } catch (err) {
        // QJR577 (D-QJR5-9) — PLUS de repli JavaScript : les lignes restent
        // celles de l'écran, l'erreur du serveur est rendue telle quelle (ou
        // une cause française générique) avec « Réessayer ».
        const detail = err?.response?.data?.detail
        setCompositionErreur(typeof detail === 'string' && detail
          ? detail
          : "Le serveur n'a pas pu composer ce devis (réseau ou serveur "
            + 'indisponible) — les lignes n\'ont pas changé.')
      } finally {
        setAutoFillLoading(false)
      }
      return
    }
    // CIQ126 — commercial ET industriel : UN appel au moteur serveur C&I
    // (`etude-ci/preview`), puis les lignes de SA composition telles quelles
    // (quantités et produits ; « prix à renseigner » nommé). Aucune
    // composition JavaScript, aucun dimensionnement local.
    if (!marcheCi) return
    const corps = corpsCiDepuisProfil(profilCi, ctxProfilCi)
    if (!corps) {
      setErrors(e => ({ ...e, autofill: 'Renseignez la consommation du site (ou une taille '
        + 'explicite) : le moteur C&I en a besoin pour composer le devis.' }))
      return
    }
    setAutoFillLoading(true)
    try {
      const { data } = await ventesApi.etudeCiPreview(corps)
      const generated = lignesDepuisCompositionCi(data?.composition, produits)
      if (!generated.length) {
        setErrors(e => ({ ...e, autofill: 'Le moteur C&I n\'a retenu aucune taille : '
          + 'voir la raison d\'arrêt sous le profil.' }))
        return
      }
      const aRenseigner = data?.composition?.prix_a_renseigner || []
      setErrors(e => ({
        ...e,
        autofill: aRenseigner.length
          ? `Prix à renseigner : ${aRenseigner.join(', ')} — devis incomplet.` : null,
        autofillKwc: null,
        marquesManquantes: null,
      }))
      setCompositionErreur(null)
      const nb = data?.taille?.nb_panneaux
      if (Number.isFinite(Number(nb)) && Number(nb) > 0) {
        dispatchSizing({ type: 'REOUVERTURE', devis: { panneaux: Number(nb) } })
      }
      recomposerLignes(generated)
    } catch (err) {
      const detail = err?.response?.data?.detail
      setCompositionErreur(typeof detail === 'string' && detail
        ? detail
        : 'Le moteur C&I n\'a pas pu composer ce devis (réseau ou serveur '
          + 'indisponible) — les lignes n\'ont pas changé.')
    } finally {
      setAutoFillLoading(false)
    }
  }

  // CJ2b — bouton « Appliquer cette taille » d'une ligne du tableau de
  // dimensionnement (moteur horaire serveur) : pose `nbPanneaux`/`panelW`
  // depuis la ligne choisie puis relance EXACTEMENT le même chemin de
  // composition que le bouton « Auto-remplir » (`handleAutoFill`) — jamais
  // une seconde règle de composition.
  //
  // QJR99 — le couple `appliquerTaillePending` (ref) + effet calé sur
  // `[nbPanneaux, panelW]` est SUPPRIMÉ : la transition `TAILLE_APPLIQUEE`
  // incrémente elle-même `compositionSeq`, et l'UNIQUE effet de composition
  // ci-dessous relance l'auto-remplissage. Au passage l'ancien montage ne
  // repartait PAS quand la ligne choisie retombait sur le compte courant (aucun
  // changement de dépendance → drapeau laissé armé pour la frappe suivante) ;
  // un compteur, lui, avance toujours.
  const appliquerTailleDimensionnement = (ligne) => {
    if (!ligne || !(ligne.panneaux > 0)) return
    // QJR570 — confirmation (quantités figées seulement) AVANT la transition.
    avecQuantitesFigees(() => dispatchSizing({ type: 'TAILLE_APPLIQUEE', ligne }))
  }

  // FOUNDER 26/08 — bouton « Recalculer le dimensionnement ». Causes RÉELLES
  // (revue adversariale 26/08 — corrige la prose initiale, qui affirmait à
  // tort que `nbPanneauxTouched` restait FERMÉ après un chargement d'édition ;
  // en réalité rien dans l'effet d'édition ?edit= ne touche ce ref, il reste
  // à sa valeur `useRef(false)` par défaut — c'est la preuve gardée par les
  // tests ROOT CAUSE 1-3 ci-dessous) :
  //   1. En ÉDITION (?edit=ID), `fHiver`/`fEte` ne sont JAMAIS reposées
  //      depuis le devis serveur (aucune source ne les porte encore côté
  //      serveur) — retaper la facture repart donc d'un champ VIDE, pas de
  //      la facture d'origine.
  //   2. Le bouton « Auto-remplir » existant (`handleAutoFill`) ne fait que
  //      recomposer le catalogue au `nbPanneaux` COURANT — il ne redérive
  //      jamais ce compte depuis la facture (`computeAutoSizing` n'y est
  //      jamais appelé).
  //   3. Dès qu'un nombre de panneaux a été touché À LA MAIN (n'importe où,
  //      n'importe quand dans la session — pas spécifiquement à cause de
  //      l'édition), `touche.nbPanneaux` se ferme et plus AUCUNE frappe sur
  //      la facture ne recalcule quoi que ce soit (N3, comportement voulu).
  // Ce bouton est le déverrouillage EXPLICITE demandé par le fondateur : un
  // clic vaut consentement à remplacer les quantités auto-dérivées (jamais
  // une frappe seule, cf. règle N3/`syncBillEstimator`).
  //
  // Rejoue le MÊME balayage palier/payback que `computeAutoSizing` sur la
  // facture ACTUELLE (fHiver/fEte), pose les DEUX résultats (sans/avec,
  // L-2OPT), puis relance la composition par le chemin EXACT du bouton
  // « Auto-remplir » (`handleAutoFill` — dry-run serveur résidentiel, repli
  // local `composeLocalement` inchangé pour les autres marchés/pannes
  // réseau) : aucune deuxième règle de composition, et donc la même FUSION
  // que l'Auto-remplir (QJR570, D-QJR5-4 : prix tapés, sections, notes,
  // options et produits ajoutés à la main conservés ; quantités figées
  // confirmées AVANT la transition, jamais dans handleAutoFill).
  //
  // QJR99 — F1/F2 (revue adversariale 26/08) exigeaient de DÉVERROUILLER le
  // garde-fou « touché » le temps du calcul synchrone, puis de restaurer
  // EXACTEMENT sa valeur d'avant le clic — une danse à trois instructions
  // (`recalcDimPriorTouched` / `= false` / restauration dans l'effet) entre
  // lesquelles une frappe pouvait s'engouffrer. Les deux refs SONT SUPPRIMÉES :
  // `RECALCUL_DEMANDE` rouvre le drapeau POUR LA COMPOSITION QUI SUIT et le
  // restaure DANS LA MÊME TRANSITION (invariant 3 du reducer) — la fenêtre
  // n'existe plus, et `toucheNbPanneauxPourComposition` est le seul lecteur qui
  // la voit ouverte, sur une seule transition.
  const recalculerDimensionnement = () => {
    // U3-MOTEUR (fondateur 29/08/2026) — en RÉSIDENTIEL, ce bouton relit la
    // recommandation du MOTEUR HORAIRE serveur (déjà interrogée par le dry-run
    // d'aperçu — aucun appel réseau supplémentaire), jamais un palier chiffré
    // à l'écran : c'était le dernier endroit où un nombre de panneaux
    // auto-calculé localement pouvait encore écraser celui du moteur.
    // `sizingInfo` reste NUL sur ce chemin : son encart parle de « palier
    // retenu / besoin lu sur la facture », deux notions du balayage local qui
    // ne décrivent pas ce que le moteur a fait (règle chiffres-vérifiés).
    let retenu = null
    if (modeInstallation === 'residentiel') {
      const dim = etudeHoraireDonnees?.dimensionnement
      const source = (scenario === SCENARIO_AVEC
        && Number(dim?.recommandation_avec?.panneaux) > 0)
        ? dim.recommandation_avec : dim?.recommandation
      if (!(Number(source?.panneaux) > 0)) {
        setErrors(e => ({
          ...e,
          // Message FRANÇAIS du serveur quand il en a un (il nomme la donnée
          // manquante), sinon la cause générique — jamais un chiffre supposé.
          recalcDim: dim?.motivation
            || etudeHoraireDonnees?.avertissements?.[0]
            || (etudeHoraireChargement
              ? 'Dimensionnement en cours de calcul — réessayez dans un instant.'
              : "Le moteur n'a pas pu chiffrer de recommandation : complétez la "
                + 'facture, la ville et le raccordement du client, puis réessayez.'),
        }))
        return
      }
      retenu = {
        nbPanneaux: Number(source.panneaux),
        kwcOptimal: source.kwc != null ? Number(source.kwc) : null,
      }
    } else {
      // CIQ126 — C&I : la taille retenue par le moteur serveur (aperçu en
      // direct du profil déclaré) ; sans elle, rien n'est inventé.
      const t = apercuCi.donnees?.taille
      if (!marcheCi || !(Number(t?.nb_panneaux) > 0)) {
        setErrors(e => ({
          ...e,
          recalcDim: 'Le moteur C&I n\'a pas encore retenu de taille : complétez le '
            + 'profil de consommation du site, puis réessayez.',
        }))
        return
      }
      retenu = {
        nbPanneaux: Number(t.nb_panneaux),
        kwcOptimal: t.retenue_kwc != null ? Number(t.retenue_kwc) : null,
      }
    }
    setErrors(e => ({ ...e, recalcDim: null }))
    // Une seule transition : la taille retenue est posée, `sizingInfo` reste
    // NUL en résidentiel (son encart parle de « palier retenu », une notion du
    // balayage local), le garde-fou « touché » est rouvert POUR LA COMPOSITION
    // QUI SUIT et restauré dans le même mouvement, et `compositionSeq` avance —
    // un recalcul qui retombe sur le MÊME compte de panneaux doit quand même
    // relancer la composition (catalogue/marques/scénario ont pu changer).
    // QJR570 — confirmation (quantités figées seulement) AVANT la transition.
    avecQuantitesFigees(() => dispatchSizing({ type: 'RECALCUL_DEMANDE', retenu }))
  }
  // QJR99 — L'UNIQUE effet de composition : « Appliquer cette taille » et
  // « Recalculer le dimensionnement » avancent tous deux `compositionSeq`, et
  // relancent donc EXACTEMENT le chemin du bouton « Auto-remplir » (dry-run
  // serveur résidentiel, repli local ailleurs) — jamais une seconde règle de
  // composition. F2 (26/08) reste satisfait sans aucune manœuvre de
  // verrouillage : `handleAutoFill` lit `resolveKwcAvec()` — donc la fenêtre
  // `recalcul` ouverte par CETTE transition — dans son préfixe SYNCHRONE, et
  // toute action ultérieure referme la fenêtre côté reducer.
  useEffect(() => {
    if (!recalcDimTick) return
    // Différé en MICROTÂCHE (règle react-hooks/set-state-in-effect — les
    // setState du préfixe synchrone de `handleAutoFill` cascaderaient dans
    // l'effet). Aucun événement utilisateur ni re-rendu ne peut s'intercaler
    // avant une microtâche, et `handleAutoFill` lit la fenêtre `recalcul` par
    // CLÔTURE du rendu qui l'a ouverte — F2 reste satisfait à l'identique.
    queueMicrotask(() => { Promise.resolve(handleAutoFill()).catch(() => {}) })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne réagit qu'au compteur de composition du reducer
  }, [recalcDimTick])

  return {
    handleAutoFill, appliquerTailleDimensionnement, recalculerDimensionnement,
  }
}

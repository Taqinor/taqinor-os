// SPL47 — LES GESTES DE LIGNES DU GÉNÉRATEUR, déplacés tels quels de
// DevisGenerator.jsx : édition (setLine, tarifs, produit, quantité,
// désignation, renommage), ajout / retrait / ordre, villas, recomposition
// (`modeRecomposition`, `recomposerLignes`, `avecQuantitesFigees`) et
// modèles (`handlePresetApplied`). Corps verbatim, deps inchangées ; `ctx`
// porte, nom par nom, ce que le corps lit du composant.
import { useCallback, useEffect, useRef, useState } from 'react'
import { ecrireLastTva } from '../../../../features/ventes/quote/ecranDefauts.js'
import ventesApi from '../../../../api/ventesApi'
import { _hasPrix, appliquerRecomposition, deriveRoleOrderFromLines, lignesManuellesEnConflitPossible, tauxTvaOf, ttcFromHt } from '../../../../features/ventes/solar'
import stockApi from '../../../../api/stockApi'
import { emptyLine, structureLine, withKeys } from '../../../../features/ventes/quote/ligneFabrique.js'
import { toast } from '../../../../ui/confirm'
import { lignesServeurVersEcran } from '../../../../features/ventes/quote/lignesEcran'

export function useLignesEcran(ctx) {
  const {
    confirm, canRenameLine, renameDialog, setRenameDialog, setRenameBusy, setRenameError, produits,
    setProduits, clientId, lines, setLines, setSavingOrdreLignes, setTauxTva, setDiscountPct,
    linesTableRef, pendingFocusKey, setPendingFocusKey, setMultiMode, villaGroups, setVillaGroups,
    appliquerMarcheEcran,
  } = ctx

  // ── Lignes ──
  // VX188 — callback stabilisé (identité stable via useCallback, clé de ligne
  // en ARGUMENT) pour que `React.memo(DevisLineRow)` saute le re-rendu d'une
  // ligne inchangée. VX93 — mémorise le dernier taux TVA saisi à la main pour
  // pré-remplir la prochaine ligne ajoutée (ecrireLastTva est un writer stable).
  const setLine = useCallback((key, k, v) => {
    if (k === 'taux_tva') ecrireLastTva(v)
    setLines(ls => ls.map(l => (l._key === key
      ? {
          ...l, [k]: v,
          // VX249(b) — une modification MANUELLE du taux retire le style
          // « suggéré » de CETTE ligne (jamais les autres) ; tout autre champ
          // laisse `_tvaSuggested` inchangé.
          ...(k === 'taux_tva' ? { _tvaSuggested: false } : {}),
          // N2 — la frappe manuelle du prix pose le verrou `prixManuel` : la
          // résolution de liste de prix (refreshTarif, déclenchée par l'effet
          // [clientId, lines.length]) ne réécrit plus ce prix tant que le
          // produit de CETTE ligne n'est pas resélectionné (onProduitChange
          // lève le verrou).
          ...(k === 'prix_unit_ttc' ? { prixManuel: true } : {}),
          // QJR569 — même règle pour la QUANTITÉ tapée d'une ligne produit :
          // le verrou `quantiteManuelle` (gardes D12 du serveur) est posé ICI
          // seulement — une composition ne le pose jamais.
          ...(k === 'quantite' && l.produit ? { quantiteManuelle: true } : {}),
        }
      : l)))
  }, [setLines])

  // XSAL3 — badge « Tarif : <liste> » par ligne, quand le prix résolu vient
  // d'une liste de prix client (source !== 'standard'). Purement informatif +
  // pré-remplissage au changement de produit/quantité/client — ne touche
  // JAMAIS une valeur déjà tapée manuellement par l'utilisateur après coup
  // (aucun re-snap sur un prix modifié à la main).
  const [tarifBadges, setTarifBadges] = useState({})

  // Identité stable (useCallback, dépend seulement de `clientId`) : référencée
  // par onProduitChange/onQuantiteChange ci-dessous (exhaustive-deps /
  // preserve-manual-memoization) sans faire recréer ces callbacks à chaque
  // rendu.
  const refreshTarif = useCallback(async (key, produitId, quantite) => {
    if (!produitId) {
      setTarifBadges(b => { const { [key]: _drop, ...rest } = b; return rest })
      return
    }
    try {
      const { data } = await ventesApi.getPrixApplicable({
        produit: produitId,
        client: clientId || undefined,
        quantite: quantite || 1,
      })
      if (data.source && data.source !== 'standard') {
        setTarifBadges(b => ({ ...b, [key]: data.liste_nom }))
        // N2 — jamais réécrire un prix TAPÉ À LA MAIN (drapeau `prixManuel`,
        // relu ICI au moment de l'écriture via la mise à jour fonctionnelle —
        // jamais un `lines` capturé au lancement de l'appel réseau, qui serait
        // périmé) : le vendeur reprend la main tant qu'il n'a pas resélectionné
        // le produit de cette ligne (onProduitChange lève le verrou).
        setLines(ls => ls.map(l =>
          (l._key === key && !l.prixManuel) ? { ...l, prix_unit_ttc: String(data.prix) } : l))
      } else {
        setTarifBadges(b => { const { [key]: _drop, ...rest } = b; return rest })
      }
    } catch {
      // Résolution de prix indisponible : on garde le prix standard déjà posé,
      // jamais de blocage de la saisie.
      setTarifBadges(b => { const { [key]: _drop, ...rest } = b; return rest })
    }
  }, [clientId, setLines])

  const onProduitChange = useCallback((key, produitId) => {
    const p = produits.find(p => String(p.id) === String(produitId))
    setLines(ls => ls.map(l =>
      l._key === key
        ? {
            ...l,
            produit: produitId,
            designation: p?.nom ?? l.designation,
            prix_unit_ttc: p ? String(ttcFromHt(p.prix_vente, tauxTvaOf(p))) : l.prix_unit_ttc,
            taux_tva: p ? String(tauxTvaOf(p)) : (l.taux_tva ?? '20'),
            // N2 — resélectionner un produit reprend la main sur son prix
            // catalogue : lève le verrou manuel posé par une frappe précédente.
            prixManuel: false,
            // QJR569 — …et le verrou de quantité (nouveau produit, nouvelle main).
            quantiteManuelle: false,
            // QJR570 — un produit choisi à la main n'est plus une ligne composée.
            compose: false,
            // QJR523 — le rôle stocké était celui de l'ANCIEN produit : le
            // serveur le re-déduit du nouveau.
            role_devis: '',
          }
        : l
    ))
    if (p) {
      const l = lines.find(x => x._key === key)
      refreshTarif(key, produitId, l?.quantite)
    }
  }, [produits, lines, refreshTarif, setLines])

  // Ré-interroge le tarif applicable quand la quantité change sur une ligne
  // déjà liée à un produit (paliers XSAL2), ou quand le client change (liste
  // XSAL1 assignée) — pour toutes les lignes liées à un produit.
  const onQuantiteChange = useCallback((key, quantite) => {
    setLine(key, 'quantite', quantite)
    const l = lines.find(x => x._key === key)
    if (l?.produit) refreshTarif(key, l.produit, quantite)
  }, [lines, setLine, refreshTarif])

  useEffect(() => {
    lines.forEach(l => { if (l.produit) refreshTarif(l._key, l.produit, l.quantite) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, lines.length])

  // QP2 — au blur d'une désignation modifiée (par un rôle autorisé) qui diffère
  // du nom du produit lié, propose les deux options : « renommer ici seulement »
  // (on garde le texte divergent, rien d'autre) ou « créer un nouveau produit
  // dans le stock » (clone serveur via /dupliquer/, puis on relie la ligne au
  // clone). Non bloquant : ne s'ouvre que sur une vraie divergence.
  const onDesignationBlur = useCallback((key) => {
    if (!canRenameLine) return
    const l = lines.find(x => x._key === key)
    if (!l || !l.produit) return
    const prod = produits.find(p => String(p.id) === String(l.produit))
    if (!prod) return
    const nouveauNom = (l.designation || '').trim()
    if (!nouveauNom || nouveauNom === (prod.nom || '').trim()) return
    setRenameError(null)
    setRenameDialog({ key, ancienNom: prod.nom, nouveauNom, produitId: l.produit })
  }, [canRenameLine, lines, produits])

  // Option (a) — « Renommer sur ce devis seulement » : on garde la désignation
  // divergente telle quelle, aucun produit créé. Juste fermer le dialogue.
  const renameHereOnly = () => setRenameDialog(null)

  // Option (b) — « Créer un nouveau produit dans le stock » : clone SERVEUR du
  // produit de base sous le nouveau nom (prix d'achat copié côté serveur,
  // jamais transmis par le client — QP2/QG4), puis relie la ligne au clone.
  const renameAsNewProduct = async () => {
    if (!renameDialog) return
    setRenameBusy(true)
    setRenameError(null)
    try {
      const res = await stockApi.dupliquerProduit(renameDialog.produitId, renameDialog.nouveauNom)
      const clone = res.data
      setProduits(ps => [...ps, clone])
      setLines(ls => ls.map(l =>
        l._key === renameDialog.key
          // AGNR32 — relier la ligne au clone SANS toucher au prix tapé ni à
          // la TVA de la ligne : seuls `produit` et `designation` changent ;
          // le prix négocié reste verrouillé (`prixManuel`).
          ? {
              ...l,
              produit: String(clone.id),
              designation: clone.nom,
              prixManuel: true,
            }
          : l))
      setRenameDialog(null)
    } catch (err) {
      const detail = err?.response?.data?.detail
      setRenameError(typeof detail === 'string'
        ? detail : 'La création du nouveau produit a échoué.')
    } finally {
      setRenameBusy(false)
    }
  }

  const addLine = () => setLines(ls => {
    const line = emptyLine()
    setPendingFocusKey(line._key) // VX90 — focus la nouvelle ligne après rendu.
    return [...ls, line]
  })
  // XSAL14 — ajoute une ligne de SECTION (intertitre) ou de NOTE (texte sans
  // prix). Exclue de tous les totaux ; rendue comme intertitre/note.
  const addStructureLine = (typeLigne) => setLines(ls => {
    const line = structureLine(typeLigne)
    setPendingFocusKey(line._key)
    return [...ls, line]
  })
  const removeLine = useCallback((key) =>
    setLines(ls => ls.filter(l => l._key !== key)), [setLines])
  // PVORD (fondateur 19/08/2026) — réordonnancement manuel des lignes dans
  // l'éditeur (monter/descendre). Mutation PURE de l'ORDRE du tableau
  // `lines` : le chemin de sauvegarde existant (`lignesPayload`, plus bas)
  // dérive déjà `ordre: idx` de cet ordre — aucun autre câblage requis pour
  // que le nouvel ordre soit persisté au « Enregistrer ». `delta` = -1
  // (monter) ou +1 (descendre) ; hors bornes = no-op silencieux.
  const moveLine = useCallback((key, delta) => setLines(ls => {
    const idx = ls.findIndex(l => l._key === key)
    if (idx < 0) return ls
    const target = idx + delta
    if (target < 0 || target >= ls.length) return ls
    const copy = ls.slice()
    const [item] = copy.splice(idx, 1)
    copy.splice(target, 0, item)
    return copy
  }), [setLines])
  const moveLineUp = useCallback((key) => moveLine(key, -1), [moveLine])
  const moveLineDown = useCallback((key) => moveLine(key, 1), [moveLine])
  // PVORD — « Enregistrer cet ordre comme ordre par défaut » : dérive la
  // séquence de rôles depuis les lignes COURANTES de l'écran (classification
  // réutilisée, jamais un nouveau mot-clé — voir deriveRoleOrderFromLines) et
  // la PATCH sur ParametresGammes.ordre_lignes. Best-effort, même patron que
  // GammesMarquesPage.jsx : un rôle non Admin/Responsable reçoit un 403 (géré
  // via un toast d'erreur), jamais un plantage de l'écran.
  const handleSaveOrdreLignes = async () => {
    const derived = deriveRoleOrderFromLines(lines)
    setSavingOrdreLignes(true)
    try {
      // CIQ127 — l'ordre enregistré est lu par le SERVEUR à chaque composition
      // (dry-run résidentiel, moteur C&I, devis automatique) : rien à garder ici.
      await ventesApi.updateParametresGammes({ ordre_lignes: derived })
      toast.success('Ordre des lignes enregistré comme ordre par défaut pour les prochains devis.')
    } catch (err) {
      const detail = err?.response?.data?.detail
      toast.error(typeof detail === 'string'
        ? detail : 'Impossible d\'enregistrer cet ordre par défaut.')
    } finally {
      setSavingOrdreLignes(false)
    }
  }
  // VX188 — identité stable pour ProduitPicker.onProduitCreated (passé à
  // chaque DevisLineRow) : setProduits est déjà un setState fonctionnel,
  // aucune dépendance réelle.
  const onProduitCreated = useCallback((p) => setProduits(ps => [...ps, p]), [])

  // VX90 — quand une ligne vient d'être ajoutée, focaliser son ProduitPicker et
  // la faire défiler dans la vue. On cible la ligne par son data-line-key, puis
  // le premier bouton (le déclencheur du ProduitPicker) de cette ligne.
  useEffect(() => {
    if (pendingFocusKey == null) return
    const row = linesTableRef.current
      ?.querySelector(`[data-line-key="${pendingFocusKey}"]`)
    if (row) {
      const picker = row.querySelector('button[type="button"]')
      picker?.focus()
      row.scrollIntoView({ block: 'nearest' })
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset one-shot du focus (VX90)
    setPendingFocusKey(null)
  }, [pendingFocusKey, lines])

  // ── QJ31 — Multi-propriétés ──────────────────────────────────────────────
  // Bascule de mode. En passant en « villas », chaque ligne sans groupe est
  // rattachée à l'équipement commun (index 0) par défaut ; en repassant en
  // « none »/« multiplier », on efface les groupes (mono-système / ×N).
  const onMultiModeChange = (m) => {
    setMultiMode(m)
    if (m === 'villas') {
      setLines(ls => ls.map(l =>
        l.groupeIndex == null ? { ...l, groupeIndex: 0, groupeLabel: 'Équipement commun' } : l))
    } else {
      setLines(ls => ls.map(l => ({ ...l, groupeIndex: null, groupeLabel: '' })))
    }
  }

  // Assigne une ligne à un groupe villa (met à jour l'index + le libellé).
  const setLineGroupe = useCallback((key, idx) => {
    const grp = villaGroups.find(g => g.index === idx)
    setLines(ls => ls.map(l =>
      l._key === key ? { ...l, groupeIndex: idx, groupeLabel: grp?.label ?? '' } : l))
  }, [villaGroups, setLines])

  const addVillaGroup = () => {
    setVillaGroups(gs => {
      const nextIndex = gs.reduce((m, g) => Math.max(m, g.index), 0) + 1
      return [...gs, { index: nextIndex, label: `Villa ${nextIndex}` }]
    })
  }

  const renameVillaGroup = (idx, label) => {
    setVillaGroups(gs => gs.map(g => (g.index === idx ? { ...g, label } : g)))
    // Répercute le nouveau libellé sur les lignes déjà rattachées à ce groupe.
    setLines(ls => ls.map(l => (l.groupeIndex === idx ? { ...l, groupeLabel: label } : l)))
  }

  const removeVillaGroup = (idx) => {
    if (idx === 0) return // l'équipement commun n'est pas supprimable
    setVillaGroups(gs => gs.filter(g => g.index !== idx))
    // Les lignes du groupe supprimé retombent sur l'équipement commun.
    setLines(ls => ls.map(l =>
      l.groupeIndex === idx ? { ...l, groupeIndex: 0, groupeLabel: 'Équipement commun' } : l))
  }

  // QJR570 (D-QJR5-4) — LE point d'écriture des trois recompositions
  // (composition locale, dry-run serveur, pompage) : FUSION par id produit
  // (`fusionnerRecomposition`) — prix tapés, sections, notes, options et
  // produits ajoutés à la main conservés d'office. Une quantité figée en
  // conflit est GARDÉE (le vendeur l'a confirmé avant le geste) et NOMMÉE.
  const modeRecomposition = useRef('garder')
  const recomposerLignes = (generated) => {
    const mode = modeRecomposition.current
    modeRecomposition.current = 'garder'
    const { conflits } = appliquerRecomposition(lines, generated, mode)
    setLines(ls => withKeys(appliquerRecomposition(ls, generated, mode).lignes))
    if (conflits.length) {
      toast.warning('Quantités figées gardées : ' + conflits.slice(0, 5)
        .map(c => `${c.designation} ${c.figee} (recalculé : ${c.recalculee})`).join(', ')
        + (conflits.length > 5 ? '…' : '') + '.')
    }
  }

  // QJR570 — la seule question posée avant une recomposition : des quantités
  // figées à la main existent (5 désignations au plus). Sans elles, AUCUNE
  // confirmation et le geste part de façon synchrone (invariant F2 QJR99 :
  // jamais de `confirm` DANS handleAutoFill). Annuler ne dispatche rien.
  const avecQuantitesFigees = (geste) => {
    // Conflit POSSIBLE seulement s'il existe une quantité figée à la main ;
    // prix tapés et options sont gardés d'office (aucun dialogue).
    const manuelles = lignesManuellesEnConflitPossible(lines)
    if (!manuelles.length) { modeRecomposition.current = 'garder'; geste(); return }
    const noms = manuelles.slice(0, 5)
      .map(l => `${l.designation || 'ligne'} : ${l.quantite}`).join(', ')
      + (manuelles.length > 5 ? '…' : '')
    confirm({
      title: 'Garder vos saisies ?',
      description: `Lignes saisies à la main (${noms}) : la recomposition peut les GARDER `
        + 'ou prendre uniquement les valeurs recalculées.',
      confirmLabel: 'Recomposer en les gardant',
      alternativeLabel: 'Prendre N (recalculé)',
      destructive: false,
    }).then((choix) => {
      if (choix === 'alternative') { modeRecomposition.current = 'recalcule'; geste() }
      else if (choix) { modeRecomposition.current = 'garder'; geste() }
    })
  }

  // QJR546 — appliquer un modèle REMPLACE les lignes À L'ÉCRAN, en création
  // comme en édition (plus d'apply-preset serveur qui ajoutait des lignes en
  // base sans que l'écran les voie) : remise, TVA et marché du modèle posés,
  // lignes au produit sans prix SAUTÉES et NOMMÉES. L'étude du client source
  // (etude_params_snapshot) n'est JAMAIS réappliquée. L'Enregistrer suivant
  // persiste le tout par replace-lines.
  const handlePresetApplied = (preset) => {
    const snapshot = Array.isArray(preset?.lignes_snapshot) ? preset.lignes_snapshot : []
    if (!snapshot.length) return
    const parId = new Map(produits.map(p => [String(p.id), p]))
    const sansPrix = []
    const retenues = snapshot.filter((l) => {
      const id = l.produit ?? l.produit_id
      if (id == null || id === '') return true
      const produit = parId.get(String(id))
      if (produit && !_hasPrix(produit)) {
        sansPrix.push(l.designation || produit.nom || `#${id}`)
        return false
      }
      return true
    })
    if (preset.mode_installation) appliquerMarcheEcran(preset.mode_installation, 'programme')
    if (preset.taux_tva != null) setTauxTva(String(preset.taux_tva))
    if (preset.remise_globale != null) setDiscountPct(String(parseFloat(preset.remise_globale) || 0))
    // QJR523 — même mappeur que la réouverture `?edit=` (HT → TTC au taux de
    // la ligne, tous les champs portés).
    setLines(withKeys(lignesServeurVersEcran(retenues, preset.taux_tva)))
    if (sansPrix.length) {
      toast.warning('Produit(s) sans prix non repris du modèle : ' + sansPrix.join(', '))
    }
  }

  return {
    setLine, tarifBadges, onProduitChange, onQuantiteChange, onDesignationBlur, renameHereOnly,
    renameAsNewProduct, addLine, addStructureLine, removeLine, moveLineUp, moveLineDown,
    handleSaveOrdreLignes, onProduitCreated, onMultiModeChange, setLineGroupe, addVillaGroup,
    renameVillaGroup, removeVillaGroup, recomposerLignes, avecQuantitesFigees, handlePresetApplied,
  }
}

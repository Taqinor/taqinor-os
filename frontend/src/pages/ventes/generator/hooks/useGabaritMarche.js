// T4-U3-006 — LA TABLE DE DÉPART DU GÉNÉRATEUR SUIT LE MARCHÉ. Sorti de
// DevisGenerator.jsx (fichier-mur, règle C20). La table posée au chargement du
// stock est celle du marché courant (pompage en agricole : jamais d'onduleur
// ni de batterie) ; son empreinte est gardée pour qu'un changement de marché
// remplace une table encore INTACTE. Une table éditée n'est jamais remplacée
// en silence : `proposerRemplacementLignes` le demande au vendeur.
import { useEffect, useRef } from 'react'
import { withKeys } from '../../../../features/ventes/quote/ligneFabrique.js'
import {
  lignesParDefautDuMarche, signatureGabarit, tableIntacte,
} from '../../../../features/ventes/calc/lignesDefaut.js'

export function useGabaritMarche({
  produits, tvaStandard, modeInstallation, lines, setLines, editId, linesInitializedRef,
  confirm, modeOptions = [],
}) {
  const gabaritRef = useRef(null)
  const poserGabarit = (mode) => {
    // QJR570 — les lignes par défaut sont une composition (pas une saisie).
    // ADVS47 — produit sans taux : TVA standard de la société (profil, D-APAR-1).
    const lignes = withKeys(lignesParDefautDuMarche(produits, mode, undefined, tvaStandard)
      .map(r => ({ ...r, compose: true })))
    gabaritRef.current = { mode, signature: signatureGabarit(lignes) }
    setLines(lignes)
  }
  // Table par défaut une fois le stock chargé (jamais par-dessus un brouillon
  // restauré : `linesInitializedRef` est posé par sa restauration).
  useEffect(() => {
    if (linesInitializedRef.current || !produits.length) return
    linesInitializedRef.current = true
    poserGabarit(modeInstallation)
  }, [produits, tvaStandard]) // eslint-disable-line react-hooks/exhaustive-deps
  // Marché changé (par le vendeur ou par le lead) sur une table INTACTE.
  useEffect(() => {
    const g = gabaritRef.current
    if (editId || !g || g.mode === modeInstallation || !tableIntacte(lines, g.signature)) return
    poserGabarit(modeInstallation)
  }, [modeInstallation]) // eslint-disable-line react-hooks/exhaustive-deps

  // Après un changement de marché demandé par le vendeur : une table ÉDITÉE
  // n'est remplacée que sur sa réponse.
  const proposerRemplacementLignes = async (m) => {
    const g = gabaritRef.current
    if (editId || !g || tableIntacte(lines, g.signature)) return
    const libelle = (modeOptions.find(o => o.value === m)?.label || m).replace(/^\S+\s/, '')
    const remplacer = await confirm({
      title: `Repartir des lignes du marché « ${libelle} » ?`,
      description: m === 'agricole'
        ? 'Vos lignes actuelles seront remplacées par celles du pompage (pompe, variateur, '
          + 'panneaux… sans onduleur ni batterie).'
        : 'Vos lignes actuelles seront remplacées par les lignes de départ de ce marché.',
      confirmLabel: 'Remplacer les lignes',
      cancelLabel: 'Garder mes lignes',
    })
    if (remplacer) poserGabarit(m)
  }
  return { proposerRemplacementLignes }
}

export default useGabaritMarche

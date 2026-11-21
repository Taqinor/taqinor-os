import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ONGLETS, PARAM_ONGLET } from './onglets'

/* ACAL415 — les outils et onglets de l'atelier dans la palette ⌘K de l'ERP.
   Contrat d'événement EXISTANT, inchangé : `taqinor:lead-workspace-actions`
   (`detail.actions = [{id, label, run}]`, écouté par `CommandPalette.jsx`, qui
   filtre sur le libellé seul). La liste est vidée en quittant l'atelier. Seuls
   les outils que `builderApi.raccourcis` expose sont proposés ; les outils
   d'édition disparaissent en lecture seule. */
const EVENEMENT = 'taqinor:lead-workspace-actions'

// [clé de `raccourcis`, libellé en mots courants, édite le document ?]
const OUTILS = [
  ['outilTrace', 'Tracer le toit (contour)', true],
  ['outilObstacle', 'Ajouter un obstacle', true],
  ['outilZone', 'Dessiner une zone', true],
  ['outilMesure', 'Mesurer une distance', false],
  ['aimantation', 'Activer ou couper l’aimantation', false],
  ['supprimer', 'Supprimer la sélection', true],
  ['dupliquer', 'Dupliquer la sélection', true],
  ['pleinEcran', 'Plein écran', false],
]

export function useCommandesAtelier({ builderApi = null, lectureSeule = false } = {}) {
  const [, setParametres] = useSearchParams()

  const actions = useMemo(() => {
    const outils = OUTILS
      .filter(([cle, , edite]) => !(edite && lectureSeule)
        && typeof builderApi?.raccourcis?.[cle] === 'function')
      .map(([cle, label]) => ({
        id: `calepinage-outil-${cle}`, label, run: () => builderApi.raccourcis[cle](),
      }))
    const onglets = ONGLETS.map((o) => ({
      id: `calepinage-onglet-${o.cle}`,
      label: `Ouvrir ${o.libelle}`,
      run: () => setParametres((prec) => {
        const suivants = new URLSearchParams(prec)
        suivants.set(PARAM_ONGLET, o.cle)
        return suivants
      }),
    }))
    return [...outils, ...onglets]
  }, [builderApi, lectureSeule, setParametres])

  useEffect(() => {
    window.dispatchEvent(new CustomEvent(EVENEMENT, { detail: { actions } }))
    return () => {
      window.dispatchEvent(new CustomEvent(EVENEMENT, { detail: { actions: [] } }))
    }
  }, [actions])
}

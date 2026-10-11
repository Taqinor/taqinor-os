// ZSAL3 — Équipes commerciales (admin CRUD). Regroupe des commerciaux pour le
// dashboard « Mes équipes » (pipeline/CA agrégés par équipe). Autonome : gère
// son propre chargement, la liste des membres assignables lui est passée par
// le parent (déjà chargée pour le reste de l'onglet Leads).
import { useEffect } from 'react'
import useEquipesAdmin from './useEquipesAdmin'
import { Plus, Trash2, Archive, ArchiveRestore } from 'lucide-react'
import EquipesAdminPanel from './EquipesAdminPanel'
import crmApi from '../../api/crmApi'
import { useConfirmDialog } from '../../ui/confirm'

export default function EquipesCommercialesSection({ assignables = [] }) {
  // APAR41 — dialogue de confirmation MAISON (jamais window.confirm).
  const { confirmDelete: confirmerSuppression } = useConfirmDialog()
  const { equipes, setEquipes, loading, setLoading, error, setError, newNom, setNewNom, busyId, setBusyId } = useEquipesAdmin()

  const load = () => {
    setLoading(true)
    crmApi.getEquipes()
      .then((r) => setEquipes(r.data.results ?? r.data))
      .catch(() => setError('Impossible de charger les équipes.'))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load() }, [])

  const addEquipe = async () => {
    if (!newNom.trim()) return
    try {
      await crmApi.saveEquipe(null, { nom: newNom.trim() })
      setNewNom('')
      load()
    } catch {
      setError("La création de l'équipe a échoué.")
    }
  }

  const renameEquipe = async (equipe, nom) => {
    if (!nom.trim() || nom === equipe.nom) return
    await crmApi.saveEquipe(equipe.id, { nom: nom.trim() }).catch(() => {})
    load()
  }

  const toggleResponsable = async (equipe, responsableId) => {
    setBusyId(equipe.id)
    try {
      await crmApi.saveEquipe(equipe.id, {
        responsable: responsableId || null,
      })
      load()
    } finally {
      setBusyId(null)
    }
  }

  const toggleMembre = async (equipe, userId) => {
    const membres = equipe.membres ?? []
    const next = membres.includes(userId)
      ? membres.filter((id) => id !== userId)
      : [...membres, userId]
    setBusyId(equipe.id)
    try {
      await crmApi.saveEquipe(equipe.id, { membres: next })
      load()
    } finally {
      setBusyId(null)
    }
  }

  const archiveEquipe = async (equipe) => {
    await crmApi.saveEquipe(equipe.id, { actif: !equipe.actif }).catch(() => {})
    load()
  }

  const delEquipe = async (equipe) => {
    if (!(await confirmerSuppression({ title: `Supprimer l'équipe « ${equipe.nom} » ?` }))) return
    await crmApi.deleteEquipe(equipe.id).catch(() => {})
    load()
  }

  return (
    <EquipesAdminPanel
      titre="Équipes commerciales"
      description={`Regroupez des commerciaux pour le tableau de bord « Mes équipes »
          (pipeline, activités en retard, CA signé agrégés). Un commercial
          sans équipe reste visible partout ailleurs.`}
      vide="Aucune équipe configurée."
      placeholder="Nouvelle équipe"
      chefLabel="Responsable d'équipe" chefField="responsable" chefIdPrefix="ec-resp"
      loading={loading} error={error} equipes={equipes} busyId={busyId}
      assignables={assignables}
      onRename={renameEquipe} onArchive={archiveEquipe} onDelete={delEquipe}
      onSetChef={toggleResponsable} onToggleMembre={toggleMembre}
      newNom={newNom} setNewNom={setNewNom} onAdd={addEquipe} />
  )
}

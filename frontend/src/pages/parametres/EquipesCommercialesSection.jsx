// ZSAL3 — Équipes commerciales (admin CRUD). Regroupe des commerciaux pour le
// dashboard « Mes équipes » (pipeline/CA agrégés par équipe). Autonome : gère
// son propre chargement, la liste des membres assignables lui est passée par
// le parent (déjà chargée pour le reste de l'onglet Leads).
import { useEffect } from 'react'
import useEquipesAdmin from './useEquipesAdmin'
import { Plus, Trash2, Archive, ArchiveRestore } from 'lucide-react'
import EquipesAdminPanel from './EquipesAdminPanel'
import ReglesAttributionEditor from './ReglesAttributionEditor'
import crmApi from '../../api/crmApi'
import { useConfirmDialog } from '../../ui/confirm'
import toutesLesPages from './toutesLesPages'
import { apiErrorMessage } from '../../lib/apiError'

export default function EquipesCommercialesSection({ assignables = [] }) {
  // APAR41 — dialogue de confirmation MAISON (jamais window.confirm).
  const { confirmDelete: confirmerSuppression } = useConfirmDialog()
  const { equipes, setEquipes, loading, setLoading, error, setError, newNom, setNewNom, busyId, setBusyId } = useEquipesAdmin()

  const load = () => {
    setLoading(true)
    toutesLesPages((params) => crmApi.getEquipes(params))
      .then((rows) => setEquipes(rows))
      .catch(() => setError('Impossible de charger les équipes.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps -- chargement des équipes commerciales au montage uniquement (D-ENF22)

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
      setError(null)
      load()
    } catch (e) {
      setError(apiErrorMessage(e, 'Le changement de responsable a échoué.'))
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
      setError(null)
      load()
    } catch (e) {
      // 400 « X est déjà membre de l'équipe Y » : on l'affiche tel quel.
      setError(apiErrorMessage(e, 'La mise à jour des membres a échoué.'))
    } finally {
      setBusyId(null)
    }
  }

  const toggleRecoitLeads = async (equipe, valeur) => {
    setBusyId(equipe.id)
    try {
      await crmApi.saveEquipe(equipe.id, { recoit_leads: valeur })
      setError(null)
      load()
    } catch (e) {
      setError(apiErrorMessage(e, 'Le réglage « reçoit les nouveaux leads » a échoué.'))
    } finally {
      setBusyId(null)
    }
  }

  // Attribution des leads : confirmation du responsable + délai automatique.
  const saveReglage = async (equipe, patch) => {
    setBusyId(equipe.id)
    try {
      await crmApi.saveEquipe(equipe.id, patch)
      setError(null)
      load()
    } catch (e) {
      setError(apiErrorMessage(e, 'Le réglage d’attribution des leads a échoué.'))
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
      description={`Les équipes définissent qui manage qui : le responsable d'une
          équipe devient le manager de ses membres et voit leurs leads ; un
          membre ne voit que les siens. Une personne = une seule équipe.
          L'équipe cochée « Reçoit les nouveaux leads » se partage les
          nouveaux leads en rotation. Alimente aussi le tableau de bord
          « Mes équipes ».`}
      vide="Aucune équipe configurée."
      placeholder="Nouvelle équipe"
      chefLabel="Responsable d'équipe" chefField="responsable" chefIdPrefix="ec-resp"
      loading={loading} error={error} equipes={equipes} busyId={busyId}
      assignables={assignables}
      onRename={renameEquipe} onArchive={archiveEquipe} onDelete={delEquipe}
      onSetChef={toggleResponsable} onToggleMembre={toggleMembre}
      onToggleRecoitLeads={toggleRecoitLeads}
      renderExtra={(eq) => (
        <ReglesAttributionEditor equipe={eq} assignables={assignables}
                                 busy={busyId === eq.id} onSaveEquipe={saveReglage} />
      )}
      newNom={newNom} setNewNom={setNewNom} onAdd={addEquipe} />
  )
}

// WIR112 — Équipes terrain canoniques (DC40) : CRUD depuis Paramètres.
//
// `installations.Equipe` est l'équipe terrain CANONIQUE (référencée par
// `Intervention.equipe_ref`, le roster FG169, le plan de charge FG299 et le
// planning camionnette FG303) mais n'avait aucun écran — contrairement à
// `crm.EquipeCommerciale` (Leads) et `gestion_projet.Equipe` (Projets), trois
// concepts DISJOINTS. Cet écran ajoute le CRUD manquant, à côté des Types
// d'intervention, sur le même gabarit que les Équipes commerciales (ZSAL3) :
// on regroupe des techniciens (utilisateurs), on désigne un chef optionnel, on
// archive sans supprimer. La liste des utilisateurs assignables est passée par
// le parent (déjà chargée pour l'onglet).
import { useEffect } from 'react'
import useEquipesAdmin from './useEquipesAdmin'
import { useConfirmDialog } from '../../ui/confirm'
import { Plus, Trash2, Archive, ArchiveRestore } from 'lucide-react'
import EquipesAdminPanel from './EquipesAdminPanel'
import installationsApi from '../../api/installationsApi'
import { apiErrorMessage } from '../../lib/apiError'

// Ajoute ou retire `userId` de la liste des membres (bascule).
const basculerMembre = (membres, userId) => (membres.includes(userId)
  ? membres.filter((id) => id !== userId)
  : [...membres, userId])

export default function EquipeTerrainSection({ assignables = [] }) {
  const { confirmDelete } = useConfirmDialog()
  const { equipes, setEquipes, loading, setLoading, error, setError, newNom, setNewNom, busyId, setBusyId } = useEquipesAdmin()

  const load = () => {
    setLoading(true)
    installationsApi.getEquipesTerrain()
      .then((r) => setEquipes(r.data.results ?? r.data))
      .catch(() => setError('Impossible de charger les équipes terrain.'))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load() }, [])

  const addEquipe = async () => {
    if (!newNom.trim()) return
    try {
      await installationsApi.saveEquipeTerrain(null, { nom: newNom.trim() })
      setNewNom('')
      load()
    } catch (e) {
      setError(apiErrorMessage(e, "La création de l'équipe a échoué."))
    }
  }

  const renameEquipe = async (equipe, nom) => {
    if (!nom.trim() || nom === equipe.nom) return
    try {
      await installationsApi.saveEquipeTerrain(equipe.id, { nom: nom.trim() })
      setError(null)
    } catch (e) {
      setError(apiErrorMessage(e, "Le renommage de l'équipe a échoué."))
    }
    load()
  }

  const setChef = async (equipe, chefId) => {
    setBusyId(equipe.id)
    try {
      await installationsApi.saveEquipeTerrain(equipe.id, { chef: chefId || null })
      load()
    } catch (e) {
      setError(apiErrorMessage(e, "Le changement de chef a échoué."))
    } finally {
      setBusyId(null)
    }
  }

  const toggleMembre = async (equipe, userId) => {
    const next = basculerMembre(equipe.membres ?? [], userId)
    setBusyId(equipe.id)
    try {
      await installationsApi.saveEquipeTerrain(equipe.id, { membres: next })
      load()
    } catch (e) {
      setError(apiErrorMessage(e, "La mise à jour des membres a échoué."))
    } finally {
      setBusyId(null)
    }
  }

  const archiveEquipe = async (equipe) => {
    try {
      await installationsApi.saveEquipeTerrain(equipe.id, { actif: !equipe.actif })
      setError(null)
    } catch (e) {
      setError(apiErrorMessage(e, "L'archivage de l'équipe a échoué."))
    }
    load()
  }

  const delEquipe = async (equipe) => {
    if (!(await confirmDelete({ title: `Supprimer l'équipe terrain « ${equipe.nom} » ?`, description: 'Cette action est définitive.' }))) return
    try {
      await installationsApi.deleteEquipeTerrain(equipe.id)
      setError(null)
    } catch (e) {
      setError(apiErrorMessage(e, "Suppression de l'équipe impossible."))
    }
    load()
  }

  return (
    <EquipesAdminPanel
      titre="Équipes terrain"
      description={`Regroupez des techniciens en équipes terrain assignables à une
          intervention. Distinct des équipes commerciales (Leads) et des
          équipes de projet. Archiver conserve l'historique.`}
      vide="Aucune équipe terrain configurée."
      placeholder="Nouvelle équipe terrain"
      chefLabel="Chef d'équipe" chefField="chef" chefIdPrefix="et-chef"
      testIdPrefix="equipe-terrain"
      loading={loading} error={error} equipes={equipes} busyId={busyId}
      assignables={assignables}
      onRename={renameEquipe} onArchive={archiveEquipe} onDelete={delEquipe}
      onSetChef={setChef} onToggleMembre={toggleMembre}
      newNom={newNom} setNewNom={setNewNom} onAdd={addEquipe} />
  )
}

import { useCallback, useEffect, useState } from 'react'
import marketingApi from '../../api/marketingApi'

/* ============================================================================
   NTMKT16 — Éditeur de versions d'une landing page d'intake.
   ----------------------------------------------------------------------------
   `FormulaireIntake` définit les CHAMPS ; ce panneau édite le CONTENU de page
   (titre / pitch / image MinIO). Chaque enregistrement crée une NOUVELLE
   version en brouillon (le numéro est posé par le serveur — jamais ici) ;
   « Publier cette version » bascule la page publique dessus, l'historique
   restant consultable.
   ========================================================================== */

export default function LandingVersions({ formulaireId, formulaireNom }) {
  const [versions, setVersions] = useState([])
  const [titre, setTitre] = useState('')
  const [pitch, setPitch] = useState('')
  const [imageKey, setImageKey] = useState('')
  const [err, setErr] = useState('')
  const [chargement, setChargement] = useState(true)

  const charger = useCallback(async () => {
    if (!formulaireId) return
    setChargement(true)
    try {
      const res = await marketingApi.versionsFormulaireIntake.list(
        { formulaire: formulaireId })
      setVersions(marketingApi.unwrapList(res))
      setErr('')
    } catch {
      setErr('Chargement des versions impossible.')
    } finally {
      setChargement(false)
    }
  }, [formulaireId])

  useEffect(() => { charger() }, [charger])

  const enregistrerBrouillon = async (e) => {
    e.preventDefault()
    try {
      await marketingApi.versionsFormulaireIntake.create({
        formulaire: formulaireId,
        titre, pitch, image_key: imageKey,
      })
      await charger()
      setErr('')
    } catch {
      setErr('Enregistrement impossible.')
    }
  }

  const publier = async (version) => {
    try {
      await marketingApi.versionsFormulaireIntake.publier(version.id)
      await charger()
      setErr('')
    } catch {
      setErr('Publication impossible.')
    }
  }

  const publiee = versions.find(v => v.publie) || null

  return (
    <div className="landing-versions">
      <h3>Page publique {formulaireNom ? `— ${formulaireNom}` : ''}</h3>
      {err && <p role="alert">{err}</p>}
      {chargement && <p>Chargement…</p>}
      <p data-testid="landing-version-en-ligne">
        {publiee
          ? `En ligne : v${publiee.version}`
          : 'Aucune version publiée (page sans contenu éditorial).'}
      </p>

      <form onSubmit={enregistrerBrouillon}>
        <label>
          Titre
          <input value={titre} onChange={e => setTitre(e.target.value)} />
        </label>
        <label>
          Pitch
          <textarea value={pitch} onChange={e => setPitch(e.target.value)} />
        </label>
        <label>
          Image (clé MinIO)
          <input value={imageKey} onChange={e => setImageKey(e.target.value)} />
        </label>
        <button type="submit">Enregistrer une nouvelle version</button>
      </form>

      <table className="data-table" data-testid="landing-versions-table">
        <thead>
          <tr><th>Version</th><th>Titre</th><th>État</th><th /></tr>
        </thead>
        <tbody>
          {versions.map(v => (
            <tr key={v.id} data-testid="landing-version-row">
              <td>v{v.version}</td>
              <td>{v.titre}</td>
              <td>{v.publie ? 'Publiée' : 'Brouillon'}</td>
              <td>
                {!v.publie && (
                  <button type="button" onClick={() => publier(v)}>
                    Publier cette version
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

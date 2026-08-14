import { useEffect, useState } from 'react'
import marketingApi from '../../api/marketingApi'

const MODELES = [
  ['dernier_touche', 'Dernier touché'],
  ['premier_touche', 'Premier touché'],
  ['lineaire', 'Linéaire'],
  ['pondere_temporel', 'Pondéré temporel'],
]

/* ============================================================================
   NTMKT21 — Rapport comparatif multi-modèle d'attribution (étend NTMKT20).
   ----------------------------------------------------------------------------
   Charge UNE SEULE FOIS la comparaison des 4 modèles pour un devis SIGNÉ
   (`marketingApi.attribution.comparaison`, réponse déjà servie par la
   décomposition NTMKT20) ; changer le modèle dans le sélecteur ne déclenche
   AUCUN nouvel appel réseau — seul le classement AFFICHÉ (déjà en mémoire)
   change, donc « sans rechargement de page » au sens strict.
   ========================================================================== */
export default function AttributionReport({ devisId: devisIdProp }) {
  const [devisIdInput, setDevisIdInput] = useState(devisIdProp || '')
  const [modele, setModele] = useState('dernier_touche')
  const [donnees, setDonnees] = useState(null)
  const [chargement, setChargement] = useState(false)
  const [erreur, setErreur] = useState('')

  const charger = (id) => {
    if (!id) return
    setChargement(true)
    setErreur('')
    marketingApi.attribution.comparaison(id)
      .then((res) => {
        setDonnees(res?.data || null)
        setModele(res?.data?.modele_actuel || 'dernier_touche')
      })
      .catch(() => {
        setDonnees(null)
        setErreur('Devis introuvable ou non accepté.')
      })
      .finally(() => setChargement(false))
  }

  useEffect(() => {
    if (devisIdProp) charger(devisIdProp)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- charge une seule fois par devisIdProp
  }, [devisIdProp])

  const classement = donnees
    ? [...(donnees.modeles?.[modele] || [])]
      .sort((a, b) => Number(b.revenu_attribue) - Number(a.revenu_attribue))
    : []

  return (
    <div className="attribution-report">
      <h2>Comparaison des modèles d'attribution</h2>
      {!devisIdProp && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
          <label htmlFor="attribution-devis-id">Devis (id)</label>
          <input
            id="attribution-devis-id"
            type="number"
            value={devisIdInput}
            onChange={(e) => setDevisIdInput(e.target.value)}
          />
          <button type="button" onClick={() => charger(devisIdInput)}>
            Charger
          </button>
        </div>
      )}
      {chargement && <p>Chargement…</p>}
      {erreur && <p data-testid="attribution-erreur">{erreur}</p>}
      {donnees && (
        <>
          <div
            role="radiogroup"
            aria-label="Modèle d'attribution"
            style={{ display: 'flex', gap: 12, marginBottom: 12 }}
          >
            {MODELES.map(([valeur, libelle]) => (
              <label key={valeur}>
                <input
                  type="radio"
                  name="attribution-modele"
                  value={valeur}
                  checked={modele === valeur}
                  onChange={() => setModele(valeur)}
                />
                {' '}{libelle}
              </label>
            ))}
          </div>
          <p>
            Revenu total : {donnees.total_revenu} — modèle société actuel :{' '}
            {MODELES.find(([v]) => v === donnees.modele_actuel)?.[1] || donnees.modele_actuel}
          </p>
          <table className="data-table" data-testid="attribution-classement">
            <thead>
              <tr>
                <th>Rang</th>
                <th>Canal</th>
                <th>Date du contact</th>
                <th>Revenu attribué</th>
              </tr>
            </thead>
            <tbody>
              {classement.map((point, index) => (
                <tr key={point.point_contact_id}>
                  <td>{index + 1}</td>
                  <td>{point.canal_libelle || point.canal}</td>
                  <td>{point.date_contact}</td>
                  <td>{point.revenu_attribue}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}

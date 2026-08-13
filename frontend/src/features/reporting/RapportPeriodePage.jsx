import { useState } from 'react'

import aiGovernanceApi from '../../api/aiGovernanceApi'

/* ============================================================================
   PACT144 — Rapport d'activité périodique (NTAI36,
   `POST /api/django/ai/rapport-periode/`), qui n'avait aucun écran.

   LE GARDE-FOU EST LA FONCTIONNALITÉ, et il doit se VOIR :

   * les CHIFFRES sont calculés par le serveur (sélecteurs métier existants) ;
     le modèle ne fait que les mettre en phrases. L'écran affiche donc les
     métriques SERVEUR à côté du narratif — jamais un chiffre recalculé ici ;
   * un narratif contenant un nombre absent des métriques est REFUSÉ côté
     serveur (400) et n'est JAMAIS rendu : l'écran montre alors le refus, avec
     le motif exact du serveur, au lieu d'un brouillon silencieusement faux ;
   * sans clé LLM configurée, le serveur répond 503 avec un message explicite —
     même exigence : l'écran le dit, il n'invente pas un brouillon local ;
   * le brouillon est ÉDITABLE et n'est jamais diffusé (`envoye: false`).
   ========================================================================== */

// Modules servis par le serveur (`services.RAPPORT_MODULES`).
const MODULES = [
  ['commercial', 'Commercial'],
  ['facturation', 'Facturation'],
]

export default function RapportPeriodePage() {
  const [module, setModule] = useState('commercial')
  const [periode, setPeriode] = useState('')
  const [rapport, setRapport] = useState(null)
  const [narratif, setNarratif] = useState('')
  const [refus, setRefus] = useState(null)
  const [occupe, setOccupe] = useState(false)

  async function generer(event) {
    event.preventDefault()
    if (occupe) return
    setOccupe(true)
    setRefus(null)
    try {
      const res = await aiGovernanceApi.rapportPeriode({ module, periode })
      setRapport(res.data)
      setNarratif(res.data?.narratif ?? '')
    } catch (err) {
      // Le motif vient du SERVEUR (400 = narratif refusé/entrée invalide,
      // 503 = aucune clé LLM configurée) : on le montre tel quel, jamais un
      // message maison qui masquerait la vraie raison.
      const statut = err?.response?.status
      setRapport(null)
      setNarratif('')
      setRefus({
        statut,
        titre: statut === 503
          ? 'Génération indisponible'
          : 'Narratif refusé par le serveur',
        message: err?.response?.data?.detail
          || 'Le serveur n’a pas produit de rapport.',
      })
    } finally {
      setOccupe(false)
    }
  }

  return (
    <div className="rapport-periode" data-testid="rapport-periode">
      <h3>Rapport d’activité périodique</h3>
      <p>
        Les chiffres sont calculés par le serveur ; le modèle ne fait que les
        mettre en phrases. Un narratif citant un chiffre absent des métriques
        est refusé côté serveur — il n’est jamais affiché ici.
      </p>

      <form onSubmit={generer} className="rapport-periode__form">
        <label htmlFor="rapport-module">Module</label>
        <select
          id="rapport-module"
          value={module}
          onChange={(e) => setModule(e.target.value)}
        >
          {MODULES.map(([valeur, libelle]) => (
            <option key={valeur} value={valeur}>{libelle}</option>
          ))}
        </select>
        <label htmlFor="rapport-periode-mois">Période (mois)</label>
        <input
          id="rapport-periode-mois"
          type="month"
          value={periode}
          onChange={(e) => setPeriode(e.target.value)}
          required
        />
        <button type="submit" disabled={occupe || !periode}>
          Générer le brouillon
        </button>
      </form>

      {refus && (
        <p
          className="rapport-periode__refus"
          role="alert"
          data-testid="rapport-periode-refus"
        >
          {refus.titre} : {refus.message}
        </p>
      )}

      {rapport && (
        <section data-testid="rapport-periode-resultat">
          <h4>Métriques serveur — {rapport.module} / {rapport.periode}</h4>
          <table>
            <thead>
              <tr>
                <th>Métrique</th>
                <th>Valeur</th>
              </tr>
            </thead>
            <tbody>
              {(rapport.metriques ?? []).map((m) => (
                <tr key={m.cle}>
                  <td>{m.label}</td>
                  <td>
                    {m.valeur}{m.unite ? ` ${m.unite}` : ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <h4>Narratif (brouillon éditable)</h4>
          <label htmlFor="rapport-narratif">Narratif</label>
          <textarea
            id="rapport-narratif"
            rows={8}
            value={narratif}
            onChange={(e) => setNarratif(e.target.value)}
          />
          <p>
            {rapport.envoye
              ? 'Diffusé.'
              : 'Brouillon — rien n’est diffusé automatiquement.'}
            {rapport.source ? ` Source : ${rapport.source}.` : ''}
          </p>
        </section>
      )}
    </div>
  )
}

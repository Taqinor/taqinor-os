import { useEffect, useMemo, useState } from 'react'

import reportingApi from '../../api/reportingApi'
import coreApi from '../../api/coreApi'
import { frenchError } from '../../lib/frenchError'
// WIR253 — l'export arrive en BINAIRE (csv/xlsx) : remise par le helper commun
// (pré-ouverture d'onglet iOS/PWA), nom de fichier posé par le serveur.
import { downloadBlobInGesture, filenameFromResponse } from '../../utils/downloadBlob'

/* ============================================================================
   PACT146 — Générateur de rapports croisés (NTEXT10,
   `apps/reporting/rapport_builder.py`), qui n'avait aucun écran.

   Une définition est une SPEC, jamais un résultat figé : un dataset enregistré
   (`core.data_explorer`, liste blanche de champs — les champs proposés ici
   viennent de LUI, jamais d'une liste écrite à la main), une spec de requête,
   et un `pivot_spec` OPTIONNEL. `POST …/rapport-definitions/<id>/executer/`
   rejoue la définition sur les données du jour et renvoie `{rows}` — plus
   `{pivot}` quand un croisement est demandé. Le croisement est calculé par le
   SERVEUR (`core.pivot.build_pivot`) : cet écran l'affiche, il ne le refait
   jamais.

   CHEVAUCHEMENT SIGNALÉ (à arbitrer par le fondateur, pas par cette tâche) :
   ce modèle est le frère structurel de la requête sauvegardée `core.SavedQuery`
   (même moteur, même visibilité privé/société) — avec en plus le croisement et
   l'abonnement d'envoi planifié. Les deux écrans peuvent converger plus tard ;
   ils ne sont pas fusionnés ici.
   ========================================================================== */

const AGGREGATS = [
  ['sum', 'Somme'],
  ['count', 'Nombre'],
  ['avg', 'Moyenne'],
  ['min', 'Minimum'],
  ['max', 'Maximum'],
]

const PARTAGES = [
  ['prive', 'Privé'],
  ['societe', 'Société'],
]

const FORM_VIDE = {
  titre: '', dataset: '', select: [], partage: 'prive',
  pivotRows: '', pivotColumns: '', pivotMeasure: '', pivotAgg: 'sum',
}

function listeDe(reponse) {
  const charge = reponse?.data
  if (Array.isArray(charge)) return charge
  if (Array.isArray(charge?.results)) return charge.results
  return []
}

/** Rend une valeur de cellule SANS jamais passer un objet à React. */
function cellule(valeur) {
  if (valeur === null || valeur === undefined || valeur === '') return '—'
  if (typeof valeur === 'boolean') return valeur ? 'oui' : 'non'
  if (typeof valeur === 'object') return '—'
  return String(valeur)
}

export default function RapportBuilderPage() {
  const [definitions, setDefinitions] = useState([])
  const [datasets, setDatasets] = useState([])
  const [form, setForm] = useState(FORM_VIDE)
  const [resultat, setResultat] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [rechargement, setRechargement] = useState(0)
  const [occupe, setOccupe] = useState(false)
  // WIR253 — id de la définition en cours de MODIFICATION (null = création).
  // Sans lui, le formulaire ne savait que CRÉER : « Modifier » n'existait pas
  // et `updateRapportDefinition` n'avait aucun appelant — toute correction de
  // définition passait par une suppression + recréation (l'id changeait, donc
  // les abonnements planifiés qui la référencent tombaient).
  const [editionId, setEditionId] = useState(null)

  useEffect(() => {
    let vivant = true
    Promise.all([
      reportingApi.listRapportDefinitions(),
      coreApi.datasetsExplorateur.list(),
    ])
      .then(([resDefs, resDatasets]) => {
        if (!vivant) return
        setDefinitions(listeDe(resDefs))
        setDatasets(listeDe(resDatasets))
      })
      .catch((err) => {
        if (vivant) setErreur(frenchError(err, 'Chargement impossible.'))
      })
    return () => { vivant = false }
  }, [rechargement])

  const champsDuDataset = useMemo(() => {
    const trouve = datasets.find((d) => d.name === form.dataset)
    return trouve?.fields ?? []
  }, [datasets, form.dataset])

  function basculerChamp(champ) {
    setForm((precedent) => ({
      ...precedent,
      select: precedent.select.includes(champ)
        ? precedent.select.filter((c) => c !== champ)
        : [...precedent.select, champ],
    }))
  }

  async function creer(event) {
    event.preventDefault()
    if (occupe) return
    setOccupe(true)
    setErreur(null)
    // Croisement OPTIONNEL : sans axe de lignes, la définition reste PLATE
    // (`pivot_spec` vide = aucun croisement appliqué côté serveur).
    const pivotSpec = form.pivotRows
      ? {
        rows: [form.pivotRows],
        columns: form.pivotColumns ? [form.pivotColumns] : [],
        measure: form.pivotMeasure || null,
        agg: form.pivotAgg,
      }
      : {}
    const corps = {
      titre: form.titre,
      dataset: form.dataset,
      spec: { select: form.select },
      pivot_spec: pivotSpec,
      partage: form.partage,
    }
    try {
      // WIR253 — en édition, on PATCH l'id existant ; JAMAIS un POST de
      // création (qui laisserait un doublon et changerait l'id référencé par
      // les abonnements planifiés).
      if (editionId != null) {
        await reportingApi.updateRapportDefinition(editionId, corps)
      } else {
        await reportingApi.createRapportDefinition(corps)
      }
      setForm(FORM_VIDE)
      setEditionId(null)
      setRechargement((n) => n + 1)
    } catch (err) {
      setErreur(frenchError(err, editionId != null
        ? 'Modification de la définition impossible.'
        : 'Création de la définition impossible.'))
    } finally {
      setOccupe(false)
    }
  }

  // WIR253 — pré-remplit le formulaire depuis la définition existante (spec +
  // pivot_spec réels du serveur), et bascule le formulaire en MODE ÉDITION.
  function modifier(definition) {
    const pivot = definition.pivot_spec || {}
    setEditionId(definition.id)
    setErreur(null)
    setForm({
      titre: definition.titre || '',
      dataset: definition.dataset || '',
      select: Array.isArray(definition.spec?.select) ? definition.spec.select : [],
      partage: definition.partage || 'prive',
      pivotRows: (pivot.rows || [])[0] || '',
      pivotColumns: (pivot.columns || [])[0] || '',
      pivotMeasure: pivot.measure || '',
      pivotAgg: pivot.agg || 'sum',
    })
  }

  function annulerEdition() {
    setEditionId(null)
    setForm(FORM_VIDE)
  }

  // WIR253/NTEXT11 — export du rapport rejoué. 503 = xlsx indisponible sur ce
  // serveur : on le DIT et on rappelle que le CSV reste possible.
  async function exporter(definition, format) {
    setErreur(null)
    const pending = downloadBlobInGesture()
    try {
      const res = await reportingApi.exportRapportDefinition(definition.id, format)
      const base = (definition.titre || definition.dataset || 'rapport')
        .replace(/[^\w-]+/g, '') || 'rapport'
      pending.deliver(res.data, filenameFromResponse(res, `${base}.${format}`))
    } catch (err) {
      setErreur(err?.response?.status === 503
        ? 'Export xlsx indisponible sur ce serveur : réessayez au format CSV.'
        : frenchError(err, 'Export impossible.'))
    }
  }

  async function executer(definition) {
    setErreur(null)
    setResultat(null)
    try {
      const res = await reportingApi.executerRapportDefinition(definition.id)
      setResultat({ definition, donnees: res.data })
    } catch (err) {
      setErreur(frenchError(err, 'Exécution impossible.'))
    }
  }

  async function supprimer(id) {
    setErreur(null)
    try {
      await reportingApi.deleteRapportDefinition(id)
      setResultat(null)
      setRechargement((n) => n + 1)
    } catch (err) {
      setErreur(frenchError(err, 'Suppression impossible.'))
    }
  }

  const rows = resultat?.donnees?.rows ?? []
  const pivot = resultat?.donnees?.pivot
  const colonnesPlates = rows.length ? Object.keys(rows[0]) : []

  return (
    <div className="rapport-builder" data-testid="rapport-builder">
      <h3>Générateur de rapports croisés</h3>
      <p>
        Une définition est rejouée à la demande sur les données du jour. Le
        croisement est calculé par le serveur ; sans axe de lignes, le résultat
        reste à plat.
      </p>
      {erreur && <p className="rapport-builder__error" role="alert">{erreur}</p>}

      <section data-testid="rapport-builder-definitions">
        <h4>Définitions enregistrées</h4>
        {definitions.length === 0 ? (
          <p>Aucune définition enregistrée.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Titre</th>
                <th>Dataset</th>
                <th>Forme</th>
                <th>Visibilité</th>
                <th>Propriétaire</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {definitions.map((d) => (
                <tr key={d.id} data-testid={`rapport-definition-${d.id}`}>
                  <td>{d.titre}</td>
                  <td>{d.dataset}</td>
                  <td>
                    {d.pivot_spec && Object.keys(d.pivot_spec).length
                      ? 'Croisé'
                      : 'À plat'}
                  </td>
                  <td>{d.partage_label || d.partage}</td>
                  <td>{d.owner_username || '—'}</td>
                  <td>
                    <button type="button" onClick={() => executer(d)}>
                      Exécuter
                    </button>
                    {/* WIR253 — modification en place (PATCH), jamais une
                        recréation qui changerait l'id. */}
                    <button type="button" data-testid={`rapport-modifier-${d.id}`}
                      onClick={() => modifier(d)}>
                      Modifier
                    </button>
                    {/* WIR253/NTEXT11 — export du rapport rejoué. */}
                    <button type="button" data-testid={`rapport-export-csv-${d.id}`}
                      onClick={() => exporter(d, 'csv')}>
                      CSV
                    </button>
                    <button type="button" data-testid={`rapport-export-xlsx-${d.id}`}
                      onClick={() => exporter(d, 'xlsx')}>
                      XLSX
                    </button>
                    <button type="button" onClick={() => supprimer(d.id)}>
                      Supprimer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section data-testid="rapport-builder-creation">
        <h4>{editionId != null ? 'Modifier la définition' : 'Nouvelle définition'}</h4>
        <form onSubmit={creer}>
          <label htmlFor="rapport-titre">Titre</label>
          <input
            id="rapport-titre"
            value={form.titre}
            onChange={(e) => setForm({ ...form, titre: e.target.value })}
            required
          />

          <label htmlFor="rapport-dataset">Dataset</label>
          <select
            id="rapport-dataset"
            value={form.dataset}
            onChange={(e) => setForm({
              ...FORM_VIDE, titre: form.titre, partage: form.partage,
              dataset: e.target.value,
            })}
            required
          >
            <option value="">Choisir un dataset…</option>
            {datasets.map((d) => (
              <option key={d.name} value={d.name}>{d.label || d.name}</option>
            ))}
          </select>

          {form.dataset && (
            <fieldset>
              <legend>Champs à extraire</legend>
              {champsDuDataset.length === 0 ? (
                <p>Ce dataset n’expose aucun champ interrogeable.</p>
              ) : champsDuDataset.map((champ) => (
                <label key={champ} htmlFor={`champ-${champ}`}>
                  <input
                    id={`champ-${champ}`}
                    type="checkbox"
                    checked={form.select.includes(champ)}
                    onChange={() => basculerChamp(champ)}
                  />
                  {champ}
                </label>
              ))}
            </fieldset>
          )}

          <fieldset>
            <legend>Croisement (facultatif)</legend>
            <label htmlFor="pivot-rows">Lignes</label>
            <select
              id="pivot-rows"
              value={form.pivotRows}
              onChange={(e) => setForm({ ...form, pivotRows: e.target.value })}
            >
              <option value="">Aucun croisement (résultat à plat)</option>
              {champsDuDataset.map((champ) => (
                <option key={champ} value={champ}>{champ}</option>
              ))}
            </select>
            <label htmlFor="pivot-columns">Colonnes</label>
            <select
              id="pivot-columns"
              value={form.pivotColumns}
              onChange={(e) => setForm({ ...form, pivotColumns: e.target.value })}
            >
              <option value="">Aucune</option>
              {champsDuDataset.map((champ) => (
                <option key={champ} value={champ}>{champ}</option>
              ))}
            </select>
            <label htmlFor="pivot-measure">Mesure</label>
            <select
              id="pivot-measure"
              value={form.pivotMeasure}
              onChange={(e) => setForm({ ...form, pivotMeasure: e.target.value })}
            >
              <option value="">Aucune (comptage)</option>
              {champsDuDataset.map((champ) => (
                <option key={champ} value={champ}>{champ}</option>
              ))}
            </select>
            <label htmlFor="pivot-agg">Agrégat</label>
            <select
              id="pivot-agg"
              value={form.pivotAgg}
              onChange={(e) => setForm({ ...form, pivotAgg: e.target.value })}
            >
              {AGGREGATS.map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>{libelle}</option>
              ))}
            </select>
          </fieldset>

          <label htmlFor="rapport-partage">Visibilité</label>
          <select
            id="rapport-partage"
            value={form.partage}
            onChange={(e) => setForm({ ...form, partage: e.target.value })}
          >
            {PARTAGES.map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>{libelle}</option>
            ))}
          </select>

          <button type="submit" disabled={occupe || !form.dataset}
            data-testid="rapport-submit">
            {editionId != null ? 'Enregistrer les modifications' : 'Enregistrer la définition'}
          </button>
          {editionId != null && (
            <button type="button" data-testid="rapport-annuler-edition"
              onClick={annulerEdition}>
              Annuler
            </button>
          )}
        </form>
      </section>

      {resultat && (
        <section data-testid="rapport-builder-resultat">
          <h4>Résultat — {resultat.definition.titre}</h4>
          {pivot ? (
            <table data-testid="rapport-builder-croise">
              <thead>
                <tr>
                  <th>{(resultat.definition.pivot_spec?.rows || []).join(', ') || 'Lignes'}</th>
                  {pivot.col_keys.map((ck) => (
                    <th key={ck.join(',')}>{ck.join(' / ') || '—'}</th>
                  ))}
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {pivot.row_keys.map((rk) => {
                  const cle = rk.join(',')
                  return (
                    <tr key={cle}>
                      <td>{rk.join(' / ') || '—'}</td>
                      {pivot.col_keys.map((ck) => (
                        <td key={`${cle}-${ck.join(',')}`}>
                          {cellule(pivot.cells?.[cle]?.[ck.join(',')])}
                        </td>
                      ))}
                      <td>{cellule(pivot.row_totals?.[cle])}</td>
                    </tr>
                  )
                })}
                <tr>
                  <td>Total</td>
                  {pivot.col_keys.map((ck) => (
                    <td key={`total-${ck.join(',')}`}>
                      {cellule(pivot.col_totals?.[ck.join(',')])}
                    </td>
                  ))}
                  <td>{cellule(pivot.grand_total)}</td>
                </tr>
              </tbody>
            </table>
          ) : (
            <table data-testid="rapport-builder-plat">
              <thead>
                <tr>
                  {colonnesPlates.map((c) => <th key={c}>{c}</th>)}
                </tr>
              </thead>
              <tbody>
                {rows.map((ligne, index) => (
                  // Lignes ANONYMES servies par le serveur (`run_query` ne
                  // garantit aucune clé métier) : l'index est la seule clé.
                  <tr key={index}>
                    {colonnesPlates.map((c) => (
                      <td key={c}>{cellule(ligne[c])}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p>{rows.length} ligne(s) servie(s) par le serveur.</p>
        </section>
      )}
    </div>
  )
}

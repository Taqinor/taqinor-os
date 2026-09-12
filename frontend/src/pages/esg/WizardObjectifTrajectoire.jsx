/* NTESG19 — Assistant « Créer un objectif de trajectoire » (3 écrans).
 *
 *   1. CHOISIR l'indicateur — autocomplete sur les codes RÉELS de la société
 *      (`objectifs-esg/codes-disponibles/`). JAMAIS de saisie libre : un code
 *      inventé produirait un objectif dont le « réalisé » resterait vide pour
 *      toujours, et le graphe mentirait en silence.
 *   2. SAISIR référence et cible — avec l'aperçu IMMÉDIAT de la trajectoire
 *      linéaire théorique, calculé ici (interpolation entre les deux points
 *      saisis) : c'est de l'arithmétique sur ce que l'utilisateur vient de
 *      taper, pas une donnée inventée.
 *   3. CONFIRMER — récapitulatif, puis création.
 *
 * DOUBLON : la contrainte serveur est company+indicateur_code+annee_cible.
 * L'écran la connaît d'avance (`objectifs_actifs` de chaque code) et refuse
 * AVANT l'appel, en NOMMANT l'année en conflit ; le serveur reste la barrière
 * finale (400 traduit et affiché si la course est perdue).
 */
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import esgApi from '../../api/esgApi'
import { Button, toast } from '../../ui'
import { frenchError } from '../../lib/frenchError'

const ETAPES = ['Indicateur', 'Référence et cible', 'Confirmation']

/** Trajectoire linéaire théorique entre (annéeRef, valRef) et (annéeCible, valCible). */
export function trajectoireLineaire(
  { anneeReference, valeurReference, anneeCible, valeurCible }) {
  const a0 = Number(anneeReference)
  const a1 = Number(anneeCible)
  const v0 = Number(valeurReference)
  const v1 = Number(valeurCible)
  if (!Number.isFinite(a0) || !Number.isFinite(a1)
      || !Number.isFinite(v0) || !Number.isFinite(v1) || a1 <= a0) {
    return []
  }
  const points = []
  for (let annee = a0; annee <= a1; annee += 1) {
    const part = (annee - a0) / (a1 - a0)
    points.push({ annee, valeur: Number((v0 + (v1 - v0) * part).toFixed(4)) })
  }
  return points
}

export default function WizardObjectifTrajectoire() {
  const navigate = useNavigate()
  const [etape, setEtape] = useState(0)
  const [codes, setCodes] = useState([])
  const [chargement, setChargement] = useState(true)
  const [recherche, setRecherche] = useState('')
  const [codeChoisi, setCodeChoisi] = useState(null)
  const [form, setForm] = useState({
    valeurReference: '', anneeReference: String(new Date().getFullYear()),
    valeurCible: '', anneeCible: '',
  })
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    let vivant = true
    esgApi.objectifs.codesDisponibles()
      .then((res) => { if (vivant) setCodes(res.data || []) })
      .catch((err) => { if (vivant) setErreur(frenchError(err)) })
      .finally(() => { if (vivant) setChargement(false) })
    return () => { vivant = false }
  }, [])

  const suggestions = useMemo(() => {
    const terme = recherche.trim().toLowerCase()
    if (!terme) return codes.slice(0, 20)
    return codes.filter(
      (c) => c.code.toLowerCase().includes(terme)
        || (c.libelle || '').toLowerCase().includes(terme),
    ).slice(0, 20)
  }, [codes, recherche])

  const points = useMemo(() => trajectoireLineaire(form), [form])

  /** Message de doublon (année cible déjà prise), ou chaîne vide. */
  const conflit = useMemo(() => {
    if (!codeChoisi || !form.anneeCible) return ''
    const annee = Number(form.anneeCible)
    return (codeChoisi.objectifs_actifs || []).includes(annee)
      ? `Un objectif actif existe déjà sur « ${codeChoisi.code} » pour `
        + `l’année cible ${annee}. Choisissez une autre année cible, ou `
        + 'désactivez l’objectif existant.'
      : ''
  }, [codeChoisi, form.anneeCible])

  const anneesCoherentes = Number(form.anneeCible) > Number(form.anneeReference)
  const etape2Valide = Boolean(
    form.valeurReference !== '' && form.valeurCible !== ''
    && form.anneeReference && form.anneeCible
    && anneesCoherentes && !conflit,
  )

  function set(cle, valeur) {
    setForm((prec) => ({ ...prec, [cle]: valeur }))
  }

  async function creer() {
    setErreur(null)
    setEnvoi(true)
    try {
      const res = await esgApi.objectifs.create({
        indicateur_code: codeChoisi.code,
        libelle: codeChoisi.libelle || '',
        valeur_reference: Number(form.valeurReference),
        annee_reference: Number(form.anneeReference),
        valeur_cible: Number(form.valeurCible),
        annee_cible: Number(form.anneeCible),
        actif: true,
      })
      toast.success('Objectif de trajectoire créé.')
      navigate(`/esg?objectif=${res.data?.id ?? ''}`)
    } catch (err) {
      setErreur(frenchError(err))
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <div data-testid="esg-wizard-objectif" style={{ maxWidth: 720 }}>
      <h1 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 4px' }}>
        Créer un objectif de trajectoire
      </h1>

      <ol aria-label="Étapes de l’assistant"
        style={{ display: 'flex', gap: 16, listStyle: 'none', padding: 0 }}>
        {ETAPES.map((libelle, index) => (
          <li key={libelle}
            aria-current={index === etape ? 'step' : undefined}
            style={{ fontWeight: index === etape ? 600 : 400,
              color: index === etape ? '#0f172a' : '#94a3b8' }}>
            {index + 1}. {libelle}
          </li>
        ))}
      </ol>

      {/* ── Étape 1 — indicateur ─────────────────────────────────────── */}
      {etape === 0 && (
        <div>
          {chargement && <p>Chargement des indicateurs…</p>}
          {!chargement && codes.length === 0 && (
            <p role="alert" data-testid="esg-wizard-aucun-code">
              Aucun indicateur ESG n’est encore saisi pour votre société. Un
              objectif ne peut pas porter sur un indicateur inexistant :
              créez d’abord l’indicateur dans QHSE.
            </p>
          )}
          {!chargement && codes.length > 0 && (
            <>
              <label style={{ display: 'flex', flexDirection: 'column',
                gap: 4 }}>
                <span>Rechercher un indicateur</span>
                <input
                  aria-label="Rechercher un indicateur"
                  value={recherche}
                  onChange={(e) => setRecherche(e.target.value)}
                  placeholder="Code ou libellé"
                />
              </label>
              <ul data-testid="esg-wizard-suggestions"
                style={{ listStyle: 'none', padding: 0, marginTop: 8 }}>
                {suggestions.map((entree) => (
                  <li key={entree.code} style={{ marginBottom: 4 }}>
                    <Button
                      type="button"
                      variant={codeChoisi?.code === entree.code
                        ? 'default' : 'outline'}
                      aria-pressed={codeChoisi?.code === entree.code}
                      onClick={() => setCodeChoisi(entree)}
                    >
                      {entree.code} — {entree.libelle}
                      {entree.objectifs_actifs?.length
                        ? ` (déjà : ${entree.objectifs_actifs.join(', ')})`
                        : ''}
                    </Button>
                  </li>
                ))}
              </ul>
            </>
          )}
          <Button
            type="button"
            disabled={!codeChoisi}
            data-testid="esg-wizard-suivant-1"
            onClick={() => setEtape(1)}
          >
            Suivant
          </Button>
        </div>
      )}

      {/* ── Étape 2 — référence, cible, aperçu ───────────────────────── */}
      {etape === 1 && (
        <div>
          <p>
            Indicateur : <strong>{codeChoisi?.code}</strong>{' '}
            {codeChoisi?.unite ? `(${codeChoisi.unite})` : ''}
          </p>
          <div style={{ display: 'grid',
            gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
            <label style={{ display: 'flex', flexDirection: 'column' }}>
              <span>Valeur de référence</span>
              <input type="number" step="any"
                aria-label="Valeur de référence"
                value={form.valeurReference}
                onChange={(e) => set('valeurReference', e.target.value)} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column' }}>
              <span>Année de référence</span>
              <input type="number" step="any"
                aria-label="Année de référence"
                value={form.anneeReference}
                onChange={(e) => set('anneeReference', e.target.value)} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column' }}>
              <span>Valeur cible</span>
              <input type="number" step="any"
                aria-label="Valeur cible"
                value={form.valeurCible}
                onChange={(e) => set('valeurCible', e.target.value)} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column' }}>
              <span>Année cible</span>
              <input type="number" step="any"
                aria-label="Année cible"
                value={form.anneeCible}
                onChange={(e) => set('anneeCible', e.target.value)} />
            </label>
          </div>

          {form.anneeCible && !anneesCoherentes && (
            <p role="alert" data-testid="esg-wizard-annees">
              L’année cible doit être postérieure à l’année de référence.
            </p>
          )}
          {conflit && (
            <p role="alert" data-testid="esg-wizard-conflit"
              style={{ color: '#b91c1c' }}>
              {conflit}
            </p>
          )}

          {points.length > 0 && (
            <table data-testid="esg-wizard-apercu"
              style={{ marginTop: 12, borderCollapse: 'collapse' }}>
              <caption style={{ textAlign: 'left', color: '#64748b' }}>
                Trajectoire linéaire théorique (interpolée entre vos deux
                points — aucune donnée supplémentaire).
              </caption>
              <thead>
                <tr><th>Année</th><th>Valeur théorique</th></tr>
              </thead>
              <tbody>
                {points.map((p) => (
                  <tr key={p.annee}>
                    <td>{p.annee}</td>
                    <td>{p.valeur}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
            <Button type="button" variant="outline"
              onClick={() => setEtape(0)}>Retour</Button>
            <Button
              type="button"
              disabled={!etape2Valide}
              data-testid="esg-wizard-suivant-2"
              onClick={() => setEtape(2)}
            >
              Suivant
            </Button>
          </div>
        </div>
      )}

      {/* ── Étape 3 — confirmation ───────────────────────────────────── */}
      {etape === 2 && (
        <div data-testid="esg-wizard-confirmation">
          <p>
            Objectif sur <strong>{codeChoisi?.code}</strong> :{' '}
            {form.valeurReference} en {form.anneeReference} →{' '}
            {form.valeurCible} en {form.anneeCible}.
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button type="button" variant="outline"
              onClick={() => setEtape(1)}>Retour</Button>
            <Button type="button" disabled={envoi}
              data-testid="esg-wizard-creer" onClick={creer}>
              {envoi ? 'Création…' : 'Créer l’objectif'}
            </Button>
          </div>
        </div>
      )}

      {erreur && (
        <p role="alert" data-testid="esg-wizard-erreur"
          style={{ marginTop: 12, color: '#b91c1c' }}>
          {erreur}
        </p>
      )}
    </div>
  )
}

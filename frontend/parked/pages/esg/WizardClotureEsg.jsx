/* NTESG18 — Assistant « Clôture de période ESG » (4 étapes).
 *
 *   1. COUVERTURE du catalogue par pilier (NTESG3) — avertissement sous 50 %.
 *   2. ÉCARTS avant/après vs la période précédente (NTESG11).
 *   3. APERÇU du PDF (NTESG4) avant génération définitive — le MÊME rendu,
 *      servi `inline` : l'aperçu ne peut pas diverger du document final.
 *   4. CONFIRMATION explicite : « cette action fige les données, non
 *      réversible ».
 *
 * LA RÈGLE QUI STRUCTURE TOUT L'ÉCRAN — et que le serveur porte aussi
 * (`prerequis-cloture/`) : une étape ne bloque le passage à la suivante que
 * sur une incohérence BLOQUANTE RÉELLE (période déjà figée, dates invalides).
 * Un simple MANQUE de donnée — couverture faible, aucune période antérieure —
 * reste un AVERTISSEMENT : une société qui démarre son reporting a le droit
 * de figer une période peu couverte.
 *
 * L'API `POST figer/` reste directement appelable pour l'automatisation :
 * c'est l'ÉCRAN qui impose les 4 étapes, jamais le serveur.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, Info } from 'lucide-react'

import esgApi from '../../api/esgApi'
import { Button, toast } from '../../ui'
import { frenchError } from '../../lib/frenchError'

const ETAPES = [
  'Couverture du catalogue',
  'Écarts vs période précédente',
  'Aperçu du rapport',
  'Confirmation',
]

const SEUIL_COUVERTURE = 50

export default function WizardClotureEsg() {
  const { periodeId } = useParams()
  const navigate = useNavigate()
  const [etape, setEtape] = useState(0)
  const [prerequis, setPrerequis] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [apercuUrl, setApercuUrl] = useState(null)
  const [apercuErreur, setApercuErreur] = useState(null)
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    let vivant = true
    esgApi.periodes.prerequisCloture(periodeId)
      .then((res) => { if (vivant) setPrerequis(res.data) })
      .catch((err) => { if (vivant) setErreur(frenchError(err)) })
      .finally(() => { if (vivant) setChargement(false) })
    return () => { vivant = false }
  }, [periodeId])

  // L'aperçu n'est demandé qu'à l'étape 3 : un PDF est coûteux, on ne le
  // rend pas « au cas où ».
  useEffect(() => {
    if (etape !== 2 || apercuUrl) return undefined
    let vivant = true
    let url = null
    esgApi.periodes.apercuRapportPdf(periodeId)
      .then((res) => {
        if (!vivant) return
        url = URL.createObjectURL(res.data)
        setApercuUrl(url)
      })
      .catch((err) => { if (vivant) setApercuErreur(frenchError(err)) })
    return () => {
      vivant = false
      if (url) URL.revokeObjectURL(url)
    }
  }, [etape, periodeId, apercuUrl])

  const bloquants = useMemo(
    () => prerequis?.bloquants || [], [prerequis])
  const avertissements = useMemo(
    () => prerequis?.avertissements || [], [prerequis])
  const peutAvancer = bloquants.length === 0

  const figer = useCallback(async () => {
    setErreur(null)
    setEnvoi(true)
    try {
      await esgApi.periodes.figer(periodeId)
      toast.success('Période figée.')
      navigate('/esg')
    } catch (err) {
      setErreur(frenchError(err))
    } finally {
      setEnvoi(false)
    }
  }, [periodeId, navigate])

  if (chargement) return <p>Chargement…</p>
  if (!prerequis) {
    return (
      <p role="alert" data-testid="esg-cloture-erreur">
        {erreur || 'Prérequis de clôture indisponibles.'}
      </p>
    )
  }

  const piliers = prerequis.couverture?.piliers || {}
  const comparaison = prerequis.comparaison

  return (
    <div data-testid="esg-wizard-cloture" style={{ maxWidth: 820 }}>
      <h1 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 4px' }}>
        Clôture de période — {prerequis.periode?.libelle}
      </h1>
      <p style={{ color: '#64748b', marginTop: 0 }}>
        Fréquence de reporting de la société :{' '}
        {prerequis.frequence_reporting}
      </p>

      <ol aria-label="Étapes de l’assistant"
        style={{ display: 'flex', gap: 16, listStyle: 'none', padding: 0,
          flexWrap: 'wrap' }}>
        {ETAPES.map((libelle, index) => (
          <li key={libelle}
            aria-current={index === etape ? 'step' : undefined}
            style={{ fontWeight: index === etape ? 600 : 400,
              color: index === etape ? '#0f172a' : '#94a3b8' }}>
            {index + 1}. {libelle}
          </li>
        ))}
      </ol>

      {bloquants.length > 0 && (
        <ul role="alert" data-testid="esg-cloture-bloquants"
          style={{ color: '#b91c1c' }}>
          {bloquants.map((message) => (
            <li key={message}>
              <AlertTriangle size={14} strokeWidth={1.75} aria-hidden="true" />{' '}
              {message}
            </li>
          ))}
        </ul>
      )}

      {/* ── Étape 1 — couverture ─────────────────────────────────────── */}
      {etape === 0 && (
        <div data-testid="esg-cloture-etape-1">
          <table style={{ borderCollapse: 'collapse', marginBottom: 8 }}>
            <thead>
              <tr><th>Pilier</th><th>Couverts</th><th>Total</th><th>%</th></tr>
            </thead>
            <tbody>
              {Object.entries(piliers).map(([pilier, bloc]) => (
                <tr key={pilier}
                  data-testid={`esg-cloture-pilier-${pilier}`}
                  style={{ color: bloc.pct < SEUIL_COUVERTURE
                    ? '#b45309' : undefined }}>
                  <td>{pilier}</td>
                  <td>{bloc.couverts}</td>
                  <td>{bloc.total}</td>
                  <td>{bloc.pct} %</td>
                </tr>
              ))}
              {Object.keys(piliers).length === 0 && (
                <tr><td colSpan={4}>Aucun catalogue seedé.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Étape 2 — écarts ─────────────────────────────────────────── */}
      {etape === 1 && (
        <div data-testid="esg-cloture-etape-2">
          {!comparaison && (
            <p data-testid="esg-cloture-sans-comparaison">
              Aucune période antérieure : les écarts avant/après ne peuvent
              pas être calculés pour cette première clôture.
            </p>
          )}
          {comparaison && (
            <table style={{ borderCollapse: 'collapse' }}>
              <caption style={{ textAlign: 'left', color: '#64748b' }}>
                {comparaison.periode_reference?.libelle} →{' '}
                {comparaison.periode_n?.libelle}
              </caption>
              <thead>
                <tr>
                  <th>Indicateur</th><th>Avant</th><th>Après</th>
                  <th>Écart</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(comparaison.piliers || {}).flatMap(
                  ([pilier, entrees]) => entrees.map((entree) => (
                    <tr key={`${pilier}-${entree.code}`}>
                      <td>{entree.code} — {entree.libelle}</td>
                      <td>{entree.comparable
                        ? entree.valeur_reference : '—'}</td>
                      <td>{entree.comparable ? entree.valeur_n : '—'}</td>
                      <td>
                        {entree.comparable
                          ? `${entree.variation_abs}${
                            entree.variation_pct !== null
                              ? ` (${entree.variation_pct} %)` : ''}`
                          : entree.raison || 'Non comparable'}
                      </td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Étape 3 — aperçu PDF ─────────────────────────────────────── */}
      {etape === 2 && (
        <div data-testid="esg-cloture-etape-3">
          {apercuErreur && (
            <p role="alert" data-testid="esg-cloture-apercu-erreur">
              L’aperçu du rapport est indisponible ({apercuErreur}). Vous
              pouvez tout de même figer la période — l’aperçu n’est qu’une
              relecture.
            </p>
          )}
          {apercuUrl && (
            <object
              data={apercuUrl}
              type="application/pdf"
              width="100%"
              height="480"
              aria-label="Aperçu du rapport ESG"
              data-testid="esg-cloture-apercu"
            >
              <p>Aperçu non affichable ici.</p>
            </object>
          )}
          {!apercuUrl && !apercuErreur && <p>Génération de l’aperçu…</p>}
        </div>
      )}

      {/* ── Étape 4 — confirmation ───────────────────────────────────── */}
      {etape === 3 && (
        <div data-testid="esg-cloture-etape-4">
          <p role="alert" style={{ fontWeight: 600 }}>
            <AlertTriangle size={16} strokeWidth={1.75} aria-hidden="true" />{' '}
            Cette action fige les données, non réversible.
          </p>
          <p>
            Les chiffres de « {prerequis.periode?.libelle} » seront gelés et
            ne seront plus jamais recalculés, même si les données sources
            changent ensuite.
          </p>
          <Button type="button" disabled={envoi || !peutAvancer}
            data-testid="esg-cloture-figer" onClick={figer}>
            {envoi ? 'Figeage…' : 'Figer la période'}
          </Button>
        </div>
      )}

      {avertissements.length > 0 && (
        <ul data-testid="esg-cloture-avertissements"
          style={{ color: '#b45309' }}>
          {avertissements.map((message) => (
            <li key={message}>
              <Info size={14} strokeWidth={1.75} aria-hidden="true" />{' '}
              {message}
            </li>
          ))}
        </ul>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <Button type="button" variant="outline" disabled={etape === 0}
          onClick={() => setEtape((e) => Math.max(0, e - 1))}>
          Retour
        </Button>
        {etape < ETAPES.length - 1 && (
          <Button
            type="button"
            disabled={!peutAvancer}
            data-testid={`esg-cloture-suivant-${etape + 1}`}
            onClick={() => setEtape((e) => e + 1)}
          >
            Suivant
          </Button>
        )}
      </div>

      {erreur && (
        <p role="alert" data-testid="esg-cloture-erreur"
          style={{ marginTop: 12, color: '#b91c1c' }}>
          {erreur}
        </p>
      )}
    </div>
  )
}

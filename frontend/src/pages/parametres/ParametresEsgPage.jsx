/* NTESG20 — Paramètres > ESG : les réglages ESG de la société.
 *
 * Quatre réglages, chacun avec UN consommateur nommé (jamais un champ
 * décoratif) — c'est ce que l'écran DIT à côté de chaque champ, pour qu'on
 * sache ce qu'on change :
 *   - seuil d'alerte de dérive → l'alerte de trajectoire (NTESG10) ;
 *   - pilote ESG → destinataire par défaut des alertes ESG ;
 *   - fréquence de reporting → informatif, rappelé par l'assistant de clôture ;
 *   - pondération du badge de maturité → le score affiché (NTESG15).
 *
 * La pondération DOIT sommer à 100. L'écran l'affiche en direct et refuse
 * d'enregistrer autrement, mais c'est le SERVEUR qui tranche (`clean()` du
 * modèle) : la garde de l'écran est un confort, jamais la seule barrière.
 *
 * Après enregistrement, le badge de maturité est RELU depuis le serveur — le
 * critère d'acceptation NTESG20 (« modifier la pondération recalcule
 * immédiatement le badge affiché, sans redémarrage »).
 */
import { useCallback, useEffect, useMemo, useState } from 'react'

import esgApi from '../../api/esgApi'
import { Button, toast } from '../../ui'
import { frenchError } from '../../lib/frenchError'

const COMPOSANTES = [
  ['couverture', 'Couverture du catalogue GRI-lite'],
  ['cibles', 'Indicateurs atteignant leur cible'],
  ['trajectoire', 'Indicateurs dotés d’une trajectoire'],
]

const FREQUENCES = [
  ['mensuelle', 'Mensuelle'],
  ['trimestrielle', 'Trimestrielle'],
  ['annuelle', 'Annuelle'],
]

const PONDERATION_DEFAUT = { couverture: 34, cibles: 33, trajectoire: 33 }

export default function ParametresEsgPage() {
  const [reglages, setReglages] = useState(null)
  const [badge, setBadge] = useState(null)
  const [chargement, setChargement] = useState(true)
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState(null)

  const rafraichirBadge = useCallback(async () => {
    try {
      const res = await esgApi.catalogue.badgeMaturite()
      setBadge(res.data)
    } catch {
      // Le badge est un INDICATEUR : son indisponibilité ne doit jamais
      // empêcher de régler les paramètres.
      setBadge(null)
    }
  }, [])

  useEffect(() => {
    let vivant = true
    async function charger() {
      try {
        const res = await esgApi.parametres.get()
        if (!vivant) return
        setReglages({
          ...res.data,
          ponderation_badge_maturite: {
            ...PONDERATION_DEFAUT,
            ...(res.data?.ponderation_badge_maturite || {}),
          },
        })
      } catch (err) {
        if (vivant) setErreur(frenchError(err))
      } finally {
        if (vivant) setChargement(false)
      }
    }
    charger()
    // Différé d'un microtask : un appel synchrone dans le corps d'un effet
    // déclenche un rendu en cascade (react-hooks/set-state-in-effect).
    Promise.resolve().then(rafraichirBadge)
    return () => { vivant = false }
  }, [rafraichirBadge])

  const poids = reglages?.ponderation_badge_maturite || PONDERATION_DEFAUT
  const totalPoids = useMemo(
    () => COMPOSANTES.reduce(
      (somme, [cle]) => somme + (Number(poids[cle]) || 0), 0),
    [poids],
  )
  const ponderationValide = totalPoids === 100

  function set(cle, valeur) {
    setReglages((prec) => ({ ...prec, [cle]: valeur }))
  }

  function setPoids(cle, valeur) {
    setReglages((prec) => ({
      ...prec,
      ponderation_badge_maturite: {
        ...prec.ponderation_badge_maturite,
        [cle]: valeur === '' ? '' : Number(valeur),
      },
    }))
  }

  async function enregistrer(event) {
    event.preventDefault()
    setErreur(null)
    setEnvoi(true)
    try {
      const res = await esgApi.parametres.update({
        seuil_alerte_derive_pct: Number(reglages.seuil_alerte_derive_pct),
        pilote_esg: reglages.pilote_esg || null,
        frequence_reporting: reglages.frequence_reporting,
        ponderation_badge_maturite: COMPOSANTES.reduce(
          (acc, [cle]) => ({ ...acc, [cle]: Number(poids[cle]) || 0 }), {}),
      })
      setReglages({
        ...res.data,
        ponderation_badge_maturite: {
          ...PONDERATION_DEFAUT,
          ...(res.data?.ponderation_badge_maturite || {}),
        },
      })
      toast.success('Réglages ESG enregistrés.')
      // Le badge est RELU : la pondération qu'on vient de poser s'y voit
      // immédiatement (critère d'acceptation NTESG20).
      await rafraichirBadge()
    } catch (err) {
      setErreur(frenchError(err))
    } finally {
      setEnvoi(false)
    }
  }

  if (chargement) return <p>Chargement…</p>
  if (!reglages) {
    return (
      <p role="alert" data-testid="esg-parametres-erreur">
        {erreur || 'Réglages ESG indisponibles.'}
      </p>
    )
  }

  return (
    <div data-testid="esg-parametres" style={{ maxWidth: 680 }}>
      <h1 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 4px' }}>
        Réglages ESG
      </h1>
      <p style={{ color: '#64748b', marginTop: 0 }}>
        Ces réglages s’appliquent à toute la société.
      </p>

      <form onSubmit={enregistrer}
        style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span>Seuil d’alerte de dérive de trajectoire (%)</span>
          <input
            type="number"
            min={1}
            max={100}
            step="any"
            aria-label="Seuil d’alerte de dérive de trajectoire (%)"
            value={reglages.seuil_alerte_derive_pct ?? ''}
            onChange={(e) => set('seuil_alerte_derive_pct', e.target.value)}
          />
          <small style={{ color: '#64748b' }}>
            Au-delà de cet écart défavorable, une alerte part à la clôture
            d’une période.
          </small>
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span>Fréquence de reporting</span>
          <select
            aria-label="Fréquence de reporting"
            value={reglages.frequence_reporting || 'annuelle'}
            onChange={(e) => set('frequence_reporting', e.target.value)}
          >
            {FREQUENCES.map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>{libelle}</option>
            ))}
          </select>
          <small style={{ color: '#64748b' }}>
            Informatif : rappelé par l’assistant de clôture de période.
          </small>
        </label>

        <fieldset style={{ border: '1px solid #e2e8f0', borderRadius: 8,
          padding: 12 }}>
          <legend style={{ fontWeight: 600 }}>
            Pondération du badge de maturité
          </legend>
          {COMPOSANTES.map(([cle, libelle]) => (
            <label key={cle}
              style={{ display: 'flex', alignItems: 'center', gap: 8,
                marginBottom: 6 }}>
              <span style={{ flex: 1 }}>{libelle}</span>
              <input
                type="number"
                min={0}
                max={100}
                step="any"
                aria-label={`Poids — ${libelle}`}
                value={poids[cle] ?? ''}
                onChange={(e) => setPoids(cle, e.target.value)}
                style={{ width: 90 }}
              />
            </label>
          ))}
          <p
            data-testid="esg-ponderation-total"
            style={{ margin: 0,
              color: ponderationValide ? '#15803d' : '#b91c1c' }}
          >
            Total : {totalPoids} %{' '}
            {ponderationValide ? '✓' : '— la pondération doit sommer à 100.'}
          </p>
        </fieldset>

        {badge && (
          <p data-testid="esg-badge-maturite" style={{ margin: 0 }}>
            Badge de maturité actuel : <strong>{badge.score}</strong> / 100
          </p>
        )}

        <div>
          <Button type="submit" disabled={envoi || !ponderationValide}>
            {envoi ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        </div>
      </form>

      {erreur && (
        <p role="alert" data-testid="esg-parametres-erreur"
          style={{ marginTop: 12, color: '#b91c1c' }}>
          {erreur}
        </p>
      )}
    </div>
  )
}

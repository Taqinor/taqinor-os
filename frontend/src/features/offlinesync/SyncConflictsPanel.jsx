// NTMOB2 — RÉSOLUTION DE CONFLIT DE SYNCHRONISATION.
//
// Le serveur refuse d'appliquer une opération hors-ligne dont l'enregistrement
// cible a été modifié par un autre acteur entre la mise en file et le rejeu :
// elle passe en `conflit` et attend un arbitrage HUMAIN — jamais d'écrasement
// silencieux, dans un sens comme dans l'autre.
//
// Cet écran liste ces opérations et propose les TROIS seules décisions
// possibles : garder ma version / garder celle du serveur / fusionner
// manuellement. Aucun choix par défaut, aucune action de masse : chaque
// conflit se tranche un par un, en connaissance de cause.
//
// Toute la logique (choix valides, corps de fusion, versions à montrer) vit
// dans `conflitsSynchro.js`, testée à part. Ici : l'affichage seulement.
import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

import offlinesyncApi from '../../api/offlinesyncApi'
import {
  Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState,
  Spinner, Textarea,
} from '../../ui'
import { CHOIX, lirePayload, peutEnvoyer, resumer } from './conflitsSynchro'

function lignes(reponse) {
  const data = reponse?.data
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.results)) return data.results
  return []
}

function Version({ titre, valeur, accent }) {
  return (
    <div className="min-w-0 flex-1 rounded border border-border p-2">
      <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {titre}
      </div>
      {/* Valeur absente ⇒ rien d'affiché (jamais un tiret qui ferait croire
          à une donnée). */}
      {valeur === null || valeur === undefined ? null : (
        <div className={`break-all text-[12px]${accent ? ' font-semibold' : ''}`}>
          {String(valeur)}
        </div>
      )}
    </div>
  )
}

function Conflit({ ligne, onResolu }) {
  const [choix, setChoix] = useState(null)
  const [texteFusion, setTexteFusion] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState('')

  const payload = choix === 'fusion' ? lirePayload(texteFusion) : undefined
  const envoyable = peutEnvoyer(choix, payload) && !envoi

  async function envoyer() {
    setEnvoi(true)
    setErreur('')
    try {
      await offlinesyncApi.resoudreConflit(ligne.id, choix, payload)
      onResolu(ligne.id)
    } catch (e) {
      setErreur(e?.response?.data?.detail || 'Arbitrage refusé par le serveur.')
      setEnvoi(false)
    }
  }

  return (
    <Card data-testid="conflit-synchro">
      <CardHeader className="flex flex-row items-center gap-2">
        <AlertTriangle className="size-4 text-destructive" aria-hidden="true" />
        <CardTitle className="flex-1 text-sm">{ligne.opType}</CardTitle>
        {ligne.module && <Badge tone="warning">{ligne.module}</Badge>}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {ligne.message && (
          <p className="text-[12px] text-muted-foreground">{ligne.message}</p>
        )}
        <div className="flex gap-2">
          <Version titre={`Ma version${ligne.champ ? ` (${ligne.champ})` : ''}`}
            valeur={ligne.mienne} accent />
          <Version titre="Version du serveur" valeur={ligne.serveur} />
        </div>
        <div className="flex flex-col gap-1">
          {CHOIX.map((c) => (
            <label key={c.cle} className="flex items-start gap-2 text-[13px]">
              <input
                type="radio"
                name={`conflit-${ligne.id}`}
                className="mt-1"
                checked={choix === c.cle}
                onChange={() => setChoix(c.cle)}
              />
              <span>
                <span className="font-medium">{c.libelle}</span>
                <span className="block text-[11px] text-muted-foreground">
                  {c.aide}
                </span>
              </span>
            </label>
          ))}
        </div>
        {choix === 'fusion' && (
          <div className="flex flex-col gap-1">
            <Textarea
              rows={4}
              value={texteFusion}
              onChange={(e) => setTexteFusion(e.target.value)}
              placeholder='{"lead": 12, "tag": "chaud"}'
              aria-label="Corps fusionné (JSON)"
            />
            {texteFusion && payload === null && (
              <p className="text-[11px] text-destructive">
                Corps illisible : un objet JSON est attendu.
              </p>
            )}
          </div>
        )}
        {erreur && <p className="text-[12px] text-destructive">{erreur}</p>}
        <div>
          <Button size="sm" onClick={envoyer} disabled={!envoyable}>
            {envoi && <RefreshCw className="size-4 animate-spin" aria-hidden="true" />}
            Appliquer ma décision
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

const ETAT_INITIAL = { chargement: true, conflits: [], erreur: '' }

export default function SyncConflictsPanel() {
  const [etat, setEtat] = useState(ETAT_INITIAL)
  // Compteur de rafraîchissement : l'effet ne relit le journal que lorsqu'il
  // change (un état posé SYNCHRONEMENT dans un effet est proscrit — toutes les
  // écritures d'état ci-dessous arrivent APRÈS la réponse réseau).
  const [rafraichissement, setRafraichissement] = useState(0)

  useEffect(() => {
    let vivant = true
    offlinesyncApi.listConflits()
      .then((reponse) => {
        if (!vivant) return
        setEtat({
          chargement: false,
          conflits: lignes(reponse).map(resumer).filter(Boolean),
          erreur: '',
        })
      })
      .catch(() => {
        if (!vivant) return
        setEtat({
          chargement: false,
          conflits: [],
          erreur: 'Journal de synchronisation indisponible.',
        })
      })
    return () => { vivant = false }
  }, [rafraichissement])

  const recharger = useCallback(() => {
    setEtat(ETAT_INITIAL)
    setRafraichissement((n) => n + 1)
  }, [])

  const retirer = useCallback((id) => {
    setEtat((precedent) => ({
      ...precedent,
      conflits: precedent.conflits.filter((l) => l.id !== id),
    }))
  }, [])

  if (etat.chargement) return <Spinner label="Chargement des conflits…" />
  if (etat.erreur) {
    return <p className="text-sm text-destructive">{etat.erreur}</p>
  }
  if (etat.conflits.length === 0) {
    return (
      <EmptyState
        title="Aucun conflit de synchronisation"
        description="Toutes vos actions hors-ligne ont été appliquées."
      />
    )
  }

  return (
    <div className="flex flex-col gap-3" data-testid="sync-conflicts-panel">
      <div className="flex items-center gap-2">
        <h1 className="flex-1 text-base font-semibold">
          Conflits de synchronisation
        </h1>
        <Badge tone="danger">{etat.conflits.length}</Badge>
        <Button size="sm" variant="outline" onClick={recharger}>
          <RefreshCw className="size-4" aria-hidden="true" />
          Actualiser
        </Button>
      </div>
      {etat.conflits.map((ligne) => (
        <Conflit key={ligne.id} ligne={ligne} onResolu={retirer} />
      ))}
    </div>
  )
}

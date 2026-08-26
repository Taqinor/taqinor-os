import { useEffect, useState } from 'react'
import { FileCode, Download, ShieldCheck, Send } from 'lucide-react'
import einvoiceApi from '../api/einvoiceApi'
import { Badge, Button } from '../ui'
import { downloadBlob } from '../utils/downloadBlob'

/* WIR106 — Action « Générer e-facture (dry-run) » sur une facture existante.
   Réutilise apps/einvoice (générateur UBL DGI, NTMAR). La génération est gated
   serveur (EINVOICE_ENABLED) : un 204 affiche « e-facturation désactivée ».

   PACT54 — le composant ne faisait QUE « Générer (à blanc) » + « Télécharger
   XML » : l'action serveur `controler` (anomalies bloquantes, NTMAR8) était
   wrappée dans le client mais jamais appelée, et `transmettre` (NTMAR7)
   n'avait aucun wrapper. Les deux vont ensemble — un contrôle sans envoi ne
   sert à rien, un envoi sans contrôle est dangereux. La transmission reste
   INERTE tant qu'aucune credential DGI n'est configurée (le serveur enregistre
   l'intention en file d'attente, sans aucun appel réseau) ; l'historique se lit
   sur l'écran `/fiscal/transmissions-dgi`. */
export default function EinvoiceActions({ factureId }) {
  const [busy, setBusy] = useState(false)
  const [state, setState] = useState(null) // { disabled?, fe?, error? }
  // PACT54 — résultat du contrôle : { anomalies: [], conforme: bool }.
  const [controle, setControle] = useState(null)
  // PACT54 — transmission déclenchée (statut renvoyé par le serveur).
  const [transmission, setTransmission] = useState(null)

  /* WIR223 — RÉHYDRATATION AU MONTAGE.
     L'état ne vivait QUE dans `state`, posé par le clic sur « Générer » :
     après un simple rechargement de la fiche, une e-facture pourtant DÉJÀ
     générée redevenait invisible — Télécharger / Contrôler / Transmettre
     disparaissaient et l'unique porte de sortie était de re-cliquer
     « Générer », ce qui POLLUE l'historique d'une version de plus à chaque
     fois. On lit donc les versions existantes au montage.

     Un échec (403 pour un rôle sans droit de lecture, réseau) est SILENCIEUX :
     l'écran reste utilisable et « Générer » reste offert — jamais une erreur
     rouge pour une simple absence d'historique.

     La rehydratation ne PIÉTINE JAMAIS un état déjà posé : si l'utilisateur a
     cliqué « Générer » avant que la liste ne réponde, c'est SA version qui
     reste affichée. */
  useEffect(() => {
    if (!factureId) return undefined
    let vivant = true
    einvoiceApi.list({ facture_id: factureId })
      .then((res) => {
        if (!vivant) return
        const versions = res?.data?.results ?? res?.data ?? []
        if (!Array.isArray(versions) || versions.length === 0) return
        // La version la PLUS RÉCENTE. Le serveur trie déjà par date
        // décroissante ; on prend malgré tout le plus grand `version` pour ne
        // dépendre d'AUCUN ordre de tri côté serveur.
        const derniere = versions.reduce((a, b) => (
          (Number(b?.version) || 0) > (Number(a?.version) || 0) ? b : a))
        setState((prev) => prev ?? { fe: derniere })
      })
      .catch(() => { /* silencieux : « Générer » reste la porte d'entrée */ })
    return () => { vivant = false }
  }, [factureId])

  const generer = async () => {
    setBusy(true)
    setState(null)
    setControle(null)
    setTransmission(null)
    try {
      const res = await einvoiceApi.generer(factureId, 'dry_run')
      if (res.status === 204 || !res.data) {
        setState({ disabled: true })
      } else {
        setState({ fe: res.data })
      }
    } catch (err) {
      setState({ error: err?.response?.data?.detail || 'La génération a échoué.' })
    } finally {
      setBusy(false)
    }
  }

  const telecharger = async () => {
    if (!state?.fe?.id) return
    try {
      const res = await einvoiceApi.telecharger(state.fe.id)
      downloadBlob(res.data, `e-facture-${factureId}.xml`)
    } catch {
      setState((s) => ({ ...s, error: 'Le téléchargement du XML a échoué.' }))
    }
  }

  // PACT54 — contrôle avant envoi : liste les anomalies BLOQUANTES (liste vide
  // = conforme). Jamais d'envoi implicite ici.
  const controler = async () => {
    if (!state?.fe?.id) return
    setBusy(true)
    try {
      const res = await einvoiceApi.controler(state.fe.id)
      setControle({
        anomalies: res.data?.anomalies ?? [],
        conforme: !!res.data?.conforme,
      })
    } catch {
      setState((s) => ({ ...s, error: 'Le contrôle de conformité a échoué.' }))
    } finally {
      setBusy(false)
    }
  }

  // PACT54 — transmission : enregistre l'intention dans la file DGI. Sans
  // credential configurée, le serveur renvoie une transmission « en attente »
  // — c'est un état normal, jamais une erreur.
  const transmettre = async () => {
    if (!state?.fe?.id) return
    setBusy(true)
    try {
      const res = await einvoiceApi.transmettre(state.fe.id)
      setTransmission(res.data)
    } catch {
      setState((s) => ({ ...s, error: 'La transmission n\'a pas pu être enregistrée.' }))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="border-t border-border pt-4">
      <p className="mb-2 text-sm font-semibold text-foreground">
        Facturation électronique DGI
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="outline" disabled={busy} onClick={generer}>
          <FileCode size={16} /> Générer e-facture (dry-run)
        </Button>
        {state?.fe && (
          <Button type="button" size="sm" variant="outline" onClick={telecharger}>
            <Download size={16} /> Télécharger XML
          </Button>
        )}
        {state?.fe && (
          <Button type="button" size="sm" variant="outline" disabled={busy} onClick={controler}>
            <ShieldCheck size={16} /> Contrôler
          </Button>
        )}
        {state?.fe && (
          <Button type="button" size="sm" variant="outline" disabled={busy} onClick={transmettre}>
            <Send size={16} /> Transmettre
          </Button>
        )}
      </div>
      {state?.disabled && (
        <p className="mt-2 text-sm text-muted-foreground">
          E-facturation désactivée pour cette société (EINVOICE_ENABLED).
        </p>
      )}
      {state?.fe && (
        <p className="mt-2 text-sm text-muted-foreground">
          {/* WIR223 — la version affichée peut venir de l'historique serveur
              (rechargement de la fiche), pas seulement d'un clic « Générer » :
              le mode réel décide du libellé plutôt qu'un « dry-run » écrit en
              dur qui mentirait sur une version transmise. */}
          E-facture {state.fe.mode === 'reel' ? 'générée' : 'générée (dry-run)'} — version {state.fe.version}. La transmission
          à la DGI reste bloquée tant qu&apos;aucune crédential n&apos;est configurée.
        </p>
      )}
      {/* PACT54 — anomalies bloquantes : la liste, jamais un simple « KO ». */}
      {controle && (controle.anomalies.length > 0 ? (
        <div className="mt-2 text-sm" role="alert">
          <p className="m-0 font-semibold text-destructive">
            Anomalies bloquantes avant transmission
          </p>
          <ul className="mt-1 list-disc pl-5 text-muted-foreground">
            {controle.anomalies.map((a) => <li key={a}>{a}</li>)}
          </ul>
        </div>
      ) : (
        <p className="mt-2 text-sm text-success">
          Facture conforme — aucune anomalie bloquante.
        </p>
      ))}
      {transmission && (
        <p className="mt-2 text-sm text-muted-foreground">
          Transmission enregistrée{' '}
          <Badge tone={transmission.statut === 'accepte' ? 'success' : 'info'}>
            {transmission.statut}
          </Badge>{' '}
          — suivie dans « Transmissions DGI ».
        </p>
      )}
      {state?.error && (
        <p className="mt-2 form-error" role="alert">{state.error}</p>
      )}
    </div>
  )
}

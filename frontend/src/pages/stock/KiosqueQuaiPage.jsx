import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Button, Input } from '../../ui'
import NoIndex from '../../components/NoIndex'
import publicStockApi from '../../features/stock/publicStockApi'
import { messageServeur } from '../../features/stock/api/erreurs'

/* ASTK219 — Kiosque de quai PUBLIC (check-in chauffeur par code, sans session).

   Route /quai/checkin, autonome (aucun layout ERP). Le chauffeur saisit le
   code d'arrivée à 8 caractères remis avec son rendez-vous ; le serveur ne
   répond QUE la confirmation et le quai attribué — l'écran n'affiche donc
   aucune donnée de société ni aucun prix. Le slug de société vient du lien
   du kiosque (`?societe=`), sinon il est demandé. Un code inconnu affiche le
   404 indistinct du serveur ; le geste est idempotent (renvoyer le même code
   redonne la même confirmation) ; le throttle (429) est expliqué lisiblement. */

function messageErreur(err) {
  if (err?.response?.status === 429) {
    const secondes = /(\d+)\s*second/i.exec(err.response?.data?.detail ?? '')?.[1]
    return secondes
      ? `Trop de tentatives. Réessayez dans ${secondes} secondes.`
      : 'Trop de tentatives. Patientez un instant puis réessayez.'
  }
  return messageServeur(err, "L'arrivée n'a pas pu être enregistrée.")
}

export default function KiosqueQuaiPage() {
  const [params] = useSearchParams()
  const societeLien = (params.get('societe') || '').trim()
  const [societe, setSociete] = useState('')
  const [code, setCode] = useState('')
  const [resultat, setResultat] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const valider = async (ev) => {
    ev?.preventDefault()
    const slug = societeLien || societe.trim()
    const saisi = code.trim().toUpperCase()
    if (!slug) { setErreur('Indiquez votre société.'); return }
    if (!saisi) { setErreur("Saisissez le code d'arrivée de votre rendez-vous."); return }
    setOccupe(true); setErreur(null)
    try {
      const { data } = await publicStockApi.quaiCheckin(slug, saisi)
      setResultat(data)
      setCode('')
    } catch (err) {
      setResultat(null)
      setErreur(messageErreur(err))
    } finally { setOccupe(false) }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 p-6">
      <NoIndex />
      <h1 className="text-2xl font-semibold">Arrivée au quai</h1>
      <p className="text-sm text-[var(--muted-foreground)]">
        Saisissez le code reçu avec votre rendez-vous pour signaler votre arrivée.
      </p>

      <form onSubmit={valider} noValidate className="flex flex-col gap-3">
        {!societeLien && (
          <label className="flex flex-col gap-1 text-sm">
            <span>Société</span>
            <Input value={societe} onChange={(e) => setSociete(e.target.value)} sanitize="code" />
          </label>
        )}
        <label className="flex flex-col gap-1 text-sm">
          <span>Code d&apos;arrivée</span>
          <Input
            value={code} onChange={(e) => setCode(e.target.value)} sanitize="code"
            maxLength={8} autoFocus className="text-center text-xl tracking-widest"
          />
        </label>
        <Button type="submit" size="lg" disabled={occupe}>Je suis arrivé</Button>
      </form>

      {erreur && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {erreur}
        </div>
      )}
      {resultat && (
        <div role="status" className="rounded-lg border border-success/30 bg-success/10 p-4 text-success">
          <p className="text-lg font-semibold">Arrivée enregistrée — quai {resultat.quai}</p>
          <p className="text-sm">Présentez-vous au quai indiqué.</p>
        </div>
      )}
    </main>
  )
}

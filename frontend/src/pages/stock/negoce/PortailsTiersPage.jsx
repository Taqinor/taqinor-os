import { useCallback, useEffect, useState } from 'react'
import { Button, Input } from '../../../ui'
import { EnteteStock, BandeauxStock } from '../EnteteStock'
import portailsTiersApi from '../../../features/stock/api/portailsTiersApi'
import { messageServeur } from '../../../features/stock/api/erreurs'

/* ASTK223 — Liens 3PL (portail du dépositaire) : générer, lister, révoquer.

   Le lien à transmettre au dépositaire est la page PUBLIQUE
   `/depot-tiers/<jeton>` (jamais la route d'API). La révocation passe par
   `revoked=true` ; elle se confirme en ligne (aucune boîte native). Chaque
   geste relit la liste du serveur. */

const liste = (d) => (Array.isArray(d) ? d : d?.results ?? [])
const lien = (token) => `${window.location.origin}/depot-tiers/${token}`

export default function PortailsTiersPage() {
  const [liens, setLiens] = useState([])
  const [nom, setNom] = useState('')
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)
  const [aRevoquer, setARevoquer] = useState(null)

  const charger = useCallback(async () => {
    try {
      const { data } = await portailsTiersApi.list()
      setLiens(liste(data))
    } catch (err) { setErreur(messageServeur(err, 'Chargement des liens impossible.')) }
  }, [])

  useEffect(() => { Promise.resolve().then(charger) }, [charger])

  const geste = async (action, repli) => {
    setOccupe(true); setErreur(null)
    try { await action(); await charger(); return true } catch (err) {
      setErreur(messageServeur(err, repli)); return false
    } finally { setOccupe(false) }
  }

  const generer = async (ev) => {
    ev.preventDefault()
    const ok = await geste(() => portailsTiersApi.generer(nom.trim()), 'Génération impossible.')
    if (ok) setNom('')
  }

  const revoquer = async (id) => {
    await geste(() => portailsTiersApi.revoquer(id), 'Révocation impossible.')
    setARevoquer(null)
  }

  return (
    <div className="space-y-4">
      <EnteteStock
                title="Dépôts tiers (3PL)"
        subtitle="Liens publics donnant à un dépositaire la lecture de son seul solde."
      />
      <BandeauxStock erreur={erreur} />

      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        <form onSubmit={generer} noValidate className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col gap-1 text-xs">
            <span>Nom du dépositaire</span>
            <Input value={nom} onChange={(e) => setNom(e.target.value)} className="w-64" />
          </label>
          <Button type="submit" disabled={occupe}>Générer un lien</Button>
        </form>
      </section>

      <section className="rounded-lg border border-[var(--border)] bg-[var(--card)] p-4">
        {liens.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)]">Aucun lien généré.</p>
        ) : (
          <ul className="space-y-3 text-sm">
            {liens.map((l) => (
              <li key={l.id} className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <strong>{l.tiers_nom}</strong>
                <span>{l.revoked ? 'Révoqué' : (l.est_valide ? 'Actif' : 'Expiré')}</span>
                <code className="break-all text-xs">{lien(l.token)}</code>
                {l.expires_at && (
                  <span className="text-[var(--muted-foreground)]">
                    expire le {new Date(l.expires_at).toLocaleDateString('fr-FR')}
                  </span>
                )}
                {!l.revoked && (aRevoquer === l.id ? (
                  <span className="flex gap-1">
                    <Button size="sm" variant="destructive" disabled={occupe} onClick={() => revoquer(l.id)}>
                      Confirmer
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setARevoquer(null)}>Annuler</Button>
                  </span>
                ) : (
                  <Button size="sm" variant="outline" onClick={() => setARevoquer(l.id)}>Révoquer</Button>
                ))}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import portailApi from '../../../api/portailApi'
import { Button, Input } from '../../../ui'

/* ============================================================================
   ADOC141 (D-ADOC-1) — Recherche globale du shell portail CLIENT.
   ----------------------------------------------------------------------------
   Contrat `recherche_portail.json` : `{query, groups:[{type,label,results:
   [{id,label,sublabel}]}]}`, toujours quatre groupes (devis, facture, ticket,
   document), scopés serveur au client connecté. Un mot vide n'appelle jamais le
   serveur et n'affiche rien. Chaque résultat mène à l'écran de son groupe.
   ========================================================================== */

// Groupe serveur → écran du portail qui liste ces objets.
const ECRAN_PAR_GROUPE = {
  devis: '/portail/client/devis',
  facture: '/portail/client/factures',
  ticket: '/portail/client/sav',
  document: '/portail/client/documents',
}

export default function PortailClientRecherche() {
  const [q, setQ] = useState('')
  const [groupes, setGroupes] = useState(null)
  const [erreur, setErreur] = useState(false)

  const chercher = async (e) => {
    e.preventDefault()
    const mot = q.trim()
    if (!mot) {
      setGroupes(null)
      return
    }
    try {
      const r = await portailApi.recherche(mot)
      setGroupes(r.data?.groups ?? [])
      setErreur(false)
    } catch {
      setGroupes(null)
      setErreur(true)
    }
  }

  const nonVides = (groupes ?? []).filter((g) => (g.results ?? []).length > 0)

  return (
    <div className="flex flex-col gap-2">
      <form onSubmit={chercher} role="search" className="flex items-center gap-2">
        <Input type="search" aria-label="Rechercher dans mon espace"
               placeholder="Rechercher un devis, une facture…"
               value={q} onChange={(e) => setQ(e.target.value)} />
        <Button type="submit" variant="outline" size="sm">
          <Search /> Rechercher
        </Button>
      </form>
      {erreur ? (
        <p className="text-sm text-destructive" role="alert">
          La recherche n’a pas abouti.
        </p>
      ) : null}
      {groupes && nonVides.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucun résultat.</p>
      ) : null}
      {nonVides.map((g) => (
        <section key={g.type} aria-label={g.label}>
          <h2 className="text-sm font-medium">{g.label}</h2>
          <ul className="flex flex-col gap-1">
            {g.results.map((r) => (
              <li key={`${g.type}-${r.id}`}>
                <Link to={ECRAN_PAR_GROUPE[g.type] || '/portail/client'}
                      className="text-sm underline">
                  {r.label}
                </Link>
                {r.sublabel ? (
                  <span className="ml-2 text-xs text-muted-foreground">{r.sublabel}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  )
}

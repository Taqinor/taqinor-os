import { useCallback, useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Network, Users } from 'lucide-react'
import {
  Avatar, AvatarFallback, AvatarImage, initials,
  Card, EmptyState, Input, Label, Spinner, Stat, toast,
} from '../../ui'
import rhApi from '../../api/rhApi'

/* ============================================================================
   NTHCM2 — Organigramme hiérarchique (lecture seule).
   ----------------------------------------------------------------------------
   Consomme `GET /rh/employes/organigramme/` (selectors.arbre_hierarchique) :
   la HIÉRARCHIE est calculée côté serveur, l'écran ne la reconstruit pas — il
   n'y a donc qu'UNE définition de « qui rapporte à qui » (NTHCM1).

   TROIS GARDES QUI COMPTENT ICI :
   * aucune boucle infinie possible, même sur des données legacy porteuses d'un
     cycle : le serveur borne la profondeur et marque le nœud coupé
     (`tronque`), l'écran l'affiche au lieu de récurser sans fin ;
   * la recherche ne devine rien : le serveur marque `correspond` (le nœud
     trouvé) et `sur_chemin` (ses ancêtres), l'écran se contente de déplier ce
     qui est marqué ;
   * aucune photo n'est fabriquée : `photo` est une URL présignée réelle ou une
     chaîne vide — dans ce cas on affiche les initiales, jamais une image
     cassée.

   Aucune dépendance de graphe n'est ajoutée : l'arbre est un simple rendu
   récursif en flexbox (NTHCM3 y superposera les rattachements fonctionnels).
   ========================================================================== */

function CarteEmploye({ noeud }) {
  return (
    <div className="flex min-w-0 items-center gap-2.5">
      <Avatar size="sm">
        {noeud.photo ? (
          <AvatarImage src={noeud.photo} alt="" />
        ) : null}
        <AvatarFallback>{initials(noeud.employe)}</AvatarFallback>
      </Avatar>
      <div className="min-w-0">
        <div className="truncate text-sm font-medium">{noeud.employe}</div>
        <div className="truncate text-xs text-muted-foreground">
          {[noeud.poste, noeud.departement].filter(Boolean).join(' — ') || '—'}
        </div>
      </div>
    </div>
  )
}

function Noeud({ noeud, deplieParDefaut, replies, basculer }) {
  const aDesEnfants = (noeud.subordonnes?.length ?? 0) > 0
  // Déplié SAUF si l'utilisateur a explicitement replié ce nœud : la
  // recherche pilote `deplieParDefaut` via `sur_chemin`, et un clic reste
  // toujours prioritaire sur elle.
  const replie = replies.has(noeud.id)
  const ouvert = aDesEnfants && !replie && deplieParDefaut(noeud)

  return (
    <li className="relative pl-4 before:absolute before:left-0 before:top-0 before:h-full before:w-px before:bg-border">
      <div
        className={[
          'my-1 flex items-center gap-2 rounded-lg border px-3 py-2',
          noeud.correspond ? 'border-primary bg-primary/5' : 'border-border',
        ].join(' ')}
        data-org-node={noeud.id}
      >
        {aDesEnfants ? (
          <button
            type="button"
            className="shrink-0 rounded p-0.5 text-muted-foreground hover:text-foreground"
            aria-expanded={ouvert}
            aria-label={ouvert
              ? `Replier ${noeud.employe}`
              : `Déplier ${noeud.employe}`}
            onClick={() => basculer(noeud.id, ouvert)}
          >
            {ouvert
              ? <ChevronDown size={16} aria-hidden="true" />
              : <ChevronRight size={16} aria-hidden="true" />}
          </button>
        ) : (
          <span className="w-[22px] shrink-0" aria-hidden="true" />
        )}
        <CarteEmploye noeud={noeud} />
        {noeud.nb_rapports_directs > 0 && (
          <span className="ml-auto shrink-0 whitespace-nowrap text-xs text-muted-foreground">
            {noeud.nb_rapports_directs} rattaché
            {noeud.nb_rapports_directs > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {noeud.tronque && (
        <p className="pl-6 text-xs text-warning">
          Branche coupée : profondeur maximale atteinte (ou boucle détectée
          dans les données).
        </p>
      )}

      {ouvert && (
        <ul className="ml-3 list-none">
          {noeud.subordonnes.map((enfant) => (
            <Noeud
              key={enfant.id}
              noeud={enfant}
              deplieParDefaut={deplieParDefaut}
              replies={replies}
              basculer={basculer}
            />
          ))}
        </ul>
      )}
    </li>
  )
}

export default function Organigramme() {
  const [recherche, setRecherche] = useState('')
  const [etat, setEtat] = useState({ data: null, loading: true, error: null })
  const [replies, setReplies] = useState(() => new Set())
  const { data, loading, error } = etat

  useEffect(() => {
    let vivant = true
    const params = recherche.trim() ? { q: recherche.trim() } : undefined
    rhApi.getOrganigramme(params)
      .then((res) => {
        if (vivant) setEtat({ data: res.data, loading: false, error: null })
      })
      .catch(() => {
        if (!vivant) return
        setEtat({
          data: null,
          loading: false,
          error: 'Impossible de charger l’organigramme.',
        })
        toast.error('Impossible de charger l’organigramme.')
      })
    return () => { vivant = false }
  }, [recherche])

  const enRecherche = Boolean(data?.recherche)

  // Sans recherche : tout est déplié. Avec recherche : seules les branches
  // marquées `sur_chemin` par le SERVEUR le sont — l'écran ne rejoue pas la
  // recherche, il suit le marquage.
  const deplieParDefaut = useCallback(
    (noeud) => (enRecherche ? Boolean(noeud.sur_chemin) : true),
    [enRecherche],
  )

  const basculer = useCallback((id, ouvert) => {
    setReplies((precedent) => {
      const suivant = new Set(precedent)
      if (ouvert) suivant.add(id)
      else suivant.delete(id)
      return suivant
    })
  }, [])

  const racines = useMemo(() => data?.racines ?? [], [data])

  return (
    <div className="page flex flex-col gap-4">
      <div className="page-header">
        <h2>Organigramme</h2>
      </div>

      <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-end">
        <div className="flex flex-col gap-1.5 sm:w-72">
          <Label htmlFor="org-recherche">Rechercher un collaborateur</Label>
          <Input
            id="org-recherche"
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
            placeholder="Nom, matricule ou poste"
          />
        </div>
        <div className="sm:ml-auto">
          <Stat
            label="Effectif"
            value={data ? String(data.effectif ?? 0) : '—'}
            hint={`${racines.length} racine${racines.length > 1 ? 's' : ''}`}
            icon={Users}
          />
        </div>
      </Card>

      <Card className="overflow-x-auto p-4">
        {loading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-4" /> Chargement de l’organigramme…
          </div>
        )}
        {!loading && error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
        {!loading && !error && racines.length === 0 && (
          <EmptyState
            icon={Network}
            title="Aucun collaborateur à afficher"
            description={enRecherche
              ? 'Aucun collaborateur ne correspond à cette recherche.'
              : 'Renseignez les managers des dossiers employés pour voir la hiérarchie.'}
          />
        )}
        {!loading && !error && racines.length > 0 && (
          <ul className="list-none">
            {racines.map((racine) => (
              <Noeud
                key={racine.id}
                noeud={racine}
                deplieParDefaut={deplieParDefaut}
                replies={replies}
                basculer={basculer}
              />
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

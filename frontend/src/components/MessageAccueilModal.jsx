import { useEffect, useRef, useState } from 'react'
import { useSelector } from 'react-redux'
import notificationsApi from '../api/notificationsApi'
import router from '../router'

/* MSGACC1 — Message d'accueil : posé par un responsable/admin pour UN
   employé précis, affiché EN PLEIN ÉCRAN à sa PREMIÈRE ouverture de l'ERP à
   partir d'une heure choisie (8h00 choisi, ouvre à 8h40 → il le voit ;
   ouvert à 7h50 → rien). CE N'EST PAS UNE NOTIFICATION : aucune ligne du
   centre de notifications, uniquement cette modale.

   Même patron que `WelcomeMoment.jsx` (montée au tout premier niveau, dans
   main.jsx, à côté du RouterProvider — jamais dans `Layout.jsx`, qui est
   remonté à chaque navigation de module et ferait refetcher `a-lire` à
   chaque clic de menu). UN SEUL fetch par chargement, gardé par une ref (pas
   par une dépendance d'effet qui pourrait re-déclencher au moindre
   changement de référence de l'objet `user`).

   Plusieurs messages dus : affichés un par un (le plus ancien d'abord — déjà
   trié côté serveur), « Compris » poste la lecture PUIS passe au suivant.
   Échec réseau (fetch OU lecture) : SILENCIEUX — jamais bloquer l'ouverture
   de l'ERP.

   AMENDEMENT FONDATEUR — chemins internes cliquables : un token du corps qui
   commence par `/` + une lettre (``/ged``, ``/crm/...``, ``/visites/...``)
   se rend cliquable, ferme la modale, puis navigue. PAS de <Link> react-
   router ici : ce composant est monté volontairement HORS de l'arbre du
   routeur (à côté de <RouterProvider>, jamais dedans) pour garantir « un
   seul fetch par chargement » — le monter dans WithLayout (router/index.jsx)
   le referait à CHAQUE navigation de module. `router.navigate()` est
   l'export du même routeur (createBrowserRouter) que <RouterProvider>
   consomme : appel impératif, même navigation SPA sans rechargement,
   utilisable sans contexte React Router (même patron qu'un thunk Redux qui
   naviguerait depuis en dehors de l'arbre). Jamais de HTML injecté — le
   corps reste du texte, seuls les tokens-chemins sont wrappés dans un
   <button> stylé en lien. */

// Chemin interne : commence par `/` suivi d'une lettre (jamais une simple
// barre isolée ou une fraction comme « 1/2 »).
const CHEMIN_INTERNE = /^\/[a-z]/i

function renderCorps(corps, onNaviguer) {
  // Tokenisation « simple » (fondateur) : coupe sur les runs d'espaces
  // (espace ET saut de ligne, capturés donc conservés dans le résultat —
  // `whitespace-pre-line` sur le conteneur préserve la mise en page).
  return corps.split(/(\s+)/).map((morceau, i) => {
    if (CHEMIN_INTERNE.test(morceau)) {
      return (
        // Clé par index : tokenisation statique du corps, jamais réordonnée.
        <button
          key={i}
          type="button"
          onClick={() => onNaviguer(morceau)}
          className="text-primary underline underline-offset-2 hover:opacity-80"
        >
          {morceau}
        </button>
      )
    }
    return morceau
  })
}

function formatDateHeure(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleString('fr-FR', {
    day: '2-digit', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function MessageAccueilModal() {
  const isAuthenticated = useSelector((s) => s.auth?.isAuthenticated)
  const [messages, setMessages] = useState([])
  const fetchedRef = useRef(false)

  useEffect(() => {
    if (!isAuthenticated || fetchedRef.current) return
    fetchedRef.current = true
    notificationsApi.messagesAccueilALire()
      .then((res) => {
        // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount, une seule fois (fetchedRef)
        setMessages(res.data?.messages || [])
      })
      .catch(() => { /* silencieux — jamais bloquer l'ouverture de l'ERP */ })
  }, [isAuthenticated])

  if (messages.length === 0) return null
  const courant = messages[0]

  const compris = () => {
    const id = courant.id
    // Optimiste : on avance tout de suite (jamais bloquer sur le réseau).
    // Un échec de `lu` laisse simplement le message revenir au prochain
    // chargement — comportement voulu (« tant que pas lu, elle se
    // représente »), jamais une erreur visible.
    setMessages((prev) => prev.slice(1))
    notificationsApi.marquerMessageAccueilLu(id).catch(() => {})
  }

  // Clic sur un chemin interne : FERME la modale (pas seulement le message
  // courant — un clic-lien n'est pas un « Compris », rien n'est marqué lu :
  // le message revient tel quel à la prochaine ouverture), PUIS navigue.
  const allerVersChemin = (chemin) => {
    setMessages([])
    router.navigate(chemin)
  }

  return (
    <div
      className="fixed inset-0 z-[var(--z-overlay)] flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="message-accueil-title"
      data-testid="message-accueil"
    >
      <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-ui-lg">
        <h2
          id="message-accueil-title"
          className="font-display text-lg font-bold tracking-tight text-foreground"
        >
          ☀️ Message d’accueil
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          {courant.auteur_nom || 'Direction'}
          {' · '}
          {formatDateHeure(courant.visible_a_partir_de)}
        </p>
        <p className="mt-4 whitespace-pre-line text-sm leading-relaxed text-foreground">
          {renderCorps(courant.corps, allerVersChemin)}
        </p>
        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={compris}
            className="btn inline-flex items-center justify-center rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-primary-foreground hover:opacity-90"
          >
            Compris
          </button>
        </div>
      </div>
    </div>
  )
}

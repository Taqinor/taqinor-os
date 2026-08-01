// ODY8 — « App non activée » : une vraie porte, plus un renvoi muet.
// ----------------------------------------------------------------------------
// Avant : ouvrir l'URL d'un module désactivé pour la société (ODX6) rebondissait
// EN SILENCE vers `/dashboard` — l'utilisateur ne comprenait ni pourquoi il
// avait changé d'écran, ni comment obtenir l'app. Le garde `moduleLoader`
// (router/index.jsx, UNE implémentation, deux points d'appel : les routes du
// registre via router/moduleRoutes.jsx et les routes déclarées directement)
// redirige désormais ici.
//
// Deux refus DISTINCTS, deux écrans distincts — jamais confondus :
//   • app non ACTIVÉE pour la société (ModuleToggle OFF) → cet écran, qui
//     nomme l'app et dit comment l'obtenir ;
//   • app activée mais RÔLE insuffisant → `/403` (ui/Forbidden.jsx, acquis
//     VX131) : message différent, et surtout AUCUNE donnée révélée — l'ordre
//     des gardes garantit que le refus de rôle arrive AVANT le test de module,
//     donc un utilisateur sans droit n'apprend même pas si l'app est installée.
//
// Le CTA dépend du rôle (matrice module OFF × rôle) : un admin va activer
// l'app dans Paramètres → Applications (ODX5) ; les autres sont invités à
// demander à leur administrateur — jamais un bouton qui mènerait à un 403.
import { Link, useSearchParams } from 'react-router-dom'
import { PackageOpen, LayoutGrid } from 'lucide-react'
import { moduleConfigs } from '../../router/moduleRoutes'
import { useIsAdmin } from '../../hooks/useHasPermission'
import { Button } from '../../ui/Button'

export default function AppNotInstalled() {
  const [searchParams] = useSearchParams()
  const cle = searchParams.get('app') || ''
  const estAdmin = useIsAdmin()

  // Le registre connaît l'app même quand la société ne l'a pas activée : on
  // peut donc la NOMMER (son nom de catalogue, déjà visible dans la boutique
  // Applications) sans rien révéler de ses données.
  const config = moduleConfigs.find((c) => c.key === cle)
  const nom = config?.nav?.label || 'Cette application'
  const icone = config?.nav?.items?.[0]?.icon

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <div
        className="flex max-w-md flex-col items-center gap-3 rounded-xl border border-warning/40 px-6 py-12 text-center"
        data-testid="app-non-activee"
      >
        <span className="flex size-12 items-center justify-center rounded-xl bg-warning/12 text-warning">
          {icone || <PackageOpen className="size-5" aria-hidden="true" />}
        </span>
        <h2 className="font-display text-base font-semibold text-foreground">
          {nom} n’est pas activée
        </h2>
        <p className="max-w-sm text-sm text-muted-foreground">
          Cette app n’est pas activée pour votre société.
          {estAdmin
            ? ' Vous pouvez l’activer dans Paramètres → Applications.'
            : ' Demandez à votre administrateur de l’activer.'}
        </p>
        <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
          {estAdmin && (
            <Button asChild>
              <Link to="/parametres">Activer</Link>
            </Button>
          )}
          <Button asChild variant="outline">
            <Link to="/apps">
              <LayoutGrid className="size-4" aria-hidden="true" /> Menu d’accueil
            </Link>
          </Button>
        </div>
      </div>
    </div>
  )
}

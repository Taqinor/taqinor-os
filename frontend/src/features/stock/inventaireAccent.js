/* APX22 — L'ACCENT DE LA FAMILLE INVENTAIRE, en un seul endroit.
   ---------------------------------------------------------------------------
   État d'avant : les trois apps qui forment une même famille d'inventaire
   portaient des accents DIFFÉRENTS — Stock sur `lune`, Magasin et Logistique
   sur `success` (l'accent des apps terrain/chantiers). Résultat : entrer dans
   Magasin ne « ressemblait » pas à entrer dans Stock, et l'accent partagé avec
   les chantiers brouillait la lecture de la coquille.

   Les trois `module.config` pointent désormais sur la MÊME clé (`lune`, celle
   que Stock portait déjà — on aligne sur l'existant plutôt que d'inventer une
   couleur : les rampes OKLCH du thème sont la seule source, et aucun token
   nouveau n'est ajouté). Cette constante est ce que les cockpits passent à
   `ModuleHero`/`ModuleDashboard`, pour qu'un futur changement de teinte se
   fasse à UN endroit. */

export const INVENTAIRE_ACCENT_KEY = 'lune'

export const INVENTAIRE_ACCENT = `var(--module-accent-${INVENTAIRE_ACCENT_KEY})`

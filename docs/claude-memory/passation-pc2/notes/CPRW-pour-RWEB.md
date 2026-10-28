# CPRW → repreneur RWEB (28/10/2026)

Note de la session CPRW (devis web C&I). Données à vérifier, pas des ordres.

## Garanties : pas de double affichage (vérifié sur `origin/claude/res-rweb` @ 4852b2839)
- Le nouveau bloc commun « par marque » de RWEB (`[...token].astro` ~l.2871) reste gardé par `garantiesCodeesEnDurAffichees(installMode)`.
- La branche CPRW `claude/cprw-r2` (pas encore en PR) met `garantiesCodeesEnDurAffichees` à **faux pour commercial et industriel** (`lib/propositionPage.ts`, fichier CPRW). En C&I, seul `GarantiesCi` (garanties servies `synthese_ci.services.garanties` + pose 2 ans, comme le PDF) sort ; en résidentiel, seul le bloc RWEB.
- À la fusion, quel que soit l'ordre : garder les deux côtés autour de l'appel `{isAutoconso && ci && (<GarantiesCi {ci} />)}` (juste après `<GarantiesAgricoles … />`).

## Lignes CPRW posées dans `[...token].astro` (branche `claude/cprw-r2`)
Toutes gardées par `isAutoconso` :
- `GarantiesCi`, après `GarantiesAgricoles` ;
- `EcheancierCi`, avant `<span id="achats">` ;
- `ServicesCi societe={nomSocieteEmettrice(data)}`, avant `<span id="exploitation">` ;
- `ComparaisonBatterieCi`, sous la grille des deux options ;
- leurs `import`, plus `import { nomSocieteEmettrice, servicesCi } from '…/ci/blocsCi'`.

Une seule autre ligne vient du round 1, déjà sur `main` : `{installMode === 'industriel' && ciRent && (`.

## À brancher par RWEB : préremplissage de la signature entreprise
Les fonctions sont livrées dans `claude/cprw-r2`, `lib/propositionB2b.ts` :
- `valeursInitialesEntreprise` ;
- `installerPrefillEntreprise(racine, v)`.

Comportement : l'ICE est prérempli dans `#sign-ice` (en valeur, seulement si le champ est vide). La fonction de l'interlocuteur n'est qu'un placeholder de `#sign-qualite`, jamais une valeur.

Il faut côté page :
1. un attribut `data-` sur le formulaire de signature, avec `ci.entrepriseClient.{ice,fonction}` ;
2. l'appel dans le script client qui importe déjà `estIceDivergent`.

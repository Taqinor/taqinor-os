# Cerveau estimateur V4 — méthode & sources (apps/web)

Documente la MÉTHODE derrière le preview privé `/preview/toiture-3d-pro-7`
(`src/lib/estimatorBrainV4.ts`). Aucune donnée client ici — uniquement la
traçabilité des chiffres. Rien sur un preview n'est un devis : toujours une
fourchette indicative.

## Ce que V4 ajoute (par rapport à V3 / pro-6)

V4 **compose** sur V2/V3 sans les modifier (pro-3/4/5/6 restent des baselines
intactes). Trois changements :

1. **PVGIS = source de vérité de la production.** La recherche de l'optimum ne se
   note plus sur le seul rendement de la table committée, mais sur le **rendement
   spécifique (kWh/kWc/an) lu sur PVGIS au GPS EXACT** de la toiture. Le rendement
   spécifique est **indépendant de la taille du système** : on l'interroge une fois
   par `(inclinaison, aspect)`, puis on **met à l'échelle par kWc**. Le navigateur
   n'appelle jamais PVGIS : le page-script passe par le proxy serveur
   `/api/roof-yield` (kWc=1, une jambe) et met en cache par `(tilt, aspect)`,
   réutilisé entre tous les réglages.

2. **Balayage en grille fine.** Inclinaison par pas d'environ 5° de 5° à 35°
   (`fineTiltGrid`), azimut {plein-sud, aligné-toit, Est-Ouest}, portrait ET
   paysage, marge gardée/retirée. Chaque config est **plafonnée au besoin** (jamais
   au-delà — le surplus reste non valorisé au Maroc) et notée sur l'**énergie
   POSÉE** (qui encode l'adéquation au besoin). Le **vrai maximum** est retenu, même
   s'il ne correspond à aucune ligne standard du tableau.

3. **Optimum comme sa propre ligne.** Quand l'optimum calculé n'est pas une config
   standard, il s'affiche en **« Optimum calculé — inclinaison X°, orientation Y »**,
   badgé « Recommandé », avec une **raison en une phrase** et la **source** du chiffre
   (`PVGIS · GPS exact` ou `estimé · table committée`).

## Conventions PVGIS

- API **v5_2 PVcalc** (Commission européenne, JRC — gratuite, sans clé, couvre le
  Maroc), pertes système **14 %**, `pvtechchoice = crystSi`.
- **`mountingplace = 'free'`** pour le toit PLAT racké de pro-7 (panneaux aérés ;
  léger gain de rendement). Les routes pro-3/4/5/6 gardent **`'building'`** par
  défaut — strictement inchangées (le proxy `/api/roof-yield` ne passe en `'free'`
  que si le corps de requête le demande explicitement).
- **Aspect** : `Sud = 0`, `Est = −90`, `Ouest = +90`, `Nord = 180`. La conversion
  azimut-boussole → aspect PVGIS vit dans `aspectFromCompass()` (un mauvais signe
  corromprait silencieusement la production — testé).

## Robustesse / repli gracieux

PVGIS lent ou injoignable pour un `(tilt, aspect)` → le rendement de ce couple
retombe sur la **table committée par latitude** (`src/lib/yieldTable.ts`,
`specificYield`). Le résultat est alors étiqueté **« estimé »** au lieu de
**« PVGIS »**. Aucune erreur visible pour le visiteur. La table committée est une
**donnée**, pas une dépendance.

## Règles d'intégrité tenues (mêmes que V2/V3)

- **Plafond besoin** : on dimensionne au besoin dérivé de la facture, jamais au
  maximum du toit (surplus non compensé en BT au Maroc).
- **Borne d'empreinte** : Σ empreintes panneaux ≤ surface utile (obstacles déduits)
  — héritée de `packConfig` (V2), aucune fork du chemin toit plat.
- **Économies plafonnées** au coût de l'énergie évitable (jamais plus).
- **Base facture → énergie** : barème régie ONEE (sélectif, TTC), aligné avec le
  reste du site.

## Tests

- `tests/estimatorBrainV4.test.ts` (moteur pur) : mapping aspect PVGIS ;
  l'optimum est le **vrai maximum** de la grille (piloté par le rendement injecté) ;
  **PVGIS déplace** l'inclinaison gagnante vs la table seule ; **repli gracieux**
  (yieldFn null → table, source « estimate ») ; couples PVGIS candidats.
- `tests/estimatorPreviewPro7.test.ts` (page/route) : route privée (noindex, hors
  sitemap, hors page publique), V4 branché, pose `'free'`, ligne « Optimum calculé »,
  et baselines pro-3/4/5/6 + le défaut `'building'` du proxy strictement préservés.

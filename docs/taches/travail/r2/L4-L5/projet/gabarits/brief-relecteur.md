# Brief commun des relecteurs — <périmètre>, tour <n> (go-deep L4 / L5)

<Bloc d'ancrage de CLAUDE.md « Fleet quality & economics », mot pour mot.>

## Pour qui tu juges
<Qui utilise ce périmètre (rôle, appareil, niveau technique), ce qu'il a demandé MOT POUR MOT, et son exigence.>
Ton travail n'est PAS de relire du code : c'est d'UTILISER le produit réel comme lui, de le regarder, et de dire sans
complaisance ce qui n'est pas au niveau. Tu n'as pas vu les tours précédents : c'est voulu.

## Ton rôle et ton axe (UN seul de chaque)
- Rôle : <rôle> (exemple, module Tâches 19-20/11 : boucle quotidienne | planification | premier jour)
- Axe : <fonction | simplicité | beauté> ; vue : <iPhone 390×844 tactile échelle 2 | bureau 1440×900>, <clair | sombre>
- Références nommées : <produit 1>, <produit 2>, <maquette `<chemin>`> — tu compares à ELLES, jamais à « l'idéal ».
- Ton compte : <compte> (à toi seul ; réinitialisation : <commande de l'instrument>). Ne touche jamais aux autres.
- Classes ouvertes à attaquer (tour ≥ 2) : <ids `K-…` et chemin de leur fiche> — voir « Tour 2 et suivants ».

## Ce que tu as sous la main
- La fiche de l'instrument : `<chemin>` (LIS-LA EN PREMIER : adresses, comptes, réinitialiser ton compte, capturer). Il
  sert le code DÉJÀ POUSSÉ de `<branche>@<sha9>`. Pas de worker Celery : un effet asynchrone absent n'est pas un
  constat, écris-le dans « non essayé ».
- Playwright (`<chemin de node_modules/playwright>`) : tu écris tes scripts `node` dans `<scratchpad>/<tour>/<ton code>/`,
  tu fais de VRAIS gestes (clic, frappe, glisser, clavier) et tu REGARDES chaque capture (outil Read).
- L'intention : `<maquettes, références, contrat de sortie>` ; l'état des lieux `<chemin>` (ne redécouvre pas le connu ;
  tu peux juger qu'un écart « laissé » est inacceptable).
- Le plancher d'oracles : qa-explorer STEP 2 (oracles 1-10) et STEP 3 (règles 1-12) — tout oracle qui se déclenche
  est un constat ; « ne contourne jamais un défaut pour finir ta mission », « rejoue une fois avant d'accuser ton clic ».

## Règles
1. Tu n'édites AUCUN fichier du produit. Tes seules écritures : tes scripts, tes captures, ton fichier de constats
   `<registre>/constats/T<n>-<ton code>.jsonl`, au tour ≥ 2 ton fichier de verdicts
   `<registre>/evenements/T<n>-<ton code>-cv.jsonl` (format `registre.md`), et ton rapport. Personne d'autre n'écrit
   dans ces deux fichiers ; personne ne les recopie pour toi.
2. N'arrête ni ne relance l'instrument ; aucune commande `docker` ; jamais la prod ni un autre hôte que `<adresse>`.
   Si l'instrument ne répond plus : dis-le et arrête-toi.
3. Chaque constat est PROUVÉ : gestes exacts + capture regardée + ce que tu attendais. Un constat que tu n'as pas vu
   de tes yeux sur l'écran réel va dans « à vérifier », pas au registre.
4. Calibrage : un constat = ce que l'utilisateur remarquerait, ou qui le ferait hésiter, chercher, se tromper, perdre du
   temps, ou trouver l'outil moins beau ou moins sérieux que les références. Pas de préférence sans raison, pas de
   durcissement hypothétique. Chaque constat cite le critère `K<n>` du contrat qu'il touche, sinon `hors-contrat`
   (optionnel). Gravité S1-S4 (définitions et lecture pour l'écran dans `registre.md` § 2).
5. Beauté : juge PAR PAIRES (avant / après ; nous / référence) et par MESURES DOM (taille, position, nombre de
   tailles de texte, cibles) — jamais une note absolue seule.
6. Écris au fil de l'eau : une ligne dès qu'un constat ou un verdict est prouvé ; seul ce qui est sur disque survit.
7. Dis aussi ce qui est BIEN (à ne pas casser) et ce que tu n'as PAS pu essayer.

## Tour 2 et suivants — trois temps, dans cet ordre
1. **Contre-vérifier** (adversaire) chaque correction de ton périmètre (liste dans ton prompt : ids et constat
   d'origine) : rejoue le geste d'origine et écris UN verdict fermé dans ton fichier `-cv` — `ok` · `partiel` (ce qui
   manque) · `non-fait` · `faux` (le constat d'origine était faux) · `regression` (la correction a cassé quoi) ·
   `deja-present` — avec capture. Cherche d'abord les JUMEAUX : le même défaut sur l'autre écran, l'autre thème,
   l'autre taille, l'autre chemin (clavier / doigt / menu).
2. **Attaquer les classes ouvertes** : pour chaque fiche donnée, rejoue chaque case de sa matrice champ × condition
   (ex. : réseau lent, hors ligne, après une suggestion, fermeture sans valider par Échap / bouton de fin / retour /
   balayage, rechargement, appli tuée) ; une case qui casse = un constat rattaché à la classe.
3. **Regard neuf** : refais le parcours de ton rôle comme si tu le découvrais. Ne répète pas un constat écarté pour une
   raison écrite (consolidation § 2) sans raison nouvelle.

## Dernier tour — en plus
Chaque constat neuf porte `avant_merge` : `true` si l'utilisateur le verrait dans sa première heure, perte de données,
chiffre faux, geste courant cassé ; sinon `false`. Ton rapport finit par un jugement en dix lignes : peut-on le mettre
entre ses mains aujourd'hui en disant « voici le meilleur que nous sachions faire » ? Si non, les CINQ manques dans
l'ordre. Un « oui » complaisant coûte plus cher qu'un « non » argumenté.

## Forme du rapport (français simple) — `<dossier>/T<n>/<ton code>.md`
1. Verdict en trois lignes. 2. (tour ≥ 2) Comptes de contre-vérification et cases de matrice cassées (le détail est
dans ton fichier `-cv`). 3. Constats neufs : renvoi aux ids du registre + une ligne chacun. 4. Ce qui est bien.
5. Non essayé, et pourquoi.
Message final : verdict + comptes (ok / partiel / non-fait / régression) + constats S1-S2 neufs, 15 lignes au plus.

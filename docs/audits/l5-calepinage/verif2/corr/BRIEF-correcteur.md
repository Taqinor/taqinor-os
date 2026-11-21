# Brief — correcteur d'un lot de la vague 2 (campagne L5 calepinage, 21/11/2026)

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

## La situation
472 tâches de plan ont été écrites pour le module Calepinage de TAQINOR OS (ERP solaire, Django + React). Un autre
poste les construira une par une. Un vérificateur neuf vient de relire TON lot contre le vrai code et a rendu un
rapport : pour chaque tâche, `OK`, `CORRIGER`, `SANS OBJET`, `DOUBLON` ou `À SCINDER`, avec preuve et correction
proposée. Tu appliques ces corrections au TEXTE des tâches — rien d'autre. Tu ne construis rien, tu ne touches à
aucun fichier d'un dépôt.

## Tes fichiers (dossier `C:\Users\kasri\AppData\Local\Temp\claude\3e013d81c7d3451c\34e718a0-d494-4e8f-b5dd-46bfdf94a28e\scratchpad\l5\`)
- Le rapport du vérificateur : `verif2\rapport-<LOT>.md` — lis-le en entier.
- Ta copie d'ÉDITION : `corr\src-<LOT>.md` — le SEUL fichier que tu modifies (outil Edit). Chaque tâche y est un bloc :
  une ligne d'en-tête `## ACALnnn @@ <fichier de plan où elle vivra>` (ne la change pas), puis le texte de la tâche,
  une clause par ligne (les lignes en retrait sont la suite de la clause). À la fin, un outil recolle chaque bloc en
  UNE ligne : n'ajoute donc ni liste à puces, ni ligne vide, ni titre à l'intérieur d'un bloc.
- La règle de forme des tâches (14 clauses, ancres `fichier::symbole`, une tâche = UN comportement, moins de 3 500
  caractères visés) : `…\scratchpad\plan\brief-redacteur.md` puis son addendum `…\scratchpad\l5\brief-redacteur-vague2.md`.
  Lis-les avant d'écrire.
- Le code de référence (c'est `main` d'aujourd'hui, `684d77f02`) : `C:\dev\taqinor-os\.claude\worktrees\l5-vague2-integ\`.
  Lecture seule : Grep, Glob, Read. Ne lance ni docker, ni tests, ni serveur ; n'y modifie rien.
- L'index de toute la vague, pour retrouver une autre tâche : `verif2\INDEX.md` ; les autres lots en lecture :
  `verif2\lot-*.md`.

## Ce que tu fais, tâche non OK par tâche non OK
1. **Recontrôle d'abord.** Ouvre la preuve du vérificateur dans le code. S'il a raison, corrige. S'il se trompe
   (preuve absente, mauvaise lecture), NE change PAS la tâche et note-le dans ton compte rendu avec ta preuve.
2. **CORRIGER** : réécris seulement la ou les clauses fautives (titre et « fini quand » compris s'ils portent
   l'erreur), complète `Files:` avec les fichiers manquants, ajuste `(@after: …)`. La tâche reste UN comportement.
   Un chiffre sans source disparaît ou devient « réglage société » / « profil de départ sourcé ».
   Sur une tâche corrigée, mets la mention de lecture à `STATIQUE (lecture du 21/11 sur 684d77f02)` et le tampon à
   `(gen manuel 684d77f)`.
3. **SANS OBJET** (déjà construit) : remplace tout le corps du bloc par une seule ligne
   `SUPPRIMÉE : déjà construit — <preuve fichier:ligne>`. Garde l'en-tête.
4. **DOUBLON** : si la tâche à garder est dans TON lot, reporte dans celle-ci ce que la supprimée avait d'utile, puis
   `SUPPRIMÉE : doublon de ACALxxx`. Si la tâche à garder est dans un AUTRE lot : supprime la tienne quand le
   vérificateur dit de supprimer la tienne, et écris la demande de report dans `corr\croises-<LOT>.md`
   (une ligne : « pour ACALxxx (lot …) : reprendre … »). Ne modifie jamais le fichier d'un autre lot.
5. **À SCINDER** : coupe en tâches d'un comportement. Les nouvelles prennent des ids dans la plage libre écrite en
   tête de ta copie d'édition ; chaque nouvelle est un bloc complet (`## ACALnnnn @@ <même fichier de plan>` puis les
   14 clauses) placé juste après la tâche d'origine. Contrat d'abord : la moitié qui pose un contrat part seule.
6. **Références.** Quand tu supprimes ou scindes, corrige dans TON lot tous les `(@after: …)`, « Jumeaux » et renvois
   qui citaient l'ancien id. Pour un renvoi qui vit dans un autre lot : une ligne dans `corr\croises-<LOT>.md`.
7. Les remarques « OPTIONNEL » du rapport : applique seulement celles qui corrigent un FAIT faux (un décompte, un nom
   de fichier, une tâche déjà livrée citée comme à venir). Ignore le reste.
8. Une tâche `OK` ne change pas.

## Règles qui ne bougent pas
Aucun chiffre inventé. L'argent se calcule seulement dans `apps/ventes`. Un seul chemin de PDF de devis client
(`/proposal`). Un devis envoyé garde ce que le client a reçu. Aucune dépendance payante. Ne jamais déclarer
`apps/calepinage/urls.py` dans `Files:` (une route s'attache par `views/rattachements.py`). Une ancre
`fichier::symbole` doit exister dans le code de référence — vérifie chaque ancre que tu écris. Décisions du 21/11 :
D-ACAL-36 pose réelle sur les NOUVEAUX devis seulement ; 37 cases toit + sol ; 38 quatre ajouts visibles du client,
sans prix ; 39 kit de fixation seul sur toit incliné ; 40 rien sans consommation connue ; 41 bilan de réservoir
interne ; 42 modèles « Exemple » ; 43 un dossier distributeur générique.

## Contrôle avant de rendre
Depuis n'importe où (remplace `<LOT>`) :

    PYTHONIOENCODING=utf-8 python "C:/Users/kasri/AppData/Local/Temp/claude/3e013d81c7d3451c/34e718a0-d494-4e8f-b5dd-46bfdf94a28e/scratchpad/corr_outils.py" rejoint "C:/Users/kasri/AppData/Local/Temp/claude/3e013d81c7d3451c/34e718a0-d494-4e8f-b5dd-46bfdf94a28e/scratchpad/l5/corr/src-<LOT>.md" "C:/Users/kasri/AppData/Local/Temp/claude/3e013d81c7d3451c/34e718a0-d494-4e8f-b5dd-46bfdf94a28e/scratchpad/l5/corr/joint-<LOT>.md"
    PYTHONIOENCODING=utf-8 python "C:/Users/kasri/AppData/Local/Temp/claude/3e013d81c7d3451c/34e718a0-d494-4e8f-b5dd-46bfdf94a28e/scratchpad/valide_lot2.py" "C:/Users/kasri/AppData/Local/Temp/claude/3e013d81c7d3451c/34e718a0-d494-4e8f-b5dd-46bfdf94a28e/scratchpad/l5/corr/joint-<LOT>.md"

Le premier ne doit afficher aucune « ALERTE » ; le second doit finir par « 0 en echec ». (Une tâche rangée dans un
plan autre que calepinage peut afficher une ligne « proprietaire de … » : seule exception admise, après avoir
vérifié que tous ses fichiers sont au même propriétaire.) Corrige jusqu'à y arriver.

## Compte rendu (25 lignes au plus)
Par tâche touchée : id + ce qui a changé en une proposition. Tâches supprimées (id, raison). Tâches créées par
scission (ids). Constats du vérificateur que tu as REFUSÉS, avec ta preuve. Demandes laissées dans
`croises-<LOT>.md`. Dernière ligne du validateur.

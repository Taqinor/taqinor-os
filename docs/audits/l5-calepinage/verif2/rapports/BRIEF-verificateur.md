# Brief — vérificateur neuf de la vague 2 (campagne L5 calepinage, 21/11/2026)

Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output.

## Ce que tu vérifies
TAQINOR OS (ERP d'un installateur solaire marocain, Django + React). Une campagne a écrit 472 tâches de plan pour
améliorer le module Calepinage (conception d'une installation : toit, panneaux, électrique, résultats, documents).
Un AUTRE poste construira ces tâches une par une, sans te demander ton avis : une tâche dont la prémisse est fausse,
déjà construite, en double ou contraire à une règle du fondateur lui coûte une construction pour rien (mesuré sur ce
dépôt : 48 % seulement des tâches passent du premier coup). Tu n'as PAS écrit ces tâches. Ton travail : les relire
une par une contre le VRAI code et dire lesquelles sont à corriger avant d'entrer au plan.

## Où lire
- Ton lot (copie de LECTURE, une clause par ligne) : le fichier `lot-<TON LOT>.md` nommé dans ta consigne, dans
  `C:\Users\kasri\AppData\Local\Temp\claude\3e013d81c7d3451c\34e718a0-d494-4e8f-b5dd-46bfdf94a28e\scratchpad\l5\verif2\`.
  Lis-le EN ENTIER (par tranches si besoin). Dans le plan, chaque tâche tient sur UNE ligne ; ne juge pas la forme.
- L'index de toute la vague (une ligne par tâche) : `INDEX.md`, même dossier — pour chercher un doublon par mots-clés
  (Grep), pas pour le lire en entier.
- Le CODE à lire : `C:\dev\taqinor-os\.claude\worktrees\l5-verif\` — c'est `main` tel qu'il sera quand le constructeur
  commencera (il contient déjà une cinquantaine de tâches calepinage construites ces dernières heures : import PVsyst,
  vue du ciel, table d'ombrage, bifacial, optimiseur, tracé proposé du toit, rapport, mesures d'écran, parcours guidé…).
  Lis UNIQUEMENT là. N'y modifie RIEN, ne lance ni docker, ni tests, ni serveur. Outils : Grep, Glob, Read.
  Carte du dépôt si tu cherches où vit quelque chose : `docs/CODEMAP.md` §3-§4 de ce même dossier.

## Pour CHAQUE tâche de ton lot, dans cet ordre
1. **Déjà construit ?** Le comportement demandé (« fini quand … ») existe-t-il déjà dans le code ? Cherche-le (nom du
   bouton, de la clé, de la fonction). S'il existe en entier → `SANS OBJET` ; en partie → `CORRIGER` (dis ce qui reste).
2. **Prémisse.** Ouvre le `fichier::symbole` de la clause « Emplacement » et ceux cités par « Constat » : le code
   fait-il bien ce que la tâche affirme (la constante en dur est là, le bouton manque, la fonction écarte tel cas) ?
3. **Ancres.** Le module de test nommé par « Test rouge d'abord » existe ; un appelant au moins de « Appelants » est
   vrai ; un littéral de « Assertions existantes » est bien dans le test cité.
4. **Chiffres.** Toute valeur que la tâche fait METTRE dans le produit (défaut, seuil, coefficient, pourcentage) sans
   source nommée ni réglage société → à signaler (règle du fondateur : aucun chiffre inventé ; une valeur de départ
   vient du « profil de départ » sourcé ou d'un réglage). Une MESURE du code ou de l'écran actuel n'est pas concernée.
5. **Règles du fondateur.** À signaler si la tâche : calcule de l'argent hors de `apps/ventes` ; crée un PDF de devis
   client hors de `/proposal` ; change ce qu'affiche un devis DÉJÀ ENVOYÉ ; ajoute une dépendance ou une API payante ;
   montre un prix d'achat ; met un prénom en dur ; pose une action destructrice sur un raccourci clavier ; importe les
   `models` d'une autre app métier (on passe par ses `selectors.py` / `services.py`).
6. **Décisions du fondateur (21/11).** À signaler si la tâche les contredit :
   D-ACAL-31 valeurs de départ = profil sourcé ; D-ACAL-32 parcours guidé en 5 étapes pour tous (Toit, Panneaux,
   Électrique, Résultats, Documents), mode expert sur un interrupteur ; D-ACAL-33 détection du toit par IA planifiée ;
   D-ACAL-36 les NOUVEAUX devis ayant un calepinage enregistré impriment la production de la pose réelle, les devis
   envoyés ne changent pas, la liste des écarts est montrée d'abord ; D-ACAL-37 toit + sol : cases à cocher, toutes
   cochées ; D-ACAL-38 quatre ajouts visibles du client autorisés, SANS prix (soleil animé sur la page du devis, courte
   vidéo 3D pour WhatsApp, panneaux sur la photo du site, pertes en mots simples) ; D-ACAL-39 toit incliné posé à plat :
   kit de fixation seulement, ni structures acier ni plots de lestage ; D-ACAL-40 sans consommation connue : ni économies,
   ni TRI, ni retour sur investissement, ni à l'écran ni imprimés ; D-ACAL-41 bilan de réservoir du pompage : interne
   seulement, le document agricole client de 3 pages ne change pas ; D-ACAL-42 exemples = modèles de bibliothèque
   marqués « Exemple » ; D-ACAL-43 un seul dossier distributeur générique.
7. **Doublon ou contradiction** avec une autre tâche de ton lot, ou de l'index (cherche 2-3 mots-clés du titre).
8. **Faisable d'un coup.** Le « fini quand » est observable ; la tâche est UN comportement (pas trois) ; la liste
   `Files:` contient ce qui doit vraiment changer (un champ de modèle sans migration, une clé servie sans sérialiseur
   ni échantillon de contrat = à signaler).

## Calibrage
Ne signale QUE le faux ou le contraire à la règle (points 1 à 8). Le style, une clause qui pourrait être mieux dite,
un durcissement hypothétique : à part, sous « OPTIONNEL », 5 lignes au plus pour tout le lot. Un chiffre inventé est
TOUJOURS du faux, jamais de l'optionnel. Ne propose pas de nouvelles tâches.

## Profondeur
Chaque tâche : au moins l'« Emplacement » ouvert et lu, et le point 1 cherché. Compte 4 à 8 appels d'outil par tâche.
Ne t'arrête pas avant la dernière tâche du lot ; si tu ne peux pas finir, nomme les tâches non vérifiées.

## Ce que tu rends
Écris ton rapport dans `…\scratchpad\l5\verif2\rapport-<TON LOT>.md` (le dossier de ton lot), une entrée par tâche :

    ### ACALnnn — OK | CORRIGER | SANS OBJET | DOUBLON | À SCINDER
    (OK : une ligne — ce que tu as ouvert pour le confirmer, `fichier:ligne`.)
    (Sinon : ce qui est faux en 1 à 3 lignes ; la preuve `fichier:ligne` lue dans l5-verif ; la correction EXACTE
    proposée — le texte de remplacement de la clause fautive quand il est court, ou « supprimer », « fusionner dans ACALxxx ».)

Puis ton message final (25 lignes au plus) : nombre de tâches par verdict ; la liste des tâches non OK, une proposition
chacune ; les tâches non vérifiées ; le chemin du rapport.

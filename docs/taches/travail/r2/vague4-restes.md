# r2 — vague 4 : ce qui est plié, ce qui reste (pour le rapport final)

Plis (worktree `taches-r2-ci`) : V4-B `61d21089b`, V4-C `67fbeb42c`, V4-A `39f28dbc0`, couture finale `aafac7084` ;
tête d'intégration `ac233800e`. Plan : TCH198 à TCH200. Suite front du module sur l'assemblage (avant la couture) :
1 254 verts. Gardes de la racine : toutes vertes sur l'hôte.

## Laissé volontairement (à dire à Reda)
- Carte « Retour » (après trois jours d'absence) : la première tâche tombe à y = 369 sur iPhone (les libellés de ses
  boutons, servis, ne tiennent pas sur une ligne) ; toutes les autres cartes : 231 à 260.
- Éditeur de durée d'un bloc qu'on vient de poser : affiche « 30 min » cochés pour une tâche sans durée (durée de
  dessin du bloc ; décision d'affichage à prendre) ; le volet « À placer », lui, n'invente plus de durée.
- Au bureau, la page d'un projet n'a plus la ligne « Ajouter une tâche » du haut (pour que le Tableau commence plus
  haut) : restent la touche `n` et « + Ajouter » par étape ou colonne.
- Horizontalement, le titre d'un projet se décale entre la Liste (colonne des projets visible) et le Tableau /
  la Chronologie (colonne masquée) : choix C-4 conservé ; hauteurs identiques.
- Chronologie en points (pas en barres) ; quatre marques d'importance (étoile, drapeau, `!!`, priorité de projet) ; le
  sablier qui veut dire durée ET attente ; « Plus tard » à côté de « Sans jour » ; mots de Mon rythme (« Sans données »,
  « Hors objectif ») ; aucun chemin évident pour « je suis en congé demain » ; vide à droite d'une liste à 1920 ;
  tablette 768-1279 px : en-têtes de jours de la Semaine non collants (défilement horizontal dans un cadre).
- Cibles de moins de 44 px : blocs d'agenda de 30 min (34 px) et puces « Toute la journée » de la Semaine.
- Hors ligne après un rechargement complet de la page : page blanche si le code de l'écran n'est pas en cache (le
  service worker n'est pas actif dans la pile de revue : à voir en production).
- Échantillons `aujourdhui` et `journee_ecrite` qui ne valident pas contre leur schéma publié (`obligations` : `nb` /
  `en_retard` requis mais absents d'un élément) : constat de la couture, non traité ; la CI (api-fuzz) le dira si le
  serveur sert ce cas.
- `planification/` n'accepte pas de jour par action (le samedi d'une « première action » est posé par un second appel).
- Hors module, signalés et non touchés : recherche de l'ERP blanche en sombre, fil d'Ariane de l'ERP tronqué, anneau de
  focus du Copilote, panneau de notifications de l'ERP blanc en sombre HORS de Tâches, fenêtre « Bienvenue », l'onglet
  « Apps », l'assistant (`features/ia`) muet quand son service ne répond pas.
- Jamais vu sur un vrai iPhone ni Safari : glisser une feuille (élasticité, clavier ouvert), ordre des événements d'un
  appui long, keepalive quand iOS tue l'app, `field-sizing`, `container-type`, notifications, Siri, tuile, calendrier
  abonné.
- Résidu sur le disque : `C:\b97` (copie temporaire de 62 Mo faite par une lane ; la suppression m'est refusée par une
  garde de sécurité : à supprimer à la main).

## À rejouer sur l'écran après le pli (serveur servi) — vérification ciblée finale
1. La charge du jour dit la même chose sur Aujourd'hui (détail), Agenda Semaine / Mois, Planifier ma semaine et le
   Copilote (« Où j'en suis ? », « Aide-moi à prioriser »).
2. Heure du bilan avancée avant l'heure courante : la carte est « Faire le bilan », jamais « Alléger » ; clore le bilan
   fait disparaître « Alléger » ; compte à objectif par défaut : pas d'« Alléger » ; « Pas maintenant » tient après
   rechargement.
3. Hors ligne : trois phrases enchaînées par Entrée → trois titres entiers au retour du réseau, sans doublon.
4. Appui long : la feuille reste ouverte, rien n'est modifié ; une feuille se tire vers le bas (80 pt : revient ;
   300 pt : ferme).
5. Coller « Pompage Ouled Saleh : … » à côté d'un projet « Pompage Douar Ouled Saleh » → « Ressemble à » sans réécrire
   la réponse.
6. Premier passage sur Projets / Agenda / À trier : pas de page blanche ; Semaine : en-têtes de jours collants.
7. « Derniers gestes » nomme le projet ou l'étiquette ; une date passée s'écrit « mer. 18 nov. ».

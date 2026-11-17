# Recherche L3 n°7 — Simplicité et facilité d'usage

Étiquettes : **[lu]** page lue dans cette session ; **[mémoire]** non relu, à vérifier ; **[témoignage]** opinion, pas étude.

## 1. Complet mais simple
- **Divulgation progressive** [lu, NN/g] : reporter les fonctions rares à un écran secondaire. Échoue si le premier niveau est surchargé, si des fonctions courantes sont cachées, ou si l'accès au niveau suivant est obscur. NN/g : deux niveaux au plus, un seul chemin vers le secondaire, partage décidé sur la fréquence d'usage.
  → **Règle** : ESSENTIEL = usage quotidien ; AVANCÉ = derrière UN « Plus » par écran ; jamais de troisième niveau.
- **Hick** [lu, lawsofux] : le temps de décision croît avec le nombre de choix ; mettre l'option recommandée en avant.
  → Une ligne de tâche ne montre que titre, case, jour/échéance, projet.
- **Fitts** [lu, lawsofux] : temps = f(distance, taille). → La case à cocher et le bouton d'ajout sont les plus grandes cibles.
- **Tesler** [lu, lawsofux] : la complexité se déplace, elle ne disparaît pas. → Le moteur (classement, analyse de la saisie) l'absorbe ; l'utilisateur ne fait aucun calcul que le serveur peut faire.
- **Paradoxe de l'utilisateur actif** (Carroll & Rosson, 1987, *Interfacing Thought* [lu via recherche]) : on se met au travail sans lire la documentation. NN/g `mobile-tutorials` [lu] : 4 apps iOS, tutoriel lu 91 % de réussite contre 94 % sauté (non significatif) ; tâches jugées plus dures (4,92 contre 5,49 sur 7, significatif).
  → La première utilisation marche sans rien lire ni régler.

## 2. Pourquoi on abandonne
**Aucune étude sérieuse trouvée** sur les gestionnaires de tâches. Indices : Localytics [lu via résumé, apps en général] : 25 % d'abandon en une session (2015), 21 % (2018), 19 % (2019). [témoignage] Inc. : les listes échouent quand on cesse de les entretenir. [témoignage] Analyse d'avis d'un éditeur : lenteur, synchro, prix, puis complexité. Hypothèses non prouvées : coût d'entretien, saisie longue, retards qui culpabilisent, réglages au départ.
→ **Règle** : zéro entretien obligatoire ; un retard se tranche (faire / replanifier / abandonner), il n'accuse pas ; aucun écran de départ à plus d'un champ.

## 3. Nombre de gestes (hors texte)
- **Things** [lu, aide 2803582] : on glisse le bouton Magic Plus à l'endroit voulu, le to-do s'insère là ; balayage à droite = « When » ; appui long + glisser = déplacer. Aucun simple tap décrit.
- **Todoist** [lu] : `Send the report tomorrow #Work` en une saisie, touche Q sur bureau.
- **Apple Rappels** [lu via guide iOS 13] : barre rapide au-dessus du clavier, horloge = Aujourd'hui / Demain / Ce week-end / Personnalisé.

| Geste | Cible (nos choix) |
|---|---|
| a. Ajouter pour demain dans un projet | 2 taps + texte (projet prérempli, « demain » compris) |
| b. Cocher | 1 tap |
| c. Reporter à demain | 1 balayage ou 2 taps |
| d. Déplacer dans un projet | ≤ 3 taps (appui long → Déplacer → projet) |
| e. Voir sa journée | 0 tap |

Bureau : a 2 touches (N + texte + Entrée), b 1, c 1, d 2, e 0.

## 4. Une main sur iPhone
- **Hoober 2013** [lu, UXmatters] : 1 333 observations ; **49 % une main**, 36 % bercé, 15 % deux mains. Smashing 2020 [lu] : actions de création dans la zone du pouce, tâche finissable à une main.
- **HIG et Material** : pages Apple non lisibles (rendu JS), Material réduit à un plan. Tout le reste est **[mémoire]** : cible 44 × 44 pt ; feuille du bas avec crans, poignée, glissement, jamais de saisie perdue ; balayage complet = action non destructive ; suppression jamais sur un seul geste sans filet ; appui long = menu contextuel.
- **Haptique** : `navigator.vibrate` absent de Safari iOS (MDN : « disponibilité limitée » [lu] ; Safari nommé = mémoire). Contournement par case `switch` (iOS 17.4 ou 18 selon les sources). → Bonus, jamais porteur d'information.
→ **Règle** : actions primaires dans le tiers bas, formulaires en feuille du bas, alternative visible à chaque balayage.

## 5. Clavier sur bureau
Linear [lu via résultats] : Cmd/Ctrl+K = palette (toute action), `?` = aide des raccourcis, `/` = recherche. Superhuman [lu via résultats] : Cmd/Ctrl+K, « E » = fait, la touche s'affiche à côté de chaque commande, règle des 100 ms. Todoist : Q = ajout rapide.
→ **Règle** : tout au clavier ; touches uniques (j/k, x, Entrée) ; Ctrl/Cmd+K ; `?` ; touche affichée dans chaque menu.

## 6. Annuler plutôt que confirmer
NN/g [lu] : l'annulation protège mieux ; les confirmations s'usent (« Oui » automatique), à réserver aux conséquences graves, boutons nommés d'après l'action. WCAG 2.2.1 (A) [lu] : un délai se désactive, s'ajuste (≥ 10×) ou se prolonge (avertissement ≥ 20 s). Angular Material [lu via résultats] : pas de durée sur un toast à action (lecteurs d'écran). Plage 4–10 s : source tierce seulement.
→ **Règle** : suppression douce + toast « Annuler » ; il reste tant qu'il est survolé ou focalisé ; durée 8 s (choix non sourcé).

## 7. États vides, première utilisation
NN/g `empty-state-interface-design` [lu] : dire l'état du système (pas « Aucun résultat » avant chargement), enseigner en contexte, offrir un chemin direct (bouton, données de démonstration). NN/g : tutoriel seulement si nécessaire, aide contextuelle plutôt que cartes statiques.
→ **Règle** : état vide = une phrase + un bouton ; aucune visite bloquante ; exemples proposés (D-TCH-4) ; astuce affichée une fois, au bon geste.

## 8. Vocabulaire
NN/g [lu] : heuristiques 2 et 4 ; erreurs : près du champ, simples, précises, remède proposé, saisie gardée, pas la couleur seule.
→ **Règle** : un geste = un mot (« Reporter » partout) ; « Demain », « lun. 23 » ; durées « 25 min ».

## 9. Performance perçue
Nielsen [lu] : **0,1 s** instantané ; **1 s** le fil de pensée tient (au-delà, montrer le travail) ; **10 s** limite d'attention (barre de progression). NN/g `skeleton-screens` [lu] : < 1 s rien ; 2-10 s spinner par module ; squelette pour une page entière < 10 s.
→ **Règle** : optimiste (case cochée < 0,1 s, retour arrière si échec) ; une liste ne se vide jamais pendant un rafraîchissement.

## 10. Accessibilité WCAG 2.2
[lu] : 1.4.3 Contraste AA, 4,5:1 ; 2.1.1 Clavier A ; 2.5.7 Glissements AA (alternative à pointeur unique) ; 2.5.8 Cible AA, 24 × 24 px CSS ; 2.2.1 Délais A. [mémoire] : 1.4.11 contraste non textuel AA ; 2.4.7 focus visible AA ; 2.4.11 focus non masqué AA ; 4.1.3 messages d'état AA ; 3.3.1 et 3.3.3 erreurs A/AA ; 2.5.5 cible 44 px AAA ; 2.3.3 animation AAA (`prefers-reduced-motion`).

## 11. Mesurer
**KLM** [lu, Wikipédia ; Card, Moran, Newell 1980, CACM 23(7)] : K 0,20 s, P 1,1 s, H 0,4 s, M 1,35 s, B 0,1 s. Estimation (bureau) de « Appeler Karim demain #Chantier » : M 1,35 + N 0,2 + 30 × 0,2 + Entrée 0,2 ≈ **7,75 s**. Heuristiques et parcours cognitif : voir la grille.

## LES 20 RÈGLES DE SIMPLICITÉ
1. Un écran = une action principale (un seul bouton plein).
2. Deux niveaux au plus : écran, puis un seul « Plus ».
3. Aucune fonction utile supprimée : classée AVANCÉ, trouvable en ≤ 2 gestes.
4. Première ouverture : saisie possible sans réglage.
5. Une tâche sans champ est valide (Boîte de réception) ; tout champ vide a un défaut.
6. Le contexte s'hérite (dans un projet : projet prérempli ; dans « Demain » : jour prérempli).
7. Ajout : ≤ 2 taps hors texte ; « demain » et « #projet » compris dans le texte.
8. Cocher : 1 tap, case ≥ 44 pt.
9. Reporter à demain : 1 geste, mot unique « Reporter ».
10. Déplacer : ≤ 3 taps.
11. L'icône ouvre « Ma journée » (0 tap).
12. Ligne de tâche : 4 informations au plus.
13. Commandes principales dans le tiers bas ; formulaires en feuille du bas (poignée, glissement + bouton explicite, saisie jamais perdue).
14. Chaque balayage ou glisser-déposer a un équivalent visible (menu ⋯, boutons monter/descendre).
15. Balayage complet = action non destructive ; toute suppression offre « Annuler » 8 s, en pause au survol/focus.
16. Confirmation seulement pour l'irréversible, boutons nommés d'après l'action.
17. État vide : une phrase + un bouton ; zéro visite guidée ; astuce une seule fois.
18. Un geste = un mot ; dates relatives ; une erreur dit quoi faire, près du champ, saisie gardée.
19. Retour < 0,1 s (optimiste) ; squelette > 1 s ; une liste ne se vide jamais pendant un rafraîchissement.
20. Clavier complet (Ctrl/Cmd+K, `?`, touche affichée dans les menus) ; WCAG AA : contraste 4,5:1, focus visible, cible ≥ 24 px, mouvement réduit.

## LA GRILLE D'ÉVALUATION
**A. Heuristiques de Nielsen** [lu] (0 viole / 1 partiel / 2 respecté, par écran) : 1 Visibilité de l'état du système · 2 Correspondance avec le monde réel · 3 Contrôle et liberté de l'utilisateur · 4 Cohérence et standards · 5 Prévention des erreurs · 6 Reconnaître plutôt que se rappeler · 7 Flexibilité et efficacité d'utilisation · 8 Design esthétique et minimaliste · 9 Aider à reconnaître, diagnostiquer et corriger les erreurs · 10 Aide et documentation.
**B. Parcours cognitif** [lu, NN/g] par étape des parcours a-e, un « Non » = échec : 1 Tentera-t-il le bon résultat ? 2 Verra-t-il l'action ? 3 Reliera-t-il l'action à son but ? 4 Verra-t-il un progrès ensuite ?
**C. Cibles de gestes** (hors texte) : a ≤ 2 · b 1 · c 1 (ou 2 taps) · d ≤ 3 · e 0 ; bureau a 2 · b 1 · c 1 · d 2 · e 0. Dépassement = défaut. KLM de (a) ≤ 8 s.
**D. Binaires** : les 20 règles (oui/non) ; WCAG 1.4.3, 2.1.1, 2.4.7, 2.5.7, 2.5.8.

## NON VÉRIFIÉ
- Pages HIG (44 pt, feuilles, balayages, haptique) non lues : mémoire. Material : plan seul ; durée 4–10 s non confirmée.
- Aucune étude chiffrée sur l'abandon des gestionnaires de tâches ; Localytics est générique.
- Nombre de taps des apps : Things sans tap décrit ; Rappels = guide iOS 13 ; Todoist = bureau.
- Haptique iOS : absence de `navigator.vibrate` dans Safari et version du contournement `switch` incertaines.
- Niveaux WCAG [mémoire] listés au §10 ; page Quickref tronquée.
- Touches uniques de Linear ; carte thermique du pouce de Hoober (contestée par lui, non retrouvée).
- Cibles de gestes, 8 s du toast, estimation KLM : nos choix de conception.

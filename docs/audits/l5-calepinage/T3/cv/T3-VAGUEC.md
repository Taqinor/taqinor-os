# Contre-vérification de la vague C (1re partie) — T3-VAGUEC

Corrections livrées l'après-midi du 23/11 (PR #1530), jamais vues à l'écran réel. La pile sert le code `d972960ed5`
(reconstruite vers 13 h 50 UTC). Texte complet de chaque tâche : `grep -n "<ID> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md`
dans `C:/dev/taqinor-os/.claude/worktrees/calpinage-module-l5-aadbde`. Les gestes d'origine (ceux qui montraient le
défaut) sont dans les constats du tour 3 cités : rejoue-les tels quels, puis lis le résultat.

Dans cet ordre (les plus graves d'abord) :

1. **ACAL1900** (S1, constat T3-POSE-004, `registre/constats/T3-POSE.jsonl`) — toit plat 12 × 8 m, module 710 W, cible 5 :
   Expert > Déplacer les panneaux > Remplir automatiquement ⇒ 16 panneaux ; Enregistrer ; RECHARGER la page : la carte,
   l'en-tête et « Pose actuelle » disent 16 ; Enregistrer sans geste ; relire le serveur (`GET` du calepinage) : 16.
   L'écart à la cible est DIT (où ?). Jumeau : une pose « Le plus de panneaux » se rouvre à son nombre.
2. **ACAL1909** (ACAL1610 non faite) — « Mes factures » : saisir trois mois, enregistrer, recharger : les trois mois sont
   relus dans la grille ; en ajouter un quatrième, enregistrer : le document porte quatre mois.
3. **ACAL1901** (T3-POSE-001) — coin de toit glissé (70 → 91 m²), clic sur le bouton Annuler : 70 m² ; Rétablir : 91 m².
4. **ACAL1902** (T3-POSE-007) — retraits à 0,8 m sur un pan de 3 × 1,5 m : 0 panneau ; 2 m sur 10 × 7 : moins de panneaux,
   dans la pose ET dans « Comparer les poses ».
5. **ACAL1903** (T3-POSE-002) — « Production visée » 40 000 : « au plus N panneaux » = le nombre que « + » atteint.
6. **ACAL1904** (T3-T3-ECRANS-001) — calepinage sans toit, 1440 × 900 : la pile de zoom et la boussole sont visibles et
   cliquables ; quatre clics de tracé sur la carte (y < 332 compris) posent quatre points.
7. **ACAL1912** (reste d'ACAL1602) — pose dont des panneaux ne sont raccordés à aucun onduleur : l'avertissement
   « N panneaux ne sont raccordés à aucun onduleur : ils ne sont pas comptés » est servi et affiché à Résultats.
8. **ACAL1910** (T3-PROD-013) — module posé différent du module par défaut : les étapes « niveau d'éclairement » et
   « qualité module » de la cascade nomment le module POSÉ.
9. **ACAL1911** (T3-PROD-003) — batterie avec fenêtres de charge / décharge + stratégie « autoconso » : le bloc batterie
   est simulé, avec un avertissement qui dit que les fenêtres sont ignorées.
10. **ACAL1913** (T3-PROD-004) — « Affiner ma consommation » d'un lead à facture : « kWh conso / jour » n'est pas 0,0.
11. **ACAL1976** (T3-B3-001) — provoquer un toast (par exemple un enregistrement refusé) à 1440 × 900 : il ne recouvre
    pas le bouton d'action doré du panneau d'étape, en clair et en sombre.
12. **ACAL1907** (T3-T3-ECRANS-003, -004, -008) — avec un bandeau d'alerte (GPS / C&I) la pile de zoom reste entière ;
    Expert > Résultats : rien de la carte ne dépasse autour du panneau plein ; « Localiser » fait 44 px de haut.
13. **ACAL1985 / ACAL1986 / ACAL1977** (T3-B3-008, -009, -002) — Documents en Guidé : « Générer le devis » est le bouton
    doré v2 (52 px, rayon 14) et en Expert il n'est PAS doré ; la barre « Étape n sur 5 » n'a qu'un trait doré, celui de
    l'étape courante ; en thème sombre la carte sans photo est sombre.
14. **ACAL1906** (ACAL1818) — WebKit 390 × 844 : la zone tactile du curseur « Heure du soleil » fait au moins 44 px.
15. **ACAL1908** (ACAL1344) — Démarrage rapide à 1440 × 900 : défilement maximal 0 px.
16. **ACAL1905** — moitié « Enregistrer » seulement : si un enregistrement dépasse son délai, l'écran dit « Enregistré »
    quand le serveur l'a écrit. Difficile à provoquer : « non essayé » accepté, dis-le.

Garde-fou de non-régression (à jouer en dernier, court) : un parcours Guidé complet Toit → Panneaux → Électrique →
Résultats → Documents sur un calepinage neuf, sans écran mort ; une pose de 60 panneaux se rouvre à 60.

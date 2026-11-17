# Vérification contradictoire, troisième tour — `spec-7-ecrans.md` (révision 3)

Lu : consignes, brief §1, socle §0 et §2, arbitrages A11-A16, R7, `verif-spec-7.md`, `verif-spec-7-tour2.md`, spec-7 r3 ;
recoupé dans spec-5a, 5b, 6a, 6b, `reference/api.md`, et le code (`Header.jsx`, `shortcuts.js`). « l.N » = ligne de
spec-7 r3. Hauteurs iPhone et comportement iOS : non mesurés. Q1-Q4 = parcours cognitif ; seuls les « non » sont notés.

## 1. Suivi

| Constat | État | Preuve · reste |
|---|---|---|
| N1 préfixes `g`/`c` | corrigé | l.162 |
| N2 clavier découvrable | corrigé | l.27, 174-176 |
| N3 semaine | corrigé dans la spec | l.55, 128, 134, 209 ; `agenda/` de la référence n'a pas « Mes projets » (api.md:385) |
| N4 visites sans heure | corrigé dans la spec | l.72, 115 ; la référence garde `"heure":"10:30"` (api.md:178, 386) |
| N5 pastille | corrigé dans la spec | l.32 ; la référence compte encore Proposé (api.md:195-196) |
| N6, N7, N8, N10, N11, N12 | corrigés | l.118 ; l.53, 138, 144 ; l.109, 145 ; §6 ; l.111, 234 ; l.146 |
| N9 retour accusateur | corrigé dans la spec | l.91-92, 114, 214 ; aucune donnée `semaine_courte`/`reprise` dans la référence |
| M2 « N sur objectif » | **partiel** | l.95, 132 ✓ ; mais « 1 sur 6 à 15 h » (l.111, 208) ; texte serveur « 4 faites (objectif 5) · … plan tenu 3 sur 5 » (api.md:374) |
| M3 priorité projet | **partiel** | l.51, 88, 131 ✓ ; projets nés d'un collage : jamais demandés |
| M5 Mon iPhone | corrigé | l.146-147, 222 |
| M7 alléger | corrigé | l.45, 118, 133 (lignes ERP et Essentiel dans Alléger : non dit) |
| M8 agenda | corrigé | l.142 (bloc → Déplacer), l.240 |
| Orphelines 1-5, 8-11 | placées | l.53, 49, 51, 25/53, 131, 56/111, 118, 28, 128 |
| « Encore 10 min · 1 h · Demain 9 h » | **partiel** | lexique l.100 et §9 seulement ; absent de la ligne Fiche (l.126) et du §2 |
| Lier une tâche à une activité ERP | **partiel** | placée (l.47, 158) ; aucune route : `activite_origine` n'est posé que par `convertir-activite/` (api.md:241), et une activité n'est pas une cible liable (A3) |

## 2. Un mardi chargé, sur iPhone

| Heure · pas | Il voit / touche | Gestes | Q non · réflexion |
|---|---|---|---|
| 8 h 30 notification | texte « 3 prévues · objectif 5 » (l.277) ; touche | 1 | — |
| Garder la proposition | progression, carte du moment, Toute la journée (visite), Prévu (3 reports + 2 activités + « Suivi des relances »), puis Proposé **sous la ligne de flottaison** ; il défile, « Garder ces 5 » (contour), ★ ★ | 4 | Q2 non (rien en haut ne dit « garde ta proposition ») · 2 réflexions (Prévu ou Proposé ? quel essentiel ?) |
| Siri, en voiture | « Dis Siri, nouvelle tâche… demain 10 h » → « Ajouté pour demain 10 h » | 0 | `#Polydesign` à la voix : produire « # » en dictée, de mémoire, non vérifié → la tâche va dans À trier |
| Fiche d'un lead | ✓+ → liste → « Nouvelle tâche liée » → dictée → Ajouter (spec-6a:92 ; 6a:9 dit 2) | 3 | Q2 non : la place de ✓+ sur iPhone n'est écrite nulle part ; l'en-tête a déjà 9 cibles (`Header.jsx:236-239`) · 1 réflexion |
| Tapée, 12 h 30 | icône → + → « Envoyer offre jeudi #Polydesign » → Retour | 3 | — |
| 11 h, l'appel | + « Devis Settat urgent » (aujourd'hui par contexte) → Retour, ★ dessus, ★ retirée d'une autre, balayage Reporter sur une 3e | 6 | 1 réflexion : Reporter (report compté) ou Alléger (sans report) ? Il reportera ; le report compte |
| 14 h rappel | « Rappel · Une tâche à faire » (6b §3 ; titres coupés par défaut, socle §2.8) → fiche → « Encore 1 h » | 2 | Q1 non tant qu'il n'a pas ouvert : il ne sait pas quoi · 1 réflexion |
| 15 h message | → Aujourd'hui (A15) → carte « 1 sur 6 à 15 h · Alléger » → coche 2 → Garder ces 2 | 5 | 1 réflexion : « 1 sur 6 » alors que la ligne du haut dit « 1 sur 5 » |
| Cocher depuis la tuile | **impossible** : la tuile Scriptable n'a que `ListWidget.url` (6b §6) ; la toucher ouvre un lien, peut-être Safari et sa page de connexion (non vérifié) ; spec-7 n'en dit rien | 1 + 2 cases | 1 réflexion |
| Cochages de la journée | 4 cases, 2 ouvertures | 6 | — |
| 18 h bilan | notification → Aujourd'hui → « Faire le bilan » → Tout reporter → Valider | 4 | une reportée 3 fois est exclue de « Tout reporter » (api.md:376-377) : Valider refusé, spec-7 muette |
| « Qu'est-ce que tu as compris de moi ? » | icône → Copilote → phrase tapée (pas parmi les 4 demandes) → envoi ; réponse = `profil.lire` avec n et période, « d'accord ? » (5b:224-227) | 3 | sans clé : une phrase ; repli Mon rythme → constats (replié) |

**Total : ≈ 40 gestes hors texte et voix. Il réfléchit 9 fois, dont 3 décisions légitimes (essentiel, quoi alléger,
répondre au Copilote) et 6 causées par la conception.**

## 3. La première semaine

- **Jour 1.** Cockpit → Tâches → « Colle ou dicte tes listes » → 4 notes = 30 gestes dont 24 d'iOS (l.207). 40 tâches,
  6 projets **tous à la même priorité** (rien ne la demande). Carte Mon iPhone (5 réglages). Proposé se remplit aussitôt
  (A11), alors que §8 dit « le lendemain ».
- **Jour 2.** Rien gardé → notification « 0 prévues · objectif 5 », vide. Proposé classé sans signal (projets égaux,
  aucune échéance). La carte « Mon iPhone » passe avant « astuce » (l.111) : sans tuile posée, **aucune révélation**
  (`#`, balayage, Copilote, Planifier, Revue) n'apparaît.
- **Jour 5 (vendredi).** La revue remplace le bilan (l.91) : 6 projets + Planifier ma semaine ≈ 40 gestes ; les restes
  du jour ne sont tranchés nulle part. La révélation « Revue » vient le jour 6, après.
- **Jour 10.** « Ton objectif passe de 5 à 3 » (5a §3.10) : annoncé, deux crans, contre A2.2. Avant, Mon rythme dit
  « 3 jours sur 10 » sans dire à quoi il sert : il ne le comprend pas.
- Trop d'aide le jour 1, trop peu sur les priorités, découverte bloquée.

## 4. Contradictions internes, tableau par tableau

| Où | Contradiction | Correction |
|---|---|---|
| l.111, 208 vs l.95, 114 | « 1 sur 6 » vs « 1 sur 5 » (objectif) | « 1 sur 5 à 15 h » |
| l.256 vs l.40, 119, 183, 200 | ★ « replié davantage » vs ★ touché sur la ligne | « ★ sur Essentiel et Prévu, jamais sur Proposé » |
| l.32 vs l.56, 201 | « notifications → Aujourd'hui » vs bilan en 3 gestes (ouverture directe) | « sauf le bilan (`?ouvrir=bilan`) » ; ou parcours 8 = 4 |
| l.60 vs l.135 | Mes jours 3/4 alors qu'il est replié dans Mon rythme | 4/5 |
| l.211 | « ≈ 19 touches » ; décompte minimal ≈ 27 (`g j` 2 ; `n` + 3 Entrée + Échap 5 ; 2 × `j` Espace 4 ; 2 × `j d` Entrée 6 ; 2 × `j m` Entrée 6 ; palette 3-4) | 27 |
| l.137 vs l.78 | « 5 étapes » de Mon iPhone ; Étape = section | « 5 réglages » |
| l.110-111 vs api.md:195 | carte du moment : la carte « pause » (5a §3.9) manque | l'ajouter après rythme |
| l.223 vs A11 | « le lendemain Proposé est rempli » | « Proposé est rempli aussitôt ; la notification sonne le lendemain » |
| §4 | états vides absents : En réserve, À placer, Trier une par une (fin), Archive, Modèles ; une section vide s'affiche-t-elle ? non dit | une phrase par écran ; section vide masquée sauf l'invite ★ |
| l.117 | « Garder ces N » : N = objectif ou objectif − gardées ? (parcours 13 : 5 ; 21 : 3) | « N = objectif − gardées ouvertes » |

Aucune touche attribuée deux fois (`t` seul dans l'Agenda, `c t` protégé par N1). Lexique : aucun mot interdit dans
spec-7 hors « 5 étapes » ; les restes sont dans les textes serveur de la référence (« plan tenu », « demain ») et les
cartes 5b (« Tout au prochain jour ouvré », « Ma journée », « à décider »).

## 5. Ce qui est trop

Jour 1, Aujourd'hui : titre (3 contrôles), progression, carte, Toute la journée, Prévu, Proposé (5 lignes + explication
+ Garder + surcharge + Voir tout), 4 repliés, + : **jusqu'à 9 blocs, ≈ 25 cibles** hors en-tête ERP. ⋯ : **8 entrées**.
Onglets : **5** (4 + Apps). Saisie : **3 puces** + champ. Tenable en repliant : (1) section vide non affichée ;
(2) « Toute la journée » = 1re ligne de Prévu, pas un bloc ; (3) surcharge seulement si vraie et calculable ; (4) ⋯
contextuel (Alléger si Prévu non vide ; « En faire mon accueil » disparaît une fois fait). Rien à retirer. Le modèle
mental en cinq phrases tient : Alléger, Reprise, Semaine courte sont des gestes ou des états, pas des concepts.

## 6. Note (établie sur mes constats, avant de la comparer aux 13/20 précédents)

| # | Note | Constat |
|---|---|---|
| 1 État | 1 | pastille et progression justes ; mais rappel sans titre, « 1 sur 6 », tuile muette sur ce qu'elle permet |
| 2 Monde réel | 2 | lexique fermé tenu dans spec-7 |
| 3 Contrôle | 2 | Annuler, conflit sans perte, projet restauré en une ligne, Alléger tenu |
| 4 Cohérence | 1 | Reporter et Alléger pour « pas aujourd'hui » aux effets différents ; ★ ; « 1 sur 6 » |
| 5 Prévention | 2 | capture rangée comme comprise, doublons, rien ne disparaît sur une touche |
| 6 Reconnaître | 1 | `#` à retenir ; Mon rythme derrière une ligne ; révélations bloquées par la carte Mon iPhone |
| 7 Efficacité | 2 | clavier, Siri, semaine en 2 gestes par tâche |
| 8 Minimalisme | 1 | 9 blocs possibles, 8 entrées au ⋯, sections vides non réglées |
| 9 Erreurs | 2 | erreur au champ, hors ligne dit ; seul le refus muet du bilan détonne |
| 10 Aide | 1 | pas de `?` iPhone ; Mon rythme sans but écrit avant 10 jours |
| | **15/20** | |

## 7. Constats

**BLOQUANT** : aucun.

**MAJEUR — nouveaux**
- **T1 Référence en retard.** `reference/api.md` date d'avant A15-A16 (git : 98b2f4bc2 avant d0fbec592 et
  68b20a18a ; primauté s'arrêtant à A14, api.md:3-4) et contredit la r3 : pastille avec Proposé (:195-196), message de
  15 h → `?ouvrir=alleger` (:490, contre A15), visites à l'heure (:178, 386), À placer sans projets (:385), rien pour
  Semaine courte / Reprise, ★ sur Proposé (:116), textes « plan tenu », « demain » (:374, 378). → Une passe
  d'intégration A15-A16 + r3 sur la référence avant construction ; A15-A16 dans sa ligne de primauté.
- **T2 Le Copilote rouvre B1.** « Planifie ma journée » rend `plan_propose`, adopté en mode `complet` : un choix
  obligatoire par ligne d'À revoir, bouton inactif sinon (5b:41, api.md:212, 364-366). Au retour de 10 jours :
  18 choix. Parcours 12 (3 gestes) faux dès qu'un retard existe. → La carte adopte en `express` ; À revoir reste
  replié avec « Tout en réserve ».
- **T3 Découverte bloquée.** Une seule carte du moment, « Mon iPhone » avant « astuce » (l.111) : sans tuile posée,
  aucune révélation n'apparaît jamais. → Mon iPhone 3 jours au plus (ou « Plus tard »), puis Réglages seulement.
- **T4 Rappel muet.** Un rappel qu'il a posé dit « Une tâche à faire » (6b §3) ; le réglage des titres est à 3-4
  gestes (l.62), jamais proposé. → À la pose du 1er rappel et à l'étape 1 de Mon iPhone : « Montrer le titre sur
  l'écran verrouillé ? Oui · Non » (réglage explicite, conforme au socle §2.8).

**MAJEUR — déjà signalés, partiellement corrigés**
- **M1** « Garder ces N » sous la ligne de flottaison les jours chargés (l.114-118 ; le critère 5 ne garantit que la
  1re tâche). → Le matin, tant que rien n'est gardé : la carte du moment est « 5 proposées pour ton objectif · Garder
  ces 5 » (même route `express`).
- **M3** Projets nés d'un collage jamais priorisés. → Puce Haute/Moyenne/Basse sur chaque ligne « Nouveau projet : … »
  de l'aperçu (défaut Moyenne).

**MINEUR** : les 10 lignes du §4 ; ✓+ à placer sur iPhone (en-tête plein) avec son compte réel ; « Lier une tâche »
par le `lien` vers la cible de l'activité (lead, client, devis), sans route nouvelle ; « Encore 10 min… » dans la ligne
Fiche ; tuile : écrire « lecture seule, toucher = ouvrir Aujourd'hui » ; Siri : accepter « projet <nom> » en tête ;
bilan : reportées 3 fois marquées « à trancher » au lieu d'un refus ; revue du vendredi ouverte par les restes du
jour ; phrase du matin sans tâche gardée (« 5 proposées · objectif 5 ») ; premier palier en carte [Oui, 3] [Garder 5]
(A2.2) ; Mon rythme avant 10 jours : une phrase de but ; révélations déclenchées par leur événement ; toast « Reportée ·
1 report » pour distinguer de Alléger.

## Choix par défaut

Un écart spec-7 / référence est compté contre la construction (la référence se dit « unique »). T1 vaut pour
`api.md` tel que lu dans cette session : d'autres fichiers de `reference/` changeaient pendant la lecture (git status).
Un geste iOS non vérifié (dictée de « # », tuile qui ouvre Safari) est signalé, pas compté comme échec.

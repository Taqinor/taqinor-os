# Critique finale avant construction — gestionnaire de tâches, agenda, Copilote

Regard neuf, lecture seule. Lu en entier : consignes, brief, socle, arbitrages, `donnees.md`, `api.md`, spec-7 r3.1,
consignes-construction, `verif-squelette`, `verif-securite-specs`. Lu en partie : `regles.md` (§3-§10), `textes.md`
(§3-§9), PLAN_TACHES (en-tête, les 152 titres, 19 tâches en entier). 8 captures regardées. Code vérifié par moi
(`sw.js`, `notifications/services.py`, `offlineOutbox.js`, `sql_agent_service.py`, `qa_export_anonymise.py`) et par
deux lanes (16 affirmations de code, 9 hypothèses iOS). **Non vérifié** : le `.env` de production, tout comportement
sur un iPhone réel ; **non lus** : spec-8, `regles.md` §1-§2, `textes.md` §1-§2, les quatre autres rapports de
vérification (parcourus par recherche).

Bilan : **1 BLOQUANT, 8 MAJEURS, 10 MINEURS**.

## 1. La demande, phrase par phrase

| Exigence | Ce qui est livré | Note |
|---|---|---|
| Son gestionnaire dans l'ERP | app `taches`, 12 pages, 4 onglets | comblé |
| Tâches dans des projets, plusieurs projets, priorités | Projets, puce Haute/Moyenne/Basse, étapes | comblé |
| Toutes leurs tâches dans mon to-do quotidien | « Proposé pour aujourd'hui » (A11) + « Voir tout » | **à moitié** (M1, M2) |
| Ajouter facilement, y compris « nouveau projet » | saisie `#projet` en 2 gestes, collage, « projet X » à Siri | comblé — la meilleure partie |
| Phase de planification | Planifier le projet (7 gestes), Planifier ma semaine, « Garder ces N » | comblé |
| All the fancy stuff | récurrence, rappels, sous-tâches, check-list, étiquettes, vues, modèles, tableau, hors ligne, annuler | comblé, et au-delà (§2) |
| L'agent IA m'aide à prioriser et planifier | 4 demandes, 16 actions | **pas vraiment** (M3) |
| Me suit partout | icône → Aujourd'hui, ✓+ sur les fiches, cockpit, push, hors ligne, Siri, flux, tuile | **à moitié** : rien d'iPhone n'est essayé (M7) |
| Comprend mon comportement | 8 constats, « Qu'as-tu compris de moi ? » | **à moitié** : seuils de 28 jours, 30 lignes par créneau (`regles.md:729-736`) → rien le premier mois |
| « Plus » → m'aider | objectif +1 aussitôt (A2.1), Proposé rempli jusqu'à l'objectif | comblé à l'écran ; au Copilote seulement sous Claude (M3) |
| « Ça suffit » → tenir | mode Garder ce rythme, zone, 28 jours de silence | comblé, sobre |
| Me pousse | objectif 5 figé 10 jours, +1 par bloc de 2 semaines, Message de 15 h | à moitié, prudent par choix (recherche) : acceptable |
| La meilleure agenda | 4 vues, blocs, À placer, visites ERP | **à moitié** : aveugle à ses vrais rendez-vous (M4) |
| Le grand écran sur mon iPhone | « En faire mon accueil » (mécanisme existant `auth/mobile-home-route/`, liste blanche à élargir : TCH132) | comblé ; la tuile est un bonus fragile (lecture seule, ouvre Safari et son écran de connexion, `textes.md:691`) |
| Facile ET beau | captures propres, hiérarchie nette | beau : oui ; simple : **à moitié** (§2) |
| Tâches bien écrites | une ligne, source, preuve, appelants | à moitié (B1, §6) |
| Le meilleur, en une fois | 3 fusions, module invisible jusqu'à la dernière tâche | risque : personne n'essaie rien avant la 152e (M5) |

## 2. Ce qui manque, ce qui est de trop

**Manque (tenu pour acquis par un utilisateur de Things, Todoist, Sunsama, Fantastical)**
- Ses rendez-vous dans l'agenda (M4) ; l'ordre d'un projet respecté et plusieurs projets représentés dans la liste
  du jour (M1) ; les tâches d'hier non faites qui restent sous les yeux (M2) ; un Copilote qui change une priorité,
  une échéance ou un projet (M3).
- Une photo ou un fichier sur une tâche (écarté par le socle §2.3, raison de sécurité valable : à dire).
- Un minuteur : sans lui `duree_reelle_minutes` (`donnees.md:154`) reste vide et le constat C6 (`regles.md:734`) ne
  se déclenche jamais (m6).

**De trop (non demandé, coûte du code et de la compréhension)**
- La machine anti-triche du rythme : micro-tâches plafonnées à 2, routines à 0, garde de taille, mémoire d'échec
  (`regles.md:636-637`, `:678-690`). Il est seul juge de lui-même ; « 3 sur 5 » après 6 cases cochées ne s'explique
  pas d'un regard (m5).
- 8 états visibles d'une tâche (Essentiel, Prévu, Ce soir, Proposé, À revoir, En attente, En réserve, À trier) et le
  mot inventé « gardées ». spec-7 §12 le reconnaît (« Prévu/Proposé à apprendre »).
- Modèles, dupliquer, burn-up, chronologie, vues enregistrées, suggestions venues de l'ERP, décaler : utiles, repliés,
  donc invisibles à l'activation — à construire APRÈS elle (§4). 100 routes, 20 modèles, 213 champs : chaque repli est
  un rouge possible.

## 3. Ce qui est faux ou fragile

### BLOQUANT

**B1 — Le plan supprime ses propres sources avant la construction.** TCH150 (`PLAN_TACHES.md:144`) retire
`docs/taches/travail/` dans la PR d'atterrissage ; les lanes partent d'`origin/main`. Or, compté par script sur les
152 tâches : 119 citent une source de ce dossier, 69 citent une spec, **29 n'ont aucune source dans les quatre fichiers
gardés** (TCH41 jetons visuels « spec-8 §1-§8 », TCH110 script de la tuile « spec-6b annexe A », TCH116 douze
conversations « spec-5b annexe », TCH133-134 « spec-7 §7 », TCH142 « spec-6a crit. 1-15 »). Les gestes de ligne
(« Balayage gauche »), les critères d'accessibilité (`axe-core`, 44 px) et le tableau « visible / replié / vide » des
écrans n'existent QUE dans spec-7 (recherche dans `reference/` : 0 résultat). `consignes-construction.md` est dans le
même dossier et n'est cité nulle part dans le plan (0 occurrence).
*Correction* (`PLAN_TACHES.md`, TCH150 et « Où est la vérité ») : garder sur `main` `socle.md`, `arbitrages.md`,
`spec-2` à `spec-8`, `consignes-construction.md` (les déplacer sous `docs/taches/reference/conception/`) ; ne retirer
que brouillons, recherches, vérifications et captures ; citer les consignes de construction dans l'en-tête.

### MAJEURS

**M1 — La liste du jour sera monopolisée par un projet et ignore son ordre.** `cle_tri` (`regles.md:354-362`) : bande,
échéance, priorité maximale, priorité de la tâche, puis `rang_jour` (nul tant qu'il n'a rien réordonné), puis `created_at`, puis
`id`. Après le collage de ses listes (D-TCH-4 : toutes « Moyenne », sans date, créées à la même seconde), Proposé =
les 5 plus petits `id`, donc les 5 premières lignes de la PREMIÈRE liste, jour après jour jusqu'à épuisement ; un
projet « Haute » de 30 tâches occupe seul la liste six jours. Et `rang_projet` est écarté de la clé (`regles.md:1009`) :
réordonner un projet ne change pas ce qui est proposé. Le correctif prévu (« projet négligé ») attend 14 jours.
*Correction* (`regles.md` §3.4 + jeu de test, TCH22-TCH23 — AVANT F1, ces modules purs sont construits en premier) :
dans le pool de Proposé, prendre par projet sa prochaine action (premier `rang_projet` actionnable), alterner les
projets (priorité, puis `rang`), puis les secondes actions.

**M2 — « À revoir », replié en bas, avale l'urgent et le retard.** Dans l'exemple de la référence
(`regles.md:372-396`), 6 des 13 tâches classées tombent dans À revoir, dont « Devis Settat, échéance jeudi, projet
prioritaire » et « Déclaration TVA, priorité haute » ; la section est repliée (`regles.md:459`, `spec-7:121`) pendant
que Proposé montre « Préparer formation », sans date. Une tâche prévue hier et non faite y glisse aussi ; la carte
« bilan d'hier » ne vit que jusqu'à 12 h.
*Correction* (`regles.md` §4.1-§4.2, spec-7 §4, maquette `ecran-aujourdhui-matin`) : motifs `echeance_proche`,
`echeance_passee` et `jour_passe` de la veille → en tête de Proposé, avec leur explication, comptés dans « Garder
ces N » ; À revoir replié ne garde que les reportées 3 fois et les retards anciens.

**M3 — « L'agent IA m'aide à prioriser » : la promesse la moins tenue.**
(a) « Planifie ma journée » et « Aide-moi à prioriser » appellent le même outil et rendent la même carte
(`textes.md:563-564`), qui est la section Proposé déjà à l'écran (capture `copilote-iphone-clair`).
(b) Aucune des 16 actions ne change la priorité, l'échéance ou le projet d'une tâche (`api.md` §8 ; `lot/` sait
`prioriser` mais n'est pas exposé).
(c) Sous Groq, 5 actions seulement (`api.md:596-597`) : ni `rythme.regler`, ni `profil.lire` — « je veux en faire
plus » dit au Copilote ne fait rien.
(d) Tout est dans le lot `copilote`, servi selon `ASSISTANT_COPILOTE` ; la mémoire partagée dit la bascule Claude de
production « geste de Reda », encore ouvert. Aucun de ces réglages n'est dans les gestes du plan
(`PLAN_TACHES.md:309-321`).
(e) Sans clé, les quatre boutons disparaissent (`textes.md:568`) alors que trois rendent une carte calculée par le
serveur.
*Correction* (`api.md` §8, `textes.md` §5, TCH111, TCH114, TCH117) : action `taches.tache.modifier` (priorité,
échéance, projet, en carte à valider) ; « Aide-moi à prioriser » rend une carte distincte (3 à 5 tâches de tous les
projets, la raison de chacune, « Mettre en essentiel », « Passer en haute ») ; les demandes rendent leur carte sans
modèle de langage ; `rythme.regler` dans le jeu Groq ; vérifier le `.env` de production.

**M4 — « La meilleure agenda » ne voit pas ses rendez-vous.** Seule source : l'agenda externe ICS, classé AVANCÉ,
dernière vague, « reste à faire s'il ne tient pas » (`arbitrages.md:118-121`), un seul par utilisateur
(`donnees.md:476`). Le temps disponible (240 min par défaut) ignore donc quatre heures de réunions. Les activités ERP
n'ont pas d'heure, alors que la maquette en montre une (m3). L'ancien `/calendrier` reste (`crm/module.config.jsx:91`,
`:128-129`) : deux calendriers dans l'ERP.
*Correction* (`arbitrages.md` A14-M8, `donnees.md` §2.20, TCH121-TCH122) : lecture ICS classée ESSENTIEL, construite avec
l'écran Agenda, 3 adresses au plus, durée des rendez-vous retranchée du temps disponible du jour, proposée à
l'étape 2 de « Mon iPhone ».

**M5 — Aucun essai réel avant la 152e tâche.** Voir §4.

**M6 — Le plan et les consignes de construction se contredisent sur l'hôte.** `PLAN_TACHES.md:102` : « Django n'est pas
installé sur l'hôte » ; `consignes-construction.md:24` et `:77` : Python 3.13 avec Django, `makemigrations --check`
exécuté. Une lane qui suit le plan écrira `0001` à la main (19 modèles, contraintes et index nommés). L'hôte est dit
en 5.1, le dépôt en `Django==5.2.19` (`requirements.txt:2`). Aucun test à base ne tourne avant la CI : F2 pousserait
47 tâches jamais exécutées.
*Correction* (`PLAN_TACHES.md` en-tête) : une seule vérité — migration générée sur l'hôte, la CI arbitre ; PR ouverte
en brouillon dès le premier pli de chaque fusion, poussée à chaque pli, rouges corrigés lane par lane.

**M7 — Les promesses iPhone reposent sur des hypothèses jamais essayées.**
- Pastille : `sw.js:104-143` n'appelle pas `setAppBadge`, `notify()` n'a pas de `badge`
  (`notifications/services.py:624`) ; TCH21 et TCH120 les ajoutent, mais la preuve de TCH120 ne teste que des liens.
  iOS interdit le push silencieux (WebKit : « always show a notification ») ; que `setAppBadge` marche dans le
  service worker d'iOS n'est pas établi.
- Push en production : `VITE_VAPID_PUBLIC_KEY`, variable de build, est rangée dans les gestes « après F3 ».
- Tuile : la preuve de TCH110 lit quatre noms de champ et compte les lignes ; personne n'exécute le script.
- Siri : « Installer » exige que Reda fabrique lui-même le raccourci (douze appuis, en-tête `Authorization`,
  `textes.md:656-664`).
*Correction* (`PLAN_TACHES.md`, GATED → prérequis de F3) : vérifier le push de production maintenant (lecture seule) ;
30 minutes sur l'iPhone de Reda (push, pastille, calendrier, raccourci, script) AVANT TCH95-TCH110 ; ce qui échoue
sort des textes.

**M8 — Activation pour tous les rôles internes le premier jour.** TCH130 (`PLAN_TACHES.md:293`) accorde le droit à tous
les rôles internes ; `taches.balayer` tourne chaque minute (`api.md:603`) sans autre coupe-circuit que d'éteindre le
module entier. Le fondateur a demandé SON outil. Un défaut d'idempotence = un push par minute à toute l'équipe ; et le
profil de rythme (400 jours) devient un traitement sur des salariés.
*Correction* (TCH130, `settings/base.py` par TCH99) : droit accordé au seul rôle Administrateur ; les autres par la
case de l'éditeur de rôles, quand Reda le décide ; un réglage `TACHES_SOLLICITATIONS=0/1`.

### MINEURS
- **m1** Lien du bilan : `regles.md:854` et `textes.md:428` (Aujourd'hui sans paramètre) contre `api.md:569` et
  `spec-7:32` (`?ouvrir=bilan`). TCH98 cite `regles.md` §7. Réaligner `regles.md` et `textes.md`.
- **m2** Carte `pause` : `regles.md:975` et `:987` (« pas de valeur `pause` ») contre `donnees.md:731` et `api.md` §1.
- **m3** Maquettes contre règles : la tuile titre une visite et une activité ERP (`tuile-iphone-clair`) alors que
  `regles.md:936-938` l'interdit ; l'agenda et Aujourd'hui donnent « 10:30 » à une activité ERP qui n'a qu'une date.
  TCH110 dit « la maquette fait foi ».
- **m4** Socle §1 (a) « une seule saisie » : l'ancien « + À faire » de `/activites` reste (0 mention dans le plan) —
  deux listes de choses à faire. Une tâche chez son propriétaire : le bouton ouvre `taqinor:taches:saisir`.
- **m5** Compte du rythme : retirer le plafond des micro-tâches, la garde de taille et la mémoire d'échec de la
  première livraison (`regles.md` §6.1, §6.5).
- **m6** `duree_reelle_minutes` : un minuteur sur la fiche, ou retirer C6.
- **m7** Test de garde « aucune table `taches_*` dans `_ALLOWED_TABLES` » demandé par V2, absent du plan (0 mention).
- **m8** Capture : « Ajouté dans « {projet} » » (`textes.md:674`) lit à voix haute le nom d'un projet confidentiel et
  confirme l'existence d'un projet à qui tient le jeton. Répondre « Ajouté dans un projet ».
- **m9** Texte Vie privée : trois silences (§5).
- **m10** TCH98 : « sautée, jamais différée », alors que `notify()` DIFFÈRE par défaut hors fenêtre
  (`notifications/services.py:631-633`) ; la tâche doit dire `respect_quiet_hours=False` après son propre contrôle.

## 4. Le risque de construction et le découpage

**Ce qui tournera mal en premier** : (1) B1 ; (2) le premier passage de CI de F2 (M6) ; (3) les tâches sur des
fichiers d'un autre propriétaire pendant que l'autre session renouvelle ses réservations (connu, `verif-squelette`
M10) : F3 peut rester bloquée sur l'activation ; (4) neuf acceptations sur une pile docker lente ; (5) le goût :
Reda « n'aime pas » les gestionnaires de tâches, et le produit entier n'est jugé que sur des maquettes.

**Recommandation : garder les trois fusions, changer ce qu'elles contiennent.**
1. **F2 devient le cœur complet** : y avancer les écrans Agenda (TCH104-TCH106, TCH152), Mon rythme et Réglages
   (TCH107-TCH108), la lecture ICS (TCH121-TCH122). Ils n'attendent que des routes de F2.
2. **Essai du fondateur après F2** (tâche neuve) : `taches_voir` donné à son seul rôle par l'éditeur de rôles (ou
   compte superutilisateur, à vérifier), adresse `/taches/aujourdhui`, trois jours d'usage réel. F3 se construit
   pendant ce temps ; ses retours entrent dans la dernière lane.
3. **F3** = présence iPhone (après l'essai de M7), Copilote (M3), activation pour l'Administrateur seul (M8).
4. **F4, après l'activation** : l'AVANCÉ replié (TCH64, TCH90, modèles de TCH92, vues enregistrées, TCH71-TCH72,
   constats C1-C6, garde de taille, décaler). Replié, son absence ne se voit pas ; rien n'est écarté (D-TCH-5).
5. CI lane par lane (M6).

## 5. Vie privée et vérité

Vérifié sans fuite : agent SQL en liste fermée (`sql_agent_service.py:64`) ; export anonymisé de nuit par graphe
explicite, sans `taches` (`qa_export_anonymise.py:8-18`) ; un seul point d'appel du relais vers Django
(`action_tools.py:175`).
Restes :
- l'en-tête `X-Taqinor-Assistant` échoue OUVERT : le canari (TCH127) le pose lui-même, rien ne prouve que le relais
  l'envoie ; ajouter à TCH114 un test côté `fastapi_ia` (tout appel sortant le porte) ;
- m7 et m8 ;
- le texte « Vie privée » se tait sur trois points : la conversation du Copilote, titres compris, reste un temps côté
  serveur (48 h selon la mémoire partagée, non relu dans le code) ; chaque sollicitation et chaque rappel laisse une
  ligne dans la cloche de l'ERP ; si des salariés reçoivent le module, « les personnes qui ont accès au serveur »
  comprennent le dirigeant et ses outils de maintenance.

## 6. Les tâches (15 lues en entier, 11 lanes)

TCH22, 36, 37, 44, 46, 50, 54, 76, 98, 109, 110, 114, 117, 120, 130.
- **Bien écrites** : oui dans l'ensemble — appelants nommés, invariants numérotés, maquettes citées, « Code net » sur
  les fichiers-murs. TCH22 (300 permutations) et TCH36 (création concurrente) ont des preuves exemplaires.
- **Constructibles sans deviner** : non pour TCH44, 46, 76, 109, 110, 114 (source supprimée, B1). TCH50 (huit actions
  d'état) et TCH117 (neuf cartes) sont trop grosses pour une tâche.
- **Preuve qui prouve** : non pour TCH110 et TCH120 (M7), TCH109 (« mot pour mot » prouve le texte, pas les cinq
  étapes), TCH98 (m10).

## 7. Verdict

**Prêt après corrections — pas tel quel.** Le modèle, la saisie, les contrats et la discipline de vérification sont
solides. Le plan casse ses sources (B1), le classement trahit « toutes leurs tâches » (M1, M2), l'assistant et
l'agenda sont en dessous de la demande (M3, M4), et rien n'est essayé avant la fin (M5).

Les 10 corrections, par importance :
1. Garder les sources sur `main` — `PLAN_TACHES.md` (TCH150, en-tête).
2. Proposé : prochaine action par projet, projets alternés — `reference/regles.md` §3.2-§3.4, TCH22-TCH23.
3. Urgent et retard de la veille en tête de Proposé — `reference/regles.md` §4.1-§4.2, spec-7 §4, maquette.
4. Copilote : `taches.tache.modifier`, carte « prioriser » distincte, demandes sans modèle, jeu Groq — `reference/api.md`
   §8, `reference/textes.md` §5, TCH111-TCH117.
5. Agenda et rythme en F2, essai du fondateur, AVANCÉ en F4 — `PLAN_TACHES.md`.
6. Agenda externe ESSENTIEL, 3 adresses, temps retranché — `arbitrages.md`, `reference/donnees.md` §2.20, TCH121-TCH122.
7. Essai sur iPhone réel et push de production avant F3 — `PLAN_TACHES.md` (GATED, TCH110, TCH120).
8. Une vérité sur l'hôte, CI lane par lane — `PLAN_TACHES.md:102`, `consignes-construction.md`.
9. Activation pour l'Administrateur seul, coupe-circuit des sollicitations — TCH130, TCH99.
10. Réaligner m1-m3, alléger le rythme (m5), test `_ALLOWED_TABLES` et test du relais — `reference/regles.md`,
    `reference/textes.md`, maquette `tuile`, TCH114, TCH127.

**Hors calibrage (goût, durcissement)** : trois lignes par jour dans la cloche de l'ERP ; jeton dans le corps JSON
plutôt qu'en en-tête pour raccourcir la recette Siri ; clause « Et l'écran est ATTEIGNABLE » collée sur des tâches
sans écran (TCH101, TCH132).

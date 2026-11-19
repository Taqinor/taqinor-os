# Tour 1 — consolidation des six rapports (F1, F2, S1, S2, B1, B2)

Écrit le 19/11/2026. Code lu dans `C:\dev\taqinor-os\.claude\worktrees\taches-r2` (branche `dev-taches-r2` = `main`,
commit `efc5075e4`). Chemins de code : front relatifs à `frontend/src/`, serveur relatifs à
`backend/django_core/apps/taches/`. « Cause (lue) » = j'ai ouvert le fichier et vu la ligne ; « cause non lue » ou
« à reproduire » = je ne l'ai pas vue, je le dis. Une capture a été regardée pour lever un doute
(`S2\A17-coche-1500.png` : barre ERP, deux Copilote, pastille « → ven. 20 » qui fait passer le titre sur 2 lignes,
toast collé au +, « 2 h » ambigu — tout confirmé).

Règle de rédaction pour les lanes : les fichiers de référence `docs/taches/reference/{textes,regles,api,donnees}.md`
n'appartiennent à AUCUNE lane ; chaque lane écrit dans son message de commit les phrases ou règles qu'elle a changées,
et l'orchestrateur met la référence à jour au pli (sinon quatre lanes se marchent dessus dans `textes.md`).
Attention : des tests comparent l'écran à `textes.md` ; une lane qui change un texte met le test du module à jour et
signale la ligne de référence à changer.

---

## 1. Corrections retenues (dédoublonnées)

Gravité : A = casse ou bloque un geste courant / saute aux yeux ; B = gêne ou laideur au quotidien ; C = finition.
Axe : F = fonction, S = simplicité, Be = beauté. « Lane » renvoie au § 4.

### Lane L1 — Saisie rapide et collage

**R2-001 · A · F/S — Taper vite après « Ajouter » perd des mots ou une tâche entière**
- Relecteurs : S1 n°1 + S2 A1 + S2 A2 (A2 « rien ne montre l'envoi », même cause).
- Reda voit : il note 3 tâches en marchant ; la 2e est tronquée (« Meryem sur les leads ») ou disparaît.
- Cause (lue) : `features/taches/saisie/FeuilleSaisie.jsx::creer` l.317-322 — `enchainer()` (qui fait `setTexte('')`)
  n'est appelé qu'APRÈS `await saisieRapide(...)` ; `envoyer` l.343 attend en plus un aperçu serveur quand `frais` est
  nul. Tout ce qui est tapé pendant l'attente est effacé.
- Correction : au toucher « Ajouter » / Entrée, figer la phrase et ses lignes, vider le champ tout de suite
  (`enchainer()` avant tout `await`), envoyer en arrière-plan ; en échec, remettre la phrase seulement si le champ
  est vide, sinon toast « Pas ajoutée : … · Reprendre ». Jamais un `setTexte('')` après un `await`.
- Preuve : geste — taper « Test un », Entrée, taper aussitôt « Test deux », Entrée, avec le serveur ralenti à 2 s →
  deux tâches complètes. Test : `features/taches/saisie/FeuilleSaisie.test.jsx` (promesse `saisieRapide` retenue,
  frappe pendant l'attente, le champ garde la frappe, deux corps envoyés) ; spec `frontend/e2e/taches-saisie.spec.js`
  avec `page.route` qui retarde `saisie-rapide/` de 2 s.
- Fichiers : `FeuilleSaisie.jsx`, `FeuilleSaisie.test.jsx`, `e2e/taches-saisie.spec.js`.

**R2-002 · A · S — Une tâche ajoutée depuis Aujourd'hui n'apparaît pas dans Aujourd'hui**
- Relecteurs : S1 n°4 (+ S1 journal §4 : la même feuille ouverte depuis l'Agenda pose « aujourd'hui »).
- Reda voit : « Ajoutée », et l'écran dit « Rien de prévu aujourd'hui. 1 tâche attend dans À trier ».
- Cause (lue) : `FeuilleSaisie.jsx::recevoir` l.232-236 ne pose un « Quand » de départ que si la demande porte
  `jour_prevu` ; `coquille/CoquilleTaches.jsx::demanderSaisie` l.159 envoie `contexteSaisie`, qu'Aujourd'hui ne donne pas.
- Correction (choix C-1 appliqué) : dans `FeuilleSaisie`, sur `/taches` et `/taches/aujourdhui` (lu par
  `useLocation`), sans jour dans la demande, Quand de départ = aujourd'hui (puce visible et retirable, comme l'Agenda) ;
  une date lue dans la phrase l'emporte (à vérifier dans `construireLigne`) ; toast « Ajoutée à Aujourd'hui ».
  `c t` hors de Tâches et Siri gardent À trier.
- Preuve : + sur Aujourd'hui, « Rappeler M. Benjelloun », Ajouter → la ligne est dans Prévu. Test :
  `FeuilleSaisie.test.jsx` (route `/taches/aujourdhui` → corps avec `jour_prevu` du jour ; « demain » l'emporte).
- Fichiers : `FeuilleSaisie.jsx`, `FeuilleSaisie.test.jsx`.

**R2-003 · A · F/S — « #Salon » crée « Nouveau projet : Salon » au lieu de « Salon Solaire Expo »**
- Relecteurs : F1 n°7 + S1 n°5 (+ état des lieux « V — #Salon Solaire Expo », reclassé A : il crée des doublons
  au geste le plus courant ; 4 projets sur 5 de l'exemple ont un nom en plusieurs mots).
- Reda voit : aucune liste à `#`, pas de bouton Projet ; valider crée un projet en double.
- Cause (lue) : `saisie/analyseur.py::resoudre_projet` l.65-81 ne retient que l'égalité exacte de `cle_nom` ;
  `ui/ChampSaisie.jsx` n'a aucune liste (`listbox` absent) ; pied de la feuille `FeuilleSaisie.jsx` l.395-425 : la
  seule puce est « Quand ».
- Correction : serveur — sans égalité, un `#mot` qui est le DÉBUT (par `cle_nom`) d'un mot du nom d'UN seul projet
  ouvert le prend ; plusieurs → le premier par rang + alerte `plusieurs_projets` (existante) ; l'égalité reste
  prioritaire ; la porte `capture` est inchangée. Front — dès `#`, liste des projets filtrée sans accents
  (`role=listbox`, flèches + Entrée, toucher) qui insère `#Nom_Avec_Soulignés` (déjà lu par la grammaire) ; une puce
  « Projet » dans le pied ouvre `SelecteurProjet` (composant existant, importé tel quel).
- Preuve : « Stand #Sal » → « ● Salon Solaire Expo » ; « #Chantier » → « Chantier Benali 9 kWc » ; « #Nouveau » →
  « Nouveau projet ». Tests : `tests/test_saisie_pure.py` (préfixe unique, ambigu, exact prioritaire, capture
  inchangée), `tests/test_api_saisie.py` ; front `FeuilleSaisie.test.jsx` (liste à `#`).
- Fichiers : `saisie/analyseur.py`, `ui/ChampSaisie.jsx`, `FeuilleSaisie.jsx`, tests cités.

**R2-004 · A · F — Coller une liste « comme dans Notes » range tout dans un projet invisible**
- Relecteurs : S1 n°2 + S1 n°3 + F1 n°9.
- Reda voit : « 33 tâches · 1 projet » sans nom ; les titres de projets deviennent des tâches ; avec « : » le
  rangement est juste mais l'aperçu reste plat ; deux projets créés sans avoir été montrés.
- Cause (lue) : `ui/ApercuListe.jsx` l.64 retire de chaque ligne la puce d'un projet NOUVEAU ; l.168-183 n'affiche une
  en-tête de groupe que pour `projets_communs` (première ligne), jamais pour les titres « : » ;
  `saisie/collage.py::est_titre_groupe` l.69-71 n'accepte qu'un titre fini par « : », et la règle « première ligne =
  projet » (`projet_premiere_ligne`) prend alors tout le collage.
- Correction : front — une en-tête « Nouveau projet : X · n tâches » (priorité, « En faire une tâche ») pour CHAQUE
  groupe, puce de projet visible sur chaque ligne d'un projet existant ou nouveau (maquette `ecran-saisie-liste.html`).
  Serveur — une ligne courte (≤ 60 caractères, sans date ni puce) suivie de lignes à tiret/puce ou en retrait, ou
  précédée d'une ligne vide, est un titre de groupe même sans « : » ; la « première ligne = projet » ne joue plus
  quand d'autres titres de groupe existent.
- Preuve : coller `liste30.txt` de S1 → 7 groupes nommés visibles avant « Créer ». Tests :
  `tests/test_saisie_pure.py` (copier `liste30.txt` dans `tests/donnees/`), `ui/ApercuListe.test.jsx` (en-têtes pour
  `projets_nouveaux`).
- Fichiers : `saisie/collage.py`, `ui/ApercuListe.jsx`, `saisie/ColleListes.jsx`, tests cités.

**R2-005 · B · F — Aperçu de liste : un titre corrigé n'est pas relu, les puces ne se touchent pas**
- Relecteurs : F1 n°10 (1re moitié ; le débordement horizontal est dans R2-051).
- Cause (lue) : `ui/ApercuListe.jsx::LigneApercu` l.69-78 — seul le titre est un champ ; `PucesLues` l.52-58 rend des
  `span`.
- Correction : à la sortie du champ titre, relire CETTE ligne par l'aperçu serveur (les jetons deviennent des puces) ;
  chaque puce a un × (même effet que dans la saisie d'une ligne).
- Preuve : corriger « … lundi » en « … mardi » → puce « mar. ». Test : `ui/ApercuListe.test.jsx`.
- Fichiers : `ui/ApercuListe.jsx`, `saisie/ColleListes.jsx`.

**R2-006 · B · F — Phrases courantes non comprises**
- Relecteurs : F1 n°8 + S1 n°17.
- Reda voit : « dans une semaine », « fin du mois », « aprem », « !haute », « avant le 25 » restent dans le titre.
- Cause (lue en partie) : `saisie/grammaire.py` n'a pas de motif pour « aprem », « un/une » comme nombre, « !haute » ;
  « ce midi » est écarté exprès par la règle de contexte §1.4 (« midi » nu, `_est_midi_nu` l.499) ; « avant le 25 » :
  le déclencheur d'échéance existe (l.507) mais « le 25 » seul n'est pas lu comme jour (non vérifié ligne à ligne).
- Correction : ajouter ces motifs (« un/une » = 1 après « dans », « fin du mois » = « fin de mois », « aprem » =
  après-midi, « !haute/!moyenne/!basse », « le 25 » = prochain 25) ; lire « ce midi » (le « ce » lève l'ambiguïté).
- Preuve : les 7 phrases ratées de F1 donnent leurs puces. Test : `tests/test_saisie_pure.py` (table de phrases).
- Fichiers : `saisie/grammaire.py`, `tests/test_saisie_pure.py`.

**R2-007 · B · F — Titre de 300 caractères : « Aucune ligne lisible. »**
- Relecteurs : F1 n°16.
- Cause (lue) : l'analyseur pose `erreurs = {'titre': ['Le titre est trop long : 280 caractères au plus.']}`
  (`saisie/analyseur.py` l.576-580) mais `FeuilleSaisie.jsx::envoyer` l.353-357 n'en lit rien et affiche le message
  générique quand aucune ligne ne reste.
- Correction : afficher le message de `ligne.erreurs` sous le champ + compteur « 300 / 280 » ; proposer « Mettre le
  reste en note ».
- Preuve : coller 300 caractères → « 280 caractères au plus (300) ». Test : `FeuilleSaisie.test.jsx`.
- Fichiers : `FeuilleSaisie.jsx`.

**R2-008 · B · F — Hors ligne, la phrase n'est pas lue et la tâche n'apparaît nulle part**
- Relecteurs : F1 n°15. Deux moitiés : (a) ici, (b) dans L2.
- Cause (lue) : `FeuilleSaisie.jsx::lignesBrutes` l.171-174 met le texte entier en titre, sans jour ; la file
  (`horsligne/captureQueue.js`) rejoue `lignes[{titre}]`, donc « ce soir » reste dans le titre et la tâche tombe dans
  À trier.
- Correction (a) : mettre en file le TEXTE de la phrase (le serveur l'analyse au rejeu, même chemin que `saisie-rapide/`
  avec `apercu:false`), en gardant le `client_id` pour l'idempotence. (b) voir R2-008b en L2.
- Preuve : hors ligne « Test ce soir » → au retour, tâche « Test » dans Ce soir, une seule fois. Test :
  `horsligne/captureQueue.test.js` + `FeuilleSaisie.test.jsx`.
- Fichiers : `FeuilleSaisie.jsx`, `horsligne/captureQueue.js`, `horsligne/captureQueue.test.js`.

**R2-009 · B · S/Be — Au bureau, la saisie s'ouvre en boîte centrée sur voile**
- Relecteurs : B2 n°2 (partie saisie) + S2 B9 (« n » et le champ du haut ouvrent une autre fenêtre).
- Cause (lue) : `FeuilleSaisie.jsx` l.364 monte `FeuilleACrans` avec la variante par défaut `dialogue` ; la variante
  `popover-bureau` existe déjà (`styles/taches/base.css` l.785-792 : ancrée en haut, sans hauteur fixe).
- Correction (choix C-3 appliqué) : variante `popover-bureau` au bureau, ancrée sous la ligne « Ajouter une tâche »,
  sans voile qui cache la liste ; Entrée / Échap comme aujourd'hui.
- Preuve : bureau, `n` → le champ s'ouvre à la place de la ligne, la liste reste lisible. Test : `FeuilleSaisie.test.jsx`
  (variante passée) ; spec `e2e/taches-bureau.spec.js` n'est pas à cette lane (voir L4) → vérifier dans
  `taches-saisie.spec.js`.
- Fichiers : `FeuilleSaisie.jsx`.

### Lane L2 — Aujourd'hui (page, sections, serveur de la journée)

**R2-010 · A · F — Cocher une « Activité ERP » ne s'annule pas et le compteur ne bouge pas**
- Relecteurs : S1 n°6.
- Cause (lue) : `pages/taches/Aujourdhui.jsx::terminer` l.294-300 — `markActivityDone` part tout de suite, toast « Close
  dans l'ERP » SANS `onAnnuler`, et `poserProgression` n'est pas appelé ; décocher une activité est refusé l.295 (« ne
  se rouvre pas ici ») faute de route de réouverture côté ERP.
- Correction (choix C-9 appliqué) : envoi DIFFÉRÉ — la ligne passe cochée et le compteur +1 tout de suite, toast « Close
  dans l'ERP · Annuler » ; l'appel `markActivityDone` part à la disparition du toast (ou à la sortie de l'écran) ;
  « Annuler » ne fait que remettre la ligne. Aucun changement hors du module.
- Preuve : cocher « Rappeler pour le devis » puis Annuler → l'activité reste ouverte côté ERP ; sans Annuler → close
  après 8 s, compteur juste sans rechargement. Test : `pages/taches/Aujourdhui.test.jsx` (minuteur factice).
- Fichiers : `Aujourdhui.jsx`, `Aujourdhui.test.jsx`.

**R2-011 · B · F/Be — Cocher, annuler et reporter attendent le serveur**
- Relecteurs : B1 n°12 + S2 A3 + F1 n°17 a et b (double toucher : toast « Faite » resté après décocher).
- Reda voit : le rond vert tout de suite, mais barré, compteur et toast après 1 s ; Annuler semble raté ; un balayage
  de report ne montre rien pendant 0,8 à 2,5 s (il balaie deux fois).
- Cause (lue) : `Aujourdhui.jsx::terminer` l.301-315 (`patcher` et toast après `await`), `onAnnuler` l.310-314 (remise
  après `annulerEtRecaler`), `poserJour` l.332-345 (estampille et toast après `await planifierTache`). Décocher
  (`suivant=false`) ne retire pas le toast « Faite » précédent (l.305).
- Correction : mise à jour optimiste puis réconciliation, comme ★ : barré + compteur + toast au geste, retour en
  arrière et message si le serveur refuse ; Annuler remet l'état d'avant immédiatement ; décocher ferme le toast.
- Preuve : serveur ralenti à 2 s : cocher → barré et « 2 sur 5 » en < 100 ms ; Annuler → « 1 sur 5 » en < 100 ms ;
  balayage → « → ven. 20 » au relâcher. Test : `Aujourdhui.test.jsx` (promesses retenues) ; spec
  `e2e/taches-journee.spec.js` avec route retardée.
- Fichiers : `Aujourdhui.jsx`, `Aujourdhui.test.jsx`, `e2e/taches-journee.spec.js`.

**R2-012 · B · F — La 4e étoile ne dit rien ; par le menu, 400 invisible**
- Relecteurs : F1 n°1.
- Cause (lue) : `Aujourdhui.jsx` l.508 `refusEssentiel: () => annoncer('3 au plus.')` (lecteur d'écran seulement) ;
  `basculerEssentiel` l.365-391 envoie la requête sans tester le plafond et ne fait qu'`annoncer` l'erreur.
- Correction : toast visible « 3 essentielles au plus — retire une étoile d'abord » ; tester le plafond avant l'appel
  (étoile ET menu).
- Preuve : 3 ★ posées, 4e étoile → toast, aucune requête. Test : `Aujourdhui.test.jsx`.
- Fichiers : `Aujourdhui.jsx`.

**R2-013 · B · F — « En attente de… » : la ligne disparaît au lieu de passer dans En attente**
- Relecteurs : F1 n°3.
- Cause (lue) : `Aujourdhui.jsx` l.485 `sortApres: … code === 'attente'` retire la ligne ; rien ne l'insère dans
  `en_attente` (contrairement à `rangerEssentielle` l.191 pour ★).
- Correction : après le geste, déplacer la ligne dans `en_attente` (compteur compris) ; Annuler la remet.
- Preuve : menu ⋯ > En attente de… > Karim → la section En attente passe à 2 sans rechargement. Test :
  `Aujourdhui.test.jsx`.
- Fichiers : `Aujourdhui.jsx`.

**R2-014b · B · S — « Oui » de la carte « tâches reportées » ne fait rien** (moitié page de R2-014, voir L3)
- Cause (lue) : `Aujourdhui.jsx::repondre` l.422-444 ne traite que `retour` ; serveur `services/rythme.py::_constat_accepte`
  l.423-434 : « C7 vit par la carte acceptée elle-même ».
- Correction : `repondre` — constat C7 + « oui » → déplier « À revoir » et y faire défiler.
- Preuve : carte C7 > Oui → À revoir ouvert (`aria-expanded=true`) et visible. Test : `Aujourdhui.test.jsx`.
- Fichiers : `Aujourdhui.jsx`, `aujourdhui/Replies.jsx` (prop d'ouverture).

**R2-019 · B · F — « essentiel 1/3 » compte l'essentielle reportée à demain**
- Relecteurs : S2 A4 + F1 n°17 d.
- Cause (lue) : `selectors/journee.py::progression_du_jour` l.446-456 compte `journee.lignes` (le plan du matin) ;
  une ligne reportée y reste. C'est voulu pour la mesure du plan (`services/journee.py` l.912), pas pour l'affichage.
- Correction : à l'écran, « essentiel f/p » se calcule sur la section Essentiel affichée (la mesure du plan gardée
  telle quelle côté serveur). Même règle pour « 2 des 6 gardées » du détail.
- Preuve : reporter une ★ → « essentiel 0/1 ». Test : `Aujourdhui.test.jsx` / `aujourdhui/Progression` (voisin).
- Fichiers : `aujourdhui/Progression.jsx`.

**R2-020 · B · S — Proposé : phrases fausses ou vides, compteur qui ne correspond pas**
- Relecteurs : F2 n°8 + F2 n°24 + S2 A8 + F1 n°17 e + S1 n°10 (Proposé vide) + S2 C4 (Proposé après le bilan).
- Cause (lue) : `aujourdhui/Propose.jsx` l.88 phrase « Objectif couvert par ce que tu as gardé » quel que soit le
  mode ; l.71 `reste = propose.reste_nb` (tâches sans jour) alors que `suite_par_projet` montre aussi les tâches prévues
  plus tard (16-17 lignes pour « (7) ») ; section rendue quand `n === 0` ; rien ne dépend du bilan fait.
- Correction : mode « Sans objectif » → pas de phrase d'objectif ; `n === 0` → section repliée en une ligne « Voir les
  tâches de mes projets » ; le chiffre = le nombre de lignes montrées ; journée close par le bilan → plus de Proposé
  ni de « Garder » pour aujourd'hui ; un squelette pendant le chargement de « Voir tout » ; pas de nom de projet dans
  les lignes d'un groupe déjà titré.
- Preuve : mode libre → aucune phrase d'objectif ; « Voir toutes … (n) » déplie n lignes. Test :
  `aujourdhui/Propose.test.jsx`.
- Fichiers : `aujourdhui/Propose.jsx`, `aujourdhui/Propose.test.jsx`.

**R2-021 · B · S — À revoir : pas de raison ; « Découper » ouvre une fiche où on ne trouve pas où découper**
- Relecteurs : F1 n°18 + S1 n°10 (À revoir sans raison). Deux moitiés : ici l'appel, la fiche en L4 (R2-021b).
- Cause (lue) : `aujourdhui/Replies.jsx` l.91-92 — « Découper » appelle `geste.ouvrir(item)` (fiche ordinaire) ; la
  ligne a `item.motif` mais ne l'écrit pas.
- Correction : sous chaque ligne d'À revoir, la raison en clair (« reportée 3 fois », « en retard depuis le 12 ») ;
  « Découper » ouvre la fiche avec `section=decouper` (paramètre ajouté par L4).
- Preuve : À revoir montre « reportée 3 fois » ; Découper → curseur dans le champ Découper. Test : `Aujourdhui.test.jsx`.
- Fichiers : `aujourdhui/Replies.jsx`.

**R2-022 · B · S — « Choisir un jour » : un seul raccourci et un champ date brut**
- Relecteurs : S2 B6.
- Cause (lue) : `Aujourdhui.jsx::ChoisirJour` l.227-242 — un `input type=date` et un bouton.
- Correction : réutiliser `ui/SelecteurQuand` (Aujourd'hui · Demain · Ce soir · Reporter à … · Choisir un jour ·
  En réserve), importé sans le modifier ; Entrée garde « Reporter à {jour} ».
- Preuve : `d` → six tuiles, Demain en 1 toucher. Test : `Aujourdhui.test.jsx`.
- Fichiers : `Aujourdhui.jsx`.

**R2-023 · A · Be — Au bureau 1280 × 720, la liste du jour est écrasée à 290 px**
- Relecteurs : B2 n°3.
- Cause (lue) : `styles/taches/coeur.css` l.191-193 — grille fixe `216px minmax(0,1fr) 380px` dès 1024 px, sous la
  barre latérale de l'ERP.
- Correction : `minmax(480px, 1fr)` pour la liste ; sous 1360 px la colonne « Mes projets » se replie (elle est déjà
  dans le menu de gauche).
- Preuve : 1280 × 720 → titres sur une ligne, ⋯ ne recouvre plus l'étoile. Test : spec `e2e/taches-journee.spec.js`
  (largeur de `.tch-bureau-liste` ≥ 480 à 1280 px).
- Fichiers : `styles/taches/coeur.css`.

**R2-025 · B · F — `e` et `h` ouvrent la fiche entière, pas le titre ni l'heure**
- Relecteurs : S2 B5. Deux moitiés : ici l'appel, la fiche en L4 (R2-025b).
- Cause (lue) : `Aujourdhui.jsx` l.559 — `renommer` et `heure` appellent `ouvrirFiche(item.id)` sans rien de plus.
- Correction : `ouvrirFiche(id, { focus: 'titre' | 'heure' })`.
- Preuve : `e` → curseur dans le titre ; `h` → champ heure ouvert. Test : `Aujourdhui.test.jsx`.
- Fichiers : `Aujourdhui.jsx`.

**R2-026 · C · S — « Alléger ma journée » : « Garder ces 0 » mort, entrée offerte quand il n'y a rien ; carte de 15 h télégraphique**
- Relecteurs : F2 n°22 + S2 B8 + S2 C5 + S1 n°10 (« Garder ces 0 »).
- Cause (lue) : `aujourdhui/FeuilleAlleger.jsx` l.59-62 (`k === 0` grisé, libellé « Garder ces 0 ») ;
  `aujourdhui/MenuJournee.jsx` l.44 (entrée toujours offerte) ; texte de la carte `ui/CarteDuMoment.jsx` l.222 (voir L3).
- Correction : 0 coché → bouton « Tout renvoyer aux projets » ; entrée masquée quand rien à alléger (bilan fait ou
  aucune ouverte) ; aide raccourcie à une ligne.
- Preuve : soir, une seule tâche → « Tout renvoyer aux projets » marche. Test : `aujourdhui/FeuilleAlleger.test.jsx`.
- Fichiers : `aujourdhui/FeuilleAlleger.jsx`, `aujourdhui/MenuJournee.jsx`.

**R2-027 · C · S — Mots ambigus : « En attente 1 · 2 en attente d'une autre tâche » ; toast de l'étoile**
- Relecteurs : S2 T3 + S2 T4 + S1 n°10 (« En attente » double).
- Cause (lue en partie) : libellés de `aujourdhui/Sections.jsx` (ligne exacte non relevée) ; toast « Essentielle »
  posé par `basculerEssentiel` l.376-388.
- Correction : « En attente 1 · Bloquées 2 » ; l'étoile ne pose plus de toast (l'étoile pleine suffit), Annuler reste
  par Ctrl+Z / Derniers gestes.
- Preuve : relire les deux libellés. Test : `Aujourdhui.test.jsx`.
- Fichiers : `aujourdhui/Sections.jsx`, `Aujourdhui.jsx`.

**R2-029 · C · F — Au bureau, les compteurs de « Mes projets » ne suivent pas « Déplacer… »**
- Relecteurs : F1 n°17 c.
- Cause : non lue (`aujourdhui/ColonneBureau.jsx` probable) — à reproduire.
- Correction : relire les compteurs de la colonne après un déplacement (ou les ajuster sur place).
- Preuve : Déplacer vers Salon → « Salon … » +1 sans rechargement. Test : `aujourdhui/ColonneBureau.test.jsx`.
- Fichiers : `aujourdhui/ColonneBureau.jsx`.

**R2-030 · C · Be/S — Bilan du soir : tâches « Reste » sans rond, quatre pilules par tâche**
- Relecteurs : B1 n°21 + B1 « défauts des maquettes » (20 pilules pour 5 tâches) + B2 n°2 (bilan : 4 boutons par tâche).
- Cause : `aujourdhui/FeuilleBilan.jsx` (non relu ligne à ligne).
- Correction : rond à gauche comme partout ; par tâche une seule action visible (« Reporter à ven. 20 », déjà
  présélectionnée) + ⋯ pour les autres ; « Tout reporter » en tête (existe).
- Preuve : bilan à 5 tâches → 5 ronds, 5 boutons. Test : `aujourdhui/FeuilleBilan.test.jsx`.
- Fichiers : `aujourdhui/FeuilleBilan.jsx`, `styles/taches/coeur.css`.

**R2-031 · B · F — Mettre un projet en pause fait disparaître une tâche posée aujourd'hui à 16:00**
- Relecteurs : F2 n°13. Deux moitiés : journée ici, agenda en L7 (R2-031b).
- Cause (lue) : `selectors/journee.py::taches_de_la_journee` l.90-95 — une tâche ouverte n'entre que si son projet est
  `actif` ; c'est la règle écrite (`reference/regles.md` l.455 « Absentes : Salon (en pause) »).
- Correction (choix C-5 appliqué) : une tâche ouverte d'un projet en pause reste dans la journée si elle est prévue CE
  jour-là (jour ou heure posés) ; la pause continue de la retirer de Proposé, d'À trier et des jours futurs ; la
  décision « Pause » de la Revue dit « 1 tâche prévue aujourd'hui reste dans ta journée ».
- Preuve : tâche à 16:00 aujourd'hui, Revue > Pause → toujours dans Prévu et dans l'agenda du jour. Test :
  `tests/test_api_journee.py` (projet en pause + `jour_prevu` = J).
- Fichiers : `selectors/journee.py`, `tests/test_api_journee.py`.

**R2-033 · B · S — Journée vide : « Coller mes listes » ouvre une feuille vide, le + n'est pas montré**
- Relecteurs : S1 n°8 (moitié module ; le bandeau « Installer Taqinor OS » est hors module, § 2).
- Cause (lue) : `FeuilleSaisie.jsx` reçoit `detail.liste` et rouvre le champ (l.229), sans lire le presse-papiers ;
  l'état vide est dans `aujourdhui/Sections.jsx` (non relu ligne à ligne).
- Correction : « Coller mes listes » lit le presse-papiers (`navigator.clipboard.readText`) et, refusé ou vide, écrit
  « Appuie longuement dans le champ puis Coller » ; une phrase « ou touche + pour une tâche » sous le bouton.
- Preuve : presse-papiers à 3 lignes → l'aperçu s'ouvre directement. Test : `Aujourdhui.test.jsx`.
- Fichiers : `aujourdhui/Sections.jsx` (l'appel) — la lecture du presse-papiers passe par l'événement existant
  `taqinor:taches:saisir` avec `detail.texte` (aucun changement de `FeuilleSaisie.jsx`).

**R2-035 · C · S — Détail de la journée : deux nombres et « (accepté) »**
- Relecteurs : S1 n°10 (« 1 sur 5 » contre « 1 des 6 gardées », « Objectif du jour : 5 (accepté) »).
- Cause : `aujourdhui/Progression.jsx` (non relu ligne à ligne).
- Correction : une seule phrase « 1 faite sur 5 visées · 6 tâches gardées » ; « (accepté) » retiré.
- Preuve : toucher la barre → une phrase lisible. Test : voisin de `Progression.jsx` (`Aujourdhui.test.jsx`).
- Fichiers : `aujourdhui/Progression.jsx`.

**R2-008b · B · F — Hors ligne : la tâche ajoutée ne s'affiche pas, décocher ne dit rien** (moitié de R2-008)
- Cause (lue) : `Aujourdhui.jsx::terminer` l.282-292 — hors ligne, seul `suivant=true` est traité ; décocher tombe sur
  `garde()` qui annonce sans toast visible.
- Correction : une ligne « en attente d'envoi » (grisée) apparaît dans Aujourd'hui dès l'ajout hors ligne (lue dans la
  file) ; décocher hors ligne → toast « Décocher attend le réseau ».
- Preuve : hors ligne, + « Test ce soir » → ligne grisée visible. Test : `Aujourdhui.test.jsx`.
- Fichiers : `Aujourdhui.jsx`.

### Lane L3 — Lignes, cartes du moment, À trier

**R2-014 · B · S — Cartes du moment : des constats sans question, des « Oui » sans effet, trois cartes en relais le matin**
- Relecteurs : F1 n°4 + S2 A7 + S1 n°9 + S2 A6 + S2 C4 (carte 57 % remontée après le bilan). Moitié page en L2 (R2-014b).
- Cause (lue) : `moteur/gabarits.py` l.401-415 définit `C1.question` … `C8.question` mais aucune ligne du serveur ne les
  lit (recherche `.question` : seul le dictionnaire) — d'où « 2 tâches reportées 3 fois ou plus. Oui / Pas maintenant »
  sans question, et « 57 % … » + OK ; `ui/CarteDuMoment.jsx` l.247-250 place une astuce dès qu'aucune carte serveur
  n'est là, donc OK d'une carte en fait venir une autre.
- Correction : `_constat` ajoute la question à la phrase (« … Les revoir maintenant ? ») et les boutons deviennent
  la réponse ; la carte C1 propose son geste (« Mettre l'essentiel entre 10 h et 12 h ? ») ; une carte au plus par
  matin : une astuce ne vient pas le jour où une carte a été répondue ; après le bilan, aucune carte de constat.
- Preuve : compte semé → carte C7 avec sa question ; OK sur une carte → pas d'autre carte ce jour. Tests :
  `tests/test_gabarits.py` (question présente pour C1-C8), `ui/CarteDuMoment.test.jsx`.
- Fichiers : `moteur/gabarits.py`, `tests/test_gabarits.py`, `ui/CarteDuMoment.jsx`, `ui/CarteDuMoment.test.jsx`.

**R2-015 · B · S — Astuce du balayage montrée au bureau ; l'appui long n'est jamais appris**
- Relecteurs : F1 n°6 + S1 n°15.
- Cause (lue) : `ui/CarteDuMoment.jsx` l.19-23 — liste d'astuces sans condition d'appareil ; aucune astuce « appui long ».
- Correction : astuce « balayage » et « appui long » seulement si `matchMedia('(pointer: coarse)')` ; au bureau,
  astuce « glisse une tâche sur l'agenda » à la place.
- Preuve : bureau → jamais « Balaie une ligne ». Test : `ui/CarteDuMoment.test.jsx` (matchMedia simulé).
- Fichiers : `ui/CarteDuMoment.jsx`.

**R2-016 · B · F — Balayer à droite ne coche jamais, contrairement à la promesse de la carte**
- Relecteurs : F1 n°5.
- Cause (lue) : `ui/LigneTache.jsx::useBalayage` l.66 plafonne le déplacement à `LARGEUR_DROITE + 40` = 172 px, alors
  que l.77 exige `largeur * 0.5` (195 px sur 390) : inatteignable.
- Correction : juger le seuil sur le déplacement du doigt (non plafonné), ou plafond ≥ moitié de la ligne.
- Preuve : balayage complet à droite → cochée + « Faite · Annuler ». Test : `ui/LigneTache.test.jsx` (pointer events
  tactiles, largeur 390).
- Fichiers : `ui/LigneTache.jsx`, `ui/LigneTache.test.jsx`.

**R2-017 · B · Be — La pastille « → ven. 20 » fait sauter la ligne de 65 à 150 px**
- Relecteurs : S2 A5 (vu sur capture `S2\A17-coche-1500.png`).
- Cause (lue sur la capture) : la pastille s'ajoute à la colonne de fin à côté de l'heure et du drapeau, le titre passe
  sur deux lignes.
- Correction : la pastille REMPLACE l'heure dans la colonne de fin (même largeur), puis la ligne s'efface en fondu.
- Preuve : reporter → hauteur de ligne inchangée. Test : `ui/LigneTache.test.jsx`.
- Fichiers : `ui/LigneTache.jsx`.

**R2-018 · B · S/Be — « 2 h » se lit « à 2 h » ; lignes sur 3 étages, 5 tâches par écran**
- Relecteurs : S1 n°10 (« échéance demain 2 h ») + S2 A10. Moitié CSS en L6 (R2-018b).
- Cause : méta d'une ligne dans `ui/LigneTache.jsx` (durée affichée nue).
- Correction : durée avec icône sablier (« ⧗ 2 h ») ; le nom de projet omis quand la ligne est dans un groupe titré ;
  méta sur la ligne du titre quand elle tient (classe posée ici, règle CSS en L6).
- Preuve : ligne « Envoyer le devis révisé » → « échéance demain · ⧗ 2 h » sur une ligne. Test : `ui/LigneTache.test.jsx`.
- Fichiers : `ui/LigneTache.jsx`.

**R2-024 · B · F — La pastille rouge d'À trier ne suit pas les gestes**
- Relecteurs : F1 n°14.
- Cause (lue) : `features/taches/useBadgeTaches.js` l.86-100 ne relit qu'au retour au premier plan et à la reconnexion.
- Correction : `chargerBadgeTaches({ force: true })` après chaque geste d'À trier (et après une création).
- Preuve : ranger 2 cartes → pastille 4 → 2 tout de suite. Test : `useBadgeTaches.test.js`, `pages/taches/ATrier.test.jsx`.
- Fichiers : `useBadgeTaches.js`, `pages/taches/ATrier.jsx`.

**R2-028 · C · S — La ligne ne dit pas qu'il y a une note, une check-list, un rappel**
- Relecteurs : F1 n°20 + F1 n°13 (2e moitié : « rien n'indique un rappel »).
- Cause : `ui/LigneTache.jsx` (méta sans ces indices).
- Correction : petits indices discrets (≡ note, ☑ 1/2, cloche) dans la méta, comme Things.
- Preuve : tâche avec note + check-list + rappel → trois indices. Test : `ui/LigneTache.test.jsx`.
- Fichiers : `ui/LigneTache.jsx`.

**R2-032 · C · Be — Balayage : bande grise à mi-course, ligne ouverte qui ne se referme pas**
- Relecteurs : B1 n°27.
- Cause : `ui/LigneTache.jsx::useBalayage` (non relu ligne à ligne).
- Correction : actions dévoilées proportionnellement ; un toucher ailleurs referme d'abord la ligne ouverte.
- Preuve : demi-balayage puis toucher une autre ligne → la première se referme, rien d'autre ne s'ouvre. Test :
  `ui/LigneTache.test.jsx`.
- Fichiers : `ui/LigneTache.jsx`.

**R2-034 · C · S — Phrases de la Revue (« 4 tâches en 1 jour (précédente : 9) », « il faudrait 24 jours »)**
- Relecteurs : S2 C6 + S1 n°16 (partie Revue). Moitié écran en L5 (R2-068).
- Cause (lue) : `moteur/gabarits.py::_debut_revue` l.434-439.
- Correction : « Cette semaine : 4 faites (9 la précédente). » ; la santé dit la conséquence (« à ce rythme, pas prêt
  pour le 22 »).
- Preuve : relire la carte de Revue. Test : `tests/test_gabarits.py`.
- Fichiers : `moteur/gabarits.py`, `tests/test_gabarits.py`.

**R2-036 · B · F — `j`/`k` ne marchent que sur Aujourd'hui** (en trois parts : À trier ici, Projet en L5, Recherche en L8)
- Relecteurs : S2 B4 (état des lieux : « choisi seule » — jugé gênant au quotidien, retenu).
- Cause (lue) : `lib/clavierListe.js` n'est branché que par Aujourd'hui.
- Correction : brancher `useClavierListe` (sans le modifier) sur À trier ; L5 sur la liste d'un projet ; L8 sur la
  Recherche. L'Agenda n'en a pas besoin.
- Preuve : À trier, `j` `j` Entrée → la 2e carte s'ouvre. Test : `pages/taches/ATrier.test.jsx`.
- Fichiers : `pages/taches/ATrier.jsx`.

### Lane L4 — Fiche d'une tâche et feuilles

**R2-040 · A · F — Ce qu'on fait dans la fiche (Fait, Supprimer, mettre à aujourd'hui) n'apparaît pas dans la liste**
- Relecteurs : F1 n°19 (+ F1 n°21 « la ligne reste »).
- Cause (lue) : la fiche est montée par la coquille (`CoquilleTaches.jsx` l.275), pas par l'écran ; `fiche/Fiche.jsx`
  écrit (`terminerTache` l.256, `planifierTache` l.248-252, `modifierTache` l.236) sans rien dire à l'écran ; les
  écrans n'écoutent que `taqinor:taches:creees` via `lib/fiche.js::useApresCreation`.
- Correction : `Fiche.jsx` émet `taqinor:taches:ecrite` (`{tache}`) après chaque écriture réussie et à la fermeture ;
  `lib/fiche.js::useApresCreation` écoute AUSSI cet événement — Aujourd'hui (l.468) et l'Agenda (l.693) se relisent
  donc sans qu'on touche à leurs fichiers.
- Preuve : iPhone, fiche > Fait, fermer → ligne cochée, compteur +1 ; fiche > Supprimer → ligne partie ; bureau, fiche
  > Quand > Aujourd'hui → la ligne arrive dans Prévu. Tests : `fiche/Fiche.test.jsx` (événement émis), test de
  `lib/fiche.js` (les deux événements appellent le rappel) ; spec `e2e/taches-bureau.spec.js`.
- Fichiers : `fiche/Fiche.jsx`, `lib/fiche.js`, `fiche/Fiche.test.jsx`, `e2e/taches-bureau.spec.js`.

**R2-041 · A · F — Taper « 1145 » dans l'heure enregistre 11:04**
- Relecteurs : F1 n°11 (prouvé au clavier du bureau ; sur iPhone la roue pose la valeur d'un coup).
- Cause (lue) : `ui/SelecteurQuand.jsx` — champ heure contrôlé, `onChange={surHeure}` l.120 → `onChoisir` à chaque frappe
  valide ; la fiche enregistre et redessine, le 2e chiffre des minutes est perdu.
- Correction : valeur locale dans le sélecteur ; `onChoisir` à la sortie du champ ou à Entrée (et sur changement d'une
  roue tactile : `blur` suffit) ; idem pour le champ jour l.104.
- Preuve : taper 1145 à 250 ms entre touches → 11:45 enregistré. Test : `ui/composants.test.jsx` (frappe pas à pas,
  un seul `onChoisir` à la sortie).
- Fichiers : `ui/SelecteurQuand.jsx`, `ui/composants.test.jsx`.

**R2-042 · A · F — Taper une échéance envoie « 0002-11-27 » → erreur 400 et jargon « YYYY-MM-DD »**
- Relecteurs : F1 n°12.
- Cause (lue) : `fiche/Fiche.jsx` l.417-420 — `input type=date` avec `onChange={(e) => patcher({ echeance: … })}` :
  écrit dès le 1er chiffre de l'année.
- Correction : écrire à la sortie du champ et seulement une date complète ; raccourcis comme « Quand » (Demain, Vendredi,
  Fin de mois, Choisir) ; tout message serveur de date traduit (« Date incomplète »), jamais « YYYY-MM-DD ».
- Preuve : taper 27112026 → échéance « ven. 27 nov. », aucune requête intermédiaire. Test : `fiche/Fiche.test.jsx`.
- Fichiers : `fiche/Fiche.jsx`.

**R2-043 · A · F — Au bureau, les feuilles gardent le focus derrière et Échap ne les ferme pas**
- Relecteurs : F1 n°2 + S2 B1 + S2 B2 + B2 n°14.
- Cause (lue) : `ui/FeuilleACrans.jsx` l.114-119 met le focus sur le premier élément focalisable, la poignée — or
  `styles/taches/base.css` l.782-784 la cache au bureau (`display:none`) : `focus()` échoue, le focus reste derrière ;
  Échap n'est écouté que sur la feuille (`onKeyDown` l.151), donc jamais reçu. (La saisie ferme parce qu'elle a son
  propre écouteur sur `document`, `FeuilleSaisie.jsx` l.251-256.)
- Correction : focus initial = premier élément VISIBLE (`[data-focus-initial]`, sinon le premier champ, sinon
  « Fermer ») ; Échap écouté sur `document` tant que la feuille est la plus haute ouverte ; piège de Tab inchangé.
- Preuve : bureau, fiche ouverte à la souris → Échap ferme, le focus revient à la ligne ; Tab reste dans la fiche ;
  pareil pour Alléger, Choisir un jour, Priorité, En attente de… Test : `ui/composants.test.jsx` (poignée cachée :
  le focus va au champ) ; spec `e2e/taches-bureau.spec.js`.
- Fichiers : `ui/FeuilleACrans.jsx`, `ui/composants.test.jsx`.

**R2-044 · B · F — Notes et titre en cours de frappe perdus au rechargement (ou quand iOS tue l'appli)**
- Relecteurs : F1 n°22.
- Cause (lue) : `fiche/Fiche.jsx` l.342-343 et l.462-463 — enregistrement seulement `onBlur`.
- Correction : enregistrement différé (~1 s après la dernière frappe) + à `pagehide`/`visibilitychange`.
- Preuve : taper dans Notes, attendre 1,5 s, recharger → texte gardé. Test : `fiche/Fiche.test.jsx` (minuteur factice).
- Fichiers : `fiche/Fiche.jsx`.

**R2-045 · B · S — Le champ Notes n'invite à rien**
- Relecteurs : B2 n°27 + B1 n°24.
- Cause (lue) : `fiche/Fiche.jsx` l.462 — `textarea` des notes sans `placeholder` ni `aria-label`.
- Correction : invite « Ajouter une note… » + `aria-label="Notes"` ; hauteur d'une ligne quand vide.
- Preuve : fiche neuve → invite grise visible. Test : `fiche/Fiche.test.jsx`.
- Fichiers : `fiche/Fiche.jsx`.

**R2-046 · B · S — Rappel affiché « 0 jour avant l'échéance à 22:00 » sur une tâche sans échéance**
- Relecteurs : F1 n°13 (1re moitié).
- Cause (lue) : `fiche/FichePlus.jsx` l.75 — `r.ancre` → « {n} jour avant l'échéance », même à 0 et quand l'ancre est
  le jour prévu.
- Correction : 0 → « le jour même à 22:00 » ; ancre = jour prévu → « le jour prévu à 22:00 ».
- Preuve : « Arroser … chaque jour rappel 22h » → « Le jour prévu à 22:00 ». Test : `fiche/FichePlus.test.jsx`.
- Fichiers : `fiche/FichePlus.jsx`.

**R2-047 · B · Be — La confirmation « Supprimer » déborde de l'écran iPhone**
- Relecteurs : F1 n°21.
- Cause : rangée `.carte-actions` de `fiche/FichePlus.jsx` (CSS non relue ligne à ligne) — à reproduire à 390 px.
- Correction : la confirmation sur sa propre ligne, pleine largeur, « Annuler » visible.
- Preuve : iPhone, Plus > Supprimer → les deux boutons visibles. Test : `fiche/FichePlus.test.jsx` (structure) +
  spec `e2e/taches-bureau.spec.js` en 390 px.
- Fichiers : `fiche/FichePlus.jsx`, `styles/taches/saisie.css`.

**R2-048 · B · Be — Feuilles sans animation ; feuilles à moitié vides**
- Relecteurs : B1 n°13 + B2 n°2 (saisie « 300 px de blanc sous les boutons »).
- Cause (lue) : `styles/taches/base.css` l.580-599 — `.tch .feuille` sans `transition` ; `.cran-50 { height: 50vh }`
  fixe ; la ligne l.1169 prévoit pourtant de couper l'animation en « réduire les animations ».
- Correction : nouvelles règles dans `saisie.css` (lane L4, pas `base.css`) : montée `translateY(100%) → 0` en
  `--motion-slow` + `@starting-style`, voile en fondu ; variante `cran-auto` (hauteur au contenu, plafond 85 %) posée
  par `FeuilleACrans` quand le contenu est court.
- Preuve : film image par image → la feuille monte en ~260 ms ; Alléger sans blanc sous ses boutons. Test :
  `ui/composants.test.jsx` (classe `cran-auto`).
- Fichiers : `ui/FeuilleACrans.jsx`, `styles/taches/saisie.css`.

**R2-049 · B · Be — Anneau de focus épais après un simple toucher**
- Relecteurs : B1 n°22 (moitié module ; le focus sur « Signaler un bug » à l'ouverture du Copilote est dans
  `features/ia`, hors module, § 2).
- Cause (lue) : `ui/FeuilleACrans.jsx` l.120 — `origine.current?.focus?.()` à la fermeture, sans `focusVisible: false`.
- Correction : rendre le focus avec `{ focusVisible: false }` quand l'ouverture ne venait pas du clavier.
- Preuve : toucher ⋯ > Alléger > fermer → pas d'anneau sur ⋯. Test : `ui/composants.test.jsx`.
- Fichiers : `ui/FeuilleACrans.jsx`.

**R2-050 · A · Be/S — Au bureau, fiche, bilan et Alléger sont des boîtes centrées qui cachent tout**
- Relecteurs : B2 n°1 + B2 n°2 (bilan, alléger) + B2 tableau de cohérence « forme des feuilles ».
- Cause (lue) : `FeuilleACrans` au bureau = `dialogue-bureau` (`base.css` l.775-781), 560 px au centre sous voile.
- Correction (choix C-2 appliqué) : variante `panneau-bureau` ≥ 1024 px : panneau fixe à droite (420 px, pleine
  hauteur, sans voile, la liste reste cliquable ; toucher une autre ligne change la fiche), règles dans `saisie.css` ;
  `Fiche`, bilan et Alléger passent `variante="panneau"` ; l'iPhone garde la feuille du bas.
- Preuve : bureau, ouvrir la fiche → la liste reste visible, la ligne surlignée, `j` puis Entrée change de fiche. Test :
  `ui/composants.test.jsx` ; spec `e2e/taches-bureau.spec.js`.
- Fichiers : `ui/FeuilleACrans.jsx`, `fiche/Fiche.jsx`, `styles/taches/saisie.css`. Le bilan et Alléger passent la
  variante depuis leurs fichiers (L2) — 1 ligne chacun, APRÈS le pli de L4 (ordre : L4 puis L2, ou L2 l'ajoute en dernier).

**R2-051 · B · Be — Contrôles de saisie : segmentés décalés, champ entre deux filets, puce « Nouveau projet » nue, débordement de l'aperçu**
- Relecteurs : B1 n°8 + B1 n°9 + B1 n°10 + B2 n°23 + F1 n°10 (2e moitié : `.feuille-corps` défile de travers).
- Cause (lue en partie) : `saisie.css` (marges du `radiogroup`, `box-shadow` haut/bas du champ) ; puce
  `.tch .puce.nouveau` (`base.css` l.956-958) peinte avec `--tch-point`/`--tch-bloc-fond`, posés par une couleur de
  projet qu'un projet nouveau n'a pas ; débordement de 24 px non isolé (largeur des lignes d'aperçu).
- Correction (dans `saisie.css` seulement) : segmentés à la gouttière, pleine largeur, `white-space: nowrap` ; champ
  sans filets ; règle `.tch .feuille-saisie .puce.nouveau` à fond et bord neutres + point ; `overflow-x: hidden` sur
  l'aperçu.
- Preuve : captures 390 px de la saisie et de l'aperçu de liste sans décalage. Test : spec `e2e/taches-saisie.spec.js`
  n'étant pas à L4, contrôle par capture + `ui/composants.test.jsx` si un attribut change.
- Fichiers : `styles/taches/saisie.css`.

**R2-021b · B — La fiche s'ouvre sur « Découper »** et **R2-025b · B — la fiche s'ouvre sur le titre ou l'heure**
- Cause (lue) : `lib/fiche.js::useOuvrirFiche` l.17-26 ne prend que l'identifiant.
- Correction : `useOuvrirFiche()(id, { section, focus })` pose `?tache=…&section=decouper` ou `&focus=titre|heure` ;
  `Fiche.jsx` déplie « Plus », fait défiler et met le curseur. À plier AVANT les moitiés L2 (R2-021, R2-025).
- Preuve : `?tache=12&section=decouper` → curseur dans Découper. Test : `fiche/Fiche.test.jsx`.
- Fichiers : `lib/fiche.js`, `fiche/Fiche.jsx`, `fiche/FichePlus.jsx`.

### Lane L5 — Projets, Tableau, Chronologie, Revue

**R2-060 · A · F — Sur iPhone, « Mettre en haut » est inatteignable (le ⋯ d'une ligne de projet est invisible)**
- Relecteurs : F2 n°1 + S1 n°18 (la pastille de priorité recouvre « Actions »).
- Cause (lue) : `styles/taches/base.css` l.1152-1159 — `.ligne-actions` à `opacity:0; pointer-events:none`, visible
  seulement au survol bureau ; `features/taches/projets/LigneProjet.jsx` l.109-126 : « Mettre en haut » n'existe que
  dans ce menu ; le ⋯ de l'écran du projet (`pages/taches/Projet.jsx`) ne l'a pas.
- Correction : dans `projets.css`, `@media (hover: none)` → `.tch .ligne.projet .ligne-actions` visible et touchable,
  placé APRÈS la pastille (plus de chevauchement) ; « Mettre en haut » ajouté au ⋯ de l'écran du projet ; appui long
  sur une ligne de projet = ce menu.
- Preuve : iPhone, Projets > ⋯ d'un projet > Mettre en haut → il passe en tête. Test : `pages/taches/Projets.test.jsx` ;
  spec `e2e/taches-projets.spec.js` en 390 px tactile.
- Fichiers : `styles/taches/projets.css`, `projets/LigneProjet.jsx`, `pages/taches/Projet.jsx`.

**R2-061 · A · F — Impossible de renommer un projet, changer sa couleur ou son échéance**
- Relecteurs : F2 n°2.
- Cause (lue) : `pages/taches/Projet.jsx` n'appelle `modifierProjet` que pour `affichage` (l.193), `priorite` (l.289),
  `statut` (l.300) ; le serveur accepte déjà `nom`, `couleur`, `echeance`, `objectif`
  (`serializers/projets.py::ProjetModificationSerializer` l.65-80) : correction 100 % front, aucun contrat touché.
- Correction : titre éditable au toucher (Entrée/sortie = enregistrer, Échap = annuler) ; « Couleur » et « Échéance »
  dans le ⋯ ; « Fini quand… » éditable en place.
- Preuve : renommer « Voyage Agadir » → nouveau nom partout (Projets, Proposé, saisie `#`). Test :
  `pages/taches/Projet.test.jsx`.
- Fichiers : `pages/taches/Projet.jsx`, `projets/Dialogues.jsx`.

**R2-062 · A · F — Dans « Planifier le projet », les « Étapes » tapées deviennent des tâches**
- Relecteurs : F2 n°3.
- Cause (lue) : `projets/PlanifierProjet.jsx` l.113-118 — le champ « Étapes » est lu par `saisie/plan.py::decouper_plan`
  (via `serializers/projets.py` l.301), qui exige un « : » en fin de ligne pour une étape (`regles.md` §1.10) ; rien ne
  le dit à l'écran.
- Correction : dans CE champ, une ligne non indentée sans puce = une étape ; ses lignes indentées ou à tiret = ses
  tâches (paramètre `mode='etapes'` de `decouper_plan`) ; l'aperçu dit « 3 étapes · 0 tâche ».
- Preuve : « Transport / Hébergement / Sur place » → 3 étapes créées. Tests : `tests/test_api_projets.py`,
  `projets/PlanifierProjet.test.jsx`.
- Fichiers : `saisie/plan.py`, `serializers/projets.py`, `projets/PlanifierProjet.jsx`, tests cités.

**R2-063 · A · F — L'ordre des tâches d'un projet ne se change pas (il décide pourtant ce qui remonte dans Proposé)**
- Relecteurs : F2 n°3b + S2 A9 (« Déplacer… » se lit « dans le temps »).
- Cause (lue) : `ui/Tableau.jsx::surFin` l.101-107 ne sait que changer de colonne ; `projets/VueListe.jsx` n'a aucun
  réordonnancement ; le serveur sait déjà réordonner (`services/taches.py::reordonner_tache`, liste `'projet'`
  l.759-776 ; `api/tachesApi.js::reordonnerTache` l.179) — correction front seulement.
- Correction : glisser pour réordonner dans la Liste et dans une colonne du Tableau (`reordonnerTache(id, {liste:'projet',
  avant_id, apres_id})`) ; « Monter / Descendre » dans le menu d'une ligne de projet (iPhone) ; dans
  `ui/ActionsLigne.jsx`, « Déplacer… » devient « Changer de projet… ».
- Preuve : monter « Préparer le matériel » en tête → elle devient la prochaine action dans Proposé. Test :
  `pages/taches/Projet.test.jsx` ; spec `e2e/taches-projets.spec.js`.
- Fichiers : `ui/Tableau.jsx`, `projets/VueListe.jsx`, `ui/ActionsLigne.jsx`, `pages/taches/Projet.jsx`.

**R2-064 · A · Be/F — Tableau d'un projet coupé à 2 colonnes et demie, la dernière inatteignable**
- Relecteurs : B2 n°4 + B2 n°8.
- Cause (lue) : `styles/taches/projets.css` l.196 `.ep-tableau { … overflow: hidden }` au bureau, dans la page de 760 px
  (`base.css` l.24).
- Correction : dans `projets.css`, la vue Tableau/Chronologie sort du 760 px (`.tch[data-ecran="projet"] .tch-page`
  élargie quand la vue est Tableau ou Chronologie) ; `overflow-x: auto` ; colonnes de 260 px, cartes ≥ 240 px.
- Preuve : bureau 1440 → 4 colonnes lisibles, « Pose » visible. Test : spec `e2e/taches-projets.spec.js`.
- Fichiers : `styles/taches/projets.css`.

**R2-065 · B · S — « Dupliquer » et « Utiliser ce modèle » : le premier « Créer » ne crée rien**
- Relecteurs : F2 n°19.
- Cause (lue) : `projets/Dialogues.jsx` l.353-392 — « un Créer sans aperçu à jour LIT l'aperçu seulement » ; le nom part
  vide.
- Correction : nom prérempli « {nom} (copie) », aperçu lu à l'ouverture et à chaque changement, un seul « Créer » qui
  écrit.
- Preuve : Dupliquer > Créer → le projet existe au premier toucher. Test : `projets/Dialogues.test.jsx`.
- Fichiers : `projets/Dialogues.jsx`.

**R2-066 · B · Be — La Chronologie ne montre ni étapes sans date ni tâches datées**
- Relecteurs : F2 n°20 + B2 n°17 (pastilles qui débordent du cadre).
- Cause (lue) : `projets/VueChronologie.jsx` l.9-14 — ne dessine que les étapes DATÉES, le jalon, aujourd'hui et
  l'échéance ; pastilles centrées sans borne.
- Correction : tâches datées en points sur la frise, groupées par étape ; étape sans dates = bande « Sans date »
  (maquette `projet-chronologie.html`) ; pastilles bornées au cadre.
- Preuve : « Chantier Benali » → 4 étapes, tâches du 20, 21, 28 visibles. Test : `projets/VueChronologie.test.jsx`.
- Fichiers : `projets/VueChronologie.jsx`, `styles/taches/projets.css`.

**R2-067 · B · Be/S — Projet ouvert : retour sous le titre, 4 « + Ajouter » bleus, pas de liste à côté au bureau**
- Relecteurs : B2 n°19 + B1 n°7 (partie Projet) + état des lieux « Projets au bureau sans maître-détail ».
- Cause (lue en partie) : la coquille rend le titre avant ses enfants (`CoquilleTaches.jsx` l.243-264) et
  `ui/BarreRetourProjets.jsx` est un enfant de la page ; « + Ajouter une tâche » par étape dans `pages/taches/Projet.jsx`.
- Correction (choix C-4 appliqué) : bureau ≥ 1024 px, Projets en maître-détail (liste à gauche, projet surligné, projet
  à droite) ; « ‹ Projets » passe AU-DESSUS du titre par la prop `retour` de la coquille (R2-093, L6, à plier avant) ;
  « + Ajouter » gris, visible au survol de l'étape.
- Preuve : bureau, cliquer un projet puis un autre sans retour. Tests : `pages/taches/Projets.test.jsx`,
  `pages/taches/Projet.test.jsx`.
- Fichiers : `pages/taches/Projets.jsx`, `pages/taches/Projet.jsx`, `ui/BarreRetourProjets.jsx`, `styles/taches/projets.css`.

**R2-068 · B · S/Be — Revue de la semaine : repart à 1/N, intention demandée 5 fois, pas de résumé**
- Relecteurs : F2 n°12 + S2 C2 + B1 n°20 + S1 n°16 (partie Revue). Les phrases du serveur sont en L3 (R2-034).
- Cause (lue) : `pages/taches/Revue.jsx` — chaque `Carte` porte son propre état `intention` (l.53) ; la position dans la
  revue n'est pas gardée.
- Correction : revue déjà décidée cette semaine → résumé + « Planifier ma semaine » ; revue interrompue → reprise à la
  première carte non décidée ; une seule intention, en tête ; Garder/Pause/Terminer en segmenté + « Suivant → ».
- Preuve : décider 5 projets, recharger → résumé. Test : `pages/taches/Revue.test.jsx`.
- Fichiers : `pages/taches/Revue.jsx`, `styles/taches/projets.css`.

**R2-069 · C · Be — Planifier le projet : pas d'étapes visibles, date native anglaise, deux dessins de « choisi »**
- Relecteurs : B1 n°19 + B2 n°25 + F2 n°23 (action non retirable ; tâche née d'un risque titrée par la phrase du risque).
- Cause : `projets/PlanifierProjet.jsx` + `projets.css` (non relus ligne à ligne).
- Correction : barre d'étapes, priorités en 3 colonnes, « Suivant » fixe en bas, durées en puces, même dessin de
  sélection ; × par action ; titre « Parer : … ».
- Preuve : captures 390 et 1440 px du rituel. Test : `projets/PlanifierProjet.test.jsx`.
- Fichiers : `projets/PlanifierProjet.jsx`, `styles/taches/projets.css`.

**R2-070 · B · F — Hors ligne, Projets dit « Aucun projet » ; en chargement, rien**
- Relecteurs : B1 n°15 (état vide trompeur) + B1 n°14 (partie Projets/Projet).
- Cause (lue) : `pages/taches/Projets.jsx` l.247-252 — sans réponse, « Aucun projet » ; pas de cache hors ligne pour les
  projets (il existe pour la journée : `horsligne/cacheJournee.js`).
- Correction : garder la dernière liste lue (même mécanisme que `cacheJournee`, sans modifier ce fichier) et l'afficher
  hors ligne ; squelette tant que rien n'est lu ; jamais « Aucun projet » sans réponse du serveur.
- Preuve : hors ligne, onglet Projets → les 5 projets. Test : `pages/taches/Projets.test.jsx`.
- Fichiers : `pages/taches/Projets.jsx`, `pages/taches/Projet.jsx`.

**R2-071 · C · Be/S — Projet vide et priorité « — »**
- Relecteurs : B1 n°25 + S1 n°19.
- Cause (lue) : `projets/LigneProjet.jsx::PuchePriorite` l.61-82 affiche « — » pour 0.
- Correction : « Aucune » écrit ; projet vide → invite « Ajoute la première tâche » + « Planifier le projet ».
- Preuve : nouveau projet sans rituel → pastille « Aucune ». Test : `pages/taches/Projets.test.jsx`.
- Fichiers : `projets/LigneProjet.jsx`, `pages/taches/Projet.jsx`.

**R2-036 (part Projet)** — brancher `useClavierListe` sur la liste d'un projet (`pages/taches/Projet.jsx`).
**R2-085 (part Projets)** — la page Projets ne passe plus la date du jour en sous-titre (`pages/taches/Projets.jsx`).

### Lane L6 — Enveloppe du module (coquille + `base.css`)

Tout ce qui touche l'enveloppe de l'ERP se fait d'ICI, par des sélecteurs `:has(.tch)` dans `styles/taches/base.css`
(le module le fait déjà : `.layout-content:has(> .route-fade > .tch)` l.941) — aucun fichier de l'ERP n'est modifié.

**R2-080 · A · Be/S — Sur iPhone, la barre de l'ERP mange le haut de chaque écran (fil coupé, deux Copilote, icône invisible en sombre)**
- Relecteurs : B1 n°1 + B1 n°2 + S1 n°7 + S2 T1 (+ état des lieux « deux Copilote »).
- Cause (lue) : la coque de l'ERP (`components/layout/Header.jsx` l.119, `header.header`) reste au-dessus de la
  coquille ; le bouton menu est peint `#0f172a` en dur (`styles/deploy/12-progression-mobile.css` l.37-41 : 1,03:1 en
  sombre).
- Correction (choix C-6 appliqué) : `@media (max-width: 767px)`, `.layout:has(.tch) .header { display: none }` ; la
  coquille ajoute à gauche de son en-tête un bouton ☰ qui ouvre le tiroir de l'ERP (clic programmatique sur
  `.header-menu-btn`, ou un événement du Layout s'il en existe — à vérifier) ; le grand titre se replie en titre compact
  collant au défilement. Bureau inchangé.
- Preuve : iPhone, Aujourd'hui → titre en haut de l'écran, un seul Copilote, ☰ ouvre le menu de l'ERP. Test :
  `features/taches/routes.test.jsx` (bouton ☰ rendu) ; spec `e2e/taches-a11y.spec.js` en 390 px.
- Fichiers : `coquille/CoquilleTaches.jsx`, `styles/taches/base.css`.

**R2-081 · A · Be — Le fond blanc s'arrête au milieu de l'écran ; au bureau, une « carte » à angles vifs**
- Relecteurs : B1 n°5 + B2 n°10.
- Cause (lue) : `base.css` l.24 — `.tch .tch-page { max-width: 760px; …; background: var(--tch-surface) }` sans hauteur
  minimale, posée sur le gris de l'ERP.
- Correction : une seule surface jusqu'en bas (fond `--tch-surface` sur `.layout-content:has(> .route-fade > .tch)`, ou
  `min-height`) ; au bureau, pas de carte (contenu sur le fond, comme Things).
- Preuve : Supprimées / Réglages / Recherche vides → aucune cassure grise. Test : spec `e2e/taches-a11y.spec.js`
  (couleur du bas de page).
- Fichiers : `styles/taches/base.css`.

**R2-082 · A · Be — Interrupteurs déformés en « gouttes » sur iPhone**
- Relecteurs : B1 n°3.
- Cause (lue) : `styles/deploy/01-base.css` l.273-278 — `@media (pointer: coarse) { button, [role="button"] … {
  min-height: 44px } }` étire `.tch .interrupteur` (51 × 31, `base.css` l.989).
- Correction : `.tch .interrupteur { min-height: 0 }` dans `base.css` (la cible de 44 pt existe par `::after`) ; passer
  en revue les autres petits boutons du module (cases de l'agenda : R2-104, L7).
- Preuve : Réglages > Notifications sur iPhone → 51 × 31, pastille centrée. Test : spec `e2e/taches-a11y.spec.js`
  (tactile).
- Fichiers : `styles/taches/base.css`.

**R2-083 · B · Be — Bande grise en dégradé sur le bord gauche de chaque écran iPhone**
- Relecteurs : B1 n°6.
- Cause (lue) : `styles/deploy/12-progression-mobile.css` l.326-328 — le tiroir fermé (`translateX(-105%)`) garde son
  ombre `8px 0 28px`, qui déborde dans l'écran. Défaut de TOUTE l'ERP (signalé § 2).
- Correction (depuis le module) : `.layout:not(.drawer-open):has(.tch) .sidebar { box-shadow: none }` sous 768 px.
- Preuve : capture 390 px, bord gauche net. Test : spec `e2e/taches-a11y.spec.js`.
- Fichiers : `styles/taches/base.css`.

**R2-084 · B · Be/S — Le bouton + flottant apparaît partout et couvre du contenu**
- Relecteurs : B1 n°18 + S1 n°18 (couvre « Moyenne » et « En réserve »).
- Cause (lue) : `CoquilleTaches.jsx` l.267-273 — le + est rendu sur tout écran sans sélection.
- Correction : + seulement sur Aujourd'hui (journée non vide), À trier, Projets, Projet, Agenda hors `placer=1` (lu dans
  `params`) ; marge basse sous le dernier élément égale à la hauteur du +.
- Preuve : Planifier le projet, Revue, Réglages → pas de +. Test : `features/taches/routes.test.jsx`.
- Fichiers : `coquille/CoquilleTaches.jsx`, `styles/taches/base.css`.

**R2-085 · B · Be — Au bureau, deux largeurs de page et un titre qui saute d'un écran à l'autre**
- Relecteurs : B2 n°9 + B2 n°11 + B2 cohérence (« largeur de page », « date en tête »).
- Cause (lue) : `base.css` l.24 (760 px centrés) contre `coeur.css` l.192 (1320 px pour Aujourd'hui) ; sur-titre présent
  ou absent selon l'écran.
- Correction : titre toujours au même x (colonne de lecture alignée à gauche, 720 px ; l'espace à droite sert au panneau
  R2-050) ; hauteur d'en-tête fixe (sur-titre réservé même vide). La date sur Projets est retirée par L5.
- Preuve : Aujourd'hui → À trier → Projets : `h1` au même pixel. Test : spec `e2e/taches-a11y.spec.js`.
- Fichiers : `styles/taches/base.css`, `coquille/CoquilleTaches.jsx`.

**R2-086 · B · S — Recherche : deux champs empilés et une loupe qui ouvre… la recherche**
- Relecteurs : B2 n°22 + B1 n°23 (partie en-tête).
- Cause (lue) : `CoquilleTaches.jsx` l.246-260 — loupe et `SaisieBureau` rendues sur tous les écrans.
- Correction : sur `ecran === 'recherche'`, ni loupe ni « Ajouter une tâche ».
- Preuve : Recherche → un seul champ. Test : `features/taches/routes.test.jsx`.
- Fichiers : `coquille/CoquilleTaches.jsx`.

**R2-087 · B · S — « ? » n'affiche pas les touches de Tâches ; « / » ne fait rien**
- Relecteurs : S2 B3 (la partie « g + lettre pour les 4 onglets » est écartée, § 2).
- Cause (lue en partie) : `reference/textes.md` l.99 promet « `n` Ajouter ici · `/` Chercher · Espace Fait … » ; `?`
  ouvre l'aide générale de l'ERP (`providers/shortcuts.js`, hors module, non relu).
- Correction (depuis le module) : la coquille intercepte `?` et `/` dans `/taches` (écouteur `document`, hors champ et
  hors feuille) : `?` ouvre une feuille « Touches de Tâches » (ligne §99 de `textes.md`) ; `/` va à la Recherche.
- Preuve : `?` sur Aujourd'hui → les touches du module. Test : `features/taches/routes.test.jsx`.
- Fichiers : `coquille/CoquilleTaches.jsx`.

**R2-088 · B · F — « Messages sans délai » allumé : le toast part quand même**
- Relecteurs : F2 n°21.
- Cause (lue) : `configurerGestes` (`lib/gestes.js` l.65) n'est appelé que par `pages/taches/Reglages.jsx` l.98 et l.109 :
  le réglage ne vaut qu'après un passage dans Réglages.
- Correction : la coquille lit les réglages une fois au montage et appelle `configurerGestes`.
- Preuve : réglage allumé, recharger Aujourd'hui, cocher → « Annuler » encore là à 30 s. Test : `lib/gestes.test.js`
  n'est pas touché ; test dans `features/taches/routes.test.jsx`.
- Fichiers : `coquille/CoquilleTaches.jsx`.

**R2-089 · B · Be — Chargement : squelette des tableaux de bord de l'ERP ; erreur : trois toasts empilés**
- Relecteurs : B2 n°18 + B1 n°14 (Agenda).
- Cause (lue en partie) : `ui/ChargementTardif.jsx` n'est qu'un indicateur tardif ; le squelette vu vient du fondu de
  route de l'ERP (non relu).
- Correction : `ChargementTardif` rend des squelettes en lignes de tâches (maquette `etat-chargement.html`) dès 300 ms ;
  une seule bannière d'erreur en tête de liste.
- Preuve : réseau ralenti → squelette en lignes. Test : `ui/composants.test.jsx` n'est pas à cette lane → nouveau voisin
  `ui/ChargementTardif.test.jsx`.
- Fichiers : `ui/ChargementTardif.jsx`, `styles/taches/base.css`.

**R2-090 · B · S — Hors ligne : quatre messages empilés**
- Relecteurs : B1 n°15 (empilement) + état des lieux « bandeau orange de l'ERP ET ligne de Tâches ».
- Cause (lue en partie) : ligne « Hors ligne · dernière synchro » de la coquille (l.230-238) + bandeau orange de l'ERP
  (hors module, classe non relevée) ; l'empilement des toasts est à reproduire.
- Correction : `.layout:has(.tch)` masque le bandeau hors ligne de l'ERP ; un seul signal, celui du module.
- Preuve : couper le réseau → une seule ligne « Hors ligne ». Test : spec `e2e/taches-a11y.spec.js` (`setOffline`).
- Fichiers : `styles/taches/base.css`, `coquille/CoquilleTaches.jsx`.

**R2-091 · C · Be — Onglet actif or sur blanc (3,25:1, libellé 9,9 px)**
- Relecteurs : B1 n°11 (contraste ; l'ordre « Apps » est écarté, § 2).
- Cause (lue) : couleur de l'onglet actif de l'ERP (`styles/deploy/34-pouce-ody.css` l.54-59, hors module).
- Correction (depuis le module) : `.layout:has(.tch) .bottom-tabbar--app` — onglet actif ≥ 4,5:1, libellé ≥ 10 pt.
- Preuve : contraste mesuré ≥ 4,5. Test : spec `e2e/taches-a11y.spec.js`.
- Fichiers : `styles/taches/base.css`.

**R2-092 · C · Be — Un seul langage : tailles de titres, ors, « sélectionné », densité**
- Relecteurs : B1 n°28 + B1 n°29 + B2 tableau de cohérence (boutons, priorité, pastille, sélectionné, titres) + S2 A10
  (moitié CSS : R2-018b).
- Cause (lue) : jetons `--tch-*` de `base.css` (titre de section 17 px = titre de tâche 17 px).
- Correction : sections 15 px / 650 doux ; 4 tailles au plus ; un or de marque + une variante texte ; « sélectionné » =
  fond d'accent léger partout ; méta sur la ligne du titre quand la classe de R2-018 est posée.
- Preuve : captures avant/après des 10 écrans (aucun test automatique utile).
- Fichiers : `styles/taches/base.css`.

**R2-093 · B · Be — Écrans enfants : retour SOUS le titre, loupe et Copilote répétés**
- Relecteurs : B1 n°7.
- Cause (lue) : `CoquilleTaches.jsx` l.227-258 — pas d'emplacement « retour » au-dessus du titre ; mêmes actions partout.
- Correction : prop `retour={{ libelle, vers }}` rendue AU-DESSUS du titre ; écran enfant = ni loupe ni Copilote. Les
  pages passent la prop APRÈS le pli de L6 : Projet (L5, R2-067), sous-pages de Réglages (L8, R2-128).
- Preuve : Projet → « ‹ Projets » en haut, titre sur une ligne dessous. Test : `features/taches/routes.test.jsx`.
- Fichiers : `coquille/CoquilleTaches.jsx`, `styles/taches/base.css`.

**R2-094 · C · Be — Focus clavier d'une ligne : anneau collé aux lettres qui mord sur l'heure**
- Relecteurs : B2 n°26.
- Cause (lue) : `base.css` l.1146 et l.1113 (`.ligne-corps-bouton`, anneau sur le seul texte).
- Correction : ligne entière encadrée (`.tch .ligne:has(.ligne-corps-bouton:focus-visible)`), fond de survol.
- Preuve : Tab sur Aujourd'hui → la ligne entière encadrée. Test : spec `e2e/taches-a11y.spec.js`.
- Fichiers : `styles/taches/base.css`.

**R2-018b** — la règle CSS « méta sur la ligne du titre » (moitié de R2-018) est faite dans R2-092 (`base.css`).

### Lane L7 — Agenda et Planifier ma semaine

**R2-100 · A · F — Sur iPhone, la Semaine cache les rendez-vous de l'agenda externe**
- Relecteurs : F2 n°15.
- Cause (lue) : `pages/taches/Agenda.jsx::SemaineListe` l.375-399 — un jour ne liste que `toute_la_journee`, `blocs`,
  `sans_heure` ; `j.externes` est ignoré (la charge de `PlanifierSemaine.jsx::resume` ne les déduit pas — à vérifier).
- Correction : rendez-vous (heure + titre, lecture seule) dans chaque jour, déduits du temps libre.
- Preuve : semaine suivante, mar. 24 → « 14:30 Rendez-vous … », temps libre réduit. Test : `pages/taches/Agenda.test.jsx`.
- Fichiers : `pages/taches/Agenda.jsx`, `agenda/PlanifierSemaine.jsx`.

**R2-101 · A · F — À venir montre deux fois la même tâche le jour de son échéance**
- Relecteurs : F2 n°16.
- Cause (lue) : `Agenda.jsx::ListeDuJour` l.273-277 ajoute `jour.echeances` aux lignes ALORS QUE `ToutesLaJournee`
  l.248-258 les montre déjà en puce « · échéance » ; le filtre ne retire que celles qui ont un bloc ce jour-là.
- Correction : le jour d'échéance, la puce seule.
- Preuve : « Envoyer le devis révisé » (prévue jeu. 9 h, échéance ven.) → vendredi : une puce. Test : `Agenda.test.jsx`.
- Fichiers : `pages/taches/Agenda.jsx`.

**R2-102 · A · F — « 3 faites » ici, « 4 » là pour le même mercredi**
- Relecteurs : F2 n°9.
- Cause (lue) : `Agenda.jsx::teteJour` l.338-344 compte les faites PARMI les tâches prévues ce jour-là ; Mon rythme et
  la Revue comptent les tâches finies ce jour-là.
- Correction (règle C-12) : « faites » = finies ce jour-là, partout ; le serveur sert `faites_nb` par jour dans
  `agenda/` (contrat `contract_samples/agenda.json` d'abord, même lane, règle PACT10) ; Agenda et Planifier ma semaine
  l'affichent.
- Preuve : 4 finies le 18 → Agenda Semaine dit « 4 faites ». Tests : `tests/test_api_agenda.py`, `Agenda.test.jsx`,
  `agenda/PlanifierSemaine.test.jsx`.
- Fichiers : `views/agenda.py` (ou la fonction qui bâtit les jours, à relever), `contract_samples/agenda.json`,
  `Agenda.jsx`, `agenda/PlanifierSemaine.jsx`, tests cités.

**R2-103 · A · F — Le vendredi, « Planifier ma semaine » planifie la semaine qui finit**
- Relecteurs : S2 C1 (horloge du navigateur avancée ; la plage est calculée côté navigateur, le défaut est réel) + S2 C2
  (pas d'entrée dans le ⋯ de l'Agenda).
- Cause (lue) : `Agenda.jsx` l.652-656 et `periodeDe` l.68-78 — la semaine de `jour` (aujourd'hui par défaut), sans
  navigation en mode planifier ; `actionsEcran` l.785 n'a que « Mes agendas ».
- Correction : à partir du jeudi 15 h (ou venant de la Revue), le mode s'ouvre sur la semaine SUIVANTE ; flèches ‹ › ;
  « Planifier ma semaine » ajouté au ⋯ de l'Agenda.
- Preuve : vendredi → « 23 – 29 novembre ». Test : `Agenda.test.jsx` (aujourd'hui = vendredi).
- Fichiers : `pages/taches/Agenda.jsx`.

**R2-104 · A · Be — Cases à cocher des blocs horaires en pilules verticales sur iPhone**
- Relecteurs : B1 n°4.
- Cause (lue) : même règle tactile globale que R2-082 (`deploy/01-base.css` l.273-278) sur `.tch .ag-bc`
  (`agenda.css` l.98).
- Correction : `.tch .ag-bc { min-height: 0 }` dans `agenda.css` (cible gardée par `::after`, l.102).
- Preuve : Agenda Jour iPhone → ronds. Test : nouvelle spec `e2e/taches-agenda.spec.js` (tactile, hauteur ≤ 20).
- Fichiers : `styles/taches/agenda.css`, `e2e/taches-agenda.spec.js`.

**R2-105 · B · S — Placer une tâche sur iPhone : volet sous la grille, aide de bureau, pas de déplacement**
- Relecteurs : F2 n°10 + S2 C3.
- Cause (lue en partie) : aide « Glisse une tâche sur un jour · ou Entrée puis ← → » (`agenda/PlanifierSemaine.jsx` l.150
  et l.168) ; volet rendu après la grille (`Agenda.jsx::VueJour` l.298-307).
- Correction : sur iPhone, aide « Touche une tâche, puis un jour (ou un créneau) » ; après le choix, la vue revient sur
  la grille près de l'heure courante (ou une feuille « Quel jour ? ») ; toucher un bloc posé → « Déplacer » puis un
  créneau.
- Preuve : iPhone, 3 tâches placées sans défilement manuel. Tests : `agenda/PlanifierSemaine.test.jsx`,
  `ui/VoletAPlacer.test.jsx`.
- Fichiers : `agenda/PlanifierSemaine.jsx`, `ui/VoletAPlacer.jsx`, `ui/GrilleAgenda.jsx`, `pages/taches/Agenda.jsx`.

**R2-106 · B · F — Poser sur aujourd'hui une tâche « À revoir » la laisse dans À revoir**
- Relecteurs : F2 n°14.
- Cause (lue) : le placement appelle `planifierTache` (`Agenda.jsx::usePlacement`) ; `moteur/classement.py::reportee_3_fois`
  l.205-208 la garde dans À revoir tant que `reports_tranches` n'a pas bougé (seul `trancher/` le fait).
- Correction : élément portant `motif === 'reportee_3_fois'` (champ présent dans `contract_samples/agenda.json`) →
  placement par `trancher/` avec le jour choisi.
- Preuve : placer « Mettre à jour le planning des poses » sur aujourd'hui → dans Prévu. Test : `Agenda.test.jsx`.
- Fichiers : `pages/taches/Agenda.jsx`.

**R2-107 · B · Be/F — Mode « placer » : tous les créneaux écrits « Placer à HH:MM » ; 60 Tab dans des créneaux vides**
- Relecteurs : B2 n°15 + S2 B7.
- Cause (lue) : `agenda.css` l.91-92 `.ag-creneau-vide.cible span { opacity: 1 }` ; `ui/GrilleAgenda.jsx::Creneaux`
  l.155-180 rend un bouton focalisable par créneau, même sous les blocs.
- Correction : libellé seulement au survol/focus du créneau ; un seul arrêt de Tab pour la grille (flèches dedans) ;
  aucun créneau sous un bloc.
- Preuve : clic sur une tâche d'À placer → grille propre ; Tab depuis le haut atteint le menu en < 15 arrêts. Test :
  `Agenda.test.jsx`.
- Fichiers : `ui/GrilleAgenda.jsx`, `styles/taches/agenda.css`.

**R2-108 · B · Be — Planifier ma semaine au bureau : colonnes de 110 px, texte qui déborde, week-end chargé à 64 px**
- Relecteurs : B2 n°5 + B2 n°20 + B1 « défauts des maquettes » (gouttière de 8 px).
- Cause : grille de semaine dans `agenda.css` (non relue ligne à ligne).
- Correction : colonnes ≥ 160 px, panneau « À placer » ≤ 360 px, cartes tronquées par « … », week-end étroit seulement
  s'il est vide, une gouttière.
- Preuve : capture 1440 px sans débordement. Test : `e2e/taches-agenda.spec.js`.
- Fichiers : `styles/taches/agenda.css`, `agenda/PlanifierSemaine.jsx`.

**R2-109 · B · Be — Mois : des points seulement au bureau ; week-end teinté sur une seule semaine**
- Relecteurs : B2 n°6 + B1 n°17.
- Cause (lue) : `agenda/VueMois.jsx` l.64 pose `repos` seulement si `jour && !jour.ouvre` ; un jour absent de la réponse
  prend `jourVide` (`Agenda.jsx` l.106) qui vaut `ouvre: true`.
- Correction : `ouvre` d'un jour vide déduit des jours travaillés servis ; au bureau, titres des tâches dans les cases
  (3 au plus, « +n »).
- Preuve : Mois → toutes les colonnes sam./dim. teintées ; titres visibles au bureau. Test : `Agenda.test.jsx`.
- Fichiers : `agenda/VueMois.jsx`, `pages/taches/Agenda.jsx`, `styles/taches/agenda.css`.

**R2-110 · B · Be — Jour au bureau : en-tête empilé, la grille commence à 575 px**
- Relecteurs : B2 n°7.
- Cause (lue) : `Agenda.jsx::VueJourGrille` l.310-331 empile bande des 7 jours, Toute la journée, Sans heure, puis grille.
- Correction : au bureau, en-tête sur une ligne, pas de bande des 7 jours, tâches sans heure dans « À placer » à droite.
- Preuve : 1440 × 900 → 07:00 visible sous 200 px. Test : `e2e/taches-agenda.spec.js`.
- Fichiers : `pages/taches/Agenda.jsx`, `styles/taches/agenda.css`.

**R2-111 · B · Be — « Toute la journée » écrit sur 3 lignes hors de la gouttière**
- Relecteurs : B1 n°16 + B2 n°24.
- Cause (lue) : `.tch .ag-tj-label` (`agenda.css` l.23) dans une colonne étroite.
- Correction : libellé au-dessus des puces, sur une ligne, dans la gouttière.
- Preuve : À venir iPhone et bureau (capture).
- Fichiers : `styles/taches/agenda.css`.

**R2-112 · B · Be — Toucher un rendez-vous : bulle coupée, « Ouvrir dans ton agenda » qui n'est pas un lien**
- Relecteurs : F2 n°17.
- Cause : bulle de `ui/GrilleAgenda.jsx` (non relue ligne à ligne).
- Correction : bulle de largeur fixe ; lien réel si l'agenda fournit une adresse, sinon la phrase retirée.
- Preuve : clic sur le rendez-vous → titre entier. Test : `Agenda.test.jsx`.
- Fichiers : `ui/GrilleAgenda.jsx`.

**R2-113 · C · Be — Blocs côte à côte coupés net, sans « … »**
- Relecteurs : B2 n°16 (+ cascade connue de l'état des lieux).
- Cause (lue) : `base.css` l.962-967 (titre de bloc sur 2 lignes) ; les blocs étroits n'ont pas de règle propre.
- Correction : dans `agenda.css`, titre sur une ligne terminé par « … » quand le bloc est étroit.
- Preuve : blocs 09:00-11:00 et 10:00-10:30 → « Appeler le fourn… » (capture).
- Fichiers : `styles/taches/agenda.css`.

**R2-114 · C · S — Jour trop chargé dans Planifier ma semaine, sans alerte**
- Relecteurs : F2 n°11.
- Cause : `agenda/PlanifierSemaine.jsx` (seul un segment devient orange).
- Correction : « 3 h 30 de trop » écrit sur la ligne du jour.
- Preuve : vendredi à 7 h 30 pour 4 h → phrase visible. Test : `agenda/PlanifierSemaine.test.jsx`.
- Fichiers : `agenda/PlanifierSemaine.jsx`.

**R2-031b** — même règle de pause que R2-031 pour l'agenda : une tâche d'un projet en pause prévue ce jour-là reste
dans `agenda/` (`views/agenda.py`) ; test `tests/test_api_agenda.py`.

### Lane L8 — Mon rythme, Réglages, Recherche, Supprimées, Mon iPhone

**R2-120 · A · F — « Les 10 derniers jours travaillés » : 6 barres, jours absents, lettres ambiguës**
- Relecteurs : F2 n°6 + S1 n°16 (partie Mon rythme).
- Cause (lue en partie) : `pages/taches/Rythme.jsx` l.206-215 — titre fixe « 10 derniers jours » et barres prises dans
  `serie` (`evalue` ou `sans_donnees`) ; F2 a lu dans l'API 6 entrées seulement (jours sans données non servis) ; la
  fonction serveur qui bâtit `serie` n'est pas relue (`selectors/rythme.py` probable).
- Correction : le serveur sert les 10 derniers jours travaillés, `sans_donnees` compris ; barre vide nommée ;
  « lun. / mar. / mer. » au lieu d'une lettre.
- Preuve : compte de F2 → 10 barres dont 4 vides. Tests : `tests/test_api_rythme.py`, `pages/taches/Rythme.test.jsx`.
- Fichiers : `selectors/rythme.py`, `pages/taches/Rythme.jsx`, tests cités.

**R2-121 · B · F — « Garder ce rythme : environ 6 » ne dit pas qu'il est provisoire**
- Relecteurs : F2 n°4 (reclassé B : le chiffre suit la règle §6.6 — palier courant tant que R n'est pas fixée ; il
  manque la mention).
- Cause (lue) : `pages/taches/Rythme.jsx` l.77-80 écrit la phrase sans « À confirmer… » ; le serveur a le texte
  (`moteur/gabarits.py` l.341-343, clé `garder_ce_rythme.provisoire`, choisie par `services/rythme.py` l.246) ; le toast
  vu par F2 ne la portait pas (à reproduire).
- Correction : la page lit `tenir_fixee_le` (ou la source) et ajoute « provisoire, à confirmer sur 14 jours ».
- Preuve : compte neuf → Garder ce rythme → « provisoire » visible. Test : `pages/taches/Rythme.test.jsx`.
- Fichiers : `pages/taches/Rythme.jsx`.

**R2-122 · B · F — Essayer les modes efface l'objectif et le graphe**
- Relecteurs : F2 n°5.
- Cause (lue) : `moteur/rythme.py::_vers_pousser` l.433-435 — Sans objectif → En faire plus avec moins de 10 jours =
  démarrage à froid (palier nul → « valeur par défaut ») ; `Rythme.jsx` l.328-329 masque le graphe dès que
  `source === 'defaut'`.
- Correction (choix C-7 appliqué) : revenir à « En faire plus » rend le dernier palier (garder le palier en passant en
  libre) ; le graphe ne dépend jamais de la source de l'objectif.
- Preuve : 6 → Garder → Sans objectif → En faire plus → « 6 », graphe visible. Tests : `tests/test_rythme_pur.py`,
  `pages/taches/Rythme.test.jsx`.
- Fichiers : `moteur/rythme.py`, `pages/taches/Rythme.jsx`, tests cités.

**R2-123 · B · F/Be — « Mes jours » montre 7 jours allumés alors que samedi et dimanche ne comptent pas**
- Relecteurs : F2 n°7.
- Cause (lue) : `rythme/MesJours.jsx` l.58 — sans préférence, `TOUS_LES_JOURS` ('1111111') ; côté serveur, le masque par
  défaut est « tous » mais le calendrier de la société retire le week-end (`selectors/base.py` l.24, l.119-122).
- Correction : afficher les jours RÉELLEMENT travaillés (masque ∩ calendrier de la société, servis par `rythme/` —
  contrat `contract_samples/rythme.json` d'abord) ; état choisi en fond plein.
- Preuve : compte neuf → lun.-ven. allumés. Tests : `tests/test_api_rythme.py`, `pages/taches/Rythme.test.jsx`.
- Fichiers : `rythme/MesJours.jsx`, `views/rythme.py` (ou son sérialiseur), `contract_samples/rythme.json`.

**R2-124 · B · S — « Qu'ai-je fini cette semaine ? » n'a pas de réponse**
- Relecteurs : S1 n°11 (« 7 jours » = 7 jours À VENIR).
- Cause : filtre de `pages/taches/Recherche.jsx` (non relu ligne à ligne).
- Correction : filtre « Faites cette semaine » (liste par jour, comme le Journal de Things) ; « 7 jours » renommé
  « 7 prochains jours ».
- Preuve : Recherche > Faites cette semaine → les tâches finies, groupées par jour. Test : `pages/taches/Recherche.test.jsx`.
- Fichiers : `pages/taches/Recherche.jsx`.

**R2-125 · B · S — « Derniers gestes » sans nom de tâche, caché sous « Supprimées récemment », vide 3 s**
- Relecteurs : S1 n°12 + F1 n°17 g.
- Cause (lue) : `pages/taches/Supprimees.jsx` l.144-150 affiche `geste.message` seul (« Faite ») ; aucun état de
  chargement.
- Correction : chaque geste avec le titre de la tâche (servi par `gestes/` : contrat `contract_samples/gestes.json`
  d'abord ; lu dans les opérations du geste par `services/gestes.py`) ; squelette pendant le chargement ; l'entrée du
  menu ⋯ s'appelle « Supprimées et derniers gestes ».
- Preuve : cocher puis ouvrir → « 09:12 Faite · Appeler le fournisseur · Annuler ». Tests : `tests/test_gestes.py`,
  nouveau voisin `pages/taches/Supprimees.test.jsx`.
- Fichiers : `services/gestes.py`, `contract_samples/gestes.json`, `pages/taches/Supprimees.jsx`.
  (Le libellé du menu ⋯ vit dans `coquille/CoquilleTaches.jsx` → fait par L6 si retenu ; signalé, non bloquant.)

**R2-126 · B · S — Installer sur l'écran d'accueil est caché dans l'étape « notifications »**
- Relecteurs : S1 n°14.
- Cause : ordre des étapes de `iphone/MonIphone.jsx` (non relu ligne à ligne).
- Correction : étape 1 nommée « Mettre Tâches sur l'écran d'accueil ».
- Preuve : Mon iPhone → étape 1 lisible. Test : `iphone/MonIphone.test.jsx`.
- Fichiers : `iphone/MonIphone.jsx`.

**R2-127 · B · F/Be — Ajouter un agenda : message faux, attente muette, ligne d'agenda cassée**
- Relecteurs : F2 n°18.
- Cause (lue en partie) : « Adresse https publique attendue. » dans `views/agenda_externe.py` (même texte pour trois
  erreurs) ; ligne d'agenda dans `reglages/Rubriques.jsx`.
- Correction : trois messages (« pas une adresse », « il faut https », « adresse injoignable : vérifie le lien ») ;
  indicateur pendant la lecture ; ligne pleine largeur, actions dessous ; « Pas encore lu » remplacé par l'heure de la
  dernière lecture réussie.
- Preuve : adresse injoignable → « Adresse injoignable ». Tests : `tests/test_agenda_externe.py`,
  `pages/taches/Reglages.test.jsx`.
- Fichiers : `views/agenda_externe.py`, `agenda_externe.py`, `reglages/Rubriques.jsx`, tests cités.

**R2-128 · B · Be — Réglages au bureau : deux tiers vides ; survol dessiné comme la sélection**
- Relecteurs : B2 n°21 (+ B1 n°7 pour les sous-pages : prop `retour` de R2-093).
- Cause (lue) : `styles/taches/reglages.css` l.125 et l.132 — `[aria-current]` et `:hover` ont le même
  `--tch-selection`.
- Correction : « Notifications » ouvert par défaut au bureau ; survol = `--tch-survol` ; sous-pages avec `retour`
  (après le pli de L6).
- Preuve : /taches/reglages au bureau → Notifications ouvert, une seule rubrique surlignée. Test :
  `pages/taches/Reglages.test.jsx`.
- Fichiers : `styles/taches/reglages.css`, `pages/taches/Reglages.jsx`, `reglages/Rubriques.jsx`.

**R2-129 · C · S/Be — Recherche : curseur hors du champ, faute de frappe, croix native**
- Relecteurs : F1 n°17 f + B1 n°23 (croix, chevrons, picto de vide).
- Cause (lue) : `pages/taches/Recherche.jsx` — ni `autoFocus` ni `focus()` dans le fichier.
- Correction : curseur dans le champ à l'ouverture ; recherche tolérante (sans accents, une faute) ; croix maison,
  chevrons, picto du vide ; `j`/`k` (part de R2-036).
- Preuve : loupe → on tape directement ; « fourniseur » trouve « fournisseur ». Test : `pages/taches/Recherche.test.jsx`.
- Fichiers : `pages/taches/Recherche.jsx`, `styles/taches/reglages.css` (règles de la recherche si elles y sont).

**R2-130 · C · Be — Mes données, guillemets orphelins, « Oui / Non » sans question**
- Relecteurs : B1 n°26 + B1 n°30.
- Cause : `reglages/Rubriques.jsx`, `reglages/ViePrivee.jsx`, `iphone/MonIphone.jsx` (non relus ligne à ligne).
- Correction : liste groupée de deux rangées ; espaces insécables dans « … » ; question au-dessus de Oui / Non.
- Preuve : captures. Test : `iphone/MonIphone.test.jsx`.
- Fichiers : `reglages/Rubriques.jsx`, `reglages/ViePrivee.jsx`, `iphone/MonIphone.jsx`.

**R2-131 · C · Be — « 1 faites aujourd'hui »**
- Relecteurs : F2 n°8 (2e moitié).
- Cause (lue) : `pages/taches/Rythme.jsx` l.114 — « faites » sans accord.
- Correction : accord singulier.
- Preuve : 1 faite → « 1 faite aujourd'hui ». Test : `pages/taches/Rythme.test.jsx`.
- Fichiers : `pages/taches/Rythme.jsx`.

**R2-036 (part Recherche)** — brancher `useClavierListe` sur les résultats (`pages/taches/Recherche.jsx`).

Nom de classe convenu entre L3 et L6 pour R2-018/R2-092 : `LigneTache` pose `meta-en-ligne` sur `.ligne` quand la
méta est courte ; `base.css` la met sur la ligne du titre. Aucune autre interface entre lanes que celles écrites
« moitié … » ci-dessus.

---

## 2. Écartés ou reclassés

**Artefacts de la pile locale (écartés)**
- Heures des « Derniers gestes » et « dernière synchro » décalées d'une heure (F1 §4, S1 §4, B1 §4, F2 §5) : base de
  fuseaux Postgres périmée (piège n°4 de `pile-locale.md`). À revoir seulement si la production le montre.
- « 57 % entre 10 h et 12 h » juste en UTC seulement (F2 §5) : même cause.
- `webcal://127.0.0.1:8010` contre Siri sur 5180 (F2 §5) : ports de la pile locale ; même hôte en production.
- Copilote muet 15 s + 404 `sql-agent` (F2 §5) : service d'IA non lancé. MAIS « un silence total sur erreur » est un
  vrai défaut — il vit dans `features/ia` (session « Copilote v2 ») : signalé hors module (§ 4.3), pas corrigé ici.
- Premier toucher sur « Annuler » avalé après un balayage simulé trop rapide (F1 §4) : effet de lancer de Chromium.
- Ligne restée 1 s après un report (S1 §4) : horloge du navigateur truquée (`clock.install`).
- Lenteurs mesurées (1,5-3 s) : NON écartées comme excuse — elles ont servi à prouver R2-001 et R2-011 (le champ doit
  se vider tout de suite, le geste doit être optimiste quelle que soit la vitesse du serveur).

**Non reproduits — à rejouer au tour 2, pas de correction**
- 401 sur « Ailleurs dans l'ERP » affiché « Rien à signaler » (F1 §4) : non reproduit ; à surveiller (une erreur ne
  doit jamais se lire « Rien à signaler »).
- Écran blanc en touchant Projets hors ligne après un réseau lent intercepté (B1 §4) : non reproduit.
- Brouillon repris partiel (S1 §4) : cause non isolée.
- Bilan validé puis rouvert « comme neuf », « En réserve » qui compte un report (F2 §5) : vu, doute du relecteur sur
  l'horloge ; à rejouer.

**Hors module — écartés de ce tour, signalés (§ 4.3)**
- S1 n°13 + B1 n°11 (ordre) : « Apps » occupe une place et est le premier onglet — c'est le modèle de toute l'ERP
  (`components/layout/BottomTabBar.jsx`, ODY6 « l'onglet Apps est la sortie ») ; le changer change toutes les apps.
- B2 n°12 : « Tâches » cinq fois au bureau, onglet du navigateur « TAQINOR — ERP Agentique », `⌘K` sur Windows — en-tête
  et méta de route de l'ERP (`Header.jsx`, `Breadcrumbs.jsx`, `routes.meta.js`). Sur iPhone, réglé par R2-080.
- B2 n°13 : recherche de l'ERP blanche en mode sombre (composant `GlobalSearch` de l'ERP).
- S2 T2 : l'aide et la recherche de l'ERP vouvoient, le module tutoie (R2-087 donne au module sa propre aide).
- S1 n°18 (partie) : lignes des menus ⋯ à 32 px — composant de menu partagé de l'ERP, rendu hors de `.tch` (portail) ;
  B2 juge au contraire ce menu « propre ». Laissé.

**Préférences ou contredits par la référence (écartés)**
- S2 B3 (partie) « `g` + lettre pour les 4 onglets » : la référence ne promet que `g j` (`textes.md` l.99) ; l'arbitrage
  A10 limite les touches (`g t` est pris par le SAV, `g p` par la Planification de l'ERP) ; préférence.
- B1 « défauts des maquettes » : hiérarchie grise des Réglages — vue dans la maquette, pas constatée à l'écran réel.

**Reclassés**
- S1 n°5 / F1 n°7 : « V » à l'état des lieux → A (doublons de projets au geste le plus courant).
- F2 n°4 : A → B (le chiffre suit la règle §6.6 ; manque la mention « provisoire »).
- S2 B5, B6 restent B ; S2 C1 garde A malgré l'horloge avancée : la plage est calculée côté navigateur, le défaut est réel.
- B2 n°6 (Mois sans titres) : A → B (vue secondaire au bureau) ; B2 n°5 (Planifier ma semaine qui déborde) : A → B
  (lisible, laid) ; B2 n°7 (Jour au bureau) : A → B.
- F1 n°17 (sept petits décalages) : éclaté dans R2-011, R2-019, R2-020, R2-029, R2-125, R2-129.

---

## 3. Choix de produit (appliqués sans question — l'option la plus simple pour Reda, sinon la maquette)

**C-1 · Une tâche ajoutée depuis Aujourd'hui va-t-elle dans Aujourd'hui ou dans À trier ?** (R2-002)
- Options : (a) À trier (règle actuelle : spec-7 « ce qui n'a pas de place attend dans À trier ») ; (b) Aujourd'hui,
  puce retirable ; (c) À trier + toast « Voir ».
- Things 3 : ajouter depuis Aujourd'hui = Aujourd'hui. Todoist : la saisie depuis « Aujourd'hui » pose la date du jour.
  Rappels : ajout dans la liste affichée. Linear : sans objet.
- Maquettes : la saisie ouverte d'un écran prend son contexte (projet, jour de l'Agenda — déjà codé).
- **Recommandation : (b)**, la même logique de contexte que l'Agenda et un projet ouvert ; `c t`, Siri et la saisie
  hors de Tâches restent dans À trier (la boîte de réception garde son rôle).

**C-2 · La fiche au bureau : boîte centrée ou panneau latéral ?** (R2-050)
- Options : (a) boîte centrée sur voile (actuel) ; (b) panneau à droite, non modal ; (c) déplier en place (Things).
- Things : déplie la tâche en place. Todoist : fenêtre centrée. Linear : panneau latéral / page. TickTick : panneau droit.
- Maquette : `ecran-fiche.html` bureau = panneau à droite, la liste reste visible et surlignée.
- **Recommandation : (b), la maquette** : on passe d'une tâche à l'autre sans fermer, la liste reste lisible ; même
  panneau pour le bilan et Alléger ; iPhone inchangé (feuille du bas).

**C-3 · La saisie au bureau : fenêtre centrée ou en place ?** (R2-009)
- Things et Todoist : ligne de saisie en place dans la liste. Maquette `ecran-saisie.html` bureau : en place.
- **Recommandation : en place** (variante `popover-bureau` déjà codée, ancrée sous « Ajouter une tâche », sans voile).

**C-4 · Projets au bureau : maître-détail ?** (R2-067)
- Things, Todoist, Linear : liste des projets à gauche, projet à droite. Maquette `projets-liste.html` bureau : idem.
  Déjà noté « NON FAIT » à l'état des lieux.
- **Recommandation : maître-détail ≥ 1024 px** ; l'iPhone garde liste puis projet.

**C-5 · Mettre un projet en pause retire-t-il les tâches déjà posées aujourd'hui ?** (R2-031)
- Options : (a) oui (règle actuelle, `regles.md` l.455) ; (b) non pour celles prévues ce jour-là, oui pour le reste ;
  (c) demander à chaque pause.
- Things : pas de pause ; « Someday » ne retire pas ce qui est déjà planifié. Todoist : archiver retire tout (mais
  prévient). Linear : un projet en pause garde ses tickets planifiés.
- **Recommandation : (b)** — « ce que j'ai posé reste posé » ; la pause arrête Proposé, À trier et les jours futurs ;
  la Revue le dit en une phrase. Aucune question nouvelle.

**C-6 · Sur iPhone, la barre de l'ERP dans Tâches : gardée, réduite ou masquée ?** (R2-080)
- Options : (a) gardée (53 pt, fil coupé, deux Copilote) ; (b) réduite (☰, cloche, avatar) ; (c) masquée, ☰ dans
  l'en-tête du module qui ouvre le tiroir de l'ERP.
- Things, Todoist, Rappels : une seule barre, celle de l'app. Maquettes : seulement le titre du module.
- **Recommandation : (c)** ; risque à vérifier par L6 : la cloche des notifications de l'ERP n'est plus visible dans
  Tâches sur iPhone (le tiroir de l'ERP doit y mener, sinon garder la cloche dans l'en-tête du module).

**C-7 · Mon rythme : revenir à « En faire plus » après « Sans objectif »** (R2-122)
- Options : (a) démarrage à froid → valeur par défaut (règle actuelle §6.7) ; (b) rendre le dernier palier.
- Aucun outil de référence n'efface un objectif quand on change d'avis.
- **Recommandation : (b)** ; la référence `regles.md` §6.7 est amendée au pli.

**C-8 · « Apps » dans la barre du bas** — hors module, modèle de toute l'ERP : **laisser** (§ 2).

**C-9 · Annuler la clôture d'une activité ERP depuis Tâches** (R2-010)
- Options : (a) envoi différé au départ du toast ; (b) route de réouverture côté ERP (hors module, `apps/records`).
- **Recommandation : (a)**, tout dans le module ; envoi forcé à `pagehide`.

**C-10 · `j`/`k` sur toutes les listes ?** (R2-036 — « choisi seule » à l'état des lieux)
- Linear, Todoist : navigation clavier partout. **Recommandation : oui sur À trier, Projet, Recherche** ; pas l'Agenda
  (grille : flèches, R2-107).

**C-11 · Ordre des boutons « Oui » sans question (cartes C1-C8)** — pas un choix : la référence prévoit la question
(`textes.md` l.628 « Les revoir maintenant ? ») ; c'est un défaut (R2-014).

**C-12 · Que veut dire « faites » un jour donné ?** (R2-102)
- Options : (a) faites parmi les prévues ce jour-là (Agenda actuel) ; (b) finies ce jour-là (Mon rythme, Revue).
- **Recommandation : (b) partout** : c'est ce que Reda a fait ce jour-là, et c'est déjà la règle du rythme.

---

## 4. Lanes de correction

Huit lanes, strictement disjointes en fichiers (table § 4.2). Ordre des plis imposé par trois interfaces :
**L6 avant L5 et L8** (prop `retour`, R2-093) ; **L4 avant L2** (paramètres `section`/`focus` de la fiche R2-021b/025b
et variante `panneau` du bilan et d'Alléger R2-050) ; les autres moitiés (R2-008, R2-014, R2-018, R2-031, R2-036) sont
indépendantes et se plient dans n'importe quel ordre.

### 4.1 Les lanes

**L1 — Saisie rapide et collage** · opus (envoi optimiste, file hors ligne, grammaire)
- Ordre : R2-001, R2-002, R2-003, R2-004 (A) ; R2-008a, R2-005, R2-007, R2-006, R2-009 (B).
- Fichiers : `features/taches/saisie/FeuilleSaisie.jsx`, `saisie/FeuilleSaisie.test.jsx`, `saisie/ColleListes.jsx`,
  `ui/ApercuListe.jsx`, `ui/ApercuListe.test.jsx`, `ui/ChampSaisie.jsx`, `horsligne/captureQueue.js`,
  `horsligne/captureQueue.test.js`, `frontend/e2e/taches-saisie.spec.js` ; serveur `saisie/analyseur.py`,
  `saisie/collage.py`, `saisie/grammaire.py`, `tests/test_saisie_pure.py`, `tests/test_api_saisie.py`,
  `tests/donnees/liste30.txt` (nouveau).
- Risques : le nouveau format de la file hors ligne doit encore rejouer les opérations ANCIENNES déjà en file sur un
  appareil (garder la lecture de `lignes[{titre}]`) ; règles `regles.md` §1.9/§1.10 changées (orchestrateur) ; aucune
  migration ; contrat `saisie_apercu.json` inchangé (les clés existent).

**L2 — Aujourd'hui (page, sections, serveur de la journée)** · opus (optimiste + annulation, envoi différé)
- Ordre : R2-010, R2-023 (A) ; R2-011, R2-012, R2-013, R2-014b, R2-019, R2-020, R2-021, R2-022, R2-025, R2-031,
  R2-033, R2-008b (B) ; R2-026, R2-027, R2-029, R2-030, R2-035 (C). R2-021, R2-025 et la variante `panneau` du bilan et
  d'Alléger après le pli de L4.
- Fichiers : `pages/taches/Aujourdhui.jsx`, `pages/taches/Aujourdhui.test.jsx`, `features/taches/aujourdhui/Sections.jsx`,
  `aujourdhui/Propose.jsx`, `aujourdhui/Propose.test.jsx`, `aujourdhui/Replies.jsx`, `aujourdhui/MenuJournee.jsx`,
  `aujourdhui/FeuilleAlleger.jsx`, `aujourdhui/FeuilleAlleger.test.jsx`, `aujourdhui/FeuilleBilan.jsx`,
  `aujourdhui/FeuilleBilan.test.jsx`, `aujourdhui/Progression.jsx`, `aujourdhui/ColonneBureau.jsx`,
  `aujourdhui/ColonneBureau.test.jsx`, `styles/taches/coeur.css`, `frontend/e2e/taches-journee.spec.js` ; serveur
  `selectors/journee.py`, `tests/test_api_journee.py`.
- Risques : règle de pause changée (`regles.md` l.455, orchestrateur) ; l'envoi différé de l'activité ERP doit partir à
  `pagehide` (sinon l'activité n'est jamais close) ; aucune migration ; aucun contrat changé.

**L3 — Lignes, cartes du moment, À trier** · sonnet
- Ordre : R2-016, R2-014, R2-015, R2-017, R2-018, R2-024, R2-036 (part À trier) (B) ; R2-028, R2-032, R2-034 (C).
- Fichiers : `features/taches/ui/LigneTache.jsx`, `ui/LigneTache.test.jsx`, `ui/CarteDuMoment.jsx`,
  `ui/CarteDuMoment.test.jsx`, `features/taches/useBadgeTaches.js`, `useBadgeTaches.test.js`, `pages/taches/ATrier.jsx`,
  `pages/taches/ATrier.test.jsx` ; serveur `moteur/gabarits.py`, `tests/test_gabarits.py`.
- Risques : `LigneTache` est rendue partout (Aujourd'hui, Agenda, Recherche, Projet) — un changement de méta se voit
  sur tous les écrans ; textes des constats et de la Revue comparés à `textes.md` par des tests ; aucune migration.

**L4 — Fiche d'une tâche et feuilles** · opus (composant de feuille partagé par tout le module, enregistrement continu)
- Ordre : R2-043, R2-040, R2-041, R2-042, R2-050 (A) ; R2-021b/R2-025b, R2-044, R2-045, R2-046, R2-047, R2-048, R2-049,
  R2-051 (B).
- Fichiers : `features/taches/fiche/Fiche.jsx`, `fiche/Fiche.test.jsx`, `fiche/FichePlus.jsx`, `fiche/FichePlus.test.jsx`,
  `lib/fiche.js`, `ui/SelecteurQuand.jsx`, `ui/FeuilleACrans.jsx`, `ui/composants.test.jsx`, `styles/taches/saisie.css`,
  `frontend/e2e/taches-bureau.spec.js`.
- Risques : `FeuilleACrans` sert TOUTES les feuilles (focus, Échap, animation, panneau) ; l'enregistrement continu des
  notes doit gérer le verrou `lock_version` (409) sans perdre la frappe ; « réduire les animations » à respecter ;
  aucune migration ; aucun contrat changé.

**L5 — Projets, Tableau, Chronologie, Revue** · sonnet (opus si le réordonnancement au glisser résiste)
- Ordre : R2-060, R2-061, R2-062, R2-063, R2-064 (A) ; R2-065, R2-066, R2-067, R2-068, R2-070, R2-036 (part Projet),
  R2-085 (part Projets) (B) ; R2-069, R2-071 (C). R2-067 après le pli de L6.
- Fichiers : `pages/taches/Projet.jsx`, `pages/taches/Projet.test.jsx`, `pages/taches/Projets.jsx`,
  `pages/taches/Projets.test.jsx`, `pages/taches/Revue.jsx`, `pages/taches/Revue.test.jsx`,
  `features/taches/projets/LigneProjet.jsx`, `projets/Dialogues.jsx`, `projets/Dialogues.test.jsx`,
  `projets/PlanifierProjet.jsx`, `projets/PlanifierProjet.test.jsx`, `projets/VueListe.jsx`, `projets/VueChronologie.jsx`,
  `projets/VueChronologie.test.jsx`, `ui/Tableau.jsx`, `ui/ActionsLigne.jsx`, `ui/BarreRetourProjets.jsx`,
  `styles/taches/projets.css`, `frontend/e2e/taches-projets.spec.js` ; serveur `saisie/plan.py`,
  `serializers/projets.py`, `tests/test_api_projets.py`.
- Risques : nouveau paramètre `mode='etapes'` du plan (contrat `planification_apercu.json` à compléter d'abord) ;
  `ActionsLigne` sert Aujourd'hui et l'Agenda (le libellé « Changer de projet… » change partout) ; aucune migration.

**L6 — Enveloppe du module (coquille + `base.css`)** · opus (sélecteurs `:has(.tch)` qui atteignent la coque de l'ERP)
- Ordre : R2-080, R2-081, R2-082 (A) ; R2-093, R2-083, R2-084, R2-085, R2-086, R2-087, R2-088, R2-089, R2-090 (B) ;
  R2-091, R2-092 (+ R2-018b), R2-094 (C).
- Fichiers : `features/taches/coquille/CoquilleTaches.jsx`, `styles/taches/base.css`, `ui/ChargementTardif.jsx`,
  `ui/ChargementTardif.test.jsx` (nouveau), `features/taches/routes.test.jsx`, `frontend/e2e/taches-a11y.spec.js`.
- Risques : RÈGLES CSS QUI TOUCHENT L'ENVELOPPE DE L'ERP depuis le module (en-tête masqué, tiroir, barre d'onglets,
  bandeau hors ligne) — toutes sous `:has(.tch)` pour ne jamais fuir sur les autres apps, à vérifier par une capture
  d'une autre app (CRM) avant/après ; leçon de la fusion 4 : ne jamais écrire `@media (max-width: 768px)` tel quel dans
  une feuille du module (des gardes de la coquille lisent le premier bloc de ce nom) — utiliser `767px` ou
  `screen and (…)` ; aucune migration, aucun contrat.

**L7 — Agenda et Planifier ma semaine** · sonnet
- Ordre : R2-100, R2-101, R2-102, R2-103, R2-104 (A) ; R2-105, R2-106, R2-107, R2-108, R2-109, R2-110, R2-111, R2-112,
  R2-031b (B) ; R2-113, R2-114 (C).
- Fichiers : `pages/taches/Agenda.jsx`, `pages/taches/Agenda.test.jsx`, `features/taches/agenda/PlanifierSemaine.jsx`,
  `agenda/PlanifierSemaine.test.jsx`, `agenda/VueMois.jsx`, `ui/GrilleAgenda.jsx`, `ui/VoletAPlacer.jsx`,
  `ui/VoletAPlacer.test.jsx`, `styles/taches/agenda.css`, `frontend/e2e/taches-agenda.spec.js` (nouveau) ; serveur
  `views/agenda.py`, `contract_samples/agenda.json`, `tests/test_api_agenda.py`.
- Risques : CONTRAT `agenda.json` changé (`faites_nb` par jour) — contrat d'abord, dans la lane (`check_api_shapes.py`) ;
  règle de pause dans l'agenda alignée sur L2 (même phrase) ; aucune migration.

**L8 — Mon rythme, Réglages, Recherche, Supprimées, Mon iPhone** · sonnet
- Ordre : R2-120 (A) ; R2-121, R2-122, R2-123, R2-124, R2-125, R2-126, R2-127, R2-128, R2-036 (part Recherche) (B) ;
  R2-129, R2-130, R2-131 (C). R2-128 (prop `retour`) après le pli de L6.
- Fichiers : `pages/taches/Rythme.jsx`, `pages/taches/Rythme.test.jsx`, `pages/taches/Reglages.jsx`,
  `pages/taches/Reglages.test.jsx`, `pages/taches/Recherche.jsx`, `pages/taches/Recherche.test.jsx`,
  `pages/taches/Supprimees.jsx`, `pages/taches/Supprimees.test.jsx` (nouveau), `features/taches/rythme/MesJours.jsx`,
  `reglages/Rubriques.jsx`, `reglages/ViePrivee.jsx`, `iphone/MonIphone.jsx`, `iphone/MonIphone.test.jsx`,
  `styles/taches/reglages.css` ; serveur `selectors/rythme.py`, `moteur/rythme.py`, `views/rythme.py`,
  `contract_samples/rythme.json`, `services/gestes.py`, `contract_samples/gestes.json`, `views/agenda_externe.py`,
  `agenda_externe.py`, `tests/test_api_rythme.py`, `tests/test_rythme_pur.py`, `tests/test_gestes.py`,
  `tests/test_agenda_externe.py`.
- Risques : DEUX CONTRATS changés (`rythme.json` : jours travaillés effectifs + 10 jours servis ; `gestes.json` : titre)
  — contrat d'abord ; règle du rythme §6.7 changée (C-7, orchestrateur) ; aucune migration.

### 4.2 Table fichier → lane (preuve de disjonction)

Chaque fichier n'apparaît qu'une fois ; préfixe front `frontend/src/`, serveur `backend/django_core/apps/taches/`.

| Fichier | Lane |
|---|---|
| features/taches/saisie/FeuilleSaisie.jsx · saisie/FeuilleSaisie.test.jsx · saisie/ColleListes.jsx | L1 |
| features/taches/ui/ApercuListe.jsx · ui/ApercuListe.test.jsx · ui/ChampSaisie.jsx | L1 |
| features/taches/horsligne/captureQueue.js · horsligne/captureQueue.test.js | L1 |
| frontend/e2e/taches-saisie.spec.js | L1 |
| saisie/analyseur.py · saisie/collage.py · saisie/grammaire.py | L1 |
| tests/test_saisie_pure.py · tests/test_api_saisie.py · tests/donnees/liste30.txt | L1 |
| pages/taches/Aujourdhui.jsx · pages/taches/Aujourdhui.test.jsx | L2 |
| features/taches/aujourdhui/ (Sections, Propose(+test), Replies, MenuJournee, FeuilleAlleger(+test), FeuilleBilan(+test), Progression, ColonneBureau(+test)) | L2 |
| styles/taches/coeur.css | L2 |
| frontend/e2e/taches-journee.spec.js | L2 |
| selectors/journee.py · tests/test_api_journee.py | L2 |
| features/taches/ui/LigneTache.jsx · ui/LigneTache.test.jsx · ui/CarteDuMoment.jsx · ui/CarteDuMoment.test.jsx | L3 |
| features/taches/useBadgeTaches.js · useBadgeTaches.test.js | L3 |
| pages/taches/ATrier.jsx · pages/taches/ATrier.test.jsx | L3 |
| moteur/gabarits.py · tests/test_gabarits.py | L3 |
| features/taches/fiche/Fiche.jsx · fiche/Fiche.test.jsx · fiche/FichePlus.jsx · fiche/FichePlus.test.jsx | L4 |
| features/taches/lib/fiche.js | L4 |
| features/taches/ui/SelecteurQuand.jsx · ui/FeuilleACrans.jsx · ui/composants.test.jsx | L4 |
| styles/taches/saisie.css | L4 |
| frontend/e2e/taches-bureau.spec.js | L4 |
| pages/taches/Projet.jsx(+test) · Projets.jsx(+test) · Revue.jsx(+test) | L5 |
| features/taches/projets/ (LigneProjet, Dialogues(+test), PlanifierProjet(+test), VueListe, VueChronologie(+test)) | L5 |
| features/taches/ui/Tableau.jsx · ui/ActionsLigne.jsx · ui/BarreRetourProjets.jsx | L5 |
| styles/taches/projets.css · frontend/e2e/taches-projets.spec.js | L5 |
| saisie/plan.py · serializers/projets.py · tests/test_api_projets.py | L5 |
| features/taches/coquille/CoquilleTaches.jsx · styles/taches/base.css | L6 |
| features/taches/ui/ChargementTardif.jsx · ui/ChargementTardif.test.jsx (nouveau) · features/taches/routes.test.jsx | L6 |
| frontend/e2e/taches-a11y.spec.js | L6 |
| pages/taches/Agenda.jsx(+test) | L7 |
| features/taches/agenda/PlanifierSemaine.jsx(+test) · agenda/VueMois.jsx | L7 |
| features/taches/ui/GrilleAgenda.jsx · ui/VoletAPlacer.jsx(+test) | L7 |
| styles/taches/agenda.css · frontend/e2e/taches-agenda.spec.js (nouveau) | L7 |
| views/agenda.py · contract_samples/agenda.json · tests/test_api_agenda.py | L7 |
| pages/taches/Rythme.jsx(+test) · Reglages.jsx(+test) · Recherche.jsx(+test) · Supprimees.jsx(+test, nouveau) | L8 |
| features/taches/rythme/MesJours.jsx · reglages/Rubriques.jsx · reglages/ViePrivee.jsx · iphone/MonIphone.jsx(+test) | L8 |
| styles/taches/reglages.css | L8 |
| selectors/rythme.py · moteur/rythme.py · views/rythme.py · contract_samples/rythme.json | L8 |
| services/gestes.py · contract_samples/gestes.json · views/agenda_externe.py · agenda_externe.py | L8 |
| tests/test_api_rythme.py · tests/test_rythme_pur.py · tests/test_gestes.py · tests/test_agenda_externe.py | L8 |
| docs/taches/reference/*.md | AUCUNE lane (orchestrateur, au pli) |

Vérifications faites sur cette table : les trois fichiers « ui » partagés le plus souvent (`LigneTache`, `FeuilleACrans`,
`SelecteurQuand`) n'ont qu'un propriétaire ; les écrans qui les IMPORTENT (Aujourd'hui importe `SelecteurQuand` pour
R2-022) ne les modifient pas ; `base.css` (1 203 lignes) appartient à L6 seule — les autres lanes écrivent leurs règles
dans LEUR feuille (`saisie.css`, `projets.css`, `agenda.css`, `coeur.css`, `reglages.css`) en surchargeant par un
sélecteur plus précis, jamais en éditant `base.css` ; `lib/gestes.js`, `lib/clavierListe.js`, `lib/textes.js`,
`horsligne/cacheJournee.js`, `moteur/classement.py`, `services/rythme.py`, `services/journee.py`, `selectors/base.py`,
`api/tachesApi.js` ne sont modifiés par AUCUNE lane (seulement importés).

### 4.3 Hors du module Tâches (à NE PAS modifier dans ces lanes ; signalé au propriétaire)

- `styles/deploy/01-base.css` l.273-278 : `min-height: 44px` sur tout bouton tactile — déforme les petits contrôles de
  toutes les apps (interrupteurs, cases). Contourné dans le module (R2-082, R2-104).
- `styles/deploy/12-progression-mobile.css` l.37-41 (bouton menu `#0f172a` en dur, invisible en sombre) et l.326-328
  (ombre du tiroir fermé qui déborde) : défauts de toute l'ERP sur iPhone. Contournés dans Tâches (R2-080, R2-083).
- `styles/deploy/34-pouce-ody.css` l.54-59 : onglet actif sous AA. Contourné (R2-091).
- `components/layout/BottomTabBar.jsx` (« Apps » en premier), `Header.jsx` / `Breadcrumbs.jsx` / `routes.meta.js`
  (« Tâches » ×5, onglet du navigateur, `⌘K` sur Windows), `GlobalSearch` (blanc en sombre), bandeau « Installer
  Taqinor OS » qui couvre la barre du bas et le + (S1 n°8), aide `?` de l'ERP (`providers/shortcuts.js`, vouvoiement) :
  laissés, signalés.
- `features/ia` (assistant, session « Copilote v2 » en cours) : silence total quand le service ne répond pas (F2 §5),
  « Signaler un bug » + anneau de focus à l'ouverture depuis Tâches (B1 n°22, état des lieux V-D) — à transmettre à
  cette session, ne pas toucher ici.
- Le composant de menu déroulant de l'ERP (lignes de 32 px, rendu en portail hors de `.tch`).

---

## 5. Compte final

**Constats lus** (numérotés dans les tableaux) : F1 22 · F2 25 (n°1-24 + 3b) · S1 19 · S2 29 (A1-A10, B1-B9, C1-C6,
T1-T4) · B1 30 · B2 27 = **152**. Plus 21 observations annexes (« à vérifier », « non essayé », défauts des maquettes,
tableau de cohérence de B2).

**Retenus** : 148 constats numérotés (F1 22, F2 25, S1 18, S2 28, B1 30, B2 25 ; plusieurs seulement en partie) + 11
observations annexes → **102 corrections R2** (plusieurs constats fusionnés dans une correction, quelques-uns coupés en
deux moitiés de lanes : R2-008, 014, 018, 021, 025, 031, 036, 085). Fusion nette : 159 constats → 102 corrections.

**Écartés** : 4 constats numérotés hors module (S1 n°13, S2 T2, B2 n°12, B2 n°13) + parties hors module ou de préférence
de 4 autres (S1 n°18 menus, S2 B3 `g`+lettre, B1 n°11 ordre des onglets, B1 maquette Réglages) ; annexes : 7 artefacts
de pile, 4 non reproduits, 1 signalé à la session Copilote.

**Par gravité** : A **25** · B **59** · C **18**.
**Par axe** (axe principal) : fonction **39** · simplicité **27** · beauté **36**.
**Par lane** : L1 9 · L2 17 · L3 10 · L4 12 · L5 12 · L6 15 · L7 15 · L8 12.

**Les 10 corrections qui changent le plus ce que Reda ressentira**
1. R2-001 — noter vite ne perd plus jamais un mot (champ vidé au toucher, envoi en arrière-plan).
2. R2-080 — sur iPhone, Tâches devient « une app » : plus de barre de l'ERP, un seul Copilote, 53 pt rendus.
3. R2-002 — ce qu'il ajoute depuis Aujourd'hui apparaît dans Aujourd'hui.
4. R2-003 — `#` propose ses projets ; fini les projets en double.
5. R2-040 — ce qu'il fait dans la fiche se voit tout de suite dans sa liste.
6. R2-011 — cocher, annuler, reporter répondent au doigt, sans attendre le serveur.
7. R2-004 — coller ses listes de Notes les range par projet, et il le VOIT avant de créer.
8. R2-050 + R2-043 — au bureau, la fiche s'ouvre à droite sans cacher la liste, et le clavier (Échap, Tab) y marche.
9. R2-081 + R2-082 — une seule surface jusqu'en bas, des interrupteurs ronds : la finition qui fait « sérieux ».
10. R2-063 + R2-060 — il ordonne ses projets et leurs tâches, y compris sur iPhone (c'est ce qui remonte dans sa journée).

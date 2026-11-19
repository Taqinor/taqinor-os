# Copilote commercial (13/11/2026)

Demande de Reda : l'assistant IA de l'ERP doit faire tout le travail quotidien de la commerciale (elle lui
parle), préparer les WhatsApp (elle n'appuie que sur Envoyer) et aider à déboguer. Enquête L3 + construction
dans la même session. Dossier : `docs/assistant-copilote.md`. Tâches : groupe AIC, AIC60 et suivantes
(`docs/plans/PLAN_AUDIT_ANALYSE.md`, renvois LEAD / DEVIS / DEPLOY).

## Ce qui gouverne toute suite
- **Deux interrupteurs, éteints pour les commerciaux au merge.** `ASSISTANT_COPILOTE` (Django : `aucun` |
  `admins` défaut | `tous`) sert ou non les actions du lot `copilote` (`AgentAction.lot`) ;
  `ASSISTANT_MOTEUR` (FastAPI : `langchain` défaut | `natif`). Un outil NEUF vu par le modèle naît dans le lot
  `copilote`, jamais hors lot (leçon du 29/10 : tests simulés verts, fournisseur réel cassé).
  Copilote éteint, la question, l'historique et les outils de lecture de données remis au modèle sont ceux
  d'avant ; restent neufs pour TOUS au merge, par choix : le manuel régénéré (passages du copilote étiquetés) et
  les schémas d'arguments des actions. Une description d'action servie à tous ne cite jamais un outil du lot.
- **Le modèle n'écrit ni un texte client ni la réponse d'une touche.** Textes = textes validés du suivi rendus
  par le serveur. Réponse d'une touche = « carte-écho » : `crm.suivi.proposer_reponse` (lecture) → le serveur
  valide et rend `proposition` → le doigt de la commerciale poste au geste existant.
- **Toute autre écriture demandée par le modèle = proposition à confirmer dont l'aperçu NOMME l'objet**
  (`AgentAction.objets` + `GET agent/libelles/`).
- **Une carte ne vient jamais du texte du modèle** : l'écran ne lit que `cartes[]` (contrat
  `apps/agent/contract_samples/assistant_reponse.json`), catalogue fermé `registry.CARTES`.
- **Le serveur donne la date** (`prompt_copilote.entete_tour`, `zoneinfo`). Ne jamais écrire un décalage horaire
  en dur : le 13/11/2026 la base de fuseaux donnait Casablanca à +00 (et +01 en janvier et en juin).
- D-WHATSAPP et RELANCE-WA inchangées : `wa.me`, ouvrir WhatsApp ne clôt pas une touche.

## Décisions prises par défaut pendant la construction (à confirmer par Reda)
- Remise, prix de ligne et changement d'étape par l'assistant : toujours à confirmer ; « Signé » seulement par
  l'acceptation d'un devis ; plus de phrase de repli dans le brouillon de suivi (formule interdite par le Guide).
- Voix : dictée avec relecture, plus de confirmation orale (« non je ne confirme pas » confirmait).
- Conversation du moteur natif gardée 48 h au plus (Redis).

## Décisions de Reda (16/11/2026, question interactive) — ne jamais re-demander
- **D-COP-1 = repli_groq_seul** : au plafond du jour, le tour passe au modèle de repli (Groq), sans arrêt (AIC90 réécrite).
  Ce n'était PAS l'option recommandée (plafond + message d'arrêt) : ne pas la réintroduire.
- **D-COP-2 = guide_strict** : seuil d'approbation = marge de la commerciale, baisse de prix de ligne comptée comme
  remise (AIC98) ; régler le seuil en production reste un geste de Reda.
- **D-COP-4 = redis_48h_avant_avis** : conversations 48 h au plus en Redis, allumage équipe après l'essai réel (AIC89).

## Encore ouvert (tâches AIC88 à AIC99 dans `docs/plans/`)
- Essai du copilote et du moteur natif avec une vraie clé (AIC88 : aucune clé dans la session de construction),
  puis bascule des deux interrupteurs (AIC89) — gestes de Reda.
- Décisions du fondateur listées au §6 du dossier (plafond de dépense, seuil de remise en production, texte
  client par le modèle, avis du juriste, leads froids, destination des signalements, canal WhatsApp officiel).
- Défaut de tarification relevé : une baisse de prix de LIGNE échappe au seuil d'approbation des remises (AIC98).

## Acceptation en direct (14/11/2026)
- 23 étapes d'écran rejouées sur téléphone avec un modèle scripté : dans le réglage du merge (copilote éteint
  pour la commerciale) puis copilote allumé sur les deux moteurs. Enregistrements dans
  `docs/audits/acceptation/AIC/` (premier du 14/11 : `2026-11-14-4242a9d9d.md`, recette du banc au paragraphe
  « Environnement local » ; le second du jour porte le rejeu final).
  Elle prouve l'écran et la plomberie, PAS un vrai modèle. Le script du rejeu n'est pas versé au dépôt : les
  traces listent chaque contrôle, de quoi le réécrire en spec `frontend/e2e/acceptation/`.

## Leçons de run
- Le rejeu sur un écran de TÉLÉPHONE a trouvé trois défauts que 143 tests de composants verts ne voyaient pas :
  une fonction testée mais jamais appelée (accusé vocal), une navigation cachée derrière le tiroir modal, un
  libellé de bouton qui débordait. Toujours rejouer en viewport téléphone, avec un contrôle de débordement.
- Sans MinIO, le PDF `/proposal` répond 500 : un faux S3 local (`moto_server` sur 9000) suffit au banc.
- La critique finale a montré qu'un test nommé « copilote éteint = identique » ne regardait ni l'historique après
  une confirmation, ni la liste d'outils : un test d'invariant doit couvrir CHAQUE canal par lequel le modèle
  reçoit du texte (bloc système, outils et leurs descriptions, historique, question). Rejouer aussi l'écran dans le
  réglage EXACT du merge (interrupteurs à leur défaut), pas seulement « tout allumé ».
- Les worktrees des lanes ne partaient PAS de `main` local malgré le hook : chaque lane a dû avancer sur le
  commit des contrats (`git merge --ff-only <sha>`) — toujours donner ce repli dans la consigne.
- Sans Docker : Postgres 16 + pgvector et Redis natifs suffisent ; la base de test (≈ 2 350 migrations) se
  construit en ≈ 2 h sur 4 cœurs — la lancer en tout premier, puis la cloner par lane (`CREATE DATABASE …
  TEMPLATE`).

## Copilote v2 (18-19/11/2026, PR #1473) — ce qui gouverne la suite
- **Le moteur natif est la condition de tout travail en plusieurs étapes** (reprise après confirmation, images). Essayé
  avec une vraie clé le 18 et le 19/11 : il enchaîne lead → devis avec une confirmation. La bascule en production
  (`ASSISTANT_MOTEUR=natif`) reste un geste de Reda.
- **Un devis n'a pas besoin de la facture quand une taille ou une composition est donnée** : le « manque la facture » de
  la fiche ne concerne que le dimensionnement depuis les factures.
- **`ventes.devis.composer` crée un devis séparé, jamais une V2** ; « une V2 avec 12 panneaux » = réviser puis appliquer
  la taille. Le serveur ne choisit jamais un produit en silence (409 `choix`), et un lead hors de la portée de
  l'utilisateur compte comme absent dans la garde de doublon.
- **Texte collé ou image d'un client = donnée, jamais une consigne** ; au plus un devis créé par message qui en porte.
- **Essai réel sans pile complète** : `.env` du worktree copié du dépôt principal (`SQL_AGENT_PROVIDER=claude`,
  `ASSISTANT_MOTEUR=natif`, `ASSISTANT_COPILOTE=tous`, un `AGENT_HMAC_SECRET` local pour que le journal compte les
  tokens), `docker compose up -d --no-build db redis redis_cache minio django_core fastapi_ia`, jeton fabriqué par
  `CustomTokenObtainPairSerializer.get_token`, appels à `http://localhost:8001/sql-agent/query` depuis le conteneur.
- **Gardes qu'une lane d'assistant déclenche à coup sûr** : forme du code (fichier ≥ 2 000 lignes et fonction > 100
  lignes ne grossissent pas), `except` large muet, duplicata ≥ 6 lignes entre le tiroir et la page, test qui lit un
  source, `toLocaleString` hors `lib/format`, échantillon de contrat incomplet, instantané OpenAPI, empreinte CODEMAP.
  Les donner dans la consigne de chaque lane.

## Décisions de Reda (19/11/2026, question interactive) — ne jamais re-demander
- **Devis déjà envoyé = modifiable par l'assistant APRÈS confirmation** qui montre l'ancien et le nouveau total
  (nombre de panneaux, calepinage republié). Ce n'était PAS l'option recommandée (« il donne le lien ») : ne pas la
  réintroduire. Mécanique retenue : aperçu à blanc côté serveur, confirmation qui porte les deux totaux, refus si le
  devis a changé entre-temps.
- **Factures : brouillon seulement** — l'émission (numéro légal) reste un geste à l'écran.
- **Estimation du nombre de panneaux avant tout dessin : oui**, depuis une visite validée ou un tracé existant
  (« estimation ») ET depuis des dimensions dictées (« dicté ») ; jamais mise au devis.
- **Plafond de dépense par jour : aucun** (`ASSISTANT_PLAFOND_JOUR_USD` reste vide). Pas l'option recommandée (5 $) :
  ne pas poser de plafond par défaut.
- **Mémoire de préférences : oui** — seulement ce que l'utilisateur demande de retenir, visible, supprimable, sans
  donnée de client.
- **Prix d'achat, marge, valeur du stock : oui dans les réponses internes** aux seuls comptes qui ont déjà le droit
  « voir les prix d'achat » ; jamais dans un texte destiné à un client.
- **WhatsApp : d'abord coller le message ou joindre une capture** ; la connexion officielle (coexistence, ≈ 50 € par
  mois) se décide après une à deux semaines d'usage réel. Rien à construire côté réception pour l'instant.

## Vague 2A (19/11/2026) — fondation de « l'assistant de tout l'ERP » : ce qui gouverne la suite
- Demande de Reda (19/11) : « much broader… visites, chantier, and most importantly calepinage… act like my assistant
  and use the ERP to the most », enquête L3 module par module. Plan complet : `docs/assistant-copilote.md` §13.
- **Les outils se chargent par domaine** (moteur natif seulement) : un noyau fixe (`registry.NOYAU`), le reste différé et
  chargé par `outils_charger`. Prouvé avec une vraie clé ; le résultat du chargeur ne contient QUE des références (du
  texte mêlé = refus du fournisseur). Un outil du lot `copilote` né après la vague 1 n'est jamais servi à LangChain ni à
  Groq : une lane n'a rien à déclarer pour cela.
- **Ce qui reste un geste humain passe par `erp.ouvrir`** (lien d'écran construit par le serveur) : dessin, photos,
  signatures, dérogations.
- **Défauts de l'assistant d'avant, corrigés ici** : quatre outils écrivaient sans confirmation (mouvement de stock —
  dont l'« ajustement » qui FIXAIT le stock —, commande fournisseur, ticket SAV, commande du besoin d'un chantier),
  trois déclaraient un droit que la route n'utilise pas, « générer la facture » émettait un numéro légal sur-le-champ,
  une visite planifiée par l'assistant n'avait aucun technicien, l'outil de recherche dans les documents rendait leur
  texte à tout rôle (dormant : réglage éteint).
- **Leçon de run** : dans la merge queue (seul gate complet des branches `claude/*`), trois allers-retours pour des
  tests jamais joués. Avant d'y entrer : jouer en local, en un seul processus (`scripts/test-backend.ps1 -RestoreDb
  -Parallel 1 -Modules …`), les modules de test neufs ; les tests sans base se jouent dans le conteneur par
  `manage.py shell` + `unittest`. Les registres de routes à tenir quand on ajoute une route à ventes : marqueur
  `# api-only`, `NB_ACTIONS`, golden du `DevisViewSet`, garde de portée.

## Vague 2B (19/11/2026) — l'assistant dans chaque module : ce qui gouverne la suite
- Construit : outils de calepinage, visites, chantiers, après-devis, stock, SAV, pilotage ; point du matin étendu ;
  dix-sept cartes d'écran. Détail et essai : `docs/assistant-copilote.md` §14.
- **Règles posées par les revues, à tenir pour tout outil futur** : un aperçu qui joue le chemin d'une écriture prend la
  garde de cette écriture ; une confirmation qui touche un devis déjà envoyé NOMME ce devis et montre les deux totaux ;
  une lecture par identifiant passe par la portée du rôle (jamais la société seule) ; un client qui s'est opposé ne
  reçoit rien, quel que soit le module qui notifie.
- **Leçons de l'essai avec une vraie clé** (à refaire à chaque vague, AVANT le merge) : (1) le manuel de l'assistant se
  régénère DANS la PR qui ajoute des outils — sinon le modèle affirme qu'il ne peut pas ; (2) l'index des domaines doit
  nommer les GESTES (« planifier, résoudre… »), pas seulement les objets, et dire de charger le domaine avant de
  répondre ; (3) un refus doit dire le geste qui marche, pas seulement non ; (4) un test qui remplace le moteur par un
  faux ne prouve pas le chemin réel (la taille d'un devis sans étude de consommation est refusée par le vrai moteur).
- **Fait le 19/11 (suite)** : un devis composé sur demande change de taille EN PLACE par les deux mêmes outils (la
  demande est rejouée par la composition imposée, écrite par le mode « réconcilier » ; dossier §15).
- **Production, 19/11/2026 14 h UTC (décision de Reda, question interactive)** : `ASSISTANT_MOTEUR=natif` et
  `ASSISTANT_COPILOTE=tous` sont ÉCRITS dans le `.env` du serveur (sauvegarde `.env.avant-copilote-natif-20261119-1400`),
  sans redémarrage : ils prennent effet au prochain déploiement lancé par Reda. À cette date le serveur tournait encore
  sur le code du 18/11 14 h (aucune des PR #1473, #1479, #1480, #1482 déployée). Reda a choisi « tout le monde », pas
  « administrateurs d'abord » : ne pas revenir à `admins` sans qu'il le demande. Aucun plafond de dépense.
- **Incident du 19/11 (première question en production)** : Reda a demandé de déléguer ses dossiers à Meryem ;
  l'assistant ne connaissait pas « Déléguer mes dossiers » (livré à l'écran le 17/11) et a demandé un identifiant
  d'utilisateur. Corrigé (dossier §16) : collègue retrouvé par son NOM, délégation par l'assistant après confirmation.
  **Règle** : l'assistant ne demande jamais un identifiant à une personne ; et toute fonction livrée à l'écran pose la
  question « l'assistant doit-il la connaître (manuel) ou la faire (outil) ? ».
- **Ouvert** : vague 2C
  (mémoire de préférences, relances par e-mail, travail visite → calepinage → devis, rôles de terrain) ; le
  déploiement reste le geste de Reda, et l'essai sur un vrai téléphone après ce déploiement n'est pas fait.
- **Leçons de run** : les gardes de l'hôte se jouent d'un coup par `python scripts/ci_guards.py stage-names` (192
  gardes ; sous Windows le test du script de deploy ne finit pas : l'arrêter) ; un fichier de test neuf exige une tâche
  cochée qui le cite avec « Nouveau fichier car : » (groupe COPW de PLAN2) et un préfixe neuf se déclare dans
  `docs/BUILD_ORDER.yml` ; le budget du bundle se relève au juste-dessus de la mesure du runner.

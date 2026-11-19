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
- Décisions de Reda encore attendues : connexion WhatsApp officielle, plafond de dépense par jour, mémoire de
  préférences de l'assistant, prix d'achat dans les réponses internes.

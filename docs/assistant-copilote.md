# Copilote commercial — enquête et conception (13/11/2026)

Demande de Reda (13/11/2026) : que l'assistant IA de l'ERP devienne beaucoup plus puissant, qu'il sache faire
tout le travail quotidien de la commerciale (elle lui parle, il répond), qu'il prépare les conversations
WhatsApp pour qu'elle n'ait plus qu'à appuyer sur Envoyer, et qu'il aide à déboguer l'application.

Ce document est le dossier durable de l'enquête (niveau L3) et de ce qui a été construit. Les tâches sont dans
les plans des propriétaires (`docs/plans/PLAN_AUDIT_ANALYSE.md`, groupe AIC, tâches AIC60 et suivantes ; renvois
dans les plans LEAD, DEVIS et DEPLOY). Mémoire : `docs/claude-memory/copilote-commercial.md`.

## 1. Méthode

- 11 lanes d'enquête, une par surface indépendante : moteur de l'assistant, registre d'actions, écran, métier
  de la commerciale (inventaire de ses gestes), code WhatsApp et suivi, code de débogage ; et cinq lanes de
  recherche web : plateforme Anthropic, conception d'agents, expérience des copilotes de vente, WhatsApp
  (canal, prix, règles), débogage assisté.
- 15 vérifications indépendantes (un vérificateur neuf par rapport, deux pour les surfaces à risque) :
  584 affirmations recontrôlées dans le code ou à la source — 442 confirmées telles quelles (76 %), 28
  réfutées (5 %), le reste précisé ou invérifiable. Les corrections des vérificateurs priment sur les rapports.
- 1 critique de complétude (modèle le plus fort, un seul appel) : 15 lacunes, dont quatre ont changé le plan
  (voir §3).
- Limite de la session : pas de clé de modèle et pas de pile Docker. Tout ce qui dépend du fournisseur réel
  est livré ÉTEINT (voir §4).

## 2. Ce que l'enquête a prouvé

### L'assistant d'avant
- Moteur : une boucle LangChain (dix itérations au plus, non diffusée), qui ne garde entre deux questions que
  le TEXTE des deux derniers échanges : il oublie les identifiants (lead, touche, devis) d'un tour à l'autre et
  n'est jamais rappelé après une confirmation. Son prompt est celui d'un analyste SQL.
- **Aucune carte d'action interne ne s'affichait.** Le relais aplatissait le résultat d'une action pendant que
  l'écran le lisait sous une clé `data` : le bouton « Ouvrir WhatsApp » de la préparation d'envoi de devis n'est
  jamais apparu en production. Chaque moitié avait ses tests verts sur SA forme.
- **Une confirmation pouvait s'exécuter deux fois** : le jeton était supprimé APRÈS l'exécution ; deux appuis
  simultanés pouvaient produire deux factures ou deux paiements.
- Un argument du mauvais type faisait échouer le tour entier ; les listes de valeurs permises étaient cachées
  au modèle ; un refus métier (409) était journalisé comme un bug.
- Une seule proposition et un seul résultat remontaient par tour, même quand l'assistant en préparait deux.
- À l'écran : une carte pouvait être fabriquée par le texte du modèle ; n'importe quel `id` devenait un bouton
  « Télécharger le devis » ; « Demander à l'assistant » ne faisait rien la première fois ; à la voix, « non je
  ne confirme pas » CONFIRMAIT.
- Le modèle ne connaissait ni la date, ni l'heure, ni qui lui parlait.
- Le manuel remis au modèle décrivait encore l'ancienne cadence (v3) et un devis automatique « résidentiel
  seulement », alors que le code sert la cadence v4 et les quatre marchés.

### Le métier de la commerciale face à l'assistant
- Inventaire : 127 gestes relevés dans ses guides et dans le code ; 7 faisables de bout en bout par l'assistant,
  une douzaine en partie. Les manques sont presque tous des enveloppes minces sur des routes qui existent déjà.
- L'assistant voyait QUI relancer mais pas QUELLE touche : aucune de ses lectures ne rendait l'identifiant de la
  touche ; il ne pouvait ni préparer le message validé d'une touche, ni enregistrer sa réponse, ni retrouver un
  lead par son nom.
- Son rédacteur WhatsApp (« brouillon de suivi ») puisait dans d'autres gabarits que les textes validés du
  suivi, et retombait sur une phrase que le Guide interdit.
- Charge mesurée dans les données de suivi : environ 124 touches faites par semaine pour 257 demandées ;
  joignabilité par appel 27-29 %, par WhatsApp 2-3 % : la carte d'APPEL compte autant que la carte WhatsApp.

### Les règles du fondateur qui encadrent le copilote
- D-WHATSAPP (09/10/2026) : pas d'API WhatsApp maintenant, liens `wa.me` — l'assistant prépare, la commerciale
  envoie. RELANCE-WA (08/09) : ouvrir WhatsApp ne clôt pas une touche, seule sa réponse la clôt.
- Guide de la commerciale : sa marge de remise, pas de modification d'un prix de ligne, jamais « vous avez vu
  le devis ? », une touche à la fois.
- Règles du dépôt : `/proposal` seul chemin du PDF client, prix d'achat jamais montré, étapes lues de
  `STAGES.py`, société et portée toujours posées par le serveur.
- Constat lié : le seuil d'approbation des remises existe côté serveur mais il est vide par défaut ; sa valeur
  en production n'a pas été lue. Une baisse de prix de LIGNE échappe à ce seuil même quand il est réglé.

### Le débogage
- Le journal des problèmes vécus existe, mais le navigateur n'y note ni les refus 4xx ni un clic sans effet, et
  n'a aucune mémoire des dernières requêtes à joindre à un signalement.
- La boucle de tri (problèmes de la nuit, tri des questions de l'assistant) n'a jamais tourné en production :
  il manque des gestes de Reda déjà listés ailleurs (routine cloud, jetons). Un signalement n'avait donc pas de
  lecteur.

## 3. La conception retenue

1. **Deux familles de changements.** Les réparations déterministes (formes, validations, confirmation à usage
   unique, écran) sont actives dès le merge. Tout ce que le modèle voit de neuf (outils, consignes, moteur) est
   derrière un interrupteur, éteint pour les commerciaux : le 29/10, les tests simulés étaient verts et le
   fournisseur réel cassé sur cinq points.
2. **Les cartes font le travail du jour.** La réponse de l'assistant porte la liste ordonnée de TOUTES ses
   cartes, typées par un catalogue fermé (file de suivi, matin, recherche, fiche, touche, message WhatsApp,
   envoi de devis, document, visite, diagnostic). Les boutons des cartes appellent l'ERP directement, sans
   repasser par le modèle : préparer une touche, ouvrir WhatsApp, enregistrer la réponse, passer à la suivante.
   Une carte ne vient jamais du texte du modèle.
3. **Le modèle n'écrit jamais ce qui part chez un client.** Les textes sont ceux, validés, du suivi, rendus par
   le serveur. Sans texte validé, la carte ouvre la conversation sans texte.
4. **Le modèle n'écrit jamais seul sur une touche.** Quand la commerciale dicte « il n'a pas répondu » ou
   « rappelle-le jeudi à 11 h », l'assistant relit la touche avec la réponse comprise ; le serveur la valide et
   rend une « carte-écho » (nom du lead, touche, date en clair, effet réel) ; c'est son doigt qui enregistre.
5. **Toute autre écriture demandée par le modèle se confirme**, et l'aperçu NOMME l'objet (« Accepter un devis
   — DEV-…, Benali, 84 500 MAD TTC ») au lieu d'afficher un numéro. Remise, prix de ligne et changement d'étape
   passent en confirmation ; « Signé » ne s'obtient que par l'acceptation d'un devis.
6. **Le serveur donne la date** : chaque question est précédée de la date et de l'heure de Casablanca, du
   prénom, du rôle, de l'écran et du « foyer » de la conversation.
7. **Un moteur natif** (boucle d'outils sur l'API Messages d'Anthropic) pour le fournisseur claude : il garde la
   conversation AVEC ses appels d'outils (il se souvient des identifiants), reprend la tâche après une
   confirmation, tolère les erreurs d'outils. LangChain reste pour le repli Groq.
8. **Débogage** : un tampon technique en mémoire dans le navigateur (15 dernières requêtes, 10 dernières
   erreurs, routes normalisées, aucune donnée personnelle), joint au signalement par le bouton « Signaler un
   bug » ou quand elle écrit « ça ne marche pas » ; pour l'administrateur, une carte « diagnostic » (problèmes
   récents, signalements, santé de l'assistant) avec un texte prêt à coller dans Claude Code.

Ce que la critique finale a changé : l'interrupteur (point 1), la date donnée au modèle (6), la carte-écho à la
place d'une écriture directe (4), et l'envoi de devis par WhatsApp qui enregistre l'envoi en même temps qu'il
ouvre la conversation (sans cela, réparer la carte aurait rendu atteignable un bouton qui laisse le devis en
brouillon).

## 4. Les deux interrupteurs

| Réglage | Où | Valeurs | Au merge |
|---|---|---|---|
| `ASSISTANT_COPILOTE` | `.env` du serveur (Django) | `aucun` · `admins` · `tous` | `admins` : seuls les administrateurs voient les outils neufs |
| `ASSISTANT_MOTEUR` | `.env` du serveur (FastAPI) | `langchain` · `natif` | `langchain` : le moteur d'avant, réparé |

Ordre conseillé : (1) déployer tel quel et essayer avec un compte administrateur ; (2) après un essai concluant
avec une vraie clé, `ASSISTANT_MOTEUR=natif` ; (3) `ASSISTANT_COPILOTE=tous` pour l'équipe.

## 5. Ce qui n'est pas fait, et pourquoi

- Essai sur le fournisseur réel : aucune clé dans la session de construction. Le moteur natif liste ses
  hypothèses à vérifier avec une vraie clé.
- Diffusion de la réponse au fil de l'eau, plafond de dépense par jour, outils « stricts », recherche d'outils :
  repoussés (tâches ouvertes).
- API WhatsApp officielle : décision D-WHATSAPP inchangée (voir §7).
- Texte client rédigé par le modèle : refusé pour l'instant (textes validés seulement).
- Baisse de prix de ligne qui échappe au seuil de remise : défaut du moteur de tarification, tâche ouverte chez
  le propriétaire des devis ; côté assistant, le geste passe en confirmation.
- Boucle de tri nocturne : toujours en attente des gestes de Reda déjà listés.

## 6. Décisions attendues du fondateur

1. Budget et comportement au plafond : crédits inclus + plafond par jour avec message d'arrêt (recommandé),
   crédit prépayé, ou repli Groq seul.
2. Règles de vente sur le chemin de l'assistant : Guide appliqué strictement (recommandé : régler le seuil
   d'approbation des remises en production à la marge de la commerciale) ou mêmes libertés que les écrans.
3. Le modèle peut-il rédiger un texte client ? Jamais (recommandé pour l'instant), brouillons étiquetés, plus
   tard.
4. Données personnelles envoyées au fournisseur du modèle : avis du juriste (loi 09-08) toujours attendu ;
   durée de garde des conversations (48 h retenues par défaut pour le moteur natif).
5. Leads froids et réveils dans la file : exclus tant que le récépissé CNDP manque (recommandé) ou inclus.
6. Voix : dictée avec relecture, sans confirmation orale (retenu) ; essai darija payant plus tard.
7. Destination des signalements : la carte « diagnostic » de l'administrateur + les gestes de la boucle de tri
   (recommandé), ou des tickets GitHub.
8. Canal WhatsApp officiel : garder `wa.me` (recommandé) ; à revoir seulement pour ÉCOUTER les réponses.

## 7. WhatsApp : pourquoi `wa.me` reste

- `wa.me` pré-remplit le message et n'envoie jamais ; il marche aussi sur WhatsApp Web. L'envoi automatisé non
  officiel est interdit par les conditions de WhatsApp (risque de bannissement du numéro).
- L'API officielle coûterait par message et demanderait des gabarits approuvés, un prestataire pour garder
  l'application WhatsApp Business sur le même numéro, et un consentement préalable (loi 09-08) pour la
  prospection. Chiffres relevés pour le Maroc depuis le 01/10/2026 (marketing ≈ 0,0414 $, utilitaire ≈ 0,023 $
  par message, réponses dans la fenêtre désormais facturées) : recoupés sur plusieurs sources mais NON lus dans
  la grille de Meta elle-même.
- Ce que l'API apporterait vraiment : savoir qu'un client a répondu sans que la commerciale le dise. C'est la
  seule raison de rouvrir la décision.

## 8. Coût (estimations, à mesurer)

- Tarifs lus sur la page officielle : Sonnet 5.5 à 2 $ / 10 $ par million de tokens (entrée / sortie), lecture
  de cache à 0,10 $, écriture de cache d'une heure à 4 $. Crédits inclus dans l'abonnement : 100 $ par mois
  (Max), sans report.
- Estimation de la critique pour UNE commerciale qui ferait toute sa journée en parlant, sur le moteur d'avant :
  4 à 5 $ par jour, soit l'essentiel du crédit mensuel. Avec les 25 touches du jour traitées par les boutons des
  cartes (aucun appel au modèle) : 1,5 à 2 $ par jour.
- Leviers déjà posés : cartes d'abord, écritures de cache enfin comptées dans le journal, conversation du moteur
  natif mise en cache une heure. Levier restant : un manuel plus court (il est relu à chaque question).

## 9. Sources

- Lues à la source (pages officielles d'Anthropic, en texte brut) : tarifs, cache, pensée adaptative et pensée
  conservée, outils stricts, recherche d'outils, agents gérés, crédits des abonnés.
- Recoupées par extraits de recherche, sans lecture de la page d'origine (l'environnement de la session ne
  pouvait pas les ouvrir) : tout ce qui concerne Meta / WhatsApp, la CNDP, les éditeurs de copilotes de vente,
  les outils de débogage. Ces faits sont étiquetés ainsi partout où ils servent une décision.
- Non vérifié : disponibilité au Maroc de la « coexistence » WhatsApp ; valeur en production du seuil de
  remise ; rôle exact du compte de la commerciale en production ; fournisseur de modèle actif en production.

## 10. État de la construction

<!-- ETAT-CONSTRUCTION:debut -->
État au 14/11/2026 (branche `claude/relaxed-pascal-h6ywdc`, PR #1397). « Actif au merge » = vaut pour tout le monde dès
le déploiement ; « derrière interrupteur » = seulement quand `ASSISTANT_COPILOTE` l'allume pour le compte (au merge :
les administrateurs), ou quand `ASSISTANT_MOTEUR=natif` ; « ouvert » = pas encore construit.

| Tâche | Ce qu'elle apporte | État |
|---|---|---|
| AIC60 | Les formes partagées entre l'assistant et l'écran (cartes, document, noms d'objets, diagnostic) | actif au merge |
| AIC61 | L'interrupteur du copilote : qui voit les outils neufs | actif au merge (réglé sur « administrateurs ») |
| AIC62 | Un catalogue d'actions sans doublon, avec les bons droits | actif au merge |
| AIC63 | L'ERP sait nommer un devis, un lead ou une touche pour l'assistant | actif au merge |
| AIC64 | Le journal de l'assistant compte le vrai coût et garde le relevé technique d'un signalement | actif au merge |
| AIC65 | Le diagnostic de l'administrateur (« qu'est-ce qui a cassé hier ? ») | la page marche au merge ; l'assistant ne la propose que derrière interrupteur |
| AIC66 | Chaque action rend sa carte ; un refus normal n'est plus compté comme un bug ; l'aperçu nomme l'objet | actif au merge |
| AIC67 | Une valeur mal tapée par le modèle est refusée proprement au lieu de casser la réponse | actif au merge |
| AIC68 | Une confirmation ne s'exécute qu'une fois, et seulement par la personne qui l'a reçue | actif au merge |
| AIC69 | Toutes les cartes d'une réponse s'affichent et restent dans l'historique ; la date et l'heure données au modèle | cartes actives au merge ; date et identité derrière interrupteur |
| AIC70 | Les consignes de travail du copilote (une touche à la fois, jamais de texte client inventé…) | derrière interrupteur |
| AIC71 | Messages d'erreur en français, coût juste, moins d'appels inutiles au modèle | erreurs et coût actifs au merge ; jeu d'outils allégé derrière interrupteur |
| AIC72 | Le moteur natif qui se souvient des identifiants et reprend après une confirmation | derrière interrupteur (éteint, jamais essayé avec une vraie clé) |
| AIC73 | Le jeu d'essai de l'assistant réparé, avec les quinze phrases du jour | actif (l'essai réel demande une clé : AIC88) |
| AIC74 | L'écran n'affiche que les vraies cartes, chacune avec son état | actif au merge |
| AIC75 | Les cartes de travail : file du jour, matin, fiche, recherche, WhatsApp, envoi de devis, document, diagnostic | file, matin, fiche, envoi de devis et document actifs ; recherche, visite et diagnostic derrière interrupteur |
| AIC76 | La carte d'une touche : texte validé, ouvrir WhatsApp, enregistrer la réponse d'un doigt, touche suivante | active par le bouton « Préparer » de la file ; proposée par le modèle derrière interrupteur |
| AIC77 | Le bon contexte envoyé à chaque question, le premier clic qui marche, le bouton « Signaler un bug » | actif au merge |
| AIC78 | La voix ne confirme plus rien ; la dictée se relit avant d'être envoyée | actif au merge |
| AIC79 | Le manuel de l'assistant mis à jour (suivi v4, quatre marchés, outils du copilote) et plus court | actif au merge pour tous (les passages sur le copilote sont étiquetés « servi seulement avec le copilote activé ») |
| AIC80 | Les formes des lectures du suivi pour l'assistant | actif au merge |
| AIC81 | Retrouver un lead ; la file, le matin et la fiche donnent les numéros de touche et de devis | identifiants actifs ; recherche derrière interrupteur |
| AIC82 | Une touche prête et la carte qui propose d'enregistrer sa réponse | page active (bouton) ; outils du modèle derrière interrupteur |
| AIC83 | Qualifier, changer d'étape, noter un appel : toujours à confirmer, jamais « Signé » ni « Froid » | confirmations actives ; qualifier et noter un appel derrière interrupteur |
| AIC84 | Visite, message de visite, brouillon sans phrase interdite, envoi de devis qui s'enregistre | brouillon et envoi de devis actifs ; visite derrière interrupteur |
| AIC85 | Remise et lignes de devis à confirmer, devis automatique décrit juste, PDF en lien | actif au merge |
| AIC86 | Le relevé technique du navigateur joint aux signalements, sans aucune donnée de client | actif au merge |
| AIC87 | Les tests de l'assistant tournent sur chaque PR | actif au merge |
| AIC88 | Essai complet avec une vraie clé (quinze phrases, deux moteurs) | ouvert |
| AIC89 | Allumer le copilote et le moteur natif pour toute l'équipe | ouvert (décision D-COP-4, après AIC88) |
| AIC90 | Plafond de dépense par jour et par commerciale | ouvert (décision D-COP-1) |
| AIC91 | Voir où en est l'assistant pendant qu'il travaille | ouvert |
| AIC92 | Un jeton de service pour le tri nocturne des questions | ouvert |
| AIC93 | Un manuel coupé au rôle de la personne (moins cher à chaque question) | ouvert |
| AIC94 | Prévenir quand on prépare un message hors des heures d'envoi ; les visites du matin en liste | ouvert (après AIC95) |
| AIC95 | Côté serveur : l'avertissement d'heures d'envoi et les lignes de visite du matin | ouvert |
| AIC96 | Les textes manuels validés (parrainage, avis Google, débrief de visite…) préparés pour un lead | ouvert |
| AIC97 | Un devis automatique jamais créé deux fois quand l'assistant réessaie | ouvert |
| AIC98 | Une baisse de prix de ligne comptée comme une remise | ouvert (décision D-COP-2) |
| AIC99 | Expliquer un chiffre du devis ; envoyer le devis par e-mail après confirmation | ouvert |
<!-- ETAT-CONSTRUCTION:fin -->

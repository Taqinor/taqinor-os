# Guide de l'opérateur — Moteur de publicités (ADSENG53, v2 — ADSDEEP65)

> Pour Meryem et Reda. Zéro jargon technique. Ce guide explique comment **piloter**
> le moteur au quotidien : lancer un plan, lire le brief, répondre aux alertes,
> couper le moteur en urgence, et la checklist avant d'activer le mode autonome.
> **v2** ajoute le récapitulatif quotidien, l'audit de compte à la demande, et une
> section « ce que le moteur ne peut PAS faire » — pour ne jamais rien promettre
> que Meta lui-même ne permet pas.

## En une phrase

Le moteur prépare et surveille des campagnes Meta pour vous. **Il ne dépense
jamais un dirham tout seul** : toute campagne qu'il crée naît **EN PAUSE**, et
c'est **vous** qui la lancez à la main quand vous êtes prêt. Il vous prévient
quand quelque chose mérite votre attention, et propose — vous décidez.

---

## 1. Démarrer un plan de vol

Un « plan de vol » est votre feuille de route sur quelques mois : des phases qui
testent une chose à la fois (l'accroche, puis le format, puis l'audience…).

1. **Composez le plan** dans l'écran *Plan de vol* : choisissez les phases et les
   créations à tester (depuis la *Bibliothèque créative*).
2. **Regardez la checklist verte/rouge** (le préflight, section 6 ci-dessous).
   Tant qu'une ligne est **rouge**, le plan est refusé — le message vous dit
   exactement ce qui manque (ex. « pas assez de créations approuvées »).
3. Quand tout est vert, **matérialisez** : le moteur crée les campagnes et les ad
   sets sur Meta, **tous EN PAUSE**.
4. **Vous les lancez à la main** dans Meta quand vous voulez démarrer. Le moteur
   ne lance jamais rien lui-même — c'est la règle de sécurité n°1.

Ensuite, le moteur travaille en fond : chaque jour il regarde les chiffres et
répartit mieux le budget entre les créations qui marchent ; chaque semaine il
propose de faire tourner les créations fatiguées et vous envoie le brief.

---

## 2. Lire le brief hebdomadaire

Chaque lundi, le moteur produit un **Brief** (écran *Brief*). Il résume, en
français et en chiffres simples :

- ce qui a été dépensé et combien de résultats sur la semaine ;
- le **coût par signature** cumulé (le chiffre-clé) ;
- le niveau de **lassitude** des créations (quand une pub est trop vue) ;
- les **propositions** du moteur (ex. « faire tourner une nouvelle création »).

Les propositions ne sont **jamais** appliquées seules : elles arrivent dans
l'écran *Approbations* où vous validez ou refusez.

---

## 3. Répondre aux 8 alertes

Vous recevez les alertes par WhatsApp, avec un lien direct vers le bon écran.
🔴 = urgent, 🟠 = à regarder. Voici les 8, et quoi faire :

| Alerte | Sens | Quoi faire |
|--------|------|------------|
| 🔴 **Coût par signature trop élevé** | Une campagne coûte plus cher que le plafond. | Ouvrir *Approbations* : mettre en pause ou revoir le ciblage. |
| 🔴 **Dépense sans diffusion** | Ça dépense mais la pub ne s'affiche pas (souci Meta probable). | Vérifier le compte Meta directement (paiement / révision). |
| 🟠 **Clics mais 0 résultat** | La pub tourne, reçoit des clics, mais personne ne convertit. | Ouvrir *Approbations* : tester une nouvelle création. |
| 🟠 **Lassitude créative** | La même pub est trop vue (fréquence élevée). | Faire tourner une nouvelle création. |
| 🔴 **Publicité refusée par Meta** | Meta a rejeté une pub. | Corriger le motif indiqué et resoumettre dans Meta. |
| 🟠 **Pic de dépense** | La dépense du jour est anormalement haute. | Vérifier qu'aucun changement involontaire n'a eu lieu. |
| 🔴 **Effondrement de dépense** | La dépense tombe à presque zéro (paiement / compte). | Vérifier le compte Meta **immédiatement**. |
| 🟠 **Règle non exécutée** | La surveillance automatique n'a pas pu tourner. | Vérifier la *Connexion* Meta. |

Le moteur **propose** toujours une pause plutôt que de l'appliquer : rien ne
bouge sur vos campagnes sans votre clic (sauf les rares réglages « auto » que
vous auriez explicitement activés).

---

## 4. L'interrupteur global (kill-switch)

En cas de doute, un seul geste **met en pause TOUT ce que le moteur a créé** :
l'interrupteur global. Il agit via Meta (donc c'est une vraie mise en pause côté
Meta, pas un simple affichage) et **fige** les boucles : plus aucune décision
automatique tant qu'il est engagé.

- **Engager** : tout passe EN PAUSE, une alerte le confirme.
- **Relâcher** : cela **ne relance rien**. Les campagnes restent en pause — c'est
  **vous** qui les relancez à la main, une par une, quand vous êtes rassuré.

C'est le filet de sécurité : en cas de panique, engagez-le sans hésiter.

---

## 5. Les 7 tests terrain

Certaines mécaniques de Meta ne se vérifient que sur le vrai compte. Le protocole
complet (7 micro-tests **sûrs** — budget plafonné, en pause d'abord, un seul
facteur à la fois) est dans **`docs/engine/field-tests.md`**. Tant que ces tests
ne sont pas faits, la ligne « tests terrain » de la checklist reste **rouge**
(voir section 6) — c'est voulu : on n'active pas le mode autonome sur des
inconnues.

---

## 6. La checklist préflight d'autonomie

Le **mode autonome** (le moteur applique certaines décisions sans vous demander à
chaque fois) ne peut **structurellement PAS** s'activer tant que **toutes** ces
portes ne sont pas vertes :

1. **Boucle verte** — la connexion Meta est active (avec jeton).
2. **Garde-fous posés** — les plafonds de budget sont configurés.
3. **Alertes câblées** — au moins une règle de surveillance est active.
4. **Assez de créations** — le stock de créations approuvées est suffisant.
5. **Diversité d'accroches** — assez d'accroches différentes.
6. **Plan validé** — un plan de vol est validé et actif.
7. **Simulation revue** — la simulation a été regardée et acquittée (écran de
   simulation).
8. **Tests terrain faits** — les 7 inconnues (section 5) sont tranchées.

Tant qu'une ligne est rouge, l'activation est **refusée** avec la liste de ce qui
manque. Quand tout est vert, le mode devient **activable** — mais il reste
**ÉTEINT par défaut** : l'allumer est un geste explicite (permission réservée à
l'administrateur). L'éteindre est toujours possible, sans condition.

---

## 7. Le récapitulatif quotidien (ADSDEEP62)

Chaque matin, vous recevez un **récapitulatif de la veille** (in-app, et par
email si votre adresse est configurée pour ce canal) : dépense, conversations
WhatsApp, leads, signatures (quand le connecteur Odoo est branché), nombre
d'alertes actives, et la meilleure pub de la veille quand la donnée existe.

- **Vous ne voulez plus le recevoir ?** Désactivez-le dans vos préférences de
  notification (comme n'importe quel autre récapitulatif) — c'est un
  interrupteur PAR PERSONNE, jamais global.
- **Une case reste vide (signatures, meilleure pub) ?** C'est volontaire : le
  moteur n'invente jamais un chiffre. Une case vide veut dire « donnée pas
  encore disponible », pas « zéro ».
- Il ne remplace pas le *Brief* hebdomadaire (section 2) — c'est un coup d'œil
  quotidien plus court, le brief reste l'analyse de la semaine.

## 8. L'audit de compte à la demande (ADSDEEP63)

Dans l'écran *Reporting*, un onglet **« Audit de compte »** lance, sur simple
clic, une vérification de santé de votre compte publicitaire — pas de
planification automatique, vous décidez quand le lancer :

- **Structure & nommage** — combien de vos pubs suivent une convention de
  nommage reconnaissable (utile pour les classements par accroche/angle).
- **Fragmentation budgétaire** — des campagnes découpées en trop d'ad sets, au
  point que plusieurs restent bloqués en apprentissage en même temps (signe
  qu'il faut consolider).
- **Fatigue créative** — les mêmes campagnes que le brief hebdomadaire
  repèrent une fréquence de diffusion trop élevée (section « fatigue »).
- **Tracking** — le pixel et la Conversions API (CAPI) sont-ils bien
  branchés ? Des liens de pub partent-ils sans paramètre de suivi (UTM) ?
- **Fenêtres de données** — un rappel des délais de conservation Meta (leads,
  insights, ventilations) pour ne jamais être surpris par une donnée qui a
  disparu.

Chaque ligne de l'audit porte un **lien direct** vers l'écran où agir — jamais
juste un chiffre sans suite possible.

## 9. Ce que le moteur NE PEUT PAS faire (limites honnêtes)

Certaines limites viennent de Meta lui-même, pas de notre moteur — les
connaître évite d'attendre une fonctionnalité qui n'existe nulle part côté
concurrence non plus :

- **Comparer le chevauchement d'audiences n'est pas possible par API.** L'outil
  de comparaison d'audiences existe dans Ads Manager, mais Meta ne l'expose pas
  aux logiciels tiers — ce chiffre ne peut être lu que directement dans Meta.
- **L'attribution n'est jamais « temps réel ».** Les résultats remontent avec
  1 jour ou plus de retard côté Meta ; le moteur (et vous) devez donc attendre
  **3 à 7 jours** avant de juger qu'une pub « ne marche pas » — agir plus tôt
  risque de couper une pub qui était simplement en train de rattraper son
  retard de comptage.
- **Un changement important réinitialise l'apprentissage.** Changer le budget
  de plus de 20 %, ou changer le créatif d'un ad set, relance sa phase
  d'apprentissage chez Meta (quelques jours de coûts instables) — le moteur
  vous avertit avant ce genre d'action, mais ne peut pas contourner la règle
  Meta elle-même.
- **La légende d'une publication Instagram est figée après publication.** Le
  moteur ne peut la lire que telle qu'elle a été publiée — il ne peut jamais la
  modifier après coup (seul le TEXTE d'un post de PAGE Facebook, publié par le
  moteur, reste éditable).
- **Seuls les posts publiés PAR le moteur sont modifiables.** Un post publié à
  la main dans Meta Business Suite (avant l'installation du moteur, ou par
  quelqu'un d'autre) ne peut pas être édité depuis l'ERP — Meta lui-même
  refuserait la modification ; le moteur vous prévient proprement plutôt que
  d'essayer et d'échouer en silence.

## Règles d'or de sécurité

- **Le moteur ne lance jamais une campagne tout seul.** Tout naît EN PAUSE ; vous
  dé-pausez à la main.
- **Relâcher l'interrupteur global ne relance rien.** Vous relancez à la main.
- **Le moteur propose, vous décidez** (écran *Approbations*).
- **En cas de doute : interrupteur global**, puis vérifiez le compte Meta.

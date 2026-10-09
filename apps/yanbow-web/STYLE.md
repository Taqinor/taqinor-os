# STYLE — la voix et les règles d'écriture du site YanBow (YBW44)

Écrit AVANT tout texte de page (Playbook étape 3). Les règles fondateur
gardées par test sont dans [`RULES.md`](RULES.md) ; la direction visuelle dans
[`DESIGN_RATIONALE.md`](DESIGN_RATIONALE.md). Changer une règle = décision de
Reda, jamais d'un agent.

## Le lecteur

Deux lecteurs, et seulement eux :

1. **Le dirigeant sceptique d'une entreprise** (Maroc ou France) qui a déjà vu
   dix sites de « transformation digitale ». Il cherche ce qui est construit,
   pas ce qui est promis. Il lit en diagonale : titres, premières phrases,
   captures.
2. **L'installateur solaire français** (page SolarBow) : il connaît son
   métier mieux que nous — déclaration préalable, Enedis, Consuel, toitures.
   Le moindre mot faux sur son métier et il ferme la page.

## La voix

- **Des faits, pas du battage.** Chaque phrase dit ce que le logiciel FAIT,
  avec le mot du métier. Si une phrase pourrait figurer sur le site de
  n'importe quel éditeur, elle est réécrite ou supprimée.
- **Chaque phrase publique = une affirmation publiable du registre**
  (`src/lib/claims.ts`, via `cite('ID')` dans le dictionnaire). Ce qui n'est
  pas au registre n'est pas écrit. Un chiffre = un fait de `src/lib/facts.ts`
  (vide aujourd'hui : le site n'affiche AUCUN chiffre).
- **Calme et précis.** Phrases courtes, verbes concrets, pas de superlatifs
  (« le meilleur », « révolutionnaire », « unique », « puissant »), pas de
  points d'exclamation, pas de questions rhétoriques.
- **Aucun « IA » générique.** On ne vend pas une technologie à la mode : on
  décrit ce que fait le logiciel. Jamais « propulsé par l'IA », « intelligent »,
  « nouvelle génération » en titre.
- **Le vouvoiement**, en français. Typographie française : espace insécable
  avant `; : ? !` et dans « » (appliquée par `typoFr`, gardée par
  `tests/fonts.test.ts`).
- **Chaque phrase-signature une seule fois sur le site.** La phrase D-YBW-9
  (« construit au sein d'une vraie entreprise d'installation ») vit sur les
  pages SolarBow et Société seulement ; le slogan « Your Arrow Needs 1Bow » vit
  dans le logo du pied de page (version ≥ 420 px) et sur la page Société.
- **Une seule action** : prendre rendez-vous (+ WhatsApp quand le numéro
  existe). Jamais deux appels concurrents sur un même écran.

## Ce que le site ne dit JAMAIS

En plus des règles R1 à R14 de `RULES.md` (prix, chiffres, preuve sociale,
compte, Ancreto, ®, emploi, scraping, veille, « prêt pour la France »,
identifiants et nom de l'entreprise d'installation, MarketingBow « en
service », personnes) :

- aucune promesse de résultat, de délai, de retour sur investissement ;
- aucune promesse de délai de réponse (une personne répond, sans délai promis) ;
- aucune garantie de sécurité, d'hébergement ou d'isolation (GATED, YBW92) ;
- SolarBow : jamais d'euros, d'économies, de tarifs français ; jamais
  signature électronique, Factur-X, paiement en ligne, suivi de production
  automatique, WhatsApp automatique (les relances WhatsApp sont un LIEN
  manuel), agent de requêtes ;
- MarketingBow : jamais d'image ou de vidéo générée par IA promise, jamais de
  CPL, jamais « partenaire » ou « certifié » Meta (Meta nommé en texte
  seulement, aucun logo) ; « en option, après démonstration » ;
- aucune forme juridique (« Ltd », « SARL ») tant que les sociétés ne sont pas
  immatriculées (`src/lib/legal.ts` à `null`) ;
- aucun client, aucun logo de client, aucune date de création ;
- aucune image d'illustration, aucune personne : seulement le logo (SVG en
  ligne) et les captures du kit (`src/assets/product`, légende « Données
  fictives ») — gardé par `tests/visualRules.test.ts`.

## Forme

- Un titre de page = une phrase, sans point final.
- Un paragraphe = trois lignes au plus à 1440 px.
- Les listes de capacités : un nom de capacité, puis une phrase.
- Libellés d'action : verbe à l'infinitif (« Prendre rendez-vous »).

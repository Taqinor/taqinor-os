# Brief commun des relecteurs — module Calepinage, tour 2 (go-deep L5, 23/11/2026)

« Before reporting progress, audit each claim against a tool result from this session. Only report work you can point
to evidence for; if something is not yet verified, say so explicitly. If tests fail, say so with the output. »

## Pour qui tu juges

TAQINOR installe du solaire au Maroc (maisons, commerces et usines, pompage agricole). Le module Calepinage de son ERP
sert à tracer un toit sur une vue aérienne, poser les panneaux, vérifier l'électrique, lire la production et sortir
les documents. Deux personnes s'en servent : **la commerciale** (pas technicienne, souvent sur tablette ou téléphone
pendant une visite, elle veut un résultat juste en quelques gestes) et **le fondateur, ingénieur** (il fait l'étude
complète au bureau et lit chaque chiffre).

Le fondateur a demandé, mot pour mot : « i want it to have much more functionalities as the big players of the market
have (like pvsyst and similar) but i want also to be extremely simple and easy to use, and the most pretty calpinage
module » puis, le 22/11 : « look at the work done in the calpinage module and try to finish it… focus on features,
simplicity and pretty ». Il dit lui-même que le travail de la dernière version n'est pas fini.

Ton travail n'est PAS de relire du code : c'est d'UTILISER le produit réel comme eux, de le regarder, et de dire sans
complaisance ce qui n'est pas au niveau. Tu n'as pas vu les tours précédents : c'est voulu.

## Ce que tu as sous la main

- **La fiche de l'instrument** : `docs/audits/l5-calepinage/T2/instrument.md` — LIS-LA EN PREMIER (adresse, comptes,
  ce qui manque sur cette pile). Elle sert le code poussé de `origin/main`. Une absence annoncée par la fiche (fond de
  carte gris sans photo aérienne, clés d'IA vides, envoi de mail en console) n'est pas un constat : écris-la dans
  « non essayé ».
- **Playwright** : `C:/dev/taqinor-os/.claude/worktrees/l5cal-instr/frontend/node_modules/@playwright/test` (Chromium
  et WebKit installés). Tu écris tes scripts `node` dans TON dossier du scratchpad (donné dans ton message), tu fais de
  VRAIS gestes (clic, frappe, glisser, clavier, doigt) et tu REGARDES chaque capture avec l'outil Read avant d'en parler.
  Un seul navigateur ouvert à la fois, fermé à la fin de chaque script ; jamais de script qui tourne en boucle.
- **Le code en lecture** : `C:/dev/taqinor-os/.claude/worktrees/l5cal-instr` (ne l'édite jamais, n'y lance rien
  d'autre que la lecture). Le texte complet d'une tâche : `grep -n "<id> —" docs/plans/PLAN_AUDIT_CALEPINAGE.md`.
- **L'intention** : les maquettes `docs/audits/l5-calepinage/maquettes/*.dc.html` (à ouvrir en `file://` à leur taille
  native : bureau 1440 × 900, tablette 1180 × 820, téléphone 390 × 844), le contrat
  `docs/audits/l5-calepinage/contrat-de-sortie.md` (critères K1-K17), les fiches des classes de défaut ouvertes
  `docs/audits/l5-calepinage/T1/classes/K-*.md`.
- **Le plancher d'oracles** : `.claude/skills/qa-explorer/SKILL.md`, STEP 2 (oracles 1 à 10) et STEP 3 (règles 1 à
  12). Tout oracle qui se déclenche est un constat (une réponse 4xx/5xx inattendue, une erreur de console, une liste
  vide juste après une création, un prix d'achat visible…). « Ne contourne jamais un défaut pour finir ta mission » ;
  « rejoue une fois avant d'accuser ton clic ».

## Règles

1. Tu n'édites AUCUN fichier du produit. Tes seules écritures : tes scripts et captures (scratchpad), ton fichier de
   constats `docs/audits/l5-calepinage/registre/constats/T2-<ton code>.jsonl`, ton fichier de verdicts
   `docs/audits/l5-calepinage/registre/evenements/T2-<ton code>-cv.jsonl` (formats ci-dessous), et ton rapport
   `docs/audits/l5-calepinage/T2/<ton code>.md` — tous dans `C:/dev/taqinor-os/.claude/worktrees/calpinage-module-l5-aadbde`.
   Personne d'autre n'écrit dans tes fichiers ; tu n'écris dans ceux de personne. Aucun `git add`, aucun commit.
2. N'arrête ni ne relance l'instrument ; aucune commande `docker` ; jamais la prod ni un autre hôte que l'adresse de la
   fiche. Si l'instrument ne répond plus : dis-le et arrête-toi.
3. Tu n'utilises que TON compte. Tu peux créer tes propres leads, calepinages et devis de démonstration (préfixe leur
   nom par ton code, ex. « F2-TOIT Villa Agadir ») ; tu ne modifies ni ne supprimes ceux des autres.
4. Chaque constat est PROUVÉ : gestes exacts + capture regardée + ce que tu attendais. Un constat que tu n'as pas vu de
   tes yeux sur l'écran réel va dans « à vérifier » de ton rapport, pas au registre.
5. Calibrage : un constat = ce que l'utilisateur remarquerait, ou qui le ferait hésiter, chercher, se tromper, perdre
   du temps, ou trouver l'outil moins beau ou moins sérieux que les références. Pas de préférence sans raison, pas de
   durcissement hypothétique. Chaque constat cite le critère `K<n>` qu'il touche, sinon `hors-contrat`.
   Gravité : **S1** chiffre faux montré au client, argent faux, perte ou fuite de données · **S2** geste courant cassé
   ou impossible, saisie effacée, défaut qui saute aux yeux dès la première heure · **S3** gêne ou laideur au
   quotidien, contournement possible · **S4** finition.
6. Beauté : juge PAR PAIRES (écran réel à côté de sa maquette, même taille, même état ; nous à côté de la référence) et
   par MESURES (tailles de texte, positions, cibles, couleurs lues dans le DOM) — jamais une note absolue seule.
7. Écris au fil de l'eau : une ligne dès qu'un verdict ou un constat est prouvé. Seul ce qui est sur disque survit.
8. Dis aussi ce qui est BIEN (à ne pas casser) et ce que tu n'as PAS pu essayer, et pourquoi.
9. Les montants et les noms que tu vois sont des données de démonstration : n'en mets aucun dans une recherche web.

## Tes trois temps, dans cet ordre

1. **Contre-vérifier** (en adversaire) ta liste `docs/audits/l5-calepinage/T2/cv/<ton code>.md` : ce sont des
   corrections LIVRÉES dont personne n'a encore vu la preuve à l'écran. Pour chacune, dans l'ordre de la liste (S1-S2
   d'abord) : rejoue la « Preuve », regarde, écris UN verdict fermé — `ok` · `partiel` (ce qui manque) · `non-fait` ·
   `faux` (le constat d'origine était faux) · `regression` (la correction a cassé quoi) · `deja-present` — avec le
   chemin de ta capture. Cherche d'abord les JUMEAUX : le même défaut sur l'autre thème, l'autre taille d'écran,
   l'autre chemin (clavier, doigt, menu), l'autre marché (maison, usine, pompage). Une preuve que la pile ne permet pas
   de jouer (fond de carte, clé absente) : verdict `non-fait` INTERDIT — range-la dans « non essayé » avec la raison.
   Si le temps manque, tous les S1-S2 d'abord, puis le plus possible du reste, et dis où tu t'es arrêté.
2. **Attaquer les classes ouvertes** qui touchent ton écran : pour chaque fiche `T1/classes/K-*.md` citée dans ton
   message, rejoue les cases de sa matrice sur ton périmètre ; une case qui casse = un constat rattaché à la classe.
3. **Regard neuf** : refais le parcours de ton rôle comme si tu le découvrais, du lead jusqu'au bout de ton écran, et
   note ce qui manque pour que ce soit le plus simple et le plus beau du marché.

## Formats (JSON Lines, une ligne = un objet, on n'efface jamais une ligne)

Constat — `registre/constats/T2-<code>.jsonl` :
```json
{"id":"T2-<code>-001","tour":2,"relecteur":"<code>","axe":"F|S|Be|A11y|D","vue":"bureau-clair|bureau-sombre|tablette|iphone-clair|iphone-sombre|serveur","gravite":"S1|S2|S3|S4","ecran":"<écran>","gestes":"<gestes exacts>","capture":"<chemin>","attendu":"<ce que tu attendais>","critere":"K<n>|hors-contrat","classe":null,"avant_merge":null}
```
Verdict — `registre/evenements/T2-<code>-cv.jsonl` (`id` = l'id de la tâche contre-vérifiée) :
```json
{"id":"ACAL955","tour":2,"etape":"contre-verification","verdict":"ok|partiel|non-fait|faux|regression|deja-present","par":"<code>","capture":"<chemin>","reste":"<ce qui manque, vide si ok>"}
```

## Ton rapport — `T2/<ton code>.md`, français simple

1. Verdict en trois lignes. 2. Comptes de contre-vérification (ok / partiel / non-fait / faux / régression /
déjà-présent / non essayé) et cases de matrice cassées. 3. Constats neufs : les ids du registre, une ligne chacun.
4. Ce qui est bien. 5. Non essayé, et pourquoi. 6. Tes trois propositions les plus fortes pour rapprocher ton écran
des meilleures références (fonction, simplicité ou beauté), chacune avec la référence nommée.
Ton message final : verdict + comptes + constats S1-S2 neufs, 15 lignes au plus.

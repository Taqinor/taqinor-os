# Tour 5 — rejeu des corrections : sommaire

Reconstruit le 26/11/2026 depuis le dépôt (les scripts du tour 4 étaient perdus). Sources : `git log origin/main..origin/dev-lot5`
(265 commits, dont 200 hors fusions), `registre/constats/T4-*.jsonl`, `T4/tour4/a-rejouer-{devis,calepinage}.json`,
`T4/tour4/rejeu-Y1.json`, `docs/audits/decisions.yml` (D-ACAL-102 à 130). Fichier complet : `a-rejouer.json`
(207 lignes : 199 à rejouer + 8 non rejouables à l'écran).

## Comptes

| Ensemble | Nombre |
|---|---|
| Constats T4 corrigés au lot 5 (cités dans un sujet de commit de `origine/main..dev-lot5`, ou le corps du commit) | 75 (70 nouveaux + X1-001, X1-002, U2-019, U2-020, X4-018 déjà dans la liste du tour 4) |
| Restes du tour 4 jamais rejoués (105 − 4 faits par Y1) | 101 (dont X4-018, corrigé de nouveau au lot 5 : un seul enregistrement, état le plus récent) |
| Les 4 lignes « non-rejoué » de Y1 (U2-019, U2-020, X1-001, X1-002) | remises à rejouer : D-ACAL-102 et D-ACAL-115 ont rendu leurs correctifs actifs pour les nouveaux rendus (commits 0e2e7ff8b, 5e821aba6) |
| Constats à rejouer | 174 (+ 1 non rejouable : X6-002) |
| Décisions D-ACAL à effet visible (lignes propres) | 19 ; 7 autres décisions sont portées par la ligne du constat qu'elles corrigent (102, 103, 111, 115, 116, 119, 123) |
| Corrections sans constat à effet visible | 6 (E9b-1, E9b-2, ADEV162, ACAL2047, REGLAGES-RECALCUL, B2-POSE-SUPPOSEE) |
| **Total à rejouer** | **199** |
| Non rejouables à l'écran | 8 (voir plus bas) |

Par gravité (199 lignes) : S1 4 · S2 54 · S3 98 · S4 24 · décisions sans gravité 19.

## Paquets (tailles = nombre de rejeux)

| Paquet | Contenu | Compte principal | Moteur / taille | Rejeux | S1/S2/S3/S4 |
|---|---|---|---|---|---|
| **A** `brief-a-devis-pdf-lead` | générateur de devis, PDF, onglet Devis de la fiche du lead, listes Ventes et CRM, SAV après devis | anon_resp | Chromium bureau | **56** | 2/16/29/7 (+ 2 décisions sans gravité ; les 2 extras sont déjà dans S3/S4) |
| **B** `brief-b-atelier-toit-panneaux` | atelier bureau : toit, panneaux, Expert, enregistrement, nouveau calepinage | anon_commercial | Chromium bureau | **33** | 0/8/19/5 |
| **C** `brief-c-atelier-electrique-resultats-docs` | électrique, résultats, documents, rapport, devis lié, V2 | anon_resp (+ admin2 pour X5-012) | Chromium bureau | **30** | 1/12/11/5 |
| **D** `brief-d-tactile-webkit` | tablette 1180 × 820 et téléphone 390 × 844, WebKit : relevé, vue client, atelier, Technicien | anon_commercial, anon_tech, anon_admin2 | WebKit tactile | **30** | 0/8/16/5 |
| **E** `brief-e-droits-reglages` | réglages du calepinage (Sources, Bibliothèque, Réglages), droits Commercial / responsable / Technicien, surcharges et marge (admin) | anon_admin2 (+ tech, commercial, resp pour D-104/117) | Chromium bureau | **19** | 0/1/13/1 (+ 4 décisions, 1 extra) |
| **F** `brief-f-pompage-ci` | pompage agricole (kit de protections, prix, fiches) et C&I (options, aperçu, PDF industriel) | anon_admin | Chromium bureau | **31** | 1/9/10/1 (+ 10 décisions) |

Les paquets sont plus petits que 40-60 pour B, C, D, E, F parce que le total (199) se répartit sur six zones indépendantes ;
regroupement conseillé si l'on préfère 4 séances : **A (56) · B+C (63, atelier bureau) · D+E (49) · F (31)**.

### Qui peut tourner en même temps (deux navigateurs au plus sur le poste)

Chaque relecteur crée ses propres leads (`R5A-…`, `R5B-…`) : aucun enregistrement n'est partagé. Les comptes sont répartis pour
qu'aucune paire ne partage un compte :

1. **A ∥ B** (anon_resp ∥ anon_commercial)
2. **C ∥ D** (anon_resp ∥ anon_commercial / anon_tech / anon_admin2)
3. **E ∥ F** (anon_admin2 / tech / commercial ∥ anon_admin) — E change des réglages société (valeur d'origine à rétablir) : ne le lancer
   jamais en parallèle de B, C ou D (le calepinage lit ces réglages). Le seul geste de E avec anon_resp (D-ACAL-117) se joue seul, à la fin.

## Non rejouables à l'écran (couverts par des tests, pas par un rejeu)

| Id | Raison |
|---|---|
| T4-X6-002 | production par option du PDF commercial : derrière le niveau de règles 15 (éteint) |
| D-ACAL-108 / ADEV155 | moteur sans toit sur le plan par défaut : niveau 15 seulement, et garde interne de la porte (B1 : valeur de fiche illisible) |
| D-ACAL-120 | décalage d'une heure en WebKit : aucun code changé, à regarder sur un vrai iPad |
| D-ACAL-122 | date de coupure du 26/11 : décision de déploiement |
| ACAL2044 | cache PVGIS borné + verrou + mémoire : serveur seulement |
| ACAL987 | course dans une spec e2e : test seulement |
| LOT5-TESTS-ET-GARDES | tests « CI lot 5 », gardes C20, documents régénérés, migrations stock 0190-0195 |

Sous condition (listées dans les briefs, à rendre `non-rejouable` avec la raison si la condition n'est pas réunie) : U1-011 et U2-018
(serveur lent), X9-011 (réponse lente), ACAL2047 (envoi double), D-ACAL-125 (selon que les prix du kit sont posés), D-ACAL-107 (moteur
sans toit éteint).

## Ce qui bloque ou demande une action avant

1. **Aucun compte « Technicien responsable »** dans la copie d'essai (`etat.md` : anon_admin, anon_admin2, anon_commercial, anon_resp,
   anon_tech). D-ACAL-126 (1 ligne, paquet E) est bloquée ; à créer par l'écran Utilisateurs en Administrateur (rôle Technicien
   responsable, avec anon_tech dans son sous-arbre), sinon `non-rejouable`. Je n'ai pas vérifié l'état réel de la pile.
2. **La pile doit tourner sur `dev-lot5`** (tête 647e04237 ou plus récente) avec les migrations stock 0190 à 0195 (prix et fiches du pompage :
   D-ACAL-127 à 130) ; je n'ai pas vu la pile, rien ne le prouve ici. Sinon les lignes du paquet F et la plupart des lignes du lot 5 se
   rejouent sur du code absent.
3. **Nouveaux rendus seulement** : les phrases PDF corrigées (D-ACAL-102, 111, 114, 115, 116) valent pour un brouillon ou un devis envoyé à
   partir du 26/11/2026 ; un devis déjà envoyé garde sa phrase. Dire la date de la pile si elle est antérieure.
4. **Les enregistrements cités dans les lignes** (leads X1 à X9, calepinages 1934 à 1981, devis DEV-202611-01xx) viennent des tours précédents ;
   ils peuvent ne pas exister dans la copie : les briefs demandent de refaire le scénario sur un enregistrement neuf (scénarios a-r du plan).
5. Le niveau de règles 15 reste éteint : tout ce qui en dépend (X6-002, moteur sans toit) est dans la liste des non-rejouables.
6. `anon_admin` (distinct d'`anon_admin2`) est utilisé par le paquet F pour ne pas partager un compte avec E ; je n'ai pas vérifié qu'il se
   connecte (il est cité dans `etat.md` ligne 1001 comme compte de la copie).

## Fichiers

`a-rejouer.json` · `brief-a-devis-pdf-lead.md` · `brief-b-atelier-toit-panneaux.md` · `brief-c-atelier-electrique-resultats-docs.md` ·
`brief-d-tactile-webkit.md` · `brief-e-droits-reglages.md` · `brief-f-pompage-ci.md` · `SOMMAIRE.md`
(dossier `…\scratchpad\tour5\`, rien n'a été écrit dans le dépôt).

Vocabulaire de verdict des briefs : `ok` · `non-corrige` · `regression` · `non-rejouable` (les tours précédents écrivaient
`corrige` / `pas-corrige` / `autre` / `non-rejoue` : à convertir pour `suivi-des-constats.md` : ok→corrige, non-corrige→pas-corrige).

# Audit des `ok` du tour 2 — lot D (documents, parcours, liste, téléphone et tablette), AUDIT-OK-D, 23/11

Liste : `T2/cv/AUDIT-OK-D.md` (52 verdicts, tous joués dans l'ordre). Lignes : `registre/evenements/T2-audit-ok-D.jsonl`.
Méthode : texte complet de la tâche, ligne du relecteur, rapport, capture ouverte (et voisines) ; DXF de F2-DOCS-b relus et PDF rendu par moi.

**Comptes : confirmé 26 · insuffisant 24 · contredit 2. Mal prouvés : 26 sur 52 (50 %).**

| Relecteur | conf. | insuf. | contr. | | Relecteur | conf. | insuf. | contr. |
|---|---|---|---|---|---|---|---|---|
| F2-DOCS-a | 5 | 1 | 0 | | S2-PARCOURS-b | 5 | 2 | 0 |
| F2-DOCS-b | 4 | 3 | 2 | | T2 | 6 | 2 | 0 |
| S2-PARCOURS | 2 | 13 | 0 | | RATT-2 | 4 | 3 | 0 |

## Contredits (2)
- **ACAL598** (F2-DOCS-b) : sans arête d'égout typée le manquant est générique (« illisible sur le document ») au lieu de nommer la saisie ; `p1979-409-marge.json` : le composant exemple de la tâche (« Marge d'échafaudage… ») fait refuser tout le plan de pose en 409.
- **ACAL594** (F2-DOCS-b) : la preuve avoue que `zones[].result.annualKwh` (4 312 kWh) de A est recopié dans chaque variante (la tâche exige « aucune production recopiée ») ; capture citée sans rapport.

## Insuffisants (24) — ce qu'il reste à rejouer
- ACAL1008 : annexe « paramètres du site » omise et rendement de pose `None` sur un rapide lié à un devis resynchronisé.
- ACAL595 : cas « mixte » (deux modules sur deux pans) et `null` sans moduleId.
- ACAL578 : entraxe d'ombrière non saisi nommé ; cas k ≥ 2 (pas 1,15 m, portée 2,4 m ⇒ 7 pieds).
- ACAL834 : pompe chiffrée retenue ⇒ pompe, variateur, 4 composantes de HMT, 12 volumes, couverture imprimés.
- ACAL860 : réponse de `pret-a-envoyer/` (forme, ordre, tout vert ⇒ `pret: true`, 404 autre société).
- ACAL867 : générer le devis de l'étape Documents et l'ouvrir (s30 identique à l'avant) ; un seul `cal-generer-devis`.
- ACAL1281 : ids `rp9-*` à chaque étape (jamais démontés), lignes de `ToitureDesign.jsx`, spec parcours verte.
- ACAL852 : carte Recommandation visible sans facture (« — facture inconnue », phrase « Facture inconnue »).
- ACAL861 : geste « Saisir la facture » absent de la ligne ; lire geste et cause dans la route ; lead avec facture ⇒ ok.
- ACAL893 : panneau Allées sans bouton société + page `/calepinage/reglages/allees`.
- ACAL1282 : mode lead `/crm/leads/<id>` inchangé. ACAL1284 : bande `cal-onglet-*` rouverte par Avancé/Expert ; carte non rechargée.
- ACAL938 : lien du panneau Masse et lestage vers l'ancre du premier manquant (aveu du relecteur).
- ACAL964 : `libelles` servis, six listes sans tiret bas, PUT avec la valeur technique.
- ACAL948 : recherche « Calepinage #N » / « #N » dans la liste `/calepinage`, égalité sur le pk.
- ACAL961 : champ hors liste ⇒ « Champ non reconnu » + « Retirer », renvoyé inchangé.
- ACAL871 : `GET calepinages/explications/` et mutant du test. ACAL969 : garde `langageVisuel.test.mjs` et son mutant.
- ACAL859 : dossier réglementaire incomplet ⇒ « n pièce(s) à fournir » ; capture citée = onglet Production.
- ACAL906 : onduleur « incompatible » (seul « reserve » joué). ACAL521 : la spec e2e n'a pas été lancée (10 visées à la main, pas 12).
- ACAL588 : branche `svg: None` + motif (conception changée après acceptation).
- ACAL895 : KPI du calepinage et API publique sans les exemples. ACAL577 : bandes serveur comparées à l'atelier, pas à la formule.

**Remarques.** S2-PARCOURS n'a écrit aucune preuve dans ses lignes `ok` : 13 sur 15 tombent. ACAL673 : capture citée absente (`d1936-cablage-p1.png`), jugée sur le PDF téléchargé. ACAL1027 : capture d'un autre écran, jugée sur la mesure DOM écrite.

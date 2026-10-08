# Règles juridiques du site (YBW25)

Source unique des identités : `src/lib/legal.ts`. Gardes : `tests/legal.test.ts`.

## La règle d'or

**Rien d'affiché pour une entité qui n'existe pas.** Chaque champ de `legal.ts`
reste `null` tant que Reda ne l'a pas fourni (YBWM5 pour la société
britannique, YBWM6 pour la SARLAU, YBWM8 pour le directeur de la publication,
le responsable du traitement et l'hébergeur). Un bloc d'entité n'est rendu que
s'il est COMPLET (`lignesEditeur`/`lignesMaroc` renvoient `[]` sinon) : jamais
de bloc partiel, jamais « Ltd » ni « SARL » ni numéro tant que l'entité n'est
pas immatriculée. Aucune valeur n'est inventée, déduite ou reprise de
l'entreprise d'installation. L'hébergeur est relevé À LA MAIN (valeur + URL
source + date de lecture) et confirmé par Reda — jamais téléchargé au build.

## Les deux entités (D-YBW-2)

| Bloc | Champs requis | Facultatif |
| --- | --- | --- |
| `editeur` — société britannique qui publie le site | nom exact, partie du Royaume-Uni, numéro, siège | n° TVA (seulement s'il existe) |
| `maroc` — SARLAU qui signe et facture au Maroc | dénomination + mention « SARL d'associé unique », capital, siège, RC, ICE, IF, gérant | — |
| `commun` | (requis au lancement, YBW85) e-mail, directeur de la publication | téléphone, hébergeur sourcé, récépissés CNDP, représentant UE, responsable du traitement |

## Règles et sources (telles que citées par le plan du 06/10/2026)

Les textes ci-dessous sont ceux relevés par la planification L3 du 06/10/2026
(`docs/plans/PLAN_YANBOW_WEB.md`, § Faits établis). **Cette tâche n'a pas
relu les textes à la source** : chaque point reste une question pour le conseil
(YBWM9, liste dans `docs/LEGAL_REVIEW.md` — YBW29). Aucune de ces règles n'est
citée sur le site lui-même.

| Texte | Ce qu'il impose au site |
| --- | --- |
| Companies Act 2006, s.51 (Royaume-Uni) | Avant l'immatriculation, ne rien dire ni laisser croire que la société existe (responsabilité personnelle de qui agit en son nom). |
| Company, LLP and Business (Names and Trading Disclosures) Regulations 2015, reg. 25 | Une fois immatriculée : nom exact, partie du Royaume-Uni, numéro et adresse du siège sur le site (et n° TVA s'il existe). |
| Loi marocaine 5-96 (SARL), art. 45 selon le plan | Dénomination accompagnée de la mention de forme (« SARL d'associé unique ») et du capital ; RC sur les documents. |
| Loi marocaine 09-08 (art. 2, 5, 10, 19, 43-44) et CNDP | Information des personnes, déclaration à la CNDP (récépissé) avant le traitement du formulaire si la SARLAU en est responsable. |
| LCEN (France), art. 1-1 selon le plan | Identification de l'éditeur, du directeur de la publication et de l'hébergeur (nom, adresse, téléphone) — portée sur un éditeur étranger NON tranchée. |
| RGPD art. 3(2)/27 | Représentant dans l'UE éventuel — question pour le conseil (YBW29). |

## Ce que le code garantit

- `LEGAL` = tout `null` au 07/10/2026 (aucune entité créée).
- `editeurComplet`, `marocComplet`, `hebergeurComplet` décident seuls de
  l'affichage ; les pages juridiques (YBW27/YBW28) restent non routables tant
  que leurs champs requis sont `null` (porte YBW12).
- `nomResponsable` ne renvoie jamais une forme juridique pour une entité dont le
  bloc n'est pas complet.

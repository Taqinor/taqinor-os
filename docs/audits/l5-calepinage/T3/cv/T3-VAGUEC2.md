# Contre-vérification de la vague C complète et du début de la vague D — T3-VAGUEC2

La pile sert le code `428193cc6f` (reconstruite vers 16 h 10 UTC le 23/11). Texte complet de chaque tâche :
`grep -n "<ID> —" docs/plans/PLAN_AUDIT_*.md` dans `C:/dev/taqinor-os/.claude/worktrees/calpinage-module-l5-aadbde`.
Le premier rejeu (`docs/audits/l5-calepinage/T3/T3-VAGUEC.md`) donne les gestes et ce qui n'allait pas ; ses scripts
sont dans `…/scratchpad/T3/T3-VAGUEC/`. Joue dans cet ordre.

## A. Ce que le premier rejeu avait trouvé non fait

1. **ACAL1900** (S1) — toit plat 12 × 8 m, module 710 W, cible 5 : Expert > Déplacer les panneaux > Remplir
   automatiquement ⇒ 16 ; Enregistrer ; serveur = 16 ; RECHARGER : en-tête, carte, bande et Guidé disent 16 ; bouger le
   curseur du soleil et changer de saison : toujours 16 ; Enregistrer sans geste : serveur = 16 ; où l'écart à la cible
   est-il dit ? Puis : changer de module ⇒ la pose n'est pas gardée à tort (aucun panneau hors du toit).
2. **ACAL1903** — « Production visée » 40 000 : « au plus N panneaux » = le nombre que « + » atteint (attendu 27 sur ce toit).
3. **ACAL1908** — Démarrage rapide à 1440 × 900 : défilement maximal relu = 0.
4. **ACAL1985** — étape Documents en Guidé : « Générer le devis » est le bouton doré v2 (52 px de haut, rayon 14) ; en
   Expert il n'est pas doré.
5. **ACAL1912** — pose dont des panneaux ne sont raccordés à aucun onduleur, simulée : Guidé > Résultats affiche
   l'avertissement et « Production comptée sur N des M panneaux posés ».
6. **ACAL1905** — non jouable sans ralentir le serveur : « non essayé » accepté.

## B. Un seul moteur (le calepinage prend sa conception dans le devis)

Prépare : un lead RÉSIDENTIEL avec facture (ville reconnue), son devis automatique (bouton « Devis automatique » de la
fiche du lead, ou la création de devis), puis le calepinage ouvert DEPUIS ce devis.
7. **ACAL1951** — la cible de l'atelier est la quantité de panneaux de l'option retenue du devis, et l'écran dit de quel
   devis et de quelle option ; un toit rempli au-delà dit l'écart (« N posés, M au devis »).
8. **ACAL1952** — étape Électrique, sans rien saisir : l'onduleur est celui du devis, avec la mention « Repris du devis
   <référence> » ; en désigner un autre à la main : l'écart avec le devis est dit, la saisie est gardée.
9. **ACAL1953** — aucune mention « contre 16 » dans les contrôles électriques d'un calepinage lié à un devis.
10. **ACAL1954** — le rapport panneaux / onduleur a le MÊME verdict à l'étape Électrique et dans « Prêt à envoyer ? »,
    et dit d'où vient la borne (« règle du devis », « fourchette de la société » ou « capacité publiée de l'onduleur »).
    Si le catalogue a un onduleur hybride qui publie sa capacité : vérifie qu'un champ dans cette capacité est bon.
11. **ACAL1955** — passe le devis à « envoyé » (geste d'envoi de l'ERP ; rien ne part : mails coupés) alors que le
    calepinage est lié à un AUTRE devis brouillon du même lead (crée ce cas : deux devis automatiques, calepinage sur le
    premier, envoi du second) : le calepinage suit le devis envoyé ; son journal le dit.
12. **ACAL1956 + ACAL1958** — étape Résultats du calepinage lié au devis envoyé, sans simulation : « Production retenue
    par le devis : N kWh par an » ; le bouton de pied « Préparer les documents » est là avant simulation et à l'état
    incomplet.
13. **ALEA67** — fiche d'un lead résidentiel dont la ville est « casa » (non reconnue) et sans GPS : la fiche dit ce qui
    manque (la ville) au lieu de « prêt » ; avec « Casablanca » elle redevient prête.

## C. Début de la vague D

14. **ACAL1407** — obstacle (cheminée haute) au CENTRE d'un pan dont les panneaux sont posés ailleurs : la perte
    d'ombrage proche affichée est faible (plus de « −72 % ») ; obstacle juste devant les panneaux : une perte est dite.
15. **ACAL1840** — « Montrer au client » d'un calepinage au résultat incomplet : une tuile de production
    « estimation de la pose » est affichée.
16. **ACAL1755** — si un calepinage lié à un devis a une simulation COMPLÈTE : un seul chiffre s'il est égal à celui du
    devis, sinon les deux nommés et « Réviser le devis ». Si aucun résultat complet n'est atteignable sur la pile :
    « non essayé », avec la raison.

Garde-fou (court, en dernier) : un parcours Guidé Toit → Panneaux → Électrique → Résultats → Documents sur un
calepinage neuf, par les boutons d'étape, sans écran mort ni message d'erreur.

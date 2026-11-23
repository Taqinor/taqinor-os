# Contre-vérification de la vague D (décisions du fondateur du 23/11) — T3-VAGUED

La pile sert le code de la branche à 19 h 45 UTC le 23/11 (toutes les lanes des vagues C et D pliées). Texte complet de
chaque tâche : `grep -n "<ID> —" docs/plans/PLAN_AUDIT_*.md` dans
`C:/dev/taqinor-os/.claude/worktrees/calpinage-module-l5-aadbde`. Ce que le fondateur a décidé pour chacune :
`docs/audits/l5-calepinage/controles/lanes-vague-D.md` et `coutures-vague-D.md`. Scripts de connexion et d'ouverture de
l'atelier réutilisables : `…/scratchpad/T3/T3-VAGUEC2/`, `…/scratchpad/PR2/`, `…/scratchpad/TA/`. Joue dans cet ordre.

## A. Le devis se calcule seul (demande du fondateur : « should only need the bill and one consumption profil »)

1. **ADEV125 + ADEV126 + ADEV127** — crée un lead COMMERCIAL avec seulement : une ville reconnue, une catégorie
   commerciale qui a un profil type (bureau, commerce…), une facture en dirhams. Sans contrat, sans phase, sans jours
   d'ouverture : la fiche le dit-elle prêt ? Le bouton du devis automatique aboutit-il ? Le devis (ou son journal)
   DIT-il chaque supposition avec son champ (tarif basse tension, triphasé, jours ouvrés, profil estimé, 30° plein sud) ?
   Le devis est-il marqué estimation ? Note exactement ce qui est refusé s'il est refusé (message, champ).
2. **Même lead en INDUSTRIEL** avec un régime d'équipes (2 × 8 par exemple) et sans jours : aboutit-il ? Que manque-t-il ?
3. **APAR92 + ALEA67** — lead résidentiel avec facture et ville « casa » : prêt, et le devis automatique aboutit avec la
   production de Casablanca ; ville « maroc » : la fiche dit ce qui manque (la ville) ; ville « فاس » : prêt.
4. **ADEV123** — devis automatique résidentiel d'un lead sans présence en journée déclarée : les suppositions sont
   dites avec leur champ (présence, été = hiver, kWh tirés des dirhams, 30° plein sud).

## B. Le calepinage complet au premier jour

5. **ACAL1968 + ACAL1349** — société de la pile : page « Démarrage rapide », « Remplir… » (si des valeurs manquent) :
   salissure 3 %, dégradation initiale 1,5 % / 1 %, indisponibilité 2 %, câbles 1,5 % + 1 % sont posées, dites
   « supposé » avec leur source. Un calepinage simulé ensuite a-t-il un résultat COMPLET (plus de « Ce qui manque
   encore » pour ces quatre postes) ? S'il reste incomplet, dis EXACTEMENT ce qui manque encore.
6. **ACAL1987** — calepinage neuf d'un lead à facture : toit tracé, pose, matériel électrique désigné, Enregistrer :
   l'étape Résultats passe-t-elle SEULE à « Simulation en cours… » puis au résultat, sans clic ? Ré-enregistrer sans
   geste : aucun second calcul. Pose incomplète : « Il manque … » dit quoi.
7. **ACAL1331** — calepinage vierge d'un lead à facture : dès le toit fermé, la pose est à la taille tirée de la
   facture et l'écran dit « Posé d'après la facture : N panneaux… » ; « + » : la phrase part, rien ne re-pose.
8. **ACAL1671** — un pan en châssis et un pan affleurant : la ligne « Chaleur des panneaux » dit la pose retenue
   (« pose libre », « dos isolé ») et n'est plus « sans valeur ».
9. **ACAL1407** — obstacle haut au centre d'un pan dont les panneaux sont posés ailleurs : perte d'ombrage proche
   faible ; obstacle devant les panneaux : perte dite.

## C. Un seul chiffre, et ce que l'écran dit

10. **ACAL1755 + ACAL1956** — calepinage lié à un devis ENVOYÉ, simulé : si la production simulée diffère de celle du
    devis, l'étape Résultats dit les deux, nommées, et propose « Réviser le devis » ; le rapport d'étude (PDF) dit les
    deux et « le devis envoyé n'est pas modifié ». S'ils sont égaux : un seul chiffre.
11. **ACAL1951 + ACAL1952** — calepinage ouvert depuis un devis : la note de la cible nomme le devis ET son option
    (« … au devis DEV-… (option sans batterie) »), avant et après « Remplir » ; en Guidé à l'étape Électrique :
    « Repris du devis <référence> » ; le module posé par défaut est celui du devis.
12. **Ratio** — un rapport panneaux / onduleur sous 1,00 : la phrase nomme la borne franchie et d'où elle vient.
13. **ACAL1672** — onglet de l'étude où figure le P90 : il cite ses composantes (variabilité entre années, modèle,
    météo, fiche) avec leur source. **ACAL746** : une comparaison NASA POWER est-elle visible quelque part (attendu :
    servie par l'API ; l'affichage n'est pas encore branché — dis ce que tu vois).

Garde-fou (court, en dernier) : parcours Guidé Toit → Panneaux → Électrique → Résultats → Documents d'un calepinage neuf
par les boutons d'étape, sans écran mort ni message d'erreur ; une pose de 16 pour une cible de 5 se rouvre à 16.

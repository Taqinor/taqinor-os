---
name: devis-envoyes-nouveaux-rendus
description: Décision fondateur 08/10/2026 — les correctifs de chiffres du moteur (audit AMOT) ne s'appliquent qu'aux NOUVEAUX rendus ; un devis déjà envoyé garde ce que le client a reçu
metadata:
  type: project
---
Décision du fondateur (08/10/2026, question interactive) sur 19 correctifs de l'audit moteur
(ADEV28, AMOT8–11, 15, 16, 19, 24, 26, 29–33, 35, 45, 58, 59 + dépendants) qui changent des
chiffres imprimés (retour sur investissement, économies…) au re-rendu d'un devis déjà envoyé :
**on les construit, mais « nouveaux rendus seulement »** — un devis envoyé continue de montrer
exactement ce que le client a reçu ; seuls les brouillons et les nouveaux rendus prennent le calcul
corrigé. Mécanisme : `Devis.regles_calcul` (1 = règles d'origine, posé sur tout devis non brouillon
par la migration ventes 0138 ; 2 = corrigé, défaut des nouveaux devis et révisions), lu via
`domain/regles_calcul.calcul_corrige(devis)` aux seuls points où un correctif change un chiffre.
Dry-run en lecture seule : `manage.py regles_calcul_ecarts_dryrun` (aucune écriture, aucune
réparation sans nouvel accord).
Niveau 3 (27/10/2026, D-RES-2710-1/2) : la migration ventes 0142 laisse à 2 tout devis non
brouillon et passe brouillons + devis neufs à 3 (nouveau défaut) ; les corrections du 27/10 se
branchent sur `regles_au_moins(devis, REGLES_CORRIGEES_2710)`, jamais sur `calcul_corrige` (vrai dès 2).

**Why:** un client ne doit jamais voir changer les chiffres d'une offre qu'il a déjà reçue.
**How to apply:** tout futur correctif de chiffres du moteur passe par `calcul_corrige` ; voir aussi
[[reconfirm-client-visible-repairs]].

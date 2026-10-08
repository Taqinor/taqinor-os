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
par la migration ventes 0136 ; 2 = corrigé, défaut des nouveaux devis et révisions), lu via
`domain/regles_calcul.calcul_corrige(devis)` aux seuls points où un correctif change un chiffre.
Dry-run en lecture seule : `manage.py regles_calcul_ecarts_dryrun` (aucune écriture, aucune
réparation sans nouvel accord).

**Why:** un client ne doit jamais voir changer les chiffres d'une offre qu'il a déjà reçue.
**How to apply:** tout futur correctif de chiffres du moteur passe par `calcul_corrige` ; voir aussi
[[reconfirm-client-visible-repairs]].

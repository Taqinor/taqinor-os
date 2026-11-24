---
name: contrats-chantier-decisions
description: 24/11/2026 — dossier contractuel d'un chantier (quatre actes créés avec le chantier) : décisions de Reda (pas de rétractation à domicile, date limite 30 jours, pas de pénalité chiffrée, signataire nommé, version arabe dans la même vague), choix pris seul, où vit le travail
metadata:
  type: project
---

**Demande de Reda (24/11/2026, « go L5 »)** : l'ERP crée quatre contrats pour chaque lead signé, au moment où le
chantier est créé — (1) contrat de démarrage (paiements du devis final et garanties, modifiables), (2) matériel livré
au domicile avec la part à payer, en deux versions prêtes (reste à régler / le client a payé ses 90 %), (3) travaux
bien terminés, signé par le client (protection si le solde n'est pas payé), (4) contrat final au paiement complet
(garanties + conseils de consommation). Le meilleur contenu, et surtout la beauté.

**Décisions de Reda (24/11/2026)** — ne pas re-demander :
- **Pas de droit de rétractation « signature à domicile »** dans les actes : pour lui le chapitre démarchage de la loi
  n° 31-08 vise la vente à domicile, pas une société que le client contacte de lui-même ; « forget about it and dont
  integrate it ». L'acompte reste exigible à la signature. (L'article 45 dit « même à sa demande » : noté pour un
  juriste dans `docs/contrats/juridique.md` § 4, rien de plus.)
- **Date limite d'exécution imprimée : 30 jours après la date du contrat**, par défaut (choisi contre « 60 jours »
  recommandé ; la loi n° 31-08 art. 12-13 permet au client d'annuler si elle est dépassée de plus de 7 jours).
- **Retard de paiement : sans pénalité chiffrée** (mise en demeure, puis suspension, justice ou reprise du matériel).
- **Signataire : son nom et sa qualité**, saisis une fois dans le modèle de la société, imprimés « Représentée par … »
  sur les contrats — le devis reste sans nom de gérant (D-APDF-1 inchangée).
- **Version arabe dans la même vague** (choisi contre « seconde vague » recommandé) : chaque acte se rend en français
  et en arabe ; la traduction arabe accompagne l'acte français (loi n° 31-08, art. 206).
- **Logo : celui du devis, partout** (24/11/2026, « this should be the logo used everywhere, and the logo you just
  added should not be used anywhere ») : tout acte imprime le logo que le moteur de devis imprime (détouré, lettres
  blanches et soleil doré sur l'en-tête bleu nuit), lu par la porte `apps.ventes.selectors.logo_entete_html`. Jamais
  le fichier téléversé posé tel quel, jamais de pastille blanche autour — ni dans un nouveau document.

**Why :** Reda a des soldes impayés sur des chantiers posés (≈ 50 090 DH au 23/11) ; son avocat lui a dit de faire
signer la bonne exécution des travaux.

**How to apply :** la spécification est `docs/contrats/conception.md` (§ 8 choix pris seul et à confirmer, § 9
décisions de Reda), le droit lu et les dix points à faire trancher par un juriste dans `docs/contrats/juridique.md`,
l'état du chantier L5 dans `docs/contrats/ETAT.md`. Le code vit dans `apps/documents/contrats/` (jamais dans
`apps/contrats`, coquille parquée) et `frontend/src/pages/installations/contrats/`. Aucun montant ne se modifie dans
un acte : l'échéancier se corrige sur la vente. Le quitus est refusé tant que la vente n'est pas réglée dans l'ERP.
Les textes par défaut ne sont PAS un avis juridique ; l'arabe doit être relu par un arabophone avant un usage réel.

Related: [[apdf-decisions-fondateur]], [[strategie-v2-2311]], [[decisions-audit-0810]]

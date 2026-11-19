---
name: sensibilites-deux-options
description: Décision fondateur du 19/11/2026 (D-SENS-1) — tableau des sensibilités C&I : retour de chaque scénario au dixième (plus l'entier « 4,0 ans ») et sensibilités propres à l'option « avec batterie » (production re-simulée avec la batterie) ; niveau de règles 14
metadata:
  type: project
---

Décision de Reda du 19/11/2026 (« Yes, fix it »), après un contrôle indépendant des chiffres du devis
industriel DEV-202611-0080.

- **Les deux défauts.** (1) La ligne centrale imprimait le retour au dixième (3,2 ans) mais chaque scénario
  imprimait l'ENTIER servi formaté au dixième (« 4,0 ans » au lieu de 3,3 / 3,2). (2) Un devis à deux options
  n'avait de sensibilités que pour l'option réseau.
- **La règle.** Chaque ligne de sensibilité sert `retour_dixieme_ans` (`economie_ci_options.retour_au_dixieme`
  sur le flux DU scénario, la même interpolation que la ligne centrale) ; le PDF l'imprime. L'option « avec
  batterie » sert `option_avec.economie_flux.sensibilites`, même forme, mêmes scénarios société, même ordre
  (`apps/ventes/domain/sensibilites_option_avec.py`) : production = option RÉ-ÉVALUÉE sur la production ×
  (1 + v) (batterie re-simulée, jamais une économie mise à l'échelle), remplacement de la batterie lu sur les
  cycles du bilan du scénario (niveau 13) ; dégradation / indexation / prix du kWh = une seule grandeur changée
  sur le flux central (batterie comprise). Un scénario non calculable : motif nommé, aucun chiffre.
- **Nouveaux rendus seulement : niveau de règles 14** (`REGLES_SENSIBILITES_1911`, migration 0159 : seuls les
  brouillons jamais envoyés passent de 13 à 14 ; drapeau de rendu `regles_sensibilites_historique`). Un devis
  envoyé garde son tableau et ses lignes servies octet pour octet.
- **Mise en page.** Le PDF empile aujourd'hui un tableau par option ; un tableau combiné est un autre chantier.

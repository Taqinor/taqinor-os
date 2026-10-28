# AGV (vendeur agricole) — état au 27/10 soir

Branche locale `claude/agr-agv` (worktree fervent-cartwright-f8f4b6), main fusionné (c53582bd9), rien de poussé (jeton CI n° 14).

## Fait (R1 + R2 + correctifs Fable)
- AGV1 colonne `Lead.depense_electricite_pompe_mad_mois` + AGV8 `depense_electricite_pompe_part_fixe_mad_mois` (migration crm **0144**, chaînée sur 0143). CQST8 et CSV (appelGuidance) attendent AGV1 sur main.
- AGV2 `visites/visite_checklist_pompage.py` (déplacement pur de CATEGORIES_POINT_EAU ; visite_checklist.py garde un import) + mesure `pompe_actuelle_kw`.
- AGV3/4/9 retour visite → lead : plaque kW/tension 220-380/phases ; mesure non recopiable nommée au chatter ; pompe trouvée sans mode_pompe → note (mode jamais écrit).
- AGV5 devis auto : visite point d'eau VALIDÉE lève la garde D-AGR-4 (décision prise pour le fondateur).
- AGV6/10/13 générateur agricole sans vocabulaire batterie (scénario Sans par défaut ET à la réouverture, rail « Total TTC »).
- AGV7 PanneauAgricole sans jargon ; AGV11 carte économie : « Économie nette cumulée sur 10 ans (investissement déduit) » (cumul_mad serveur).
- AGV8 facture électricité → `saisies_economie_pompage.facture_reseau` ; part fixe absente ⇒ économies omises, raison qui nomme le champ.
- AGV14 tension de plaque : une seule source (colonne Lead), retirée de MESURES_VISITE.

## Pour les autres
- AGC (recapteur agricole) : la raison d'omission d'économie pompage dit maintenant « part fixe de la facture électricité du pompage non déclarée (0 si aucune) » ; aucun golden ne portait l'ancienne (grep Fable).
- Goldens générateur agricole recapturés localement avec `TZ=UTC` (sans TZ, la ligne « Brouillon enregistré à HH:MM » diffère).
- Le select Scénario masqué reste dans le DOM en agricole (ids stables).

## Non vérifié
- Aucun test Django joué (attend JETON DOCKER AGV) ; rendu réel du parcours pas fait.

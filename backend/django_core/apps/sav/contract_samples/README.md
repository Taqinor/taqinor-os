# `apps/sav/contract_samples/` — les contrats PACT10 du SAV

Même format que `apps/portail/contract_samples/README.md` : chaque fichier porte `endpoint`, `pourquoi`, `exemple` (+ `forme_serveur: partielle` et `forme_serveur_provisoire` tant que la tâche backend nommée ne sert pas toutes les clés).

| Fichier | Ce qu'il apparie |
| --- | --- |
| `releves_compteur.json` (AGR600) | GET + POST sav/equipements/{id}/releves-compteur/ : relevés heures / kWh / m³ |
| `contrat_om.json` (CIQ669) | GET sav/contrats-maintenance/<pk>/ : prestations O&M nommées, délai d'intervention, origine devis |
| `ticket_detail.json` (ASAV1) | GET sav/tickets/<pk>/ : + `statuts_suivants` (ASAV43), `equipement_fin_garantie_effective` (ASAV44), `je_suis_abonne` (ASAV39) ; partielle jusqu'à ces tâches |
| `ticket_suivi_public.json` (ASAV1) | GET public/sav/ticket/<token>/ : + `annule`, `fusionne_dans_reference`, `statut_display` « Annulé » ; partielle jusqu'à ASAV30 |
| `piece_retiree.json` (ASAV1) | POST sav/tickets/<pk>/pieces-retirees/ : corps `serie_neuve` optionnel, réponse `equipement_neuf` ; partielle jusqu'à ASAV9 |

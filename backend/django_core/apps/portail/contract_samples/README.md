# `apps/portail/contract_samples/` — les contrats PACT10 du portail client

Même format que `apps/ventes/contract_samples/README.md` : chaque fichier porte `endpoint`, `pourquoi`, `exemple`.

| Fichier | Ce qu'il apparie |
| --- | --- |
| `mes_devis_liste.json` | GET portail/mes-devis/ : liste des devis du client + `mis_a_jour_le` (QJR514) |
| `mes_devis_liste.json` (ADOC110) | + `deux_options` / `options` par élément (exemple `exemple_deux_options`) et corps `option?` de POST mes-devis/<id>/accepter/ (400 « Ce devis comporte deux options — précisez … » sans `option`) ; `forme_serveur` partielle jusqu'à ADOC113 |
| `mes_demandes_sav_liste.json` (ADOC111) | GET + POST portail/mes-demandes-sav/ : liste des demandes SAV du client et ouverture d'une demande |
| `mes_documents.json` (ADOC111) | GET portail/mes-documents/ (+ `version_numero`/`version_date`, D-ADOC-2, partielle jusqu'à ADOC134), téléchargement, dépôt multipart |
| `mon_equipe.json` (ADOC111) | GET/POST portail/mon-equipe/ + revoquer/ ; `peut_gerer` (partielle jusqu'à ADOC137) |
| `ma_consommation.json` (ADOC111) | GET portail/client/ma-consommation/ : série de production + alertes ouvertes |
| `recherche_portail.json` (ADOC111) | GET portail/client/recherche/?q= : quatre groupes devis/facture/ticket/document |
| `invitation_accepter.json` (ADOC111) | POST public/portail/invitations/accepter/ : 200 / 400 `mot_de_passe` (ADOC122, partielle) / 400 jeton invalide |

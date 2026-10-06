# `apps/portail/contract_samples/` — les contrats PACT10 du portail client

Même format que `apps/ventes/contract_samples/README.md` : chaque fichier porte `endpoint`, `pourquoi`, `exemple`.

| Fichier | Ce qu'il apparie |
| --- | --- |
| `mes_devis_liste.json` | GET portail/mes-devis/ : liste des devis du client + `mis_a_jour_le` (QJR514) |
| `mes_devis_liste.json` (ADOC110) | + `deux_options` / `options` par élément (exemple `exemple_deux_options`) et corps `option?` de POST mes-devis/<id>/accepter/ (400 « Ce devis comporte deux options — précisez … » sans `option`) ; `forme_serveur` partielle jusqu'à ADOC113 |

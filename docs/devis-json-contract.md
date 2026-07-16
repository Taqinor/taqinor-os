# Contrat JSON du Devis (lecture seule) — SCA49

> **But.** La leçon Aurora Solar : le moteur de design est la moat ; les
> financeurs et partenaires sont des **LECTEURS** de l'objet devis. Il suffit
> donc de **geler la forme** de l'objet Devis sérialisé (y compris
> `etude_params`) pour qu'une future API partenaires existe **sans schéma
> nouveau** le jour venu. Aucune API nouvelle, aucun schéma changé ici — ce
> document + son test snapshot **figent** la forme actuelle.

Ce contrat décrit la forme **lecture seule** produite par
`apps.ventes.serializers.DevisSerializer` (endpoint interne
`GET /api/django/ventes/devis/<id>/`). Un partenaire financement qui LIT un
devis peut s'appuyer sur les clés listées ci-dessous.

## Règle de stabilité (garde CI)

Le test `apps/ventes/tests/test_devis_contract_shape.py` fige l'ensemble des
clés du contrat :

- **Ajouter une clé = OK** (rétro-compatible — un lecteur existant l'ignore).
- **Renommer ou supprimer une clé du contrat = RUPTURE** (le test devient rouge).

Autrement dit : le jeu de clés gelées doit rester un **sous-ensemble** des clés
réellement exposées par le serializer. Retirer/renommer une clé gelée casse le
test ; en ajouter une nouvelle le laisse vert.

## Clés du contrat (stables)

### Identité & entête
| Clé | Type | Sémantique |
|-----|------|-----------|
| `id` | int | Identifiant du devis. |
| `reference` | str | Référence lisible (unique par société+mois). |
| `statut` | str | `brouillon` / `envoye` / `accepte` / `refuse` / `expire`. |
| `date_creation` | datetime ISO | Horodatage de création. |
| `date_validite` | date ISO / null | Date de validité. |
| `client` | int | FK client (id). |
| `client_nom` | str | Nom du client (dénormalisé, lecture). |
| `lead` | int / null | FK lead d'origine (si devis issu d'un lead). |

### Montants (lecture seule, dérivés)
| Clé | Type | Sémantique |
|-----|------|-----------|
| `taux_tva` | decimal str | Taux de TVA global (%). |
| `remise_globale` | decimal str | Remise globale (%). |
| `total_ht` | decimal str | Total HT. |
| `total_tva` | decimal str | Total TVA. |
| `total_ttc` | decimal str | Total TTC. |
| `total_affiche` | decimal str | Total d'affichage canonique (option 1 pour un devis à deux options). |
| `nb_options` | int | Nombre d'options (1 ou 2). |
| `devise` | str | Code devise (défaut `MAD`). |

### Lignes
| Clé | Type | Sémantique |
|-----|------|-----------|
| `lignes` | list | Lignes du devis (désignation, quantité, P.U., total HT par ligne). |

### Étude / simulation
| Clé | Type | Sémantique |
|-----|------|-----------|
| `mode_installation` | str / null | `residentiel` / `industriel` / `agricole`. |
| `etude_params` | object / null | Paramètres d'étude (voir ci-dessous). |

#### Forme de `etude_params` (object, clés optionnelles)

`etude_params` est un objet JSON libre par nature, mais les clés suivantes sont
**stables** quand elles sont présentes (leur absence est normale selon le mode) :

| Clé | Type | Présent pour | Sémantique |
|-----|------|--------------|-----------|
| `puissance_kwc` | number | résidentiel / industriel | Puissance crête (kWc). |
| `production_annuelle` | int | résidentiel / industriel | Production annuelle (kWh). |
| `economies_annuelles` | int | résidentiel / industriel | Économies annuelles estimées. |
| `toiture` | object | avec layout 3D | Config toiture importée du builder. |
| `pompe_cv` | str | agricole (pompage) | Puissance pompe (CV). |
| `pompe_kw` | number | agricole (pompage) | Puissance pompe (kW). |
| `hmt_m` | str | agricole (pompage) | Hauteur manométrique totale (m). |

> **Interne — jamais dans ce contrat côté partenaire :** aucune clé de coût
> d'achat / marge / revendeur (`prix_achat`, `marge`, …) n'apparaît dans
> `etude_params` exposé (filtrées côté serveur). Le champ modèle
> `prix_par_kwc` (SCA47) est une donnée **BI/générateur interne** : il est
> exposé sur l'API interne (et **gelé** par le test snapshot — sa disparition
> casserait les consommateurs BI NTDATA46/47), mais un partenaire financement
> ne doit PAS s'en servir : il ne fait pas partie du contrat externe et
> n'apparaît sur AUCUN PDF ni sortie client (même régime que `prix_achat`).

## Addendum — forme lecture du Paiement (SCA45)

Les paiements sont des objets de registre de première classe (leçon
ServiceTitan/Toast). `apps.ventes.serializers.PaiementSerializer` expose —
et le test snapshot gèle — les clés stables suivantes :

| Clé | Type | Sémantique |
|-----|------|-----------|
| `id` | int | Identifiant du paiement. |
| `facture` | int / null | FK facture (null pour une avance non affectée). |
| `montant` | decimal str | Montant encaissé. |
| `date_paiement` | date ISO | Date du règlement. |
| `mode` | str | `especes` / `virement` / `cheque` / `carte` / `prelevement` / `autre`. |
| `statut` | str | `encaisse` / `rejete`. |
| `provider_ref` | str / null | Référence PSP (provider-agnostique — SCA45). |
| `idempotency_key` | str / null | Clé d'idempotence (unique par société quand renseignée). |

## Dérogation

Ce document et son test sont la **source de vérité** de la forme lecture-seule.
Toute évolution qui renomme/supprime une clé gelée est une **rupture** : elle
exige une décision explicite (versionner l'API partenaire), jamais un simple
renommage silencieux.

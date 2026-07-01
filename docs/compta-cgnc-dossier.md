# Dossier de contrôle CGNC — prêt à valider (fiduciaire)

> Tâche **COMPTA6** — *Validation légale du plan/format CGNC (fiduciaire)*.
> **Dépendance externe assumée :** la validation LÉGALE finale du plan et du
> format CGNC est un acte réservé à un fiduciaire / expert-comptable humain
> inscrit à l'Ordre. Ce module **prépare et structure** le dossier prêt à
> valider ; il ne remplace ni ne simule cette validation.

## Ce que fait TAQINOR OS (la partie automatisée)

Le module `apps/compta` implémente déjà le plan comptable CGNC marocain
(classes 1 à 8), les journaux, les écritures en partie double et les états de
synthèse (CPC, Bilan, Balance, Grand-livre, ESG, ETIC). **COMPTA6 n'ajoute
aucun de ces éléments** : il ajoute uniquement un **dossier de contrôle** en
lecture seule, qu'un fiduciaire relit avant sa signature.

Le dossier est produit par :

- le service `apps.compta.services.construire_dossier_cgnc(company)` — lecture
  seule, scopé société, idempotent ;
- la commande de gestion `python manage.py compta_cgnc_dossier`.

Aucune donnée n'est créée ou modifiée. Aucun prix d'achat / marge n'apparaît
(le module n'en stocke pas dans le plan comptable).

## Ce que contient le dossier

| Section | Contenu |
| --- | --- |
| `synthese` | Société, date de génération, nombre de comptes, comptes par classe, nombre d'anomalies par sévérité (bloquant / avertissement / info), couverture du barème CGNC, indicateur `pret_a_transmettre`. |
| `plan_comptable` | Le plan comptable **réel** de la société, groupé par classe CGNC (1 à 8) : numéro, intitulé, sens, flags tiers/lettrable, actif/inactif. |
| `reference_cgnc` | Le **barème CGNC de référence** connu du module, groupé par classe — c'est le standard auquel le plan réel est comparé. |
| `controles` | La liste des **anomalies** détectées (voir ci-dessous). |
| `a_valider_fiduciaire` | La liste EXPLICITE de ce qui reste à la charge du fiduciaire humain. |

### Contrôles de cohérence exécutés

| Code | Sévérité | Signification |
| --- | --- | --- |
| `numero_non_numerique` | bloquant | Un numéro de compte ne commence pas par un chiffre de classe CGNC. |
| `classe_hors_cgnc` | bloquant | Classe hors du cadre 1 à 8. |
| `classe_incoherente` | bloquant | La classe déclarée du compte ≠ la classe portée par le 1ᵉʳ chiffre du numéro. |
| `sens_incoherent` | avertissement | Le sens (`actif`/`passif`/`charge`/`produit`) ne correspond pas au sens naturel attendu de la classe. |
| `compte_reference_absent` | avertissement | Un compte désactivé porte encore des écritures (à réactiver ou solder avant clôture). |
| `compte_ref_manquant` | info | Un compte usuel du barème CGNC est absent du plan (complétude du mapping). |

`pret_a_transmettre` vaut `true` uniquement quand il n'y a **aucune anomalie
bloquante** ; les avertissements et infos sont arbitrés par le fiduciaire.

## Comment le générer

```bash
# Format texte lisible, sur stdout, pour une société (par son slug)
python manage.py compta_cgnc_dossier --company <slug>

# Export JSON dans un fichier
python manage.py compta_cgnc_dossier --company <slug> \
    --format json --output dossier_cgnc.json

# Toutes les sociétés (JSON = liste, texte = sections concaténées)
python manage.py compta_cgnc_dossier --all --format text
```

Options :

- `--company <slug>` : société ciblée (obligatoire sauf avec `--all`).
- `--all` : toutes les sociétés.
- `--format {text,json}` : format de sortie (défaut `text`).
- `--output <fichier>` : écrit dans un fichier au lieu de stdout.

Depuis du code Python (ex. un endpoint d'export), appeler directement
`services.construire_dossier_cgnc(company)` qui renvoie le dictionnaire
structuré.

## Ce qui reste à la charge du fiduciaire (étape humaine, NON automatisable)

Le dossier est **prêt à valider** ; la validation elle-même reste humaine :

1. **Validation légale finale** du plan et du format CGNC — acte réservé à un
   fiduciaire / expert-comptable inscrit à l'Ordre.
2. **Adéquation à l'activité** : confirmer les comptes sectoriels (solaire /
   BTP), les éventuels sous-comptes analytiques et les spécificités locales.
3. **Arbitrage des avertissements** de sens et de cohérence signalés.
4. **Comptes de tiers et lettrage** : valider le rattachement et le paramétrage.
5. **États de synthèse** : attester la conformité (CPC, Bilan, ESG, ETIC) au
   moment de la liasse fiscale.

Tant que ces points ne sont pas signés par le fiduciaire, la tâche COMPTA6
reste **bloquée sur cette dépendance externe** : le livrable côté OS (le dossier
prêt à valider) est complet ; la validation légale, elle, est hors périmètre
logiciel.

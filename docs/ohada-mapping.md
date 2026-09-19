# Plan comptable OHADA / SYSCOHADA révisé — correspondance avec le CGNC marocain

**Tâche : NTI18N18 (pack pays Sénégal / Côte d'Ivoire). Catégorie DECISION —
rien de ce document n'est appliqué automatiquement.**

Ce document a UN seul rôle : porter noir sur blanc la correspondance entre le
plan comptable marocain **CGNC** (le seul référentiel réellement utilisé
aujourd'hui) et le plan **SYSCOHADA révisé** de l'espace OHADA, et dire
précisément ce qui est **validé** et ce qui ne l'est **pas**.

## 1. État réel du code (vérifiable)

| Élément | État |
| --- | --- |
| `apps.compta.PlanComptable` / `CompteComptable` (CGNC) | en production, inchangé |
| `apps.compta.PlanComptableOHADA` | table NEUVE, additive, **vide** |
| `EcritureComptable` / `LigneEcriture` | **non touchées** — elles pointent toujours `CompteComptable` (CGNC) |
| `CompanyProfile.pack_pays` | **n'existe pas encore** (NTI18N16, GATED-founder) |
| Correspondance compte ↔ compte | **non renseignée** (champ `compte_cgnc_equivalent` vide partout) |

Conséquence directe : **aucune société ne peut activer le plan OHADA
aujourd'hui.** `apps.compta.models.plan_ohada_actif(company)` exige
cumulativement `pack_pays == 'SN_CI'` *et* au moins un compte OHADA `actif`.
Le champ `pack_pays` étant absent, la lecture rend `''` et la porte reste
fermée — c'est l'état voulu pour une décision d'expansion commerciale.

## 2. Les deux jeux de classes (chacun tel que sa propre norme le nomme)

Les classes CGNC ci-dessous sont celles déclarées dans le code
(`CompteComptable.Classe`) ; les classes SYSCOHADA sont celles déclarées dans
`PlanComptableOHADA.Classe`. Les deux colonnes sont donc **traçables au code**,
et le tableau montre pourquoi les deux référentiels ne peuvent pas partager une
même énumération de classes.

| # | CGNC (Maroc) | SYSCOHADA révisé (OHADA) |
| --- | --- | --- |
| 1 | Financement permanent | Ressources durables |
| 2 | Actif immobilisé | Actif immobilisé |
| 3 | Actif circulant (hors trésorerie) | Stocks |
| 4 | Passif circulant (hors trésorerie) | Tiers |
| 5 | Trésorerie | Trésorerie |
| 6 | Charges | Charges des activités ordinaires |
| 7 | Produits | Produits des activités ordinaires |
| 8 | Résultats | Autres charges et autres produits |

Les classes **3**, **4** et **8** portent des contenus DIFFÉRENTS d'une norme à
l'autre. C'est la raison technique pour laquelle `PlanComptableOHADA` est une
table à part et non un `PlanComptable` de code « SYSCOHADA » : réutiliser
l'énumération CGNC aurait affiché un libellé de classe faux à l'une des deux
normes.

## 3. Correspondance compte ↔ compte — À VALIDER PAR LE FONDATEUR

**Elle est volontairement VIDE.** Aucune équivalence de compte n'est écrite
ici, ni semée en base, ni codée en dur dans le modèle.

Pourquoi : une équivalence comptable posée « au plus probable » produirait un
grand livre faux et un état de synthèse faux — exactement le type de chiffre
non vérifié que la règle fondateur « aucun chiffre inventé » interdit. Le
rapprochement compte par compte relève d'un expert-comptable de l'espace
OHADA, pas d'une déduction de nom de compte.

### Ce qu'il faut pour la remplir

1. **`pack_pays` posé** (NTI18N16) — sans lui, la gate ne peut pas s'ouvrir.
2. **Le plan de comptes OHADA effectivement retenu** pour la société cible
   (le plan SYSCOHADA est un cadre ; chaque entreprise en instancie un
   sous-ensemble).
3. **La validation, compte par compte**, de la correspondance avec les comptes
   CGNC réellement mouvementés par l'ERP aujourd'hui (clients, fournisseurs,
   TVA facturée/récupérable, ventes, achats, banque, caisse…).

### Comment elle se remplit, une fois validée

Un compte OHADA valide et sa correspondance validée :

```python
from apps.compta.models import PlanComptableOHADA

PlanComptableOHADA.objects.create(
    company=societe,
    numero='<numéro OHADA validé>',
    intitule='<intitulé OHADA validé>',
    classe=<classe 1-8>,
    compte_cgnc_equivalent='<numéro CGNC validé>',  # vide = NON validé
    actif=True,  # refusé si pack_pays != 'SN_CI'
)
```

`compte_cgnc_equivalent` reste **vide** tant que la ligne n'a pas été validée :
un champ vide dit « je ne sais pas », ce qui est exact ; un champ rempli
« au mieux » dirait « c'est validé », ce qui serait faux.

## 4. Ce que NTI18N18 ne fait PAS (moitiés restantes, nommées)

| Moitié manquante | Où elle vivra | Pourquoi pas ici |
| --- | --- | --- |
| Champ `CompanyProfile.pack_pays` | NTI18N16 (`apps/parametres`) | GATED-founder, non construit |
| Saisie d'écriture SUR un compte OHADA | `apps/compta/{services,serializers,views}.py` | exige `pack_pays` + la correspondance validée ; toucher le chemin d'écriture GL sans elle produirait des écritures fausses |
| Export « FEC-équivalent » en référentiel OHADA | `core/accounting_export.py` | hors périmètre de cette lane ; l'export actuel est CGNC et reste inchangé |
| Restriction au rôle Admin société | NTI18N41 (`apps/parametres/localisation.py`) | tâche AUTH distincte, déjà au plan |
| Trace `audit.AuditLog` du changement de plan | NTI18N50 (`apps/audit`) | tâche distincte, déjà au plan |

Tant que ces moitiés ne sont pas livrées, `PlanComptableOHADA` est un
**référentiel déclaratif** : il permet de décrire un plan OHADA et de le
soumettre à validation, il ne détourne aucune écriture existante.

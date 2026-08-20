"""PVFCH (fondateur 20/08/2026, « never invent numbers ») — soigne les fiches
techniques manquantes/incomplètes qui font DISPARAÎTRE le schéma unifilaire.

CONTEXTE. ``apps/ventes/electrical_service.py`` (commit ff38e6e3) refuse
désormais de rendre le schéma unifilaire dès qu'UNE SEULE des 7 variables
MODULE (``VARIABLES_MODULE_REQUISES``) ou 7 variables ONDULEUR
(``VARIABLES_ONDULEUR_REQUISES``) d'une ``FicheTechnique`` est absente —
aucun repli, aucune valeur inventée. Ces variables sont posées par
``manage.py seed_catalogue`` (dictionnaire ``FICHES_TECHNIQUES``), mais ce
seeder n'a longtemps JAMAIS été appelé par ``scripts/deploy-prod.ps1``
(seuls ``migrate`` + ``init_roles`` l'étaient) ; un appel a été ajouté depuis
(PVOND, 18/08/2026) mais il ne couvre QUE la société ``$SEED_COMPANY_SLUG``
(``taqinor-demo`` par défaut) et reste NON BLOQUANT (``set +e`` — un échec
n'arrête pas le déploiement). Une base créée avant cette date, ou une AUTRE
société, peut donc encore porter une fiche NULL ou partiellement remplie —
c'est le trou que cette migration comble, UNE FOIS, pour TOUTES les sociétés,
garanti par le fait qu'une migration s'exécute toujours (contrairement au
seeder, best-effort et par société).

RÈGLE — UNE SEULE SOURCE, JAMAIS D'ÉCRASEMENT. Les chiffres viennent
EXCLUSIVEMENT du dictionnaire ``FICHES_TECHNIQUES`` de
``apps/stock/management/commands/seed_catalogue.py`` (importé ici, jamais
recopié — un seul endroit à corriger si une datasheet est révisée) ; le
seeder EXPOSE aussi une fonction ``_fiche_champ_vide`` réutilisée ici pour
la MÊME garde. Contrairement au mode ``--reappliquer-fiches`` du seeder (qui
PEUT écraser pour porter une correction de datasheet), cette migration ne
COMBLE QUE les champs actuellement vides (``None`` ou chaîne vide) — une
valeur déjà saisie par le fondateur, fût-elle fausse, n'est JAMAIS touchée.
Si la fiche n'existe pas du tout, elle est créée avec les valeurs du
dictionnaire, exactement comme le fait le seeder (``FicheTechnique.objects
.create(company=..., produit=..., **valeurs)``).

MULTI-TENANT. ``Produit`` est scopé par société (FK ``company``) : le
SKU est apparié à travers TOUTES les sociétés (pas de filtre société), et
la fiche créée reprend la société du produit trouvé.

GARDE DE ROBUSTESSE. Si ``FICHES_TECHNIQUES`` (ou ``_fiche_champ_vide``) a
été renommé/déplacé côté seeder, l'import échoue et cette migration ne fait
RIEN (NO-OP) plutôt que de lever une exception qui bloquerait un
déploiement — un renommage côté seeder n'est pas une raison de casser une
migration figée dans le temps.

RÉVERSIBLE : non — ``noop``. On ne peut pas distinguer, en sens inverse, un
champ que CETTE migration a comblé d'un champ saisi par le fondateur entre
temps ; revenir en arrière risquerait donc d'effacer une vraie saisie
(même doctrine que 0121/0123/0124 : la réversibilité n'a de sens que quand
on connaît l'état d'AVANT précisément — ici on ne le connaît pas)."""
from django.db import migrations


def soigner_fiches_manquantes(apps, schema_editor):
    """Comble les champs vides de ``FicheTechnique`` (ou crée la fiche) pour
    chaque ``Produit`` dont le SKU figure dans ``FICHES_TECHNIQUES`` du
    seeder — jamais d'écrasement d'une valeur déjà présente."""
    try:
        from apps.stock.management.commands.seed_catalogue import (
            FICHES_TECHNIQUES, _fiche_champ_vide,
        )
    except ImportError:
        # Dictionnaire/garde renommés ou déplacés côté seeder — NO-OP plutôt
        # qu'une exception qui bloquerait un déploiement.
        return

    Produit = apps.get_model('stock', 'Produit')
    FicheTechnique = apps.get_model('stock', 'FicheTechnique')

    for sku, valeurs in FICHES_TECHNIQUES.items():
        for produit in Produit.objects.filter(sku=sku).iterator():
            fiche = FicheTechnique.objects.filter(produit=produit).first()
            if fiche is None:
                FicheTechnique.objects.create(
                    company=produit.company, produit=produit, **valeurs)
                continue
            modifies = []
            for champ, valeur in valeurs.items():
                actuel = getattr(fiche, champ)
                if actuel == valeur:
                    continue  # déjà à jour — aucune écriture (idempotence)
                if not _fiche_champ_vide(actuel):
                    continue  # valeur SAISIE : elle appartient au fondateur
                modifies.append(champ)
            if not modifies:
                continue
            for champ in modifies:
                setattr(fiche, champ, valeurs[champ])
            fiche.save(update_fields=modifies)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0124_correction_garanties_deye_generiques'),
    ]

    operations = [
        migrations.RunPython(soigner_fiches_manquantes, migrations.RunPython.noop),
    ]

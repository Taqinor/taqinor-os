# STKCAT4 (16/09/2026) — type les catégories DÉJÀ en base, uniquement là où
# `type_equipement` est NULL, par nom EXACT de taxonomie.
#
# STKCAT3 a branché les quatre chemins d'amorçage, mais un tenant amorcé HIER
# garde ses catégories non typées : sans cette passe, le rail « type
# d'équipement » resterait vide sur toutes les bases existantes (le défaut
# mesuré par l'audit L3 du 16/09 — `type_equipement` NULL partout).
#
# POURQUOI LA TABLE EST DUPLIQUÉE ICI ET PAS IMPORTÉE DU SEEDER
# -------------------------------------------------------------
# Une migration est de l'HISTOIRE FIGÉE : elle doit rejouer à l'identique dans
# dix ans, même si `seed_catalogue.py` a changé de table, de nom ou a disparu.
# Aujourd'hui ce module ne charge aucun modèle à l'import (ses imports de
# modèles sont tous locaux à `handle()`), donc l'import serait TECHNIQUEMENT
# possible — mais rien ne le garantit demain, et un import de commande depuis
# une migration ferait dépendre un `migrate` du code applicatif courant. La
# copie est donc DÉLIBÉRÉE, et un test verrouille qu'elle ne CONTREDIT jamais
# la table vivante (`TYPES_PAR_CATEGORIE`) : y ajouter une catégorie plus tard
# est libre, en changer une d'avis exige une nouvelle migration explicite.

from django.db import migrations

# Copie figée de `seed_catalogue.TYPES_PAR_CATEGORIE` au 16/09/2026.
TYPES_PAR_CATEGORIE = {
    'Panneaux photovoltaïques': 'panneau',
    'Onduleurs réseau': 'onduleur',
    'Onduleurs hybrides': 'onduleur',
    'Onduleurs hors réseau': 'onduleur',
    'Batteries': 'batterie',
    'Structures & fixation': 'structure',
    'Protection & accessoires': 'protection',
    'Câbles': 'cable',
    'Pompes': 'pompe',
    'Variateurs': 'variateur',
    'Services & prestations': 'service',
    # Les trois libellés du jeu de démonstration (`seed_demo`).
    'Panneaux solaires': 'panneau',
    'Onduleurs': 'onduleur',
    'Accessoires': 'accessoire',
}


#: Taille de lot des mises à jour. `stock_categorie` est une PETITE table (une
#: douzaine de lignes par société), mais la passe est écrite PAR LOTS par
#: principe : un UPDATE global sur une table devenue grosse tiendrait un verrou
#: long pendant le déploiement (garde `scripts/check_safe_migrations.py`).
TAILLE_LOT = 500


def typer_categories_existantes(apps, schema_editor):
    """Pose `type_equipement` sur les catégories NON TYPÉES, par nom exact.

    Portée : TOUTES les sociétés, y compris les catégories à `company` NULL
    (le filtre ne mentionne jamais `company`, donc aucune ligne n'est exclue).
    JAMAIS d'écrasement : le filtre `type_equipement__isnull=True` laisse
    intacte toute catégorie déjà typée — à la main dans l'écran Catégories ou
    par le seeder. Une catégorie au nom LIBRE (hors table) n'est pas touchée :
    elle reste NULL plutôt que de recevoir un type deviné.
    """
    Categorie = apps.get_model('stock', 'Categorie')
    for nom, type_equipement in TYPES_PAR_CATEGORIE.items():
        a_typer = Categorie.objects.filter(
            nom=nom, type_equipement__isnull=True,
        ).values_list('pk', flat=True)
        lot = []
        for cle in a_typer.iterator(chunk_size=TAILLE_LOT):
            lot.append(cle)
            if len(lot) >= TAILLE_LOT:
                Categorie.objects.filter(pk__in=lot).update(
                    type_equipement=type_equipement)
                lot = []
        if lot:
            Categorie.objects.filter(pk__in=lot).update(
                type_equipement=type_equipement)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0145_stkcat2_type_equipement_service'),
    ]

    operations = [
        # Reverse = NO-OP EXPLICITE, pas un oubli : après coup, plus rien ne
        # distingue un type posé par cette passe d'un type posé à la main par
        # le fondateur. Les remettre tous à NULL détruirait ses arbitrages —
        # la migration est donc réversible (elle ne bloque aucun rollback)
        # sans jamais rien défaire.
        migrations.RunPython(
            typer_categories_existantes,
            migrations.RunPython.noop,
        ),
    ]

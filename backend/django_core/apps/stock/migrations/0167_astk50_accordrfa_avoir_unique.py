"""ASTK50 — un accord RFA ne génère qu'un avoir : contrainte d'unicité
PARTIELLE sur ``AccordRFAFournisseur.avoir_genere`` (non nul).

ADDITIF ET RÉVERSIBLE (``RemoveConstraint``). Avant de poser la contrainte,
une requête de contrôle vérifie qu'aucun avoir n'est déjà référencé par deux
accords : si c'est le cas, la migration ÉCHOUE EXPLICITEMENT (jamais de
correction silencieuse de données réelles).
"""
from django.db import migrations, models
from django.db.models import Count


def verifier_sans_doublon(apps, schema_editor):
    Accord = apps.get_model('stock', 'AccordRFAFournisseur')
    doublons = list(
        Accord.objects.filter(avoir_genere__isnull=False)
        .values('avoir_genere').annotate(n=Count('id'))
        .filter(n__gt=1).values_list('avoir_genere', flat=True))
    if doublons:
        raise RuntimeError(
            'ASTK50 : des avoirs fournisseur sont référencés par plusieurs '
            f'accords RFA (avoirs {doublons}) — à corriger à la main avant '
            'de poser la contrainte stock_accordrfa_avoir_genere_uniq.')


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0166_astk44_mouvement_cout_unitaire'),
    ]

    operations = [
        migrations.RunPython(verifier_sans_doublon, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='accordrfafournisseur',
            constraint=models.UniqueConstraint(
                condition=models.Q(avoir_genere__isnull=False),
                fields=('avoir_genere',),
                name='stock_accordrfa_avoir_genere_uniq'),
        ),
    ]

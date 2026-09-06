# AUD721 — `BulletinPaie.periode` / `.profil` passent de CASCADE à PROTECT.
#
# La garde d'immuabilité du bulletin validé (`BulletinPaie.save`/`delete`) ne
# s'applique qu'à un `instance.delete()` Python : supprimer la PÉRIODE ou le
# PROFIL depuis `/admin/` (ou par un `queryset.delete()` en masse) cascadait sur
# TOUS leurs bulletins — validés compris — sans jamais lever
# `BulletinVerrouille`. PROTECT fait refuser la base elle-même.
#
# Aucune donnée n'est touchée : seule la contrainte référentielle change (pas de
# réécriture de table, pas de perte, réversible en repassant à CASCADE).
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0046_audv21_elementvariable_source_flotte'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bulletinpaie',
            name='periode',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='bulletins', to='paie.periodepaie',
                verbose_name='Période'),
        ),
        migrations.AlterField(
            model_name='bulletinpaie',
            name='profil',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='bulletins', to='paie.profilpaie',
                verbose_name='Profil de paie'),
        ),
    ]

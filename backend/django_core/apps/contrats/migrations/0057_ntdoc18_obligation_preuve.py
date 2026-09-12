"""NTDOC18 — pièce justificative d'une obligation contractuelle.

Additive : une FK NULLABLE vers ``ged.Document`` (string-FK, jamais un import
de ``ged.models``). Aucune donnée existante n'est modifiée, et aucune règle
existante ne devient bloquante — une obligation « faite » sans preuve reste
parfaitement valide.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contrats', '0056_ntdoc29_parametres_clm'),
        ('ged', '0046_ntdoc14_journal_source_ref'),
    ]

    operations = [
        migrations.AddField(
            model_name='obligation',
            name='preuve_document',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='obligations_prouvees', to='ged.document',
                verbose_name='Document de preuve'),
        ),
    ]

# NTWFL25 — versionnement des définitions de workflow.
#
# Un `code` de définition désigne désormais une LIGNÉE de versions : l'unicité
# passe de (société, code) à (société, code, version). Toutes les définitions
# existantes valent `version=1`, donc leur unicité (société, code) reste
# STRICTEMENT garantie par le nouveau triplet — aucune ligne ne peut devenir
# invalide, et la migration est réversible.
#
# `WorkflowInstance.definition_version` épingle la version sur laquelle une
# instance a démarré. Défaut 1 : les instances existantes exécutent toutes la
# v1 de leur définition, ce qui est exact.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0068_ntwfl20_dossier_workflow'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowdefinition',
            name='version',
            field=models.PositiveIntegerField(
                default=1,
                help_text='Incrémentée à chaque modification STRUCTURELLE des '
                          'étapes faite alors que des instances tournaient.',
                verbose_name='Version'),
        ),
        migrations.AddField(
            model_name='workflowdefinition',
            name='definition_precedente',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='versions_suivantes',
                to='core.workflowdefinition',
                verbose_name='Version précédente'),
        ),
        migrations.AddField(
            model_name='workflowinstance',
            name='definition_version',
            field=models.PositiveIntegerField(
                default=1,
                help_text="Version de la définition au démarrage de "
                          "l'instance.",
                verbose_name='Version de la définition'),
        ),
        migrations.RemoveConstraint(
            model_name='workflowdefinition',
            name='core_wf_def_company_code_uniq',
        ),
        migrations.AddConstraint(
            model_name='workflowdefinition',
            constraint=models.UniqueConstraint(
                fields=('company', 'code', 'version'),
                name='core_wf_def_co_code_ver_uniq'),
        ),
        migrations.AddIndex(
            model_name='workflowdefinition',
            index=models.Index(fields=['company', 'code', 'version'],
                               name='core_wf_def_co_cod_ver_idx'),
        ),
    ]

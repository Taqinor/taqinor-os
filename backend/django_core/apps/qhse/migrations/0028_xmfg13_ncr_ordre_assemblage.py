import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('qhse', '0027_indicateuresg'),
        ('installations', '0060_xmfg12_ordredemontage'),
    ]

    operations = [
        migrations.AddField(
            model_name='nonconformite',
            name='ordre_assemblage',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='qhse_ncr', to='installations.ordreassemblage', verbose_name="Ordre d'assemblage d'origine"),
        ),
    ]

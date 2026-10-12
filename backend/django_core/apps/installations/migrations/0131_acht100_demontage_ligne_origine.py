# ACHT100 (jumeau) — OrdreDemontageLigne.origine (kit | ajout), défaut « kit »
# pour les lignes existantes. Additif, revertable.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0130_amet14_da_a_revoir_v2'),
    ]

    operations = [
        migrations.AddField(
            model_name='ordredemontageligne',
            name='origine',
            field=models.CharField(
                choices=[('kit', 'Copié du kit'),
                         ('ajout', 'Ajouté sur cet ordre')],
                default='kit', max_length=10),
        ),
    ]

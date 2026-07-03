import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0056_xmfg4_lifecycle_chatter'),
        ('stock', '0026_fg67_frais_annexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrdreAssemblageLigne',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('designation', models.CharField(blank=True, max_length=255, null=True)),
                ('quantite', models.PositiveIntegerField(default=1)),
                ('origine', models.CharField(choices=[('kit', 'Copié du kit'), ('ajout', 'Ajouté sur cet ordre')], default='kit', max_length=10)),
                ('ordre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lignes', to='installations.ordreassemblage')),
                ('produit', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='installations_ordre_assemblage_lignes', to='stock.produit')),
            ],
            options={
                'verbose_name': "Ligne d'ordre d'assemblage",
                'verbose_name_plural': "Lignes d'ordre d'assemblage",
                'ordering': ['ordre_id', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='ordreassemblageligne',
            index=models.Index(fields=['ordre'], name='idx_asmligne_ordre'),
        ),
        migrations.AddIndex(
            model_name='ordreassemblageligne',
            index=models.Index(fields=['produit'], name='idx_asmligne_produit'),
        ),
    ]

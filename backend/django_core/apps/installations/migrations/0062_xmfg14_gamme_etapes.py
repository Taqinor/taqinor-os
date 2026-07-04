import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0061_xmfg13_controle_qualite'),
        ('records', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EtapeAssemblage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('libelle', models.CharField(max_length=255)),
                ('instructions', models.TextField(blank=True, default='')),
                ('duree_attendue_min', models.PositiveIntegerField(blank=True, help_text='Durée attendue de cette étape, en minutes.', null=True)),
                ('kit', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='etapes_assemblage', to='installations.kit')),
                ('piece_jointe', models.ForeignKey(blank=True, help_text='Schéma de câblage, photo de référence…', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='records.attachment')),
            ],
            options={
                'verbose_name': "Étape d'assemblage",
                'verbose_name_plural': "Étapes d'assemblage",
                'ordering': ['kit_id', 'ordre', 'id'],
            },
        ),
        migrations.CreateModel(
            name='EtapeOrdre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fait', models.BooleanField(default=False)),
                ('fait_le', models.DateTimeField(blank=True, null=True)),
                ('duree_reelle_min', models.PositiveIntegerField(blank=True, null=True)),
                ('etape_modele', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='executions', to='installations.etapeassemblage')),
                ('fait_par', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('ordre', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='etapes', to='installations.ordreassemblage')),
            ],
            options={
                'verbose_name': "Étape d'ordre",
                'verbose_name_plural': "Étapes d'ordre",
                'ordering': ['ordre_id', 'etape_modele__ordre', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='etapeassemblage',
            index=models.Index(fields=['kit'], name='idx_etapeasm_kit'),
        ),
        migrations.AddIndex(
            model_name='etapeordre',
            index=models.Index(fields=['ordre', 'fait'], name='idx_etapeord_ordre_fait'),
        ),
        migrations.AlterUniqueTogether(
            name='etapeordre',
            unique_together={('ordre', 'etape_modele')},
        ),
    ]

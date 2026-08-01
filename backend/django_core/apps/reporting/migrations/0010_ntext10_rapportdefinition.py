"""NTEXT10 — report-builder : RapportDefinition (additif, réversible)."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('reporting', '0009_vx61_webvitalmetric'),
    ]

    operations = [
        migrations.CreateModel(
            name='RapportDefinition',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('titre', models.CharField(max_length=255)),
                ('dataset', models.CharField(
                    help_text="Nom d'un dataset enregistré "
                              "(core.data_explorer).",
                    max_length=80)),
                ('spec', models.JSONField(blank=True, default=dict)),
                ('pivot_spec', models.JSONField(blank=True, default=dict)),
                ('partage', models.CharField(
                    choices=[('prive', 'Privé'), ('societe', 'Société')],
                    default='prive', max_length=10)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
                ('owner', models.ForeignKey(
                    blank=True,
                    help_text='Vide = rapport de société (non personnel).',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='rapport_definitions',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Propriétaire')),
            ],
            options={
                'verbose_name': 'Définition de rapport',
                'verbose_name_plural': 'Définitions de rapport',
                'ordering': ['-created_at', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='rapportdefinition',
            index=models.Index(
                fields=['company', 'dataset'], name='rpt_rapportdef_idx'),
        ),
    ]

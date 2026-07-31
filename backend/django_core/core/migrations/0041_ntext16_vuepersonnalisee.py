"""NTEXT16 — vues de liste personnalisées (additif, réversible)."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('core', '0040_ntapi24_changelogentry_breaking'),
    ]

    operations = [
        migrations.CreateModel(
            name='VuePersonnalisee',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cible', models.CharField(
                    help_text='Identifiant de liste, ex. « crm.lead » '
                              '(chaîne, jamais un import de modèle).',
                    max_length=80, verbose_name='Cible')),
                ('nom', models.CharField(max_length=160, verbose_name='Nom')),
                ('config', models.JSONField(
                    blank=True, default=dict,
                    help_text='Filtres / tri / colonnes / groupement (opaque '
                              'pour core).',
                    verbose_name='Configuration')),
                ('partage', models.CharField(
                    choices=[('prive', 'Privé'), ('equipe', 'Équipe'),
                             ('societe', 'Société')],
                    default='prive', max_length=8,
                    verbose_name='Partage')),
                ('equipe', models.CharField(
                    blank=True, default='',
                    help_text="Identifiant d'équipe opaque — requis pour un "
                              "partage « equipe », ignoré sinon.",
                    max_length=64, verbose_name='Équipe')),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='%(app_label)s_%(class)s_set',
                    to='authentication.company',
                    verbose_name='Société')),
                ('owner', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='vues_personnalisees',
                    to='authentication.customuser',
                    verbose_name='Propriétaire')),
            ],
            options={
                'verbose_name': 'Vue personnalisée',
                'verbose_name_plural': 'Vues personnalisées',
                'ordering': ['cible', 'nom', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='vuepersonnalisee',
            index=models.Index(
                fields=['company', 'cible', 'partage'],
                name='core_vueperso_idx'),
        ),
    ]

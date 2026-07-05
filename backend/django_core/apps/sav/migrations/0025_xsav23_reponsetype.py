import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('sav', '0024_xsav19_equipement_public_token'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReponseType',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('titre', models.CharField(max_length=150)),
                ('corps', models.TextField()),
                ('nouveau_statut', models.CharField(
                    blank=True, default='', max_length=12,
                    help_text="Statut optionnel appliqué au ticket à l'insertion.")),
                ('archived', models.BooleanField(default=False)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reponses_type', to='authentication.company')),
            ],
            options={
                'verbose_name': 'Réponse type SAV',
                'verbose_name_plural': 'Réponses types SAV',
                'ordering': ['titre'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='reponsetype',
            unique_together={('company', 'titre')},
        ),
    ]

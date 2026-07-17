# NTEDU31 — compte parent (portail, accès tokenisé, sans mot de passe).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0024_ntprt1_customuser_portee'),
        ('education', '0013_incidentdiscipline'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompteParent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('email', models.EmailField(max_length=254, verbose_name='Email')),
                ('token_acces', models.CharField(db_index=True, max_length=64, unique=True, verbose_name="Token d'accès")),
                ('actif', models.BooleanField(default=True, verbose_name='Actif')),
                ('derniere_connexion', models.DateTimeField(blank=True, null=True, verbose_name='Dernière connexion')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
                ('famille', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comptes_parent', to='education.famille', verbose_name='Famille')),
            ],
            options={
                'verbose_name': 'Compte parent (portail)',
                'verbose_name_plural': 'Comptes parent (portail)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='compteparent',
            constraint=models.UniqueConstraint(
                fields=('company', 'email'),
                name='education_compte_parent_email_unique_par_societe'),
        ),
    ]

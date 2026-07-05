from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('roles', '0001_initial'),
        ('authentication', '0014_customuser_account_lockout'),
        ('ged', '0029_remove_folder_ged_folder_unique_alias_email_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='RegleAclMetadonnee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=200)),
                ('condition_group', models.JSONField(blank=True, default=dict)),
                ('niveau', models.CharField(choices=[('lecture', 'Lecture'), ('ecriture', 'Écriture'), ('gestion', 'Gestion')], default='lecture', max_length=8, verbose_name="niveau d'accès")),
                ('priorite', models.PositiveIntegerField(default=0)),
                ('actif', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ged_regles_acl_metadonnee', to='authentication.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ged_regles_acl_metadonnee_creees', to=settings.AUTH_USER_MODEL)),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ged_regles_acl_metadonnee', to='roles.role', verbose_name='rôle')),
            ],
            options={
                'verbose_name': 'Règle ACL par métadonnée',
                'verbose_name_plural': 'Règles ACL par métadonnée',
                'ordering': ['-priorite', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='regleaclmetadonnee',
            index=models.Index(fields=['company', 'actif'], name='ged_reglecl_co_actif_idx'),
        ),
        migrations.AddIndex(
            model_name='regleaclmetadonnee',
            index=models.Index(fields=['role'], name='ged_reglecl_role_idx'),
        ),
    ]

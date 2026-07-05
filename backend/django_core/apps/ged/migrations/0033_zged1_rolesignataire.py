from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0014_customuser_account_lockout'),
        ('ged', '0032_xged27_lotenvoi'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoleSignataire',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=100)),
                ('couleur', models.CharField(default='#2b5cab', max_length=7, verbose_name='couleur (#hex)')),
                ('auth_extra', models.CharField(choices=[('aucune', 'Aucune'), ('sms', 'Code SMS'), ('email_otp', 'Code par email (OTP)')], default='aucune', max_length=10, verbose_name='authentification supplémentaire')),
                ('peut_changer_signataire', models.BooleanField(default=False, verbose_name='peut changer de signataire')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ged_roles_signataire', to='authentication.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ged_roles_signataire_crees', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Rôle signataire',
                'verbose_name_plural': 'Rôles signataires',
                'ordering': ['nom', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='rolesignataire',
            index=models.Index(fields=['company'], name='ged_rolesign_co_idx'),
        ),
        migrations.AddField(
            model_name='signatairedemande',
            name='role_signataire',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='signataires_demande', to='ged.rolesignataire', verbose_name='rôle réutilisable'),
        ),
    ]

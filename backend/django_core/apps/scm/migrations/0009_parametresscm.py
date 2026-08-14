# NTSCM22 — ParametresSCM (opt-in du cycle S&OP automatique par société).
#
# ADAPTATION DE PÉRIMÈTRE (voir apps/scm/models.py::ParametresSCM) : le plan
# d'origine posait `sop_actif`/`animateur_sop` sur apps.parametres.
# CompanyProfile, hors périmètre de cette lane. Modèle additif, désactivé par
# défaut (sop_actif=False) : n'affecte aucune société existante.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
        ('scm', '0008_scm_unicite_abc_politique'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametresSCM',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('sop_actif', models.BooleanField(default=False, help_text="Désactivé par défaut : n'affecte AUCUNE société existante tant que non activé explicitement (NTSCM22).", verbose_name='Cycle S&OP automatique actif')),
                ('animateur_sop', models.ForeignKey(blank=True, help_text="Notifié à l'ouverture automatique du cycle du mois suivant.", null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='scm_animateur_sop_defaut', to=settings.AUTH_USER_MODEL, verbose_name='Animateur S&OP par défaut')),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='scm_parametres', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Paramètres SCM',
                'verbose_name_plural': 'Paramètres SCM',
            },
        ),
    ]

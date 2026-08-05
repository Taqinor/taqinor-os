# NTADM7 — CompanyProfile.plan : FK nullable vers le catalogue GLOBAL
# adminops.PlanLicence (starter/pro/enterprise). NULL (défaut) = accès
# complet, comportement actuel byte-identique tant qu'aucun plan n'est
# assigné (voir apps.parametres.feature_flags.has_feature).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adminops', '0003_ntadm7_seed_plans'),
        ('parametres', '0067_ez7_signature_client_obligatoire'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='plan',
            field=models.ForeignKey(blank=True, help_text='Palier de licence TAQINOR assigné à cette société. Vide = accès complet (comportement actuel). Assignation réservée au founder.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='adminops.planlicence', verbose_name='Plan de licence'),
        ),
    ]

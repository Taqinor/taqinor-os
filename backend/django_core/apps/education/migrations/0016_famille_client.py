# WIR91 — Famille.client, string-FK optionnel vers crm.Client (jamais un
# import direct de apps.crm.models — résolu via
# apps.education.services.resoudre_client_pour_famille). Additive, même
# patron que sante/migrations/0003_patient.py (Patient.client).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('education', '0015_ntedu40_date_limite_reinscription'),
        ('crm', '0067_lb48_savedview'),
    ]

    operations = [
        migrations.AddField(
            model_name='famille',
            name='client',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='familles_education', to='crm.client',
                verbose_name='Client CRM lié'),
        ),
    ]

# ZSAV8 — Convertir un ticket en opportunité CRM. Référence par ID externe
# (jamais un FK vers apps.crm.Lead — pattern devis_id_ext/facture_id_ext).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0033_zsav2_categorie_ticket'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='lead_id_ext',
            field=models.IntegerField(
                blank=True, null=True,
                help_text='ID du Lead crm créé/réutilisé depuis ce ticket '
                          '(ZSAV8).'),
        ),
    ]

# NTCRM26 — Recommandation de playbook par similarité : critère de sélection
# optionnel sur Playbook (arbre core.rules), évalué contre le lead entrant.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0074_defi'),
    ]

    operations = [
        migrations.AddField(
            model_name='playbook',
            name='condition',
            field=models.JSONField(
                blank=True, null=True, verbose_name='Critère de sélection',
                help_text="Arbre de conditions (core.rules) évalué contre "
                          "{type_installation, canal} du lead. Vide = "
                          "s'applique à tout lead."),
        ),
    ]

# Generated for XRH5 — Déclaration d'entrée CNSS/AMO (suivi de conformité).
#
# Entièrement additive : un CharField à choix (défaut ``a_faire``) + un
# DateField nullable sur ``DossierEmploye``. Réversible.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rh', '0041_checklist_integration'),
    ]

    operations = [
        migrations.AddField(
            model_name='dossieremploye',
            name='declaration_entree_statut',
            field=models.CharField(
                choices=[
                    ('a_faire', 'À faire'),
                    ('declaree', 'Déclarée'),
                    ('non_requis', 'Non requis'),
                ],
                default='a_faire', max_length=12,
                verbose_name="Déclaration d'entrée CNSS/AMO"),
        ),
        migrations.AddField(
            model_name='dossieremploye',
            name='declaration_entree_date',
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Date de déclaration d'entrée"),
        ),
    ]

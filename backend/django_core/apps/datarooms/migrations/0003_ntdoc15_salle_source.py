"""NTDOC15 — salle liée à un deal (Lead / Chantier / Contrat).

Additive : deux colonnes optionnelles (string-ref, jamais une FK dure). Aucune
donnée existante n'est modifiée. L'index de lien retour est posé À PART, EN
CONCURRENT (0004, YOPSB6) — jamais un ``AddIndex`` nu sur une table vivante.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datarooms', '0002_ntdoc12_acces_viewer'),
    ]

    operations = [
        migrations.AddField(
            model_name='sallededonnees',
            name='source_type',
            field=models.CharField(
                blank=True,
                choices=[('lead', 'Lead'), ('chantier', 'Chantier'),
                         ('contrat', 'Contrat')],
                default='', max_length=20,
                verbose_name="Type d'objet d'origine"),
        ),
        migrations.AddField(
            model_name='sallededonnees',
            name='source_id',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name="Identifiant d'origine"),
        ),
    ]

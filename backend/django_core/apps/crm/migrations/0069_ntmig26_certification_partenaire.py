"""NTMIG26 — couche certification sur ``crm.Partenaire`` (table historique
``compta_partenaire``, sortie state-only ODX13).

Strictement ADDITIVE et RÉVERSIBLE : cinq colonnes avec valeur par défaut
(``aucun`` / NULL / liste vide / 0). Aucune ligne existante n'est modifiée ;
l'agrément de base FG237 (``statut_onboarding``/``numero_agrement``/``zone``)
n'est pas touché — NTMIG ajoute la couche compétence PAR-DESSUS, jamais les
mêmes champs.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0068_ntadm2_lead_entite'),
    ]

    operations = [
        migrations.AddField(
            model_name='partenaire',
            name='niveau_certification',
            field=models.CharField(
                choices=[('aucun', 'Aucun'), ('enregistre', 'Enregistré'),
                         ('certifie', 'Certifié'), ('or', 'Or'),
                         ('platine', 'Platine')],
                default='aucun', max_length=12,
                verbose_name='Niveau de certification'),
        ),
        migrations.AddField(
            model_name='partenaire',
            name='date_certification',
            field=models.DateField(
                blank=True, null=True, verbose_name='Date de certification'),
        ),
        migrations.AddField(
            model_name='partenaire',
            name='date_expiration_certification',
            field=models.DateField(
                blank=True, null=True,
                verbose_name="Date d'expiration de la certification"),
        ),
        migrations.AddField(
            model_name='partenaire',
            name='specialites',
            field=models.JSONField(
                blank=True, default=list,
                verbose_name='Spécialités (modules)'),
        ),
        migrations.AddField(
            model_name='partenaire',
            name='nb_deploiements_reussis',
            field=models.PositiveIntegerField(
                default=0, verbose_name='Déploiements réussis'),
        ),
    ]

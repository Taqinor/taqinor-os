# AOF32 — RÉSULTAT d'ouverture des plis : ``ResultatAO`` cesse d'être un modèle
# mort. Quatre champs ADDITIFS (date d'ouverture, nombre de plis, classement,
# notre rang) sur la table héritée ``compta_resultatao``, dont le ``db_table``
# reste STRICTEMENT inchangé (aucun ``AlterModelTable``).
#
# Pourquoi c'est la fin utile de la chaîne : l'app s'arrêtait au dépôt, alors
# que la valeur récurrente est en AVAL — classement, attributaire, prix du
# moins-disant, motif de perte. C'est cette donnée qui alimentera la
# bibliothèque de prix et le KPI de taux de réussite, lequel est CALCULÉ
# (``services.taux_reussite_ao``) et jamais saisi.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ao', '0005_calepinage'),
    ]

    operations = [
        migrations.AddField(
            model_name='resultatao',
            name='classement',
            field=models.JSONField(blank=True, default=list, verbose_name='Classement des plis'),
        ),
        migrations.AddField(
            model_name='resultatao',
            name='date_ouverture',
            field=models.DateField(blank=True, null=True, verbose_name="Date d'ouverture des plis"),
        ),
        migrations.AddField(
            model_name='resultatao',
            name='nombre_plis',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Nombre de plis reçus'),
        ),
        migrations.AddField(
            model_name='resultatao',
            name='notre_rang',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Notre rang'),
        ),
    ]

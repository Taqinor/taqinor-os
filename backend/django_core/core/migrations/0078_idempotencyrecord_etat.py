from django.db import migrations, models


class Migration(migrations.Migration):
    """ERR-AGNR40-IDEMPOTENCE-EN-VOL — ``IdempotencyRecord.etat`` : la clé est
    réservée « en cours » AVANT la création. Additive (défaut « terminé » pour
    les lignes existantes, qui portent déjà une réponse), réversible."""

    dependencies = [
        ('core', '0077_workflowinstance_demandeur'),
    ]

    operations = [
        migrations.AddField(
            model_name='idempotencyrecord',
            name='etat',
            field=models.CharField(choices=[('en_cours', 'En cours'), ('termine', 'Terminé')], default='termine', max_length=10, verbose_name='État'),
        ),
    ]

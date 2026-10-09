# ENF13 — backstop DB (CheckConstraint). Additive, reversible; prod relu le 09/10/2026 : 0 ligne en violation.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('facturation', '0014_atot6_avoir_ventilation_tva'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='paiement',
            constraint=models.CheckConstraint(condition=models.Q(('frais_rejet__isnull', True), ('frais_rejet__gte', 0), _connector='OR'), name='paiement_frais_rejet_non_negatif'),
        ),
        migrations.AddConstraint(
            model_name='paiement',
            constraint=models.CheckConstraint(condition=models.Q(('escompte_montant__isnull', True), ('escompte_montant__gte', 0), _connector='OR'), name='paiement_escompte_montant_non_negatif'),
        ),
    ]

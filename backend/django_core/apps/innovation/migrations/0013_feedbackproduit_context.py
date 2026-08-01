from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('innovation', '0012_feedbackproduit_sentiment'),
    ]

    operations = [
        migrations.AddField(
            model_name='feedbackproduit',
            name='context_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('devis', 'Devis'),
                    ('ticket', 'Ticket SAV'),
                    ('chantier', 'Chantier'),
                ],
                default='', max_length=10,
                verbose_name='Type de contexte (devis/ticket/chantier)'),
        ),
        migrations.AddField(
            model_name='feedbackproduit',
            name='context_id',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='ID de contexte (opaque)'),
        ),
    ]

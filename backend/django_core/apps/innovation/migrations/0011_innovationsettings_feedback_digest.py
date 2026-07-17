from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('innovation', '0010_annonceproduit_feedbackproduit'),
    ]

    operations = [
        migrations.AddField(
            model_name='innovationsettings',
            name='feedback_digest_actif',
            field=models.BooleanField(
                default=False, verbose_name='Digest feedback produit activé'),
        ),
        migrations.AddField(
            model_name='innovationsettings',
            name='feedback_digest_frequence',
            field=models.CharField(
                choices=[('quotidien', 'Quotidien'), ('hebdo', 'Hebdomadaire')],
                default='quotidien', max_length=10,
                verbose_name='Fréquence du digest feedback produit'),
        ),
    ]

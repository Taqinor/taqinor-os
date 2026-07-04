from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0021_rename_notificatio_company_0f3808_idx_notificatio_company_453631_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='approvalreminderconfig',
            name='escalade_days',
            field=models.PositiveSmallIntegerField(
                default=6, verbose_name='Seuil escalade admin (jours ouvrés)'),
        ),
    ]

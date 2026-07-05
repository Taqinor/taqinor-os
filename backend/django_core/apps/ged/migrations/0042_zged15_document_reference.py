from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0041_zged14_demandesignature_emetteur_notifie'),
    ]

    operations = [
        migrations.AddField(
            model_name='document',
            name='reference',
            field=models.CharField(
                blank=True, default='', max_length=50,
                verbose_name='Référence'),
        ),
        migrations.AddConstraint(
            model_name='document',
            constraint=models.UniqueConstraint(
                condition=~models.Q(reference=''),
                fields=('company', 'reference'),
                name='ged_document_uniq_company_reference'),
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('crm', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ventes', '0066_zfac4_note_debit'),
    ]

    operations = [
        migrations.CreateModel(
            name='ParametrageRelanceClient',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('mode', models.CharField(
                    choices=[('auto', 'Automatique'), ('manuel', 'Manuel')],
                    default='auto', max_length=10)),
                ('prochaine_relance_manuelle', models.DateField(
                    blank=True, null=True)),
                ('client', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='parametrage_relance', to='crm.client')),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='parametrages_relance',
                    to='authentication.company')),
                ('responsable', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='clients_relance_responsable',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Paramétrage de relance client',
                'verbose_name_plural': 'Paramétrages de relance client',
            },
        ),
    ]

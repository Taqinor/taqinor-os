import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('authentication', '0001_initial'),
        ('sav', '0021_xsav14_cause_remede_defaillance'),
    ]

    operations = [
        migrations.CreateModel(
            name='EquipementDowntime',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('debut', models.DateTimeField()),
                ('fin', models.DateTimeField(blank=True, null=True)),
                ('motif', models.CharField(blank=True, default='', max_length=255)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='downtimes_equipement',
                    to='authentication.company')),
                ('equipement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='downtimes', to='sav.equipement')),
                ('ticket', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='downtimes', to='sav.ticket')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Immobilisation équipement',
                'verbose_name_plural': 'Immobilisations équipement',
                'ordering': ['-debut'],
            },
        ),
        migrations.AddIndex(
            model_name='equipementdowntime',
            index=models.Index(
                fields=['company', 'equipement'],
                name='sav_eqdown_co_equip_idx'),
        ),
        migrations.AddIndex(
            model_name='equipementdowntime',
            index=models.Index(
                fields=['equipement', 'fin'],
                name='sav_eqdown_equip_fin_idx'),
        ),
    ]

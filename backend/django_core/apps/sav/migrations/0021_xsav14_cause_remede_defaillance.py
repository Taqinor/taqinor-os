import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('sav', '0020_rename_sav_ticketsat_co_date_idx_sav_tickets_company_8e0634_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='CauseDefaillance',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('nom', models.CharField(max_length=150)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('archived', models.BooleanField(default=False)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='causes_defaillance',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': 'Cause de défaillance',
                'verbose_name_plural': 'Causes de défaillance',
                'ordering': ['ordre', 'nom'],
            },
        ),
        migrations.CreateModel(
            name='RemedeDefaillance',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('nom', models.CharField(max_length=150)),
                ('ordre', models.PositiveIntegerField(default=0)),
                ('archived', models.BooleanField(default=False)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='remedes_defaillance',
                    to='authentication.company')),
            ],
            options={
                'verbose_name': 'Remède de défaillance',
                'verbose_name_plural': 'Remèdes de défaillance',
                'ordering': ['ordre', 'nom'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='causedefaillance',
            unique_together={('company', 'nom')},
        ),
        migrations.AlterUniqueTogether(
            name='remededefaillance',
            unique_together={('company', 'nom')},
        ),
        migrations.AddField(
            model_name='ticket',
            name='cause',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tickets', to='sav.causedefaillance'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='remede',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tickets', to='sav.remededefaillance'),
        ),
    ]

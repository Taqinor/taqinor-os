# ZMFG1 — Équipes de maintenance (Configuration > Maintenance Teams, parité
# Odoo). `EquipeMaintenance` (membres M2M, responsable, actif) + `Ticket.equipe`
# optionnel (SET_NULL), sans toucher à `technicien_responsable` existant.
import django.conf
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
        ('sav', '0039_yserv12_ticket_canal_resolution'),
    ]

    operations = [
        migrations.CreateModel(
            name='EquipeMaintenance',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('nom', models.CharField(max_length=120)),
                ('actif', models.BooleanField(default=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='equipes_maintenance',
                    to='authentication.company')),
                ('membres', models.ManyToManyField(
                    blank=True, related_name='equipes_maintenance',
                    to=django.conf.settings.AUTH_USER_MODEL)),
                ('responsable', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='equipes_maintenance_dirigees',
                    to=django.conf.settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Équipe de maintenance',
                'verbose_name_plural': 'Équipes de maintenance',
                'ordering': ['nom'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='equipemaintenance',
            unique_together={('company', 'nom')},
        ),
        migrations.AddField(
            model_name='ticket',
            name='equipe',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='tickets', to='sav.equipemaintenance'),
        ),
    ]

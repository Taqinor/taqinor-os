"""APFS66 (D-APFS-3) — ``societes_autorisees`` passe par ``AppartenanceSociete`` : ÉTAT seul sur la table
EXISTANTE du M2M auto (aucune ligne perdue) + colonne nullable ``role_id``.
Réversible : ``migrate authentication 0035``."""
import django.db.models.deletion as deletion
from django.conf import settings
from django.db import migrations, models

TABLE = 'authentication_customuser_societes_autorisees'


class Migration(migrations.Migration):

    dependencies = [('authentication', '0035_customuser_fonction'), ('roles', '0013_apfs40_codes_administration')]

    operations = [
        migrations.SeparateDatabaseAndState(database_operations=[], state_operations=[
            migrations.CreateModel(name='AppartenanceSociete', fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.ForeignKey(db_column='customuser_id', on_delete=deletion.CASCADE,
                                           related_name='appartenances', to=settings.AUTH_USER_MODEL)),
                ('company', models.ForeignKey(on_delete=deletion.CASCADE, related_name='appartenances',
                                              to='authentication.company')),
            ], options={'db_table': TABLE, 'unique_together': {('user', 'company')}}),
            migrations.AlterField(model_name='customuser', name='societes_autorisees', field=models.ManyToManyField(
                blank=True, related_name='membres_autorises', through='authentication.AppartenanceSociete',
                to='authentication.company', verbose_name='Sociétés autorisées')),
        ]),
        migrations.AddField(model_name='appartenancesociete', name='role', field=models.ForeignKey(
            blank=True, null=True, on_delete=deletion.SET_NULL, related_name='appartenances', to='roles.role')),
    ]

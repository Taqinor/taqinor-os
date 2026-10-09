"""ERR-ASTK226 — `IncidentQualiteFournisseur.resolu_par` : auteur de la
résolution, posé côté serveur à la bascule `resolu=true`.

Additive et revertable : FK nullable SET_NULL, aucune donnée réécrite.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('stock', '0169_mouvementstock_mouvementstock_quantite_non_negative'),
    ]

    operations = [
        migrations.AddField(
            model_name='incidentqualitefournisseur',
            name='resolu_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='incidents_qualite_resolus',
                to=settings.AUTH_USER_MODEL),
        ),
    ]

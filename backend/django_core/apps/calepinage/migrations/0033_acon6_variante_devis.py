# ACON6 (D-ACON-2) — la variante peut PORTER un second devis actif du lead.
#
# Additive : FK nullable ``CalepinageVariante.devis`` (SET_NULL) + unicité
# conditionnelle (un devis n'est porté que par UNE variante). Réversible.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calepinage', '0032_acal375_meteo_retirees'),
        ('ventes', '0117_stkcat23_lignedevis_role_devis'),
    ]

    operations = [
        migrations.AddField(
            model_name='calepinagevariante',
            name='devis',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='variantes_calepinage', to='ventes.devis',
                verbose_name='Devis porté'),
        ),
        migrations.AddConstraint(
            model_name='calepinagevariante',
            constraint=models.UniqueConstraint(
                condition=models.Q(('devis__isnull', False)),
                fields=('devis',), name='uniq_variante_par_devis'),
        ),
    ]

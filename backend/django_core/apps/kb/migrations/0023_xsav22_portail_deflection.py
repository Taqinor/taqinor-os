# XSAV22 — champs de déflection KB sur le portail client. Additif uniquement :
# ``visible_portail`` (défaut FAUX) et ``consultations_portail_ticket``
# (défaut 0) n'affectent aucun article existant. Réversible par
# ``git revert`` / ``migrate kb 0022``.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('kb', '0022_blocreutilisable'),
    ]

    operations = [
        migrations.AddField(
            model_name='kbarticle',
            name='visible_portail',
            field=models.BooleanField(
                default=False, verbose_name='Visible sur le portail client'),
        ),
        migrations.AddField(
            model_name='kbarticle',
            name='consultations_portail_ticket',
            field=models.PositiveIntegerField(
                default=0,
                verbose_name='Consultations depuis un ticket portail'),
        ),
    ]

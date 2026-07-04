# XKB14 — Vérification, péremption & verrou d'article.
# ``verifie_par``/``verifie_jusqua`` (badge « Vérifié » + échéance de re-revue)
# et ``est_verrouille`` (lecture seule — SOP approuvées). Défauts NULL/False —
# RÉTRO-COMPATIBLE, aucun article existant n'est verrouillé ou marqué vérifié
# malgré lui. Entièrement additive, réversible par ``git revert`` /
# ``migrate kb 0012``.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("kb", "0012_kbarticle_est_gabarit"),
    ]

    operations = [
        migrations.AddField(
            model_name="kbarticle",
            name="verifie_par",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="kb_app_articles_verifies",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Vérifié par",
            ),
        ),
        migrations.AddField(
            model_name="kbarticle",
            name="verifie_jusqua",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Vérifié jusqu'au"
            ),
        ),
        migrations.AddField(
            model_name="kbarticle",
            name="est_verrouille",
            field=models.BooleanField(default=False, verbose_name="Verrouillé"),
        ),
    ]

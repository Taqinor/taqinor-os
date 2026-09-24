# CAD163 (décision fondateur du 21/09/2026, Q9) — la loi 82-21 n'est jamais
# abordée spontanément : la question de l'appel ne propose plus « injecter le
# surplus » et le libellé du choix ne nomme plus la loi. La VALEUR
# `injection_8221` est INCHANGÉE — seuls le libellé et le texte d'aide
# bougent : AlterField sans effet sur les données.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0109_cad35_periode_absence'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lead',
            name='objectif_projet',
            field=models.CharField(blank=True, choices=[('facture', 'Baisser la facture'), ('secours_coupures', 'Tenir pendant les coupures'), ('autonomie', 'Gagner en autonomie'), ('injection_8221', 'Revendre le surplus (si le client en parle)'), ('autre', 'Autre')], help_text="Question à l'appel : « Qu'est-ce qui compte le plus pour vous — baisser la facture, tenir pendant les coupures, gagner en autonomie ? » (vide = pas encore posée). « Revendre le surplus » ne se coche QUE si le client en parle lui-même : ce n’est jamais proposé à l’appel. « Tenir pendant les coupures » est un ARGUMENT : aucun dimensionnement de secours n’en découle.", max_length=16, null=True, verbose_name='Objectif du projet'),
        ),
    ]

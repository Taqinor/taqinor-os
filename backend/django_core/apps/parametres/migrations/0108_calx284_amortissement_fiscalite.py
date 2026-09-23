# CALX284 — fiscalité et amortissement SAISIS par la société avec leur source :
# taux d'imposition, mode d'amortissement (aucun / linéaire / dégressif), durée,
# coefficient dégressif. Migration ADDITIVE : tout est vide par défaut (mode
# ``aucun``) — sans saisie, le flux après impôt reprend le flux avant impôt.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0107_calx279_indexation'),
    ]

    operations = [
        migrations.AddField(
            model_name='tariffsettings',
            name='amortissement_coefficient',
            field=models.DecimalField(blank=True, decimal_places=3, help_text='Obligatoire en mode dégressif : taux dégressif = coefficient ÷ durée.', max_digits=5, null=True, verbose_name='Coefficient dégressif'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='amortissement_duree_ans',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Durée d'amortissement (ans)"),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='amortissement_mode',
            field=models.CharField(choices=[('aucun', 'Aucun amortissement'), ('lineaire', 'Linéaire'), ('degressif', 'Dégressif')], default='aucun', max_length=10, verbose_name="Mode d'amortissement"),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='fiscalite_source',
            field=models.TextField(blank=True, default='', help_text="Obligatoire dès qu'un taux d'imposition ou un amortissement est saisi (texte de loi, avis fiscal).", verbose_name='Source de la fiscalité'),
        ),
        migrations.AddField(
            model_name='tariffsettings',
            name='taux_imposition_pct',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Taux marginal appliqué au résultat imposable du projet. Vide = aucun impôt porté au flux.', max_digits=5, null=True, verbose_name="Taux d'imposition des résultats (%)"),
        ),
    ]

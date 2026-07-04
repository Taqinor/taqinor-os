# XMKT25 — Suivi d'approbation Meta des gabarits WhatsApp + variantes de
# langue. Additif : nouvelles colonnes nullable/default sur WhatsAppTemplate
# existant, aucune donnée touchée. Les lignes existantes restent en
# statut_approbation='brouillon' (comportement identique : rien n'était
# "approuvé" avant ce champ).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0012_qj28_devis_superior_contact'),
    ]

    operations = [
        migrations.AddField(
            model_name='whatsapptemplate',
            name='statut_approbation',
            field=models.CharField(
                choices=[
                    ('brouillon', 'Brouillon'),
                    ('soumis', 'Soumis'),
                    ('approuve', 'Approuvé'),
                    ('rejete', 'Rejeté'),
                ],
                default='brouillon', max_length=12,
                verbose_name="Statut d'approbation Meta"),
        ),
        migrations.AddField(
            model_name='whatsapptemplate',
            name='motif_rejet',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name='Motif de rejet'),
        ),
        migrations.AddField(
            model_name='whatsapptemplate',
            name='categorie',
            field=models.CharField(
                choices=[
                    ('marketing', 'Marketing'),
                    ('utility', 'Utilitaire'),
                ],
                default='utility', max_length=12,
                verbose_name='Catégorie Meta'),
        ),
        migrations.AddField(
            model_name='whatsapptemplate',
            name='groupe',
            field=models.CharField(
                blank=True, default='', max_length=100,
                verbose_name='Groupe de variantes'),
        ),
        migrations.AddIndex(
            model_name='whatsapptemplate',
            index=models.Index(
                fields=['company', 'statut_approbation'],
                name='nwa_tpl_company_statut_idx'),
        ),
    ]

"""NTI18N26 — traduction des modèles de message (WhatsApp/e-mail) au-delà de
fr/darija.

Additif : ``MessageTemplate`` gagne ``corps_en``/``corps_ar`` ;
``EmailTemplate`` gagne ``sujet_en``/``corps_en``/``sujet_ar``/``corps_ar``.
Tous vides par défaut — aucune société existante n'est affectée (repli FR
inchangé tant que rien n'est renseigné).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0091_companyprofile_nti18n22_adresse_structuree'),
    ]

    operations = [
        migrations.AddField(
            model_name='messagetemplate',
            name='corps_en',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='messagetemplate',
            name='corps_ar',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='emailtemplate',
            name='sujet_en',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='emailtemplate',
            name='corps_en',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='emailtemplate',
            name='sujet_ar',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='emailtemplate',
            name='corps_ar',
            field=models.TextField(blank=True, default=''),
        ),
    ]

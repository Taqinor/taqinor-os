"""ADOC75 — routages documentaires par défaut pour les documents client de
ventes (facture, avoir, note de débit, remise), pour chaque société existante.

Création seulement si absent (unicité company+source), jamais de mise à jour :
un réglage personnalisé est préservé. Les lignes créées sont marquées
``seme_par_defaut`` ; la migration inverse ne supprime que celles-là."""
from django.db import migrations, models

ROUTAGES = (
    ('ventes_facture', 'Ventes/Factures/{{ annee }}'),
    ('ventes_avoir', 'Ventes/Avoirs/{{ annee }}'),
    ('ventes_note_debit', 'Ventes/Notes de débit/{{ annee }}'),
    ('ventes_remise', 'Ventes/Remises/{{ annee }}'),
)
CABINET = 'Documents clients'


def semer(apps, schema_editor):
    Company = apps.get_model('authentication', 'Company')
    Cabinet = apps.get_model('ged', 'Cabinet')
    Routage = apps.get_model('ged', 'RoutageDocumentaire')
    for company in Company.objects.all():
        cabinet = None
        for source, dossier in ROUTAGES:
            if Routage.objects.filter(company=company, source=source).exists():
                continue
            if cabinet is None:
                cabinet = Cabinet.objects.filter(
                    company=company, nom=CABINET).first()
                if cabinet is None:
                    cabinet = Cabinet.objects.create(
                        company=company, nom=CABINET)
            Routage.objects.create(
                company=company, source=source, cabinet_cible=cabinet,
                dossier_cible=dossier, actif=True, seme_par_defaut=True)


def retirer(apps, schema_editor):
    Routage = apps.get_model('ged', 'RoutageDocumentaire')
    Routage.objects.filter(seme_par_defaut=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('ged', '0055_asec39_partage_gel'),
    ]

    operations = [
        migrations.AddField(
            model_name='routagedocumentaire',
            name='seme_par_defaut',
            field=models.BooleanField(
                default=False, verbose_name='semé par défaut (ADOC75)'),
        ),
        migrations.RunPython(semer, retirer),
    ]

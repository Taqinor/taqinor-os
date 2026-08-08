"""VAO27 — ``AvisMarche.informateur`` : QUI a signalé cet avis.

Additive et revertable : ``AddField`` avec ``blank=True`` et défaut ``''`` —
jamais un ``NOT NULL`` avec valeur forcée sur une table potentiellement
peuplée. Le caractère OBLIGATOIRE de l'informateur vit dans le SERVICE (la
saisie manuelle le refuse en 400 français), pas dans la colonne : une
contrainte en base bloquerait toute collecte automatique, où personne n'a rien
signalé — une machine a lu.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('veille_ao', '0005_vao24_execution_collecte'),
    ]

    operations = [
        migrations.AddField(
            model_name='avismarche',
            name='informateur',
            field=models.CharField(blank=True, choices=[('partenaire', 'Partenaire'), ('client', 'Client'), ('employe', 'Employé'), ('presse', 'Presse'), ('autre', 'Autre')], default='', help_text="Qui a signalé cet avis. C'est la seule porte qui aurait capté l'avis FRDISI — et la matière de la mesure d'attribution (VAO31).", max_length=20, verbose_name='Informateur'),
        ),
    ]

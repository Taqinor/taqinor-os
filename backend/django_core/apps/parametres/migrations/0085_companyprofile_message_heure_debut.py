"""Décision fondateur du 07/09/2026 — messages dès 08:30, appels jamais
avant 09:00.

POURQUOI. MRY8 n'avait posé qu'UNE fenêtre (`appel_heure_debut` 08:30) et
elle servait à TOUTES les touches. Un lead arrivé la nuit recevait donc son
message d'identité à 08:30 puis un APPEL à 08:33 — trois minutes plus tard,
avant l'heure à laquelle un appel d'affaires se fait au Maroc (recherche
citée par le fondateur : la journée téléphonique commence à 9 h ; un message
écrit, lui, passe très bien plus tôt). D'où deux ouvertures distinctes :
`message_heure_debut` (WhatsApp/e-mail) et `appel_heure_debut` (appel). La
fermeture, la pause du vendredi (appels seulement — un message est silencieux)
et la fenêtre de Ramadan restent communes.

CE QUE FAIT LA MIGRATION, dans l'ordre :

  1. AJOUTE `message_heure_debut` (nullable, défaut 08:30) — aucune ligne
     existante n'est contrainte ;
  2. `AlterField` sur `appel_heure_debut` : le DÉFAUT du modèle passe de 08:30
     à 09:00, sinon toute société créée après cette migration ferait à nouveau
     sonner le téléphone à 08:33 ;
  3. `RunPython` (retour = no-op) : pour CHAQUE profil existant,
     `message_heure_debut = appel_heure_debut` (ou 08:30 si null) — l'heure à
     laquelle la société posait déjà ses touches est conservée pour les
     messages ; et SI `appel_heure_debut` vaut EXACTEMENT 08:30, c'est-à-dire
     l'ancien défaut jamais personnalisé, il passe à 09:00. Une société qui
     avait SAISI une autre heure (08:00, 09:30…) n'est PAS touchée : on ne
     réécrit jamais un réglage choisi à la main.

Le retour est un no-op délibéré : `git revert` du code suffit à revenir au
comportement d'avant, et remettre 08:30 partout écraserait les heures que les
sociétés auront saisies entre-temps.

Opération à UN SEUL passage (Django l'enregistre dans `django_migrations` et
ne la rejoue jamais) : elle lit l'heure d'appel AVANT de la reculer, donc la
rejouer à la main ferait hériter les messages de 09:00 — ne jamais l'appeler
hors du cadre de `migrate`. `appel_heure_debut` est NOT NULL en base ; le
repli « ou 08:30 » n'est qu'une garde de lecture.
"""
import datetime

from django.db import migrations, models

#: L'ancien défaut de MRY8. Une valeur DIFFÉRENTE en base = un choix humain.
ANCIEN_DEFAUT_APPEL = datetime.time(8, 30)
#: L'heure d'ouverture des messages, et la nouvelle ouverture des appels.
DEFAUT_MESSAGE = datetime.time(8, 30)
NOUVEAU_DEFAUT_APPEL = datetime.time(9, 0)


def scinder_les_ouvertures(apps, schema_editor):
    CompanyProfile = apps.get_model('parametres', 'CompanyProfile')
    for profil in CompanyProfile.objects.all().iterator():
        ancienne = profil.appel_heure_debut or DEFAUT_MESSAGE
        profil.message_heure_debut = ancienne
        champs = ['message_heure_debut']
        if profil.appel_heure_debut == ANCIEN_DEFAUT_APPEL:
            profil.appel_heure_debut = NOUVEAU_DEFAUT_APPEL
            champs.append('appel_heure_debut')
        profil.save(update_fields=champs)


def noop(apps, schema_editor):
    """Retour volontairement vide — voir le docstring du module."""


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0084_cadence_relance_index_concurrent'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='message_heure_debut',
            field=models.TimeField(
                blank=True, null=True, default=datetime.time(8, 30),
                help_text='Heure à partir de laquelle une touche '
                          'WhatsApp/e-mail peut être posée.',
                verbose_name='Début des messages'),
        ),
        migrations.AlterField(
            model_name='companyprofile',
            name='appel_heure_debut',
            field=models.TimeField(
                default=datetime.time(9, 0),
                help_text='Heure locale à partir de laquelle on peut appeler.',
                verbose_name='Début des appels'),
        ),
        migrations.RunPython(scinder_les_ouvertures, noop),
    ]

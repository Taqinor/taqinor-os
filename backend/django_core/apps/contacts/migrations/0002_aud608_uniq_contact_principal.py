"""AUD608 — un seul contact PRINCIPAL par client, garanti par la BASE.

L'invariant était vérifié en Python (``ContactClient.clean()``), donc seulement
LISIBLE : deux écritures simultanées passaient toutes les deux le contrôle, et
le client se retrouvait avec deux contacts « principaux » — deux destinataires
officiels pour un même devis.

La contrainte est POSÉE APRÈS une remise en ordre NON DESTRUCTIVE : sur un
client qui porterait déjà plusieurs principaux, le plus ANCIEN (plus petite clé
primaire) garde le drapeau, les autres le perdent. Aucune ligne n'est supprimée,
aucune donnée d'identité n'est touchée — seul un booléen bascule, et il bascule
vers l'état que ``clean()`` prétendait déjà garantir. Sans cette étape, la pose
de la contrainte échouerait au déploiement sur une base réelle portant le
défaut que cette tâche corrige.
"""
from django.db import migrations, models

#: Taille de lot des écritures de remise en ordre (verrou court).
_LOT = 500


def _degrader(ContactClient, pks):
    if pks:
        ContactClient.objects.filter(pk__in=pks).update(
            contact_principal=False)


def _un_seul_principal_par_client(apps, schema_editor):
    # Lecture EN FLUX et écriture par LOTS : un `update()` global sur une
    # grande table garde son verrou pendant toute sa durée — et cette migration
    # tourne pendant un déploiement.
    ContactClient = apps.get_model('contacts', 'ContactClient')
    vus = set()
    lot = []
    for pk, client_id in (ContactClient.objects
                          .filter(contact_principal=True)
                          .order_by('client_id', 'pk')
                          .values_list('pk', 'client_id')
                          .iterator(chunk_size=_LOT)):
        if client_id in vus:
            lot.append(pk)
            if len(lot) >= _LOT:
                _degrader(ContactClient, lot)
                lot = []
        else:
            vus.add(client_id)
    _degrader(ContactClient, lot)


def _rien_a_defaire(apps, schema_editor):
    """Marche arrière : la contrainte part, les drapeaux restent tels quels.

    Re-marquer « principal » des contacts dégradés serait inventer une donnée :
    on ne sait pas lequel l'était à tort."""


class Migration(migrations.Migration):

    dependencies = [
        ('contacts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(_un_seul_principal_par_client, _rien_a_defaire),
        migrations.AddConstraint(
            model_name='contactclient',
            constraint=models.UniqueConstraint(
                condition=models.Q(('contact_principal', True)),
                fields=('client',),
                name='uniq_contact_principal_par_client'),
        ),
    ]

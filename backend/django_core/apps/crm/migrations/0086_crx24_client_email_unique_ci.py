from django.db import migrations, models
from django.db.models.functions import Lower

#: Clé où l'e-mail retiré d'un doublon de casse est CONSERVÉ, dans
#: ``Client.custom_data``. Rien n'est perdu : la migration inverse le remet.
CLE_SAUVEGARDE = 'email_doublon_casse_crx24'


def _groupes_en_doublon_de_casse(Client):
    """Groupes ``(company, lower(email))`` portant plus d'une fiche client.

    L'e-mail vide/NULL est EXCLU : un client sans e-mail est légitime et
    fréquent, et la contrainte posée plus bas ne le couvre pas non plus.
    """
    from django.db.models import Count

    return list(
        Client.objects
        .exclude(email=None).exclude(email='')
        .annotate(cle=Lower('email'))
        .values('company_id', 'cle')
        .annotate(combien=Count('id'))
        .filter(combien__gt=1)
        .order_by('company_id', 'cle')
    )


def desamorcer_doublons_de_casse(apps, schema_editor):
    """CRX24 — prépare la contrainte insensible à la casse SANS crasher.

    Poser l'index directement sur une base qui contient déjà « A@x.ma » ET
    « a@x.ma » dans la même société ferait échouer la migration sur une
    ``IntegrityError`` opaque de PostgreSQL, en pleine fenêtre de déploiement,
    sans dire QUELLES fiches sont en cause. Ce chemin de migration de données
    fait l'inverse : il DÉTECTE les groupes en conflit, les LISTE nommément
    (société, e-mail, identifiants des fiches) et neutralise le conflit de
    façon NON destructive et RÉVERSIBLE :

      * la fiche la plus ANCIENNE de chaque groupe (plus petit id) garde son
        e-mail — c'est elle que ``email__iexact`` renvoyait déjà en pratique ;
      * les autres voient leur e-mail retiré de la colonne et RECOPIÉ dans
        ``custom_data[CLE_SAUVEGARDE]`` — aucune fiche n'est supprimée, aucun
        devis/facture n'est touché, et la migration inverse restaure l'e-mail
        à l'identique.

    Le rapport est imprimé sur la sortie de la migration : il donne au
    fondateur la liste exacte des fiches à fusionner à la main plus tard.
    """
    Client = apps.get_model('crm', 'Client')
    groupes = _groupes_en_doublon_de_casse(Client)
    if not groupes:
        return

    print('\nCRX24 — doublons d\'e-mail (casse ignorée) détectés avant la pose '
          'de la contrainte :')
    for groupe in groupes:
        fiches = list(
            Client.objects
            .filter(company_id=groupe['company_id'])
            .annotate(cle=Lower('email'))
            .filter(cle=groupe['cle'])
            .order_by('id')
        )
        garde, perdants = fiches[0], fiches[1:]
        print(
            "  - société #%s / « %s » : fiche #%s gardée, "
            "e-mail retiré de %s (conservé dans custom_data['%s'])" % (
                groupe['company_id'], groupe['cle'], garde.pk,
                ', '.join('#%s' % c.pk for c in perdants), CLE_SAUVEGARDE))
        for perdant in perdants:
            donnees = perdant.custom_data
            if not isinstance(donnees, dict):
                donnees = {}
            donnees[CLE_SAUVEGARDE] = perdant.email
            perdant.custom_data = donnees
            perdant.email = None
            perdant.save(update_fields=['email', 'custom_data'])
    print('CRX24 — aucune fiche supprimée ; « python manage.py migrate crm '
          '0085 » restaure les e-mails à l\'identique.\n')


def restaurer_doublons_de_casse(apps, schema_editor):
    """Inverse exact de :func:`desamorcer_doublons_de_casse` : remet l'e-mail
    conservé et retire la clé de sauvegarde."""
    Client = apps.get_model('crm', 'Client')
    for client in Client.objects.filter(
            custom_data__has_key=CLE_SAUVEGARDE).iterator():
        donnees = dict(client.custom_data or {})
        client.email = donnees.pop(CLE_SAUVEGARDE, None)
        client.custom_data = donnees or None
        client.save(update_fields=['email', 'custom_data'])


class Migration(migrations.Migration):
    """CRX24 — unicité de l'e-mail client INSENSIBLE À LA CASSE.

    ``Client.Meta.unique_together = [('company', 'email')]`` est sensible à la
    casse alors que toute la résolution de client se fait en ``email__iexact``
    (``crm.services.resolve_client_for_lead``) : « A@x.ma » et « a@x.ma »
    étaient deux lignes distinctes en base que le code lisait comme une seule.
    Cette migration pose l'index fonctionnel partiel qui manquait, après avoir
    désamorcé les conflits existants de façon réversible.
    """

    dependencies = [
        ('crm', '0085_offgrid_raccordement_aucun'),
    ]

    operations = [
        migrations.RunPython(
            desamorcer_doublons_de_casse, restaurer_doublons_de_casse),
        migrations.AddConstraint(
            model_name='client',
            constraint=models.UniqueConstraint(
                models.F('company'), Lower('email'),
                condition=models.Q(('email__isnull', False), models.Q(('email', ''), _negated=True)),
                name='crx24_client_email_unique_ci',
                violation_error_message=(
                    "Un client de cette société porte déjà cet e-mail "
                    "(la casse ne compte pas)."),
            ),
        ),
    ]

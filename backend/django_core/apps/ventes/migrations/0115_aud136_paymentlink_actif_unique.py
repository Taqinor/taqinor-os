"""AUD136 — UN SEUL lien de paiement EN ATTENTE par facture.

`create_payment_link` réutilisait déjà un lien valide, mais rien en base
n'empêchait deux liens actifs sur la même facture (course entre deux appels,
écriture directe, ré-émission à volonté). Un lien de paiement est une surface
PUBLIQUE `AllowAny` : sa multiplicité doit être garantie par la base, pas par
la politesse des appelants.

Migration ADDITIVE et RÉVERSIBLE. Les liens EN ATTENTE déjà PÉRIMÉS sont
d'abord fermés (statut EXPIRÉ) — c'est exactement ce que fait désormais
`expirer_liens_paiement_perimes` avant toute ré-émission —, puis les éventuels
doublons actifs restants sont réduits au plus RÉCENT (le dernier émis est celui
que le client a reçu). Aucun `Paiement` n'est touché, aucun lien supprimé : ils
passent EXPIRÉ, la piste d'audit reste entière.
"""
from django.db import migrations, models
from django.utils import timezone


def _fermer_liens_actifs_en_double(apps, schema_editor):
    PaymentLink = apps.get_model('ventes', 'PaymentLink')
    en_attente = 'en_attente'
    expire = 'expire'

    # 1) Tout lien en attente dont la date est passée est fermé.
    PaymentLink.objects.filter(
        statut=en_attente, expires_at__lte=timezone.now(),
    ).update(statut=expire)

    # 2) S'il reste plusieurs liens actifs sur une facture, on garde le plus
    #    récent (celui que le client a effectivement reçu) et on ferme le reste.
    vus = set()
    a_fermer = []
    for lien_id, facture_id in PaymentLink.objects.filter(
            statut=en_attente).order_by(
            'facture_id', '-created_at', '-id').values_list(
            'id', 'facture_id'):
        if facture_id in vus:
            a_fermer.append(lien_id)
        else:
            vus.add(facture_id)
    if a_fermer:
        PaymentLink.objects.filter(id__in=a_fermer).update(statut=expire)


def _noop(apps, schema_editor):
    """Retour arrière : rien à rouvrir (fermer un lien reste le bon état)."""


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0114_aud135_unicite_paiement_remise'),
    ]

    operations = [
        migrations.RunPython(_fermer_liens_actifs_en_double, _noop),
        migrations.AddConstraint(
            model_name='paymentlink',
            constraint=models.UniqueConstraint(
                condition=models.Q(('statut', 'en_attente')),
                fields=('facture',),
                name='uniq_paymentlink_actif_par_facture'),
        ),
    ]

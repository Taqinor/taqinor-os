from django.db import migrations, models


def _niveau_confiance_pour_liens_existants(apps, schema_editor):
    """L-NIV (fondateur 24/08/2026) — bascule COMPATIBILITÉ ARRIÈRE.

    ``ShareLink.niveau`` a deux valeurs par défaut différentes selon le
    moment : le champ Django (``default='standard'``) s'applique à toute
    ligne créée APRÈS cette migration ; mais les lignes qui existaient
    DÉJÀ ont été partagées SOUS le comportement complet d'aujourd'hui
    (jamais dégradé) — les rebasculer sur « standard » romprait un lien
    déjà envoyé à un client, qui verrait soudain son schéma/roof_layout/
    kit changer sous ses yeux sans qu'aucun commercial n'ait choisi ce
    niveau. On les fige donc explicitement sur « confiance » ici, une
    seule fois, pour TOUT lien qui existe au moment de la migration.
    """
    ShareLink = apps.get_model('ventes', 'ShareLink')
    # Batching (garde check_safe_migrations) : mise à jour par tranches de pks
    # via .iterator() — la table est petite aujourd'hui, mais un update global
    # non borné verrouillerait toute la table le temps de la transaction.
    batch = []
    for pk in ShareLink.objects.values_list('pk', flat=True).iterator(chunk_size=500):
        batch.append(pk)
        if len(batch) >= 500:
            ShareLink.objects.filter(pk__in=batch).update(niveau='confiance')
            batch = []
    if batch:
        ShareLink.objects.filter(pk__in=batch).update(niveau='confiance')


def _noop_reverse(apps, schema_editor):
    """Reverse volontairement no-op : redescendre en 'standard' romprait la
    même garantie de compatibilité arrière décrite ci-dessus."""


class Migration(migrations.Migration):
    """L-NIV — deux niveaux d'affichage RÉVOCABLES pour le lien public de
    proposition (``ShareLink.niveau``) + un gate de lecture OTP par lien
    (``ShareLink.otp_lecture``, additif/nullable-équivalent : défaut False).

    Additive only : deux nouvelles colonnes, aucune table ni colonne
    existante modifiée. Entièrement révertable (le ``RunPython`` de bascule
    a un reverse explicite en no-op — voir sa docstring)."""

    dependencies = [
        ('ventes', '0099_pvord_ordre_lignes'),
    ]

    operations = [
        migrations.AddField(
            model_name='sharelink',
            name='niveau',
            field=models.CharField(
                choices=[('standard', 'Standard'), ('confiance', 'Confiance')],
                default='standard', max_length=16,
                verbose_name="Niveau d'affichage de la proposition"),
        ),
        migrations.AddField(
            model_name='sharelink',
            name='otp_lecture',
            field=models.BooleanField(
                default=False, verbose_name='OTP requis pour consulter'),
        ),
        migrations.RunPython(
            _niveau_confiance_pour_liens_existants, _noop_reverse),
    ]

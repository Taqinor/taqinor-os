"""AUD321 — `JalonProjet(installation, phase)` devient unique en base.

`services.notifier_reception_solde_a_facturer` crée le jalon RECEPTION par
`get_or_create` : sa reprise interne (IntegrityError → re-`get`) n'a rien à
intercepter tant que la base ne porte pas la contrainte, si bien que deux
transitions quasi-simultanées vers RECEPTIONNE créaient DEUX lignes RECEPTION
divergentes pour le même chantier.

PRUDENT, en deux temps :

1. les doublons DÉJÀ en base sont DÉSAMORCÉS sans perte : on garde la ligne la
   plus « porteuse » (jalon atteint, puis rappel déjà envoyé, puis la plus
   ancienne) et les autres passent en jalon AD HOC (`phase = NULL`, libellé
   préfixé « (doublon) ») — aucune ligne n'est supprimée, aucune donnée perdue,
   et la contrainte peut s'appliquer ;
2. la contrainte partielle est ajoutée. Les jalons ad hoc (phase vide/NULL)
   restent libres.
"""
from django.db import migrations, models


def desamorcer_doublons(apps, schema_editor):
    JalonProjet = apps.get_model('installations', 'JalonProjet')
    vus = {}
    doublons = []
    qs = (JalonProjet.objects
          .exclude(phase__isnull=True).exclude(phase='')
          .order_by('installation_id', 'phase',
                    '-atteint', '-rappel_facturation_envoye', 'id'))
    for jalon in qs.iterator():
        cle = (jalon.installation_id, jalon.phase)
        if cle in vus:
            doublons.append(jalon)
        else:
            vus[cle] = jalon.id
    for jalon in doublons:
        jalon.phase = None
        if not (jalon.libelle or '').startswith('(doublon)'):
            jalon.libelle = f'(doublon) {jalon.libelle or ""}'.strip()[:120]
        jalon.save(update_fields=['phase', 'libelle'])


def noop(apps, schema_editor):
    """Irréversible par nature (on ne sait pas quel jalon était un doublon) —
    mais non destructif : les lignes sont toutes encore là."""


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0103_aud326_cloture_verrouillee'),
    ]

    operations = [
        migrations.RunPython(desamorcer_doublons, noop),
        migrations.AddConstraint(
            model_name='jalonprojet',
            constraint=models.UniqueConstraint(
                condition=models.Q(('phase', ''), _negated=True),
                fields=('installation', 'phase'),
                name='uniq_jalonprojet_installation_phase'),
        ),
    ]

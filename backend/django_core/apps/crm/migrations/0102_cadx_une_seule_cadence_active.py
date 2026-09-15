# CADX (fondateur 15/09/2026) — « jamais deux cadences en parallèle sur un
# lead ». La garde vit désormais dans `services.initialiser_plan_relance` ;
# CETTE migration nettoie l'EXISTANT : pour chaque lead portant des touches
# À FAIRE dans PLUSIEURS cadences (1 seul cas connu en prod — lead #348,
# placement « contact » du 11/09 par-dessus un après-devis actif), on garde la
# cadence la plus PRIORITAIRE (après-devis > contact > générique > réveil) et
# on passe les autres en ANNULÉE (moteur, CKP1 : `traite_par` NULL, motif dans
# `note`) — jamais une suppression, l'historique reste lisible. Une note de
# chatter système dit ce qui a été fait.
#
# Idempotente (re-exécution : plus aucun doublon → no-op). Reverse : no-op
# assumé — les annulations portent leur motif et `git`/le chatter gardent la
# trace ; re-créer des touches doublonnées n'aurait aucun sens.
import logging

from django.db import migrations
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)

PRIORITE = {'reveil': 0, 'generique': 1, 'contact': 2, 'apres_devis': 3}
MOTIF = 'doublon de cadence — une seule cadence active par lead (CADX 15/09/2026)'


def _annuler_doublons(apps, schema_editor):
    RelanceEtape = apps.get_model('crm', 'RelanceEtape')
    LeadActivity = apps.get_model('crm', 'LeadActivity')

    doubles = (RelanceEtape.objects.filter(statut='a_faire')
               .values('lead_id')
               .annotate(n=Count('cadence', distinct=True))
               .filter(n__gt=1))
    maintenant = timezone.now()
    for entree in doubles:
        lead_id = entree['lead_id']
        cadences = list(
            RelanceEtape.objects.filter(lead_id=lead_id, statut='a_faire')
            .values_list('cadence', flat=True).distinct())
        gardee = max(cadences, key=lambda c: PRIORITE.get(c, 1))
        annulees = [c for c in cadences if c != gardee]
        touche = RelanceEtape.objects.filter(
            lead_id=lead_id, statut='a_faire').first()
        # Garde anti-verrou (check_safe_migrations) : update PAR LOTS de pks
        # (batch de 500) — l'ensemble est déjà borné par lead+statut, le
        # découpage rend le motif explicitement sûr.
        ids = list(RelanceEtape.objects
                   .filter(lead_id=lead_id, statut='a_faire',
                           cadence__in=annulees)
                   .values_list('pk', flat=True))
        for debut in range(0, len(ids), 500):
            lot = ids[debut:debut + 500]
            RelanceEtape.objects.filter(pk__in=lot).update(
                statut='annulee', note=MOTIF,
                traite_par=None, traite_le=maintenant)
        nb = len(ids)
        logger.info('CADX lead #%s : cadence « %s » gardée, %s touche(s) '
                    'annulée(s) (%s)', lead_id, gardee, nb,
                    ', '.join(annulees))
        try:
            LeadActivity.objects.create(
                company_id=touche.company_id, lead_id=lead_id, user=None,
                kind='note',
                body=(f'Nettoyage CADX : cadence « {gardee} » conservée, '
                      f'{nb} touche(s) de « {", ".join(annulees)} » '
                      'annulée(s) — une seule cadence active par lead '
                      '(règle fondateur 15/09/2026).'))
        except Exception:  # noqa: BLE001 — la note est un confort, jamais bloquante
            logger.warning('CADX : note chatter non écrite (lead #%s)',
                           lead_id, exc_info=True)


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0101_visite_cadence_outcome'),
    ]

    operations = [
        migrations.RunPython(_annuler_doublons, migrations.RunPython.noop),
    ]

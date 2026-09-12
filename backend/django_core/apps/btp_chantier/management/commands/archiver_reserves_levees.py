"""NTCON27 — Sweep mensuel : archive les réserves levées anciennes (Celery beat).

Les ``ReserveChantier`` ``statut=levee`` depuis plus de N mois (réglage société
``ParametresBtpChantier.delai_archivage_reserves_levees_mois``, défaut 24)
passent ``archivee=True`` et sortent des listes actives. JAMAIS de suppression
physique : la signature de levée et l'historique de transitions sont des
preuves de réception, cohérent avec la politique soft-delete du dépôt
(``core.SoftDeleteQuerySet``). Une réserve archivée reste consultable via le
filtre explicite ``?archivee=1`` sur la liste.

Réellement planifié : ``btp_chantier.archiver_reserves_levees`` dans
``erp_agentique/celery.py`` (queue ``scheduled``) — cf. la garde
``scripts/check_commandes_planifiees.py``. Le corps du balayage vit dans
``services.archiver_reserves_levees``, unique implémentation partagée par
cette commande (à la demande) et par la tâche planifiée.

Run :
    python manage.py archiver_reserves_levees
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Archive (drapeau, jamais suppression) les réserves levées depuis '
        'plus de N mois — N réglé par société, défaut 24. Idempotent.'
    )

    def handle(self, *args, **options):
        from apps.btp_chantier.services import archiver_reserves_levees

        resultat = archiver_reserves_levees()
        self.stdout.write(self.style.SUCCESS(
            f"archiver_reserves_levees : {resultat['examines']} réserve(s) "
            f"éligible(s), {resultat['archivees']} archivée(s) (idempotent)."))

"""ACAL34 (C-ACAL-109) — DRY-RUN : les devis ENVOYÉS liés à un calepinage
dont l'étude horaire décrit une AUTRE puissance que leurs lignes.

« Resynchroniser le devis » depuis le module calepinage ne rafraîchissait pas
les quatre études : ``etude_params.etude_horaire.kwc`` pouvait rester sur
l'ancien compte de panneaux (économies / « Rentabilisé en » imprimés depuis
une installation qui n'est plus celle des lignes). L'enveloppe
``resynchroniser_conception`` corrige les PROCHAINS gestes ; cette commande
liste, AVANT le merge, les devis envoyés déjà concernés — devis / kWc de
l'étude / kWc des lignes / économies imprimées — pour la décision du
fondateur.

LECTURE SEULE. ``--dry-run`` est le défaut ET le seul mode : aucun devis
(et surtout aucun devis envoyé) n'est jamais réécrit ici.

    python manage.py acal_etudes_perimees_dry_run [--company <slug>]
"""
from django.core.management.base import BaseCommand

#: Écart toléré entre le kWc de l'étude et celui des lignes (arrondis).
TOLERANCE_KWC = 0.01


def _kwc_etude(devis):
    etude = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    horaire = etude.get('etude_horaire')
    if not isinstance(horaire, dict):
        return None
    try:
        return float(horaire.get('kwc'))
    except (TypeError, ValueError):
        return None


def _kwc_lignes(devis):
    from apps.ventes.domain.scenario import puissance_kwc_du_devis
    try:
        return float(puissance_kwc_du_devis(devis) or 0)
    except Exception:  # noqa: BLE001 — un devis illisible est signalé, pas fatal
        return None


def ecart_du_devis(devis):
    """``(kwc_etude, kwc_lignes, economies)`` si l'étude horaire décrit une
    autre puissance que les lignes, sinon ``None``. Aucune écriture."""
    etude_kwc = _kwc_etude(devis)
    lignes_kwc = _kwc_lignes(devis)
    if etude_kwc is None or lignes_kwc is None:
        return None
    if abs(etude_kwc - lignes_kwc) <= TOLERANCE_KWC:
        return None
    etude = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    return etude_kwc, lignes_kwc, etude.get('economies_annuelles')


class Command(BaseCommand):
    help = ('ACAL34 — liste (lecture seule) les devis envoyés liés à un '
            'calepinage dont etude_horaire.kwc ≠ la puissance des lignes.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', default=True,
            help="Défaut et seul mode : rien n'est jamais écrit.")
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')

    def handle(self, *args, **options):
        from apps.calepinage.selectors import calepinage_du_devis
        from apps.ventes.models import Devis

        qs = (Devis.objects.filter(statut=Devis.Statut.ENVOYE)
              .select_related('company').prefetch_related('lignes')
              .order_by('company_id', 'reference'))
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        self.stdout.write('DRY-RUN (lecture seule) — aucune écriture.')
        self.stdout.write(
            'société | devis | calepinage | kWc étude | kWc lignes | '
            'économies imprimées')
        nb = 0
        for devis in qs.iterator(chunk_size=200):
            calepinage = calepinage_du_devis(devis.pk, devis.company)
            if calepinage is None:
                continue
            ecart = ecart_du_devis(devis)
            if ecart is None:
                continue
            nb += 1
            etude_kwc, lignes_kwc, economies = ecart
            self.stdout.write(
                f'  {devis.company.slug} | {devis.reference} | '
                f'#{getattr(calepinage, "pk", calepinage)} | '
                f'{etude_kwc:.2f} | {lignes_kwc:.2f} | {economies}')
        self.stdout.write(f'Devis concernés : {nb}')

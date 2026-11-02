"""CADV64 — fusionne les VRAIS doublons de leads (même téléphone, même nom).

``leads_fusion.merge_leads`` n'est appelée que par l'écran de fusion : aucune
commande ne traite le lot. Un vrai doublon = deux fiches vivantes de la société
qui partagent le même téléphone normalisé ET la même clé de nom
(``normalize_name``). Les fiches étiquetées ``test`` (CADV63) sont ignorées :
un numéro interne partagé n'est pas un doublon.

Survivant = l'étape la plus AVANCÉE (``_rang_funnel``, STAGES.py), puis la
fiche la plus ancienne ; les autres sont absorbées par ``merge_leads``
(activités, devis, touches déplacés vers le survivant, absorbé archivé).
Le déplacement des devis n'est pas réversible : Reda valide les paires
imprimées par le dry-run (D-CADV-9) avant ``--apply``.

Dry-run PAR DÉFAUT (paires imprimées) ; ``--apply`` fusionne. Rejouable :
l'absorbé est archivé, la paire disparaît.

    python manage.py fusionner_doublons_vrais [--company <slug|id>] [--apply]
                                              [--ids 1,2,3]
"""
from django.core.management.base import BaseCommand, CommandError

from apps.crm.fiche_funnel import _rang_funnel
from apps.crm.leads_doublons import normalize_name
from apps.crm.leads_fusion import merge_leads
from apps.crm.leads_selectors import TAG_TEST
from apps.crm.management.commands.placer_anciens_leads import (
    _resoudre_company,
)
from apps.crm.models import Lead


def _est_test(lead):
    return TAG_TEST in [t.strip().lower() for t in (lead.tags or '').split(',')]


def groupes_doublons(company, ids=None):
    """[(survivant, [absorbés])] : groupes de ≥ 2 fiches vivantes, hors test."""
    vivants = (Lead.objects.filter(company=company, is_archived=False)
               .exclude(phone_normalise='').order_by('pk'))
    groupes = {}
    for lead in vivants.iterator():
        if _est_test(lead):
            continue
        cle = normalize_name(lead.nom, lead.prenom)
        if not cle:
            continue
        groupes.setdefault((lead.phone_normalise, cle), []).append(lead)
    out = []
    for membres in groupes.values():
        if len(membres) < 2:
            continue
        if ids and not ids & {m.pk for m in membres}:
            continue
        # Étape la plus avancée d'abord, puis la plus ancienne (pk croissant).
        membres.sort(key=lambda m: (-_rang_funnel(m.stage), m.pk))
        out.append((membres[0], membres[1:]))
    return out


class Command(BaseCommand):
    help = ('CADV64 — fusionne les doublons réels de leads via merge_leads '
            '(dry-run par défaut ; --apply, --ids).')

    def add_arguments(self, parser):
        parser.add_argument('--company', dest='company', default=None)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--ids', default='',
                            help='Ne traite que les groupes touchant ces ids.')

    def handle(self, *args, **options):
        company = _resoudre_company(options.get('company'))
        try:
            ids = {int(i) for i in options['ids'].split(',') if i.strip()}
        except ValueError:
            raise CommandError('--ids : entiers séparés par des virgules.')
        groupes = groupes_doublons(company, ids or None)
        self.stdout.write(f'{len(groupes)} groupe(s) de doublons réels.')
        for survivant, absorbes in groupes:
            noms = ', '.join(f'#{a.pk}' for a in absorbes)
            self.stdout.write(
                f'  survivant #{survivant.pk} {survivant.nom} '
                f'[{survivant.stage}] ← {noms}')
        if not options['apply']:
            self.stdout.write("Dry-run — rien n'est fusionné (--apply).")
            return
        for survivant, absorbes in groupes:
            merge_leads(survivant, absorbes, None)
        self.stdout.write(self.style.SUCCESS(
            f'{len(groupes)} groupe(s) fusionné(s).'))

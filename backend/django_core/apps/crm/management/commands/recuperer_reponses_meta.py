"""Récupère chez Meta les réponses BRUTES des formulaires passés (≤ 90 jours).

Décision fondateur du 17/11/2026 : chaque soumission Meta garde ses réponses
d'origine à vie (``crm.reponses_meta``). Les soumissions reçues AVANT ce
changement n'ont que leurs colonnes mappées ; tant que Meta les garde encore
(90 jours), cette commande va les rechercher par ``leadgen_id`` avec la MÊME
résolution de jeton que le webhook (``adsengine.selectors.
resolve_lead_ads_access_token``) et les pose comme le webhook le fait :

* chaque ligne ``WebsiteLeadPayload(source=meta_lead_ads)`` sans réponses ;
* chaque lead Meta (``external_id`` = leadgen_id) qui n'a aucune ligne — une
  ligne lui est alors créée, rattachée, jamais en double.

Aucune colonne de lead n'est jamais modifiée ; un lead effacé (loi 09-08) est
sauté. Rejouable sans risque : une ligne qui garde déjà ses réponses est
comptée « déjà présente ». ``--dry-run`` n'appelle PAS Meta : il compte ce qui
serait demandé. À lancer en production SUR DÉCISION DU FONDATEUR seulement.
"""
import datetime
import logging
import urllib.error

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

_STATUTS = ('récupérées', 'déjà présentes', 'expirées chez Meta', 'erreurs',
            'ignorées (lead effacé)', 'à récupérer')


class Command(BaseCommand):
    help = ("Récupère chez Meta (≤ 90 j) les réponses brutes des formulaires "
            "Lead Ads déjà reçus et les garde à côté de leur lead.")

    def add_arguments(self, parser):
        parser.add_argument('--company-slug', default='',
                            help='Une seule société (défaut : toutes).')
        parser.add_argument('--depuis', default='',
                            help='AAAA-MM-JJ : soumissions reçues depuis cette date.')
        parser.add_argument('--dry-run', action='store_true',
                            help="Compte sans rien demander à Meta ni écrire.")

    def handle(self, *args, **options):
        from authentication.models import Company
        depuis = _date(options.get('depuis'))
        societes = Company.objects.all().order_by('pk')
        if options.get('company_slug'):
            societes = societes.filter(slug=options['company_slug'])
            if not societes.exists():
                raise CommandError(f"Société « {options['company_slug']} » introuvable.")
        bilan = dict.fromkeys(_STATUTS, 0)
        for company in societes:
            self._societe(company, depuis, bool(options.get('dry_run')), bilan)
        self.stdout.write('Bilan : ' + ' · '.join(
            f'{k} {v}' for k, v in bilan.items() if v or k != 'à récupérer'))

    def _societe(self, company, depuis, dry_run, bilan):
        from apps.adsengine.selectors import resolve_lead_ads_access_token
        cibles = list(_cibles(company, depuis))
        if not cibles:
            return
        jeton = '' if dry_run else resolve_lead_ads_access_token(company)[0]
        if not dry_run and not jeton:
            self.stdout.write(f'[{company.slug}] aucun jeton Meta — {len(cibles)} sautée(s).')
            bilan['erreurs'] += len(cibles)
            return
        for leadgen_id, raw, lead in cibles:
            statut = _traiter(company, leadgen_id, raw, lead, jeton, dry_run)
            bilan[statut] += 1
            self.stdout.write(f'[{company.slug}] leadgen {leadgen_id} — {statut}')


def _date(texte):
    if not texte:
        return None
    try:
        return datetime.date.fromisoformat(texte)
    except ValueError as exc:
        raise CommandError('--depuis attend AAAA-MM-JJ.') from exc


def _cibles(company, depuis):
    """(leadgen_id, ligne ou None, lead ou None) : lignes Meta de la société,
    puis leads Meta sans aucune ligne. Le tri rend la sortie stable."""
    from apps.crm.leads_meta import _META_LEAD_ADS_SYSTEM
    from apps.crm.models import Lead, WebsiteLeadPayload
    from apps.crm.reponses_meta import REPONSES
    lignes = WebsiteLeadPayload.objects.filter(
        company=company, source=WebsiteLeadPayload.Source.META_LEAD_ADS
    ).select_related('lead').order_by('received_at', 'pk')
    leads = Lead.all_objects.filter(
        company=company, external_system=_META_LEAD_ADS_SYSTEM,
    ).exclude(external_id__isnull=True).exclude(external_id='').order_by('pk')
    if depuis:
        lignes = lignes.filter(received_at__date__gte=depuis)
        leads = leads.filter(date_creation__date__gte=depuis)
    # Un retry Meta crée une ligne de plus pour le même leadgen : UNE ligne par
    # leadgen (celle qui garde déjà les réponses, sinon la plus ancienne).
    par_leadgen = {}
    for raw in lignes:
        payload = raw.payload if isinstance(raw.payload, dict) else {}
        cle = str(payload.get('leadgen_id') or '') or f'#ligne-{raw.pk}'
        if cle not in par_leadgen or isinstance(payload.get(REPONSES), dict):
            par_leadgen[cle] = raw
    vus = set(par_leadgen)
    for cle, raw in par_leadgen.items():
        if raw.lead_id:
            vus.add(str(raw.lead.external_id or ''))
        yield ('' if cle.startswith('#') else cle), raw, raw.lead
    for lead in leads:
        if str(lead.external_id) not in vus:
            yield str(lead.external_id), None, lead


def _traiter(company, leadgen_id, raw, lead, jeton, dry_run):
    from apps.crm import reponses_meta
    if raw is not None and isinstance((raw.payload or {}).get(reponses_meta.REPONSES), dict):
        return 'déjà présentes'
    if raw is not None and (raw.payload or {}).get('caviarde') or reponses_meta._lead_efface(lead):
        return 'ignorées (lead effacé)'
    if not leadgen_id:
        return 'erreurs'
    if dry_run:
        return 'à récupérer'
    from apps.crm.webhooks import fetch_meta_lead_data
    try:
        reponse = fetch_meta_lead_data(leadgen_id, jeton)
    except urllib.error.HTTPError as exc:
        return 'expirées chez Meta' if exc.code in (400, 404) else 'erreurs'
    except Exception:  # noqa: BLE001 — une soumission en échec n'arrête pas les autres (D-ENF22-BLE001)
        logger.warning('recuperer_reponses_meta : récupération en échec (leadgen %s)', leadgen_id,
                       exc_info=True)
        return 'erreurs'
    if raw is not None:
        if not reponses_meta.poser_reponses(raw, reponse, lead):
            return 'erreurs'
        raw.save(update_fields=['payload'])
        return 'récupérées'
    statut = reponses_meta.conserver_reponses_meta(
        company=company, leadgen_id=leadgen_id, reponse=reponse, lead=lead)
    return {'gardee': 'récupérées', 'deja': 'déjà présentes'}.get(statut, 'erreurs')

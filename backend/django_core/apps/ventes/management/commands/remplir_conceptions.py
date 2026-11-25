"""ADEV141 (D-ACAL-97) — remplir les conceptions des leads existants, LISTE D'ABORD.

Sans option, la commande LISTE (règle du 21/11 : une réparation de données ne
se fait qu'après la liste montrée) : pour chaque lead, société par société,
son marché, l'option que le moteur retiendrait, ou son refus nommé — calculé
par le moteur unique (``conception/moteur.py::calculer_conception``, aucune
écriture ; le tout dans une transaction annulée d'office). Rien n'est écrit.

``--appliquer`` range la conception de chaque lead situé (ville ou GPS : un
lead sans lieu reste un refus listé, jamais rangé) par l'écrivain unique
(``conception/service.py::relancer``, origine ``remplissage``) : une empreinte
égale n'écrit rien, donc une seconde exécution ne change rien. Aucun devis
n'est lu en écriture : le moteur ne lit aucun devis, ``relancer`` n'en écrit
aucun. Un lead d'une société n'est jamais lu pour une autre (la société est
celle du lead, filtrée à la requête).

Un lead qui a déjà une version courante n'est pas recalculé (relecture E3 M2 :
une version née d'une pose serait refaite sans son toit). ``--appliquer`` exige
``--company`` ; la liste ouvre un point de sauvegarde par lead.

``--ecarts`` (ADEV151, LECTURE SEULE) : pour chaque lead à toit tracé, la production
et l'économie que le moteur range AUJOURD'HUI (niveau 14) contre celles du niveau 15
(production de la simulation de la pose, ADEV149 ; pose ajustée souveraine, ADEV150),
écart en kWh et en %, taille, puis ses devis : un brouillon jamais envoyé « changera »,
un devis envoyé ou accepté est listé en lecture seule (il ne change jamais). Le niveau
15 n'est forcé que dans ce processus. Relecture E6 M3 : UNE transaction annulée PAR LEAD
(jamais une transaction autour du passage : aucun verrou de calepinage tenu pendant les
appels au service météo) ; le devis en mémoire du moteur porte lui aussi le niveau 15
(``moteur._devis_neuf``) ; la colonne « actuel » est la conception RANGÉE quand elle existe
(désignations comprises), calculée seulement sinon ; la simulation de la pose tourne ici
(commande, jamais une requête) et son écriture est annulée avec le lead. RIEN n'est écrit
(ni conception, ni devis, ni calepinage) — le cache météo du processus, lui, reste. Liste à
montrer au fondateur AVANT de rendre le niveau 15 courant (ACAL1001). ``--limite N`` :
N leads listés au plus ; ``--lead <id>`` : ce lead seul ; une ligne de progression toutes
les 10 leads sur la sortie d'erreur.

    python manage.py remplir_conceptions [--company <id>] [--appliquer]   (--appliquer : --company requis)
    python manage.py remplir_conceptions --ecarts [--company <id>] [--limite N] [--lead <id>]
    python manage.py remplir_conceptions --ecarts-sans-toit [--company <id>] [--limite N] [--lead <id>]

``--ecarts-sans-toit`` (ADEV154, LECTURE SEULE, même boucle que ``--ecarts``) : pour chaque
lead SANS toit tracé et chaque option de sa conception (rangée, sinon calculée), la production
d'aujourd'hui (enveloppe de pertes de 20 %) contre celle du PLAN PAR DÉFAUT (ACAL2026 : toit
supposé à la pente du lead ou 30°, plein sud, même kWc et même matériel que l'option, simulé
par la cascade de la pose ; fiche du module sans puissance : au compte de l'option), le
rendement avant → après en kWh/kWc, écart en kWh et en %, « changera » ; en tête les COMPTES
(leads listés, lignes simulées, non simulées par motif, leads refusés par motif) puis l'écart
moyen et le plus grand ; les leads refusés par le moteur en un bloc final. Liste à montrer au
fondateur AVANT de brancher le moteur sans toit (ADEV155).
"""
import logging

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)

DECLENCHEUR = {'origine': 'remplissage', 'champs': []}
#: Relecture E6 M3 — une ligne de progression (sortie d'erreur) tous les N leads examinés.
PROGRESSION_TOUS = 10


def _leads(company):
    """Les leads vivants de ``company`` (référence par chaîne : aucun import
    du modèle du CRM)."""
    from django.apps import apps
    return apps.get_model('crm', 'Lead').objects.filter(company=company).order_by('pk')


def _leads_deja_ranges(company):
    """Les leads de ``company`` qui ont déjà une version courante."""
    from apps.ventes.models import ConceptionLead
    return set(ConceptionLead.objects.filter(company=company, courante=True, lead__isnull=False)
               .values_list('lead_id', flat=True))


def _ligne(lead, resultat):
    if resultat.etat == 'refus':
        refus = resultat.refus or {}
        return f'  lead #{lead.pk} [{resultat.marche}] REFUS {refus.get("code")} ({refus.get("champ")}) : ' \
               f'{refus.get("message")}'
    return f'  lead #{lead.pk} [{resultat.marche}] option retenue : {resultat.option_retenue}'


class Command(BaseCommand):
    help = ("Liste (par défaut) ou range (--appliquer) la conception du moteur unique de chaque lead "
            "existant, société par société. Aucun devis n'est modifié.")

    def add_arguments(self, parser):
        parser.add_argument('--company', type=int, default=None)
        parser.add_argument('--appliquer', action='store_true')
        parser.add_argument('--ecarts', action='store_true',
                            help='ADEV151 : production actuelle contre production de la pose (lecture seule).')
        parser.add_argument('--ecarts-sans-toit', action='store_true',
                            help='ADEV154 : leads sans toit tracé, production actuelle contre plan par défaut '
                                 '(lecture seule).')
        parser.add_argument('--limite', type=int, default=None, help='--ecarts* : N leads listés au plus.')
        parser.add_argument('--lead', type=int, default=None, help='--ecarts* : ce lead seul.')

    def handle(self, *args, **opts):
        from authentication.models import Company

        if opts['appliquer'] and not opts['company']:
            # Relecture E3 M2 — une écriture se fait société par société, nommée.
            raise CommandError('--appliquer exige --company <id> : une société à la fois.')
        societes = Company.objects.order_by('pk')
        if opts['company']:
            societes = societes.filter(pk=opts['company'])
        for company in societes:
            self.stdout.write(f'Société #{company.pk} {company.nom}')
            if opts['ecarts']:
                self._ecarts(company, limite=opts['limite'], lead_id=opts['lead'])
            elif opts['ecarts_sans_toit']:
                self._ecarts_sans_toit(company, limite=opts['limite'], lead_id=opts['lead'])
            elif opts['appliquer']:
                self._appliquer(company)
            else:
                self._lister(company)

    def _lister(self, company):
        from apps.ventes.conception.moteur import calculer_conception

        completes = refus = erreurs = 0
        with transaction.atomic():
            for lead in _leads(company).iterator():
                try:
                    with transaction.atomic():  # relecture E3 M2 : une erreur de base reste à ce lead
                        resultat = calculer_conception(lead, company)
                except Exception as exc:  # noqa: BLE001 — lead illisible signalé (D-ENF22-BLE001)
                    logger.warning('remplir_conceptions : lead #%s illisible', lead.pk, exc_info=True)
                    erreurs += 1
                    self.stdout.write(f'  lead #{lead.pk} : calcul impossible ({type(exc).__name__})')
                    continue
                completes += resultat.etat != 'refus'
                refus += resultat.etat == 'refus'
                self.stdout.write(_ligne(lead, resultat))
            transaction.set_rollback(True)  # garantie : la liste n'écrit rien
        self.stdout.write(f'  LISTE : {completes} conception(s) complète(s), {refus} refus, {erreurs} erreur(s) '
                          '— rien n\'est écrit ; relancer avec --appliquer pour ranger.')

    def _appliquer(self, company):
        from types import SimpleNamespace

        from apps.ventes.conception.moteur import refus_localisation
        from apps.ventes.conception.service import relancer
        from apps.ventes.selectors_calepinage import pose_du_lead

        ecrites = inchangees = sans_lieu = erreurs = 0
        deja = _leads_deja_ranges(company)
        for lead in _leads(company).iterator():
            if refus_localisation(lead) is not None:  # listé comme refus : rien à ranger sans lieu
                sans_lieu += 1
                continue
            if lead.pk in deja:
                # Relecture E3 M2 — un REMPLISSAGE, pas un rafraîchissement : une
                # version courante (peut-être née d'une pose) n'est pas refaite
                # sans son toit ; le filet de la lecture la tient à jour.
                inchangees += 1
                continue
            try:
                # Relecture E3 M2 (suite) — une pose DÉJÀ enregistrée sur le
                # calepinage ouvert du lead entre dans ce premier calcul, comme
                # pour un événement ``pose_enregistree`` (jamais émis pour les
                # poses d'avant le moteur unique).
                calepinage_id, empreinte_pose = pose_du_lead(company, lead.pk)
                toit = (SimpleNamespace(empreinte=empreinte_pose, plafond_panneaux=None)
                        if empreinte_pose else None)
                relance = relancer(lead, company=company, declencheur=dict(DECLENCHEUR),
                                   toit=toit, calepinage_id=calepinage_id)
            except Exception as exc:  # noqa: BLE001 — un lead en échec n'arrête pas le remplissage (D-ENF22-BLE001)
                logger.warning('remplir_conceptions : lead #%s non rangé', lead.pk, exc_info=True)
                erreurs += 1
                self.stdout.write(f'  lead #{lead.pk} : non rangé ({type(exc).__name__})')
                continue
            ecrites += relance.ecrite
            inchangees += not relance.ecrite
        self.stdout.write(f'  APPLIQUÉ : {ecrites} version(s) rangée(s), {inchangees} inchangée(s), '
                          f'{sans_lieu} sans ville ni GPS (non rangés), {erreurs} erreur(s).')

    def _examiner(self, company, *, limite, lead_id, retenir, calculer):
        """La boucle PARTAGÉE de ``--ecarts`` et ``--ecarts-sans-toit`` (lecture seule) :
        ``--limite`` (N leads listés au plus), ``--lead``, une ligne de progression tous les
        :data:`PROGRESSION_TOUS` leads sur la sortie d'erreur ; relecture E6 M3 : UNE
        transaction annulée PAR LEAD. ``retenir(lead)`` rend le porteur ou ``None`` (lead
        écarté) ; rend ``(lead, calculer(lead, porteur))`` lead par lead (un lead illisible
        est dit et sauté)."""
        leads = _leads(company)
        if lead_id:
            leads = leads.filter(pk=lead_id)
        listes = examines = 0
        for lead in leads.iterator():
            if limite is not None and listes >= limite:
                break
            examines += 1
            if examines % PROGRESSION_TOUS == 0:
                self.stderr.write(f'  … {examines} lead(s) examiné(s), {listes} listé(s)')
            porteur = retenir(lead)
            if porteur is None:
                continue
            try:
                with transaction.atomic():
                    rendu = calculer(lead, porteur)
                    transaction.set_rollback(True)  # garantie : ce lead n'écrit rien
            except Exception as exc:  # noqa: BLE001 — un lead illisible est dit, la liste continue (D-ENF22-BLE001)
                logger.warning('remplir_conceptions (écarts) : lead #%s illisible', lead.pk, exc_info=True)
                self.stdout.write(f'  lead #{lead.pk} : calcul impossible ({type(exc).__name__})')
                continue
            listes += 1
            yield lead, rendu

    def _ecarts(self, company, *, limite=None, lead_id=None):
        """ADEV151 — la liste des écarts de production des brouillons (lecture seule)."""
        from apps.ventes.selectors_calepinage import pose_du_lead

        def retenir(lead):
            calepinage_id, empreinte_pose = pose_du_lead(company, lead.pk)
            return (calepinage_id, empreinte_pose) if calepinage_id else None  # sans toit : --ecarts-sans-toit

        def calculer(lead, toit):
            return _lignes_ecart(lead, toit[0], *_actuel_et_pose(lead, company, *toit))

        listes = 0
        for _lead, lignes in self._examiner(company, limite=limite, lead_id=lead_id, retenir=retenir,
                                            calculer=calculer):
            listes += 1
            for ligne in lignes:
                self.stdout.write(ligne)
        self.stdout.write(f'  ÉCARTS : {listes} lead(s) à toit tracé listé(s) — rien n\'est écrit ; le niveau 15 '
                          'n\'est rendu courant qu\'après lecture de cette liste par le fondateur (ACAL1001).')

    def _ecarts_sans_toit(self, company, *, limite=None, lead_id=None):
        """ADEV154 — leads SANS toit tracé : production rangée aujourd'hui (enveloppe de pertes
        de 20 %) contre la simulation du PLAN PAR DÉFAUT (ACAL2026), par option ; l'écart
        moyen et le plus grand EN TÊTE, puis les lignes des leads. Rien n'est écrit."""
        from apps.ventes.selectors_calepinage import pose_du_lead

        def retenir(lead):
            return None if pose_du_lead(company, lead.pk)[0] else lead

        rendus = [(lead, rendu) for lead, rendu in self._examiner(
            company, limite=limite, lead_id=lead_id, retenir=retenir,
            calculer=lambda lead, _porteur: _ecarts_du_plan_par_defaut(lead, company))]
        for ligne in _sortie_sans_toit(rendus):
            self.stdout.write(ligne)
        self.stdout.write(f'  ÉCARTS SANS TOIT : {len(rendus)} lead(s) sans toit tracé listé(s) — rien n\'est '
                          'écrit ; le moteur sans toit ne passe au plan par défaut qu\'après lecture de cette liste '
                          'par le fondateur (ADEV155).')


def _actuel_et_pose(lead, company, calepinage_id, empreinte_pose):
    """``(actuel, pose)`` d'un lead à toit tracé : la conception RANGÉE courante (sinon
    calculée au niveau courant, désignations comprises) contre le niveau 15 (pose simulée
    ICI, jamais dans une requête), désignations comprises."""
    from types import SimpleNamespace

    from apps.ventes.conception.moteur import calculer_conception
    from apps.ventes.conception.porte_calepinage import contexte_de_pose, designations_du_calepinage
    from apps.ventes.models import ConceptionLead

    toit = SimpleNamespace(empreinte=empreinte_pose, plafond_panneaux=None) if empreinte_pose else None
    designes = designations_du_calepinage(company, calepinage_id) or None
    rangee = ConceptionLead.objects.filter(company=company, lead=lead, courante=True).first()
    actuel = (SimpleNamespace(etat=rangee.etat, refus=rangee.refus, valeurs=rangee.valeurs,
                              option_retenue=rangee.option_retenue or None) if rangee is not None
              else calculer_conception(lead, company, toit=toit, calepinage_id=calepinage_id, imposes=designes,
                                       souple=designes is not None))
    with _niveau_pose_reelle(), contexte_de_pose(simuler=True):
        pose = calculer_conception(lead, company, toit=toit, calepinage_id=calepinage_id, imposes=designes,
                                   souple=designes is not None)
    return actuel, pose


def _niveau_pose_reelle():
    """Le niveau de règles 15 (``REGLES_POSE_REELLE_2111``) forcé DANS CE PROCESSUS le
    temps d'un calcul de liste, jamais rendu courant ailleurs."""
    from contextlib import contextmanager

    from apps.ventes.domain import regles_calcul as RC

    @contextmanager
    def forcer():
        courant = RC.REGLES_COURANTES
        RC.REGLES_COURANTES = RC.REGLES_POSE_REELLE_2111
        try:
            yield
        finally:
            RC.REGLES_COURANTES = courant
    return forcer()


def _valeur(resultat, cle):
    retenue = (resultat.valeurs or {}).get(resultat.option_retenue) or {}
    return (retenue.get(cle) or {}).get('valeur'), (retenue.get(cle) or {}).get('source')


def _nombre(valeur):
    return '—' if valeur is None else f'{valeur:,.0f}'.replace(',', ' ')


def _lignes_ecart(lead, calepinage_id, actuel, pose):
    """Les lignes d'UN lead : production / économie / taille actuelles contre pose, puis
    ses devis (brouillon : changera ; envoyé ou accepté : lecture seule)."""
    from apps.ventes.models import Devis

    if actuel.etat == 'refus' or pose.etat == 'refus':
        refus = (actuel.refus if actuel.etat == 'refus' else pose.refus) or {}
        return [f'  lead #{lead.pk} (calepinage #{calepinage_id}) : REFUS {refus.get("code")} — '
                f'{refus.get("message")}']
    (prod_a, _), (prod_p, source) = _valeur(actuel, 'production_annuelle'), _valeur(pose, 'production_annuelle')
    eco_a, eco_p = _valeur(actuel, 'economies_annuelles')[0], _valeur(pose, 'economies_annuelles')[0]
    nb_a, nb_p = _valeur(actuel, 'nb_panneaux')[0], _valeur(pose, 'nb_panneaux')[0]
    if prod_a is not None and prod_p is not None:
        ecart = prod_p - prod_a
        pct = f'{ecart / prod_a * 100:+.1f} %' if prod_a else '—'
        texte_ecart = f'{ecart:+,.0f} kWh ({pct})'.replace(',', ' ')
    else:
        texte_ecart = '—'
    change = (prod_a, eco_a, nb_a) != (prod_p, eco_p, nb_p)
    lignes = [f'  lead #{lead.pk} (calepinage #{calepinage_id}) : production {_nombre(prod_a)} → {_nombre(prod_p)} '
              f'kWh/an (écart {texte_ecart}{"" if source == "pose" else ", simulation de la pose non faite"}) ; '
              f'économie {_nombre(eco_a)} → {_nombre(eco_p)} MAD/an ; taille {nb_a} → {nb_p} panneaux']
    for devis in Devis.objects.filter(company=lead.company_id, lead=lead, is_active=True).order_by('pk'):
        if devis.statut == 'brouillon':
            lignes.append(f'    {devis.reference} brouillon jamais envoyé — changera : {"oui" if change else "non"}')
        else:
            lignes.append(f'    {devis.reference} {devis.statut} — lecture seule : ne changera jamais')
    return lignes


def _signe(kwh):
    return f'{kwh:+,.0f}'.replace(',', ' ')


def _ecarts_du_plan_par_defaut(lead, company):
    """``{refus}`` (le moteur refuse ce lead) ou ``{options: [...]}`` d'un lead sans toit : par
    option de sa conception (rangée courante, sinon calculée), la production d'aujourd'hui
    contre le plan par défaut au kWc, au compte et au matériel de l'option. Chaque option :
    ``{option, kwc, avant, apres, kwc_plan, refus, pente_supposee, pose_supposee, etapes_sans_fiche,
    puissance_conception, fiche_vide}`` (lecture seule) : ``fiche_vide`` = la fiche du module
    ne porte pas sa puissance ou fait omettre des étapes de pertes, la production « après »
    est alors SURESTIMÉE."""
    from apps.ventes.conception.moteur import calculer_conception
    from apps.ventes.conception.porte_calepinage import production_du_plan_par_defaut
    from apps.ventes.models import ConceptionLead

    rangee = ConceptionLead.objects.filter(company=company, lead=lead, courante=True).first()
    actuel = rangee if rangee is not None else calculer_conception(lead, company)
    if actuel.etat == 'refus':
        return {'refus': actuel.refus or {}}
    options = []
    for option, valeurs in (actuel.valeurs or {}).items():
        def valeur(cle, valeurs=valeurs):
            return (valeurs.get(cle) or {}).get('valeur')
        kwc = valeur('puissance_kwc')
        plan = production_du_plan_par_defaut(company, lead, kwc, {
            'module': valeur('module_produit'), 'onduleur': valeur('onduleur_produit')},
            nb_panneaux=valeur('nb_panneaux'))
        options.append({'option': option, 'kwc': kwc, 'avant': valeur('production_annuelle'),
                        'apres': plan.get('production_annuelle'), 'kwc_plan': plan.get('kwc') or kwc,
                        'refus': plan.get('refus'),
                        'pente_supposee': any(s.get('champ') == 'inclinaison_deg'
                                              for s in plan.get('suppositions') or ()),
                        'pose_supposee': next((s.get('valeur') for s in plan.get('suppositions') or ()
                                               if s.get('code') == 'pose_supposee'), None),
                        **_fiche_du_module(plan.get('suppositions') or ())})
    return {'options': options}


def _fiche_du_module(suppositions):
    """``{etapes_sans_fiche, puissance_conception, fiche_vide}`` lus sur les suppositions du
    plan par défaut (codes ``fiche_module_incomplete`` / ``puissance_module_de_la_conception``)."""
    codes = [s.get('code') for s in suppositions]
    etapes, puissance = codes.count('fiche_module_incomplete'), 'puissance_module_de_la_conception' in codes
    return {'etapes_sans_fiche': etapes, 'puissance_conception': puissance, 'fiche_vide': bool(etapes or puissance)}


def _drapeau_fiche(o):
    """Le drapeau d'une ligne simulée avec une fiche de module vide (production surestimée)."""
    if not o.get('fiche_vide'):
        return ''
    return (f', fiche du module vide : {o.get("etapes_sans_fiche", 0)} étape(s) de pertes non appliquée(s)'
            + (', puissance prise de la conception' if o.get('puissance_conception') else ''))


def _ligne_moyenne(quoi, ecarts):
    """« ÉCART MOYEN (<quoi>) : … ; PLUS GRAND : … » sur ``ecarts`` (non vide)."""
    plus_grand = max(ecarts, key=lambda ecart: abs(ecart['pct']))
    return (f'  ÉCART MOYEN ({quoi}) : {_signe(sum(e["kwh"] for e in ecarts) / len(ecarts))} kWh/an '
            f'({sum(e["pct"] for e in ecarts) / len(ecarts):+.1f} %) ; PLUS GRAND : lead '
            f'#{plus_grand["lead"]} option {plus_grand["option"]} {_signe(plus_grand["kwh"])} '
            f'kWh/an ({plus_grand["pct"]:+.1f} %)')


def _rendement(production, kwc):
    """Le rendement en kWh par kWc (« — » sans production ou sans taille)."""
    return '—' if production is None or not kwc else _nombre(production / float(kwc))


def _ligne_option(lead, o):
    """``(ligne, écart | None)`` d'UNE option d'un lead sans toit : le RENDEMENT avant → après
    (kWh/kWc : c'est lui qui bouge, pas la taille), puis la production et l'écart."""
    tete = (f'  lead #{lead.pk} (sans toit) option {o["option"]} : {o["kwc"]} kWc, rendement '
            f'{_rendement(o["avant"], o["kwc"])} → ')
    if o['refus']:
        return tete + f'— kWh/kWc : plan par défaut non simulé ({o["refus"]})', None
    avant, apres = o['avant'], o['apres']
    tete += (f'{_rendement(apres, o["kwc_plan"])} kWh/kWc ; production {_nombre(avant)} → {_nombre(apres)} kWh/an')
    if avant is None or apres is None:
        return tete + ' (écart —) ; changera : —', None
    kwh, pct = apres - avant, ((apres - avant) / avant * 100 if avant else 0.0)
    supposee = ((', pente supposée 30°' if o['pente_supposee'] else '')
                + (f', pose supposée {o["pose_supposee"]}' if o.get('pose_supposee') else '') + _drapeau_fiche(o))
    return (tete + f' (écart {_signe(kwh)} kWh, {pct:+.1f} %{supposee}) ; '
            f'changera : {"oui" if round(apres) != round(avant) else "non"}',
            {'lead': lead.pk, 'option': o['option'], 'kwh': kwh, 'pct': pct,
             'fiche_vide': bool(o.get('fiche_vide'))})


def _compte_par_motif(motifs):
    from collections import Counter
    return ' ; '.join(f'{nombre} × {motif}' for motif, nombre in Counter(motifs).most_common()) or 'aucune'


def _sortie_sans_toit(rendus):
    """Les lignes de ``--ecarts-sans-toit``, lisibles par le fondateur : les COMPTES en tête
    (leads listés, lignes d'option simulées, non simulées par motif, leads refusés par le
    moteur par motif), puis l'écart moyen et le plus grand, les lignes des options, et les
    leads refusés en UN bloc final (ce ne sont pas des écarts)."""
    refuses = [(lead, rendu['refus']) for lead, rendu in rendus if 'refus' in rendu]
    lignes, ecarts, non_simulees = [], [], []
    for lead, rendu in rendus:
        for o in rendu.get('options') or ():
            ligne, ecart = _ligne_option(lead, o)
            lignes.append(ligne)
            ecarts += [ecart] if ecart else []
            non_simulees += [o['refus']] if o['refus'] else []
    options = [o for _l, r in rendus for o in r.get('options') or ()]
    simulees = len(options) - len(non_simulees)
    vides = sum(1 for o in options if not o['refus'] and o.get('fiche_vide'))
    tete = [f'  COMPTES : {len(rendus)} lead(s) sans toit listé(s) ; {simulees} ligne(s) d\'option simulée(s), '
            f'dont {vides} avec une fiche de module vide (production surestimée) ; '
            f'{len(non_simulees)} non simulée(s) : {_compte_par_motif(non_simulees)} ; {len(refuses)} lead(s) '
            f'refusé(s) par le moteur : {_compte_par_motif([r.get("code") for _l, r in refuses])}']
    if ecarts:
        completes = [e for e in ecarts if not e['fiche_vide']]
        tete.append(_ligne_moyenne(f'fiche complète, {len(completes)} ligne(s)', completes) if completes else
                    '  ÉCART MOYEN (fiche complète) : aucune ligne simulée avec une fiche de module complète — '
                    'aucun écart fiable à moyenner')
        tete.append(_ligne_moyenne(f'toutes les lignes simulées, {len(ecarts)}', ecarts))
    fin = ([f'  LEADS REFUSÉS PAR LE MOTEUR ({len(refuses)}, pas des écarts) :']
           + [f'    lead #{lead.pk} : {r.get("code")} — {r.get("message")}' for lead, r in refuses]) if refuses else []
    return tete + lignes + fin

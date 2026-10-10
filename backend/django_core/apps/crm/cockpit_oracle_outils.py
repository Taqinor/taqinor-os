"""COCKPIT-CONTRÔLE (30/09/2026) — L'ORACLE du bloc « Contrôle du suivi ».

Ordre fondateur (Reda, 30/09/2026) : « … to make reading the data and if the commercial did
everything as she should … and test at the end ». Le bloc ne vaut que s'il DIT VRAI : ce
module recalcule, À PARTIR DES LIGNES DE LA BASE et des seules règles écrites dans le contrat
(``contract_samples/controle_suivi.json``, ``notes``), ce que ``GET relance-etapes/controle/``
doit servir — SANS réutiliser ``controle_suivi.py`` ni les fonctions de jugement du dépôt
(``selectors._a_lheure``, ``kpi_adherence``, ``suite_touche.type_etape``…). Deux écritures
indépendantes de la même règle : un écart est une erreur de l'une des deux, à trancher contre
le contrat.

Ce qui est LU tel quel (ce sont des DONNÉES d'entrée de la règle, pas la règle) : le calendrier
de la société (``is_jour_ouvre``), les minutes ouvrées de la médiane (``horaires.minutes_ouvrees_entre``), le
délai de premier contact de la société (``lead_sla_hours``), les absences déclarées
(``PeriodeAbsence``) et la table du parcours (``parcours_suivi.json``, par ``type_de``).

Ce module n'est PAS un module de test (aucune méthode ``test_*``, nom hors du motif
``test*.py``) : ``tests_cockpit_scenario.py`` l'importe. L'oracle suppose un LECTEUR QUI VOIT
TOUTE LA SOCIÉTÉ (il le vérifie) : la portée de visibilité a ses propres tests.
"""
import copy
import datetime
import statistics

from apps.crm import horaires, stages
from apps.crm.models import Lead, PeriodeAbsence, RelanceEtape
from apps.crm.parcours_suivi_outils import etapes_de_la_table, type_de
from apps.notifications.calendar_utils import is_jour_ouvre

#: Les seuils du contrat (``seuils``) — recopiés ICI exprès : si le serveur en change sans que
#: le contrat suive, l'oracle le dit.
RETARD_ALERTE_JOURS = 2
TACHE_ATTENTE_JOURS = 2
REPORTS_MIN = 2
LIGNES_MAX = 10

CASA = horaires.CASABLANCA
JUGEMENTS = ('a_temps', 'en_retard', 'sautees', 'ouvert')


def _local(instant):
    return instant.astimezone(CASA).date()


def _pct(numerateur, denominateur):
    return round(100.0 * numerateur / denominateur, 1) if denominateur else None


class Oracle:
    """L'état attendu du contrôle pour ``company`` à l'instant ``maintenant``."""

    def __init__(self, company, lecteur, *, maintenant):
        from authentication.scoping import visible_user_ids

        if visible_user_ids(lecteur) is not None:
            raise AssertionError(
                'l’oracle suppose un lecteur qui voit toute la société')
        self.company = company
        self.maintenant = maintenant
        self.today = _local(maintenant)
        self.leads = {
            lead.pk: lead for lead in
            Lead.objects.filter(company=company, is_archived=False)}
        self.proprio = {pk: lead.owner_id for pk, lead in self.leads.items()}
        self.absences = list(PeriodeAbsence.objects.filter(company=company))
        self.etapes = list(RelanceEtape.objects.filter(
            company=company, lead_id__in=list(self.leads)).order_by('pk'))
        table = etapes_de_la_table()
        self.ordre_des_types = list(table)
        self.taches = {type_id for type_id, etape in table.items()
                       if etape.get('tache')}
        self._ouvre = {}

    # ── LA règle du retard (contrat, ``notes.retard``) ──

    def ouvre(self, jour):
        if jour not in self._ouvre:
            self._ouvre[jour] = bool(is_jour_ouvre(jour, self.company))
        return self._ouvre[jour]

    def absent(self, owner_id, jour):
        return any(
            periode.date_debut <= jour <= periode.date_fin
            and (periode.utilisateur_id is None
                 or periode.utilisateur_id == owner_id)
            for periode in self.absences)

    def jours_comptes(self, apres, owner_id):
        """Jours ouvrés non excusés, STRICTEMENT après ``apres``, aujourd'hui compris."""
        compte, jour = 0, apres + datetime.timedelta(days=1)
        while jour <= self.today:
            if self.ouvre(jour) and not self.absent(owner_id, jour):
                compte += 1
            jour += datetime.timedelta(days=1)
        return compte

    def minutes_d_attente(self, debut, fin):
        """L'horloge du DÉLAI de premier contact (contrat, ``notes.exceptions``) : les
        minutes d'horloge de ``debut`` à ``fin``, jours NON ouvrés retirés."""
        total, jour = 0.0, _local(debut)
        while jour <= _local(fin):
            if self.ouvre(jour):
                minuit = datetime.datetime.combine(
                    jour, datetime.time(0, 0), tzinfo=CASA)
                lendemain = datetime.datetime.combine(
                    jour + datetime.timedelta(days=1), datetime.time(0, 0), tzinfo=CASA)
                ecoule = (min(fin, lendemain) - max(debut, minuit)).total_seconds()
                total += max(0.0, ecoule) / 60.0
            jour += datetime.timedelta(days=1)
        return total

    def juger(self, etape):
        """``a_temps`` | ``en_retard`` | ``sautees`` | ``ouvert`` | ``None`` (pas encore
        jugée) | ``'hors'`` (annulée par le moteur : hors dénominateur)."""
        owner = self.proprio.get(etape.lead_id)
        if etape.statut == RelanceEtape.Statut.ANNULEE:
            return 'hors'
        if etape.statut == RelanceEtape.Statut.SAUTEE:
            return 'sautees'
        if etape.statut == RelanceEtape.Statut.FAIT:
            if (etape.traite_le is not None
                    and _local(etape.traite_le) <= etape.due_date):
                return 'a_temps'
            # Excusée : née en retard (une touche matérialisée après son échéance)…
            if (etape.due_at is not None and etape.cadence_depart is not None
                    and etape.created_at > etape.due_at):
                return 'a_temps'
            # … ou échue un jour d'absence déclarée de son responsable.
            if self.absent(owner, etape.due_date):
                return 'a_temps'
            return 'en_retard'
        return ('ouvert' if self.jours_comptes(etape.due_date, owner) >= 1
                else None)

    # ── La lecture attendue ──

    def attendu(self, *, jours=14, owner=None, segment=None):
        """AGR542 — ``segment`` : le MÊME filtre que le serveur, écrit ici sur les
        LIGNES de la base (contrat, ``ajout_segment`` → ``notes.segment``) : seuls les
        leads dont ``type_installation`` vaut ``segment`` (``non_renseigne`` = vide ou
        nul) et leurs étapes sont lus ; toutes les règles restent celles d'au-dessus."""
        if segment:
            vue = copy.copy(self)
            vue.leads = {
                pk: lead for pk, lead in self.leads.items()
                if ((lead.type_installation or '') == ''
                    if segment == 'non_renseigne'
                    else lead.type_installation == segment)}
            vue.proprio = {pk: lead.owner_id for pk, lead in vue.leads.items()}
            vue.etapes = [e for e in self.etapes if e.lead_id in vue.leads]
            return {**vue._attendu(jours=jours, owner=owner), 'segment': segment}
        return {**self._attendu(jours=jours, owner=owner), 'segment': None}

    def _attendu(self, *, jours=14, owner=None):
        today = self.today
        debut = today - datetime.timedelta(days=jours - 1)
        debut_precedent = debut - datetime.timedelta(days=jours)

        def du_commercial(etape):
            return owner is None or self.proprio.get(etape.lead_id) == owner

        verdict = dict.fromkeys(('du',) + JUGEMENTS + ('reportees',), 0)
        cases, par_type = {}, {}
        for etape in self.etapes:
            if not (debut <= etape.due_date <= today and du_commercial(etape)):
                continue
            jugement = self.juger(etape)
            if jugement == 'hors':
                continue
            case = cases.setdefault(etape.due_date, dict.fromkeys(
                ('du',) + JUGEMENTS + ('_ouvert_en_retard',), 0))
            case['du'] += 1
            if etape.statut == RelanceEtape.Statut.A_FAIRE:
                case['ouvert'] += 1
                case['_ouvert_en_retard'] += jugement == 'ouvert'
            else:
                case[jugement] += 1
            if jugement is None:
                continue
            type_id = type_de(etape)
            ligne = par_type.setdefault(type_id, dict.fromkeys(
                ('du',) + JUGEMENTS + ('reportees',), 0) | {'reponses': {}})
            for compteurs in (verdict, ligne):
                compteurs['du'] += 1
                compteurs[jugement] += 1
                compteurs['reportees'] += etape.nb_reports >= 1
            if etape.statut == RelanceEtape.Statut.FAIT:
                cle = (etape.outcome or '').strip() or 'sans_issue'
                ligne['reponses'][cle] = ligne['reponses'].get(cle, 0) + 1

        precedente = [self.juger(etape) for etape in self.etapes
                      if debut_precedent <= etape.due_date < debut
                      and du_commercial(etape)]
        precedente = [j for j in precedente if j not in ('hors', None)]

        ouvertes = [etape for etape in self.etapes
                    if etape.statut == RelanceEtape.Statut.A_FAIRE
                    and du_commercial(etape)]
        lointain = datetime.datetime.max.replace(tzinfo=datetime.timezone.utc)
        en_retard = []
        for etape in sorted(ouvertes, key=lambda e: (
                e.due_date, e.due_at or lointain, e.pk)):
            retard = self.jours_comptes(
                etape.due_date, self.proprio.get(etape.lead_id))
            if retard >= 1:
                en_retard.append((etape.pk, etape.lead_id, retard))
        taches = []
        for etape in sorted(ouvertes, key=lambda e: (e.created_at, e.pk)):
            if type_de(etape) not in self.taches:
                continue
            attente = self.jours_comptes(
                _local(etape.created_at), self.proprio.get(etape.lead_id))
            if attente >= TACHE_ATTENTE_JOURS:
                taches.append((etape.pk, etape.lead_id, attente))
        reports = sorted(
            (etape.pk, etape.lead_id, etape.nb_reports,
             _local(etape.due_initial_at).isoformat()
             if etape.due_initial_at else None)
            for etape in ouvertes if etape.nb_reports >= 1)
        plusieurs_fois = sum(1 for _e, _l, nb, _o in reports if nb >= REPORTS_MIN)

        sans_etape = self._sans_prochaine_etape(owner)
        sla = self._delai_premier_contact()
        hors_delai = self._premier_contact_hors_delai(owner)

        def du_lead(lead):
            return ((owner is None or lead.owner_id == owner)
                    and lead.source != Lead.Source.ODOO_IMPORT_TEST)

        debut_instant = datetime.datetime.combine(
            debut, datetime.time(0, 0), tzinfo=CASA)
        nouveaux = [lead for lead in self.leads.values()
                    if lead.date_creation >= debut_instant and du_lead(lead)]
        contactes = [lead for lead in nouveaux if lead.first_contacted_at is not None]
        # La médiane : minutes OUVRÉES (le KPI voisin) ; le délai : son horloge à lui.
        delais = [horaires.minutes_ouvrees_entre(
            lead.date_creation, lead.first_contacted_at, self.company)
            for lead in contactes]
        dans_le_delai = sum(
            1 for lead in contactes if self.minutes_d_attente(
                lead.date_creation, lead.first_contacted_at) < sla * 60) if sla else 0
        attentes = [self.minutes_d_attente(lead.date_creation, self.maintenant)
                    for lead in nouveaux
                    if lead.first_contacted_at is None and lead.stage == stages.NEW
                    and not lead.perdu and not lead.ne_plus_contacter]

        if (any(retard >= RETARD_ALERTE_JOURS for _e, _l, retard in en_retard)
                or sans_etape or hors_delai):
            niveau = 'alerte'
        elif en_retard or taches or plusieurs_fois:
            niveau = 'attention'
        elif not any(case['du'] for case in cases.values()) and not reports:
            niveau = 'vide'
        else:
            niveau = 'ok'

        def etat(case):
            if not case['du']:
                return 'vide'
            if case['ouvert']:
                return 'rouge' if case['_ouvert_en_retard'] else 'en_cours'
            if case['en_retard'] or case['sautees']:
                return 'orange'
            return 'vert'

        frise = []
        if niveau != 'vide':
            for decalage in range(jours):
                jour = debut + datetime.timedelta(days=decalage)
                case = cases.get(jour) or dict.fromkeys(
                    ('du',) + JUGEMENTS + ('_ouvert_en_retard',), 0)
                frise.append({
                    'date': jour.isoformat(), 'ouvre': self.ouvre(jour),
                    'aujourdhui': jour == today, 'du': case['du'],
                    'a_temps': case['a_temps'], 'en_retard': case['en_retard'],
                    'sautees': case['sautees'], 'ouvert': case['ouvert'],
                    'etat': etat(case)})

        ids_des_leads = [pk for pk, lead in self.leads.items()
                         if owner is None or lead.owner_id == owner]
        return {
            'periode_jours': jours,
            'owner': owner,
            'seuils': {
                'retard_alerte_jours': RETARD_ALERTE_JOURS,
                'tache_attente_jours': TACHE_ATTENTE_JOURS,
                'reports_min': REPORTS_MIN,
                'premier_contact_heures': sla,
            },
            'verdict': {
                'niveau': niveau, **verdict,
                'a_temps_pct': _pct(verdict['a_temps'], verdict['du']),
                'precedent_a_temps_pct': _pct(
                    sum(1 for j in precedente if j == 'a_temps'),
                    len(precedente)),
            },
            'jours': frise,
            'en_retard': en_retard,
            'taches_en_attente': taches,
            'reports': reports,
            'reports_plusieurs_fois': plusieurs_fois,
            'sans_prochaine_etape': sans_etape,
            'premier_contact_hors_delai': [(pk, heures)
                                           for _cree, pk, heures in hors_delai],
            'par_type': [
                {'type_etape': type_id, 'est_tache': type_id in self.taches,
                 **{cle: par_type[type_id][cle]
                    for cle in ('du',) + JUGEMENTS + ('reportees',)},
                 'reponses': par_type[type_id]['reponses']}
                for type_id in self.ordre_des_types
                if type_id in par_type and par_type[type_id]['du']],
            'premier_contact': {
                'nouveaux': len(nouveaux),
                'dans_le_delai': dans_le_delai,
                # La médiane EXACTE : le contrat sert un entier sans dire son arrondi
                # (``ecarts`` accepte l'entier voisin).
                'mediane_minutes': statistics.median(delais) if delais else None,
                'delai_heures': sla,
                'plus_longue_attente_heures': (
                    round(max(attentes) / 60.0, 1) if attentes else None),
            },
            'resultats': self._resultats(ids_des_leads, debut, debut_instant),
            'commerciaux': self._commerciaux(debut),
        }

    def _delai_premier_contact(self):
        from apps.crm.leads_premier_contact import lead_sla_hours
        return lead_sla_hours(self.company)

    def _sans_prochaine_etape(self, owner):
        """``[(lead, jours calendaires depuis sa dernière étape close, étape du funnel)]``,
        le plus ancien d'abord."""
        par_lead = {}
        for etape in self.etapes:
            par_lead.setdefault(etape.lead_id, []).append(etape)
        trouves = []
        for pk, lead in self.leads.items():
            etapes = par_lead.get(pk) or []
            if (lead.perdu or lead.ne_plus_contacter
                    or lead.stage in (stages.SIGNED, stages.COLD)
                    or not etapes
                    or any(e.statut == RelanceEtape.Statut.A_FAIRE for e in etapes)
                    or (owner is not None and lead.owner_id != owner)):
                continue
            closes = [e.traite_le for e in etapes if e.traite_le is not None]
            dernier = _local(max(closes)) if closes else None
            trouves.append((
                pk, (self.today - dernier).days if dernier else None, lead.stage))
        trouves.sort(key=lambda t: (t[1] is None, -(t[1] or 0), t[0]))
        return trouves

    def _premier_contact_hors_delai(self, owner):
        """``[(créé le, lead, heures ouvrées d'attente)]``, le plus ancien d'abord."""
        sla = self._delai_premier_contact()
        if not sla:
            return []
        limite = self.maintenant - datetime.timedelta(hours=sla)
        trouves = []
        for pk, lead in self.leads.items():
            if (lead.stage == stages.NEW and lead.first_contacted_at is None
                    and not lead.perdu and not lead.ne_plus_contacter
                    and (owner is None or lead.owner_id == owner)
                    and lead.source != Lead.Source.ODOO_IMPORT_TEST
                    and lead.date_creation <= limite):
                minutes = self.minutes_d_attente(lead.date_creation, self.maintenant)
                if minutes >= sla * 60:
                    trouves.append(
                        (lead.date_creation, pk, round(minutes / 60.0, 1)))
        trouves.sort()
        return trouves

    def _resultats(self, ids_des_leads, debut, debut_instant):
        """Les trois résultats de la période, recomptés sur les tables de leurs apps (les
        mêmes imports locaux que ``parcours_suivi_outils`` : un outil de TEST lit la base
        directement, le code de l'app passe par les sélecteurs)."""
        from apps.ventes.models import Devis
        from apps.visites.models import VisiteTerrain

        devis = Devis.objects.filter(company=self.company, lead_id__in=ids_des_leads)
        return {
            'visites_planifiees': VisiteTerrain.objects.filter(
                company=self.company, lead_id__in=ids_des_leads,
                created_at__gte=debut_instant, date_prevue__isnull=False).count(),
            'devis_envoyes': devis.filter(date_envoi__gte=debut_instant).count(),
            'devis_acceptes': devis.filter(date_acceptation__gte=debut).count(),
        }

    def _commerciaux(self, debut):
        """Les responsables qui ont au moins une étape (hors annulations) due sur la période
        ou une exception — sur TOUTE la portée, quel que soit ``owner`` (c'est la liste du
        sélecteur de l'écran)."""
        concernes = {
            self.proprio.get(etape.lead_id) for etape in self.etapes
            if debut <= etape.due_date <= self.today
            and etape.statut != RelanceEtape.Statut.ANNULEE}
        for etape in self.etapes:
            if etape.statut != RelanceEtape.Statut.A_FAIRE:
                continue
            proprietaire = self.proprio.get(etape.lead_id)
            if (self.jours_comptes(etape.due_date, proprietaire) >= 1
                    or etape.nb_reports >= 1
                    or (type_de(etape) in self.taches and self.jours_comptes(
                        _local(etape.created_at), proprietaire)
                        >= TACHE_ATTENTE_JOURS)):
                concernes.add(proprietaire)
        concernes.update(self.proprio.get(pk)
                         for pk, _jours, _stage in self._sans_prochaine_etape(None))
        concernes.update(self.proprio.get(pk)
                         for _cree, pk, _heures in self._premier_contact_hors_delai(None))
        return sorted(pk for pk in concernes if pk is not None)


def ecarts(attendu, servi):
    """Les écarts entre la lecture ATTENDUE (``Oracle.attendu``) et la réponse SERVIE par
    l'API — une liste de phrases, vide quand tout concorde."""
    trouves = []

    def verifier(nom, a, s):
        if a != s:
            trouves.append(f'{nom} : attendu {a!r} — servi {s!r}')

    for cle in ('periode_jours', 'owner', 'segment', 'seuils'):
        verifier(cle, attendu[cle], servi.get(cle))
    for cle, valeur in attendu['verdict'].items():
        verifier(f'verdict.{cle}', valeur, servi['verdict'].get(cle))
    verifier('jours : dates', [j['date'] for j in attendu['jours']],
             [j['date'] for j in servi['jours']])
    for a, s in zip(attendu['jours'], servi['jours']):
        for cle, valeur in a.items():
            verifier(f'jours[{a["date"]}].{cle}', valeur, s.get(cle))
    exceptions = servi['exceptions']

    def lignes(cle, champs):
        return [tuple(ligne[c] for c in champs)
                for ligne in exceptions[cle]['lignes']]

    for cle, champs in (
            ('en_retard', ('etape', 'lead', 'jours_de_retard')),
            ('taches_en_attente', ('etape', 'lead', 'ouverte_depuis_jours')),
            ('sans_prochaine_etape', ('lead', 'depuis_jours', 'stage')),
            ('premier_contact_hors_delai', ('lead', 'attend_depuis_heures'))):
        verifier(f'exceptions.{cle}.total', len(attendu[cle]),
                 exceptions[cle]['total'])
        verifier(f'exceptions.{cle}.lignes', attendu[cle][:LIGNES_MAX],
                 lignes(cle, champs))
    verifier('exceptions.reports.total', len(attendu['reports']),
             exceptions['reports']['total'])
    verifier('exceptions.reports.plusieurs_fois', attendu['reports_plusieurs_fois'],
             exceptions['reports'].get('plusieurs_fois'))
    if len(attendu['reports']) <= LIGNES_MAX:
        verifier('exceptions.reports.lignes', attendu['reports'], sorted(lignes(
            'reports', ('etape', 'lead', 'nb_reports', 'due_initial'))))
    verifier('par_type : ordre des types',
             [ligne['type_etape'] for ligne in attendu['par_type']],
             [ligne['type_etape'] for ligne in servi['par_type']])
    servis = {ligne['type_etape']: ligne for ligne in servi['par_type']}
    for ligne in attendu['par_type']:
        servie = servis.get(ligne['type_etape'])
        if servie is None:
            continue
        for cle, valeur in ligne.items():
            if cle == 'reponses':
                verifier(f'par_type[{ligne["type_etape"]}].reponses', valeur,
                         {r['cle']: r['n'] for r in servie['reponses']})
                effectifs = [r['n'] for r in servie['reponses']]
                verifier(f'par_type[{ligne["type_etape"]}].reponses triées',
                         sorted(effectifs, reverse=True), effectifs)
            else:
                verifier(f'par_type[{ligne["type_etape"]}].{cle}', valeur,
                         servie.get(cle))
    for cle, valeur in attendu['premier_contact'].items():
        servie = servi['premier_contact'].get(cle)
        if cle == 'mediane_minutes' and valeur is not None and servie is not None:
            # Un entier à moins d'une minute de la médiane exacte (troncature ou arrondi).
            if abs(servie - valeur) >= 1:
                trouves.append(f'premier_contact.{cle} : attendu ~{valeur!r} — servi {servie!r}')
            continue
        verifier(f'premier_contact.{cle}', valeur, servie)
    for cle, valeur in attendu['resultats'].items():
        verifier(f'resultats.{cle}', valeur, servi['resultats'].get(cle))
    verifier('commerciaux', attendu['commerciaux'],
             sorted(c['id'] for c in servi['commerciaux']))
    return trouves

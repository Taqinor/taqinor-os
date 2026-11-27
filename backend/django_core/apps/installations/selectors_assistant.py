"""Copilote vague 2 (CHTA2, CHTA3, CHTA7) — lectures COMPACTES des chantiers
pour l'assistant (actions ``installations.chantier.etat`` et
``installations.chantiers.liste``, cartes ``fiche_chantier`` /
``liste_chantiers``) et le bloc ``chantiers`` du point du matin
(:func:`brief_chantiers`, lu par crm — BRF1).

Contrats : ``contract_samples/assistant_chantier_etat.json`` (une fiche, aussi
rendue par ``POST chantiers/{id}/planifier-pose/``) et
``contract_samples/assistant_chantiers.json`` (une liste). Chaque fonction
publique rend un dictionnaire LITTÉRAL dont les clés sont celles de
l'échantillon.

Règles :
* lecture seule ; la portée est celle de l'APPELANT (queryset déjà borné par
  ``InstallationViewSet.get_queryset``) ;
* le statut est la couche PROPRE du chantier (statut canonique), jamais
  STAGES.py ; rien ici ne le change ;
* aucun prix, coût, prix d'achat ni montant de commande fournisseur ; aucun
  téléphone de client ; aucune position de personne ;
* le besoin matériel (``compute_besoin_materiel``, une requête par produit)
  n'est calculé que pour UNE fiche (``etat_chantier``), jamais par ligne de
  liste : les « blocages » d'une liste sont des signaux gratuits en SQL, plus
  l'acompte exigé (réglage société), borné à :data:`ACOMPTE_BUDGET` lectures.
"""
import datetime

from django.db.models import Exists, F, OuterRef, Q
from django.db.models.functions import Coalesce

#: Ensemble FERMÉ des « à faire » (fiche ET lignes ; une ligne de liste ne
#: rend jamais ``commander_materiel`` : le matériel n'y est pas calculé).
A_FAIRE = ('commander_materiel', 'encaisser_acompte', 'planifier_pose',
           'assigner_technicien', 'poser', 'rien')
#: Ensemble FERMÉ des blocages d'une ligne (sans le besoin matériel).
BLOCAGES = ('sans_date', 'sans_technicien', 'pose_sans_intervention',
            'pose_depassee', 'acompte_non_encaisse')
VUES = ('en_cours', 'bloques', 'poses_semaine')
LIMITE_DEFAUT, LIMITE_MAX = 10, 25
#: Lignes au plus par liste du point du matin (les compteurs portent sur tout).
LIGNES_BRIEF = 5
#: Lectures « acompte encaissé ? » au plus par liste (une par devis).
ACOMPTE_BUDGET = 25
MANQUES_MAX = 8
DESIGNATION_MAX = 80
NOTE_LISTE = 'Matériel : lire installations.chantier.etat (non calculé en liste).'
LIEN_LISTE = '/chantiers'
LIEN_APPRO = '/chantiers/approvisionnement'
#: Statut d'un BCF brouillon (``BonCommandeFournisseur.Statut.BROUILLON``,
#: lu dans la ligne servie par ``achats.selectors.bcf_du_chantier``).
_BCF_BROUILLON = 'brouillon'


def _statuts():
    """(statuts canoniques après la pose, statuts stockés AVANT la pose)."""
    from .models import Installation
    s = Installation.Statut
    fin = (s.INSTALLE, s.RECEPTIONNE, s.CLOTURE)
    avant = [v for v in s.values if Installation.canonical_statut(v) not in fin]
    return fin, avant


def lien_chantier(pk):
    return f'/chantiers?id={pk}'


def _iso(jour):
    return jour.isoformat() if jour else None


def _nom(user):
    if user is None:
        return ''
    return (user.get_full_name() or '').strip() or user.username


def _client_nom(inst):
    client = inst.client if inst.client_id else None
    return f"{client.nom} {client.prenom or ''}".strip() if client else ''


def poses_par_chantier(company_id, ids):
    """``{chantier_id: intervention de pose la plus proche}`` en UNE requête :
    pose non annulée ; d'abord la non terminée la plus tôt datée (une non
    datée en dernier), sinon la dernière terminée."""
    from .models import Intervention
    finies = (Intervention.Statut.TERMINEE, Intervention.Statut.VALIDEE)
    groupes = {}
    for pose in (Intervention.objects
                 .filter(company_id=company_id, installation_id__in=list(ids),
                         type_intervention=Intervention.Type.POSE, annulee=False)
                 .select_related('technicien')):
        groupes.setdefault(pose.installation_id, []).append(pose)
    choix = {}
    for chantier_id, poses in groupes.items():
        ouvertes = [p for p in poses if p.statut not in finies]
        if ouvertes:
            choix[chantier_id] = min(ouvertes, key=lambda p: (
                p.date_prevue is None, p.date_prevue or datetime.date.max, p.pk))
        else:
            choix[chantier_id] = max(poses, key=lambda p: (
                p.date_prevue or datetime.date.min, p.pk))
    return choix


def acompte_exige_par_societe(company):
    """Le réglage société « acompte avant planification » est-il allumé ?"""
    if company is None:
        return False
    from apps.parametres.models import CompanyProfile
    return bool(getattr(CompanyProfile.lire(company),
                        'exiger_acompte_avant_planification', False))


def _acompte_paye(inst, company):
    from apps.ventes.selectors import acompte_paye_pour_devis
    return bool(inst.devis_id and acompte_paye_pour_devis(inst.devis_id, company))


class _Acomptes:
    """Lectures « acompte encaissé ? » d'une liste, bornées et mémorisées.
    Réglage éteint ou chantier sans devis : jamais bloqué, aucune lecture."""

    def __init__(self, company, budget=ACOMPTE_BUDGET):
        self.company, self.reste, self.vus = company, budget, {}
        self.exige = acompte_exige_par_societe(company)

    def bloque(self, inst):
        if not self.exige or not inst.devis_id:
            return False
        if inst.pk not in self.vus:
            if self.reste <= 0:
                return False
            self.reste -= 1
            self.vus[inst.pk] = not _acompte_paye(inst, self.company)
        return self.vus[inst.pk]


def blocages_du_chantier(inst, pose, aujourdhui, acompte_bloque):
    """Blocages GRATUITS d'un chantier pas encore posé (ensemble fermé
    :data:`BLOCAGES`, dans cet ordre) ; un chantier installé ou au-delà n'en a
    aucun."""
    from .models import Installation
    fin, _avant = _statuts()
    if Installation.canonical_statut(inst.statut) in fin:
        return []
    date_pose = inst.date_pose_prevue
    blocages = []
    if date_pose is None:
        blocages.append('sans_date')
    if not inst.technicien_responsable_id:
        blocages.append('sans_technicien')
    if date_pose is not None and (pose is None or pose.date_prevue is None):
        blocages.append('pose_sans_intervention')
    if date_pose is not None and (inst.date_pose_fin_prevue or date_pose) < aujourdhui:
        blocages.append('pose_depassee')
    if acompte_bloque:
        blocages.append('acompte_non_encaisse')
    return blocages


def a_faire(inst, blocages, nb_manques=0):
    """L'action suivante (ensemble fermé :data:`A_FAIRE`)."""
    from .models import Installation
    fin, _avant = _statuts()
    if inst.annule or Installation.canonical_statut(inst.statut) in fin:
        return 'rien'
    if nb_manques:
        return 'commander_materiel'
    if 'acompte_non_encaisse' in blocages:
        return 'encaisser_acompte'
    if {'sans_date', 'pose_sans_intervention', 'pose_depassee'} & set(blocages):
        return 'planifier_pose'
    if 'sans_technicien' in blocages:
        return 'assigner_technicien'
    return 'poser'


def _pose_ligne(pose):
    if pose is None:
        return None
    return {'id': pose.pk, 'date_prevue': _iso(pose.date_prevue),
            'technicien_nom': _nom(pose.technicien if pose.technicien_id else None)}


def ligne_chantier(inst, pose, blocages):
    """UNE ligne de ``assistant_chantiers.json`` (aussi celles du matin)."""
    from .models import Installation
    return {
        'id': inst.pk,
        'reference': inst.reference,
        'client_nom': _client_nom(inst),
        'statut': Installation.canonical_statut(inst.statut),
        'date_pose_prevue': _iso(inst.date_pose_prevue),
        'technicien_nom': _nom(inst.technicien_responsable
                               if inst.technicien_responsable_id else None),
        'pose_intervention': _pose_ligne(pose),
        'blocages': blocages,
        'a_faire': a_faire(inst, blocages),
        'lien': lien_chantier(inst.pk),
    }


def _q_bloque_sql(aujourdhui):
    """Chantier pas encore posé portant un blocage SQL (tout sauf l'acompte) ;
    suppose l'annotation ``fin_pose_assistant`` (fin prévue, sinon début)."""
    from .models import Intervention
    _fin, avant = _statuts()
    pose_datee = Intervention.objects.filter(
        installation_id=OuterRef('pk'), type_intervention=Intervention.Type.POSE,
        annulee=False, date_prevue__isnull=False)
    datee = Q(date_pose_prevue__isnull=False)
    return Q(statut__in=avant) & (
        Q(date_pose_prevue__isnull=True)
        | Q(technicien_responsable__isnull=True)
        | (datee & ~Exists(pose_datee))
        | (datee & Q(fin_pose_assistant__lt=aujourdhui)))


def _ordonner(qs):
    return qs.order_by(F('date_pose_prevue').asc(nulls_last=True), 'pk')


def _semaine(qs, debut):
    """Chantiers dont une pose est datée dans la semaine de ``debut`` (un
    lundi) OU dont la date de pose prévue y tombe."""
    from .models import Intervention
    fin = debut + datetime.timedelta(days=6)
    pose_semaine = Intervention.objects.filter(
        installation_id=OuterRef('pk'), type_intervention=Intervention.Type.POSE,
        annulee=False, date_prevue__range=(debut, fin))
    return qs.filter(Q(Exists(pose_semaine)) | Q(date_pose_prevue__range=(debut, fin)))


def _bloques(qs, limite, aujourdhui, acomptes):
    """(total, chantiers) des bloqués : blocages SQL d'abord, puis, réglage
    acompte allumé, les chantiers avec devis bloqués par le seul acompte
    (dans la limite des lectures restantes)."""
    _fin, avant = _statuts()
    sql = _ordonner(qs.filter(_q_bloque_sql(aujourdhui)))
    total = sql.count()
    chantiers = list(sql[:limite])
    for inst in chantiers:
        acomptes.bloque(inst)
    if acomptes.exige and acomptes.reste > 0:
        candidats = _ordonner(qs.filter(statut__in=avant, devis__isnull=False)
                              .exclude(pk__in=sql.values('pk')))
        seuls = [c for c in candidats[:acomptes.reste] if acomptes.bloque(c)]
        total += len(seuls)
        chantiers += seuls[:max(limite - len(chantiers), 0)]
    return total, chantiers


def liste_chantiers(base, company, *, vue='en_cours', q='', lead=None,
                    debut=None, limite=LIMITE_DEFAUT, aujourdhui=None):
    """Liste compacte (``assistant_chantiers.json``). ``base`` : chantiers
    DÉJÀ bornés à la société et à la portée de l'appelant ; annulés et
    clôturés exclus ici. ``debut`` (poses_semaine) : ramené au lundi."""
    from .models import Installation
    aujourdhui = aujourdhui or datetime.date.today()
    qs = (base.filter(annule=False).exclude(statut=Installation.Statut.CLOTURE)
          .annotate(fin_pose_assistant=Coalesce('date_pose_fin_prevue', 'date_pose_prevue')))
    if q:
        qs = qs.filter(Q(reference__icontains=q) | Q(client__nom__icontains=q)
                       | Q(client__prenom__icontains=q))
    if lead:
        qs = qs.filter(lead_id=lead)
    acomptes = _Acomptes(company)
    if vue == 'bloques':
        total, chantiers = _bloques(qs, limite, aujourdhui, acomptes)
    else:
        if vue == 'poses_semaine':
            lundi = debut or aujourdhui
            qs = _semaine(qs, lundi - datetime.timedelta(days=lundi.weekday()))
        qs = _ordonner(qs)
        total, chantiers = qs.count(), list(qs[:limite])
    poses = poses_par_chantier(getattr(company, 'pk', None), [c.pk for c in chantiers])
    lignes = [ligne_chantier(c, poses.get(c.pk), blocages_du_chantier(
        c, poses.get(c.pk), aujourdhui, acomptes.bloque(c))) for c in chantiers]
    return {
        'vue': vue,
        'total': total,
        'limite': limite,
        'lignes': lignes,
        'note': NOTE_LISTE,
        'lien': LIEN_LISTE,
    }


def _materiel(appro):
    """Quantités seulement (jamais un prix) : compteurs du résumé, BCF
    brouillons, et au plus :data:`MANQUES_MAX` lignes en manque."""
    resume = appro['resume']
    manques = [{'produit_id': li['produit_id'],
                'designation': (li['designation'] or '')[:DESIGNATION_MAX],
                'manque': li['manque']}
               for li in appro['lignes'] if li['manque'] > 0][:MANQUES_MAX]
    return {
        'nb_lignes': resume['nb_lignes'],
        'nb_manques': resume['nb_manques'],
        'nb_en_commande': resume['nb_en_commande'],
        'nb_recues': resume['nb_recues'],
        'bcf_brouillons': sum(1 for bon in appro['bons_commande']
                              if bon['statut'] == _BCF_BROUILLON),
        'manques': manques,
    }


def _planning(inst, pose):
    tech = inst.technicien_responsable if inst.technicien_responsable_id else None
    return {
        'date_pose_prevue': _iso(inst.date_pose_prevue),
        'date_pose_fin_prevue': _iso(inst.date_pose_fin_prevue),
        'technicien': {'id': tech.pk, 'nom': _nom(tech)} if tech else None,
        'intervention_pose': None if pose is None else {
            'id': pose.pk,
            'date_prevue': _iso(pose.date_prevue),
            'technicien_nom': _nom(pose.technicien if pose.technicien_id else None),
            'statut': pose.statut,
        },
    }


def _etapes(inst):
    """(étape courante, étape suivante et son gate) — ``(None, None)`` tant
    que la société n'a pas amorcé ses étapes (CH2)."""
    from .services import etape_courante, stage_gate_status, stages_actifs
    stages = stages_actifs(inst.company)
    if not stages:
        return None, None
    courante = etape_courante(inst)
    ids = [s.pk for s in stages]
    rang = ids.index(courante.pk) + 1 if courante is not None and courante.pk in ids else 0
    suivante = stages[rang] if rang < len(stages) else None
    prochaine = None
    if suivante is not None:
        gate = stage_gate_status(inst, suivante)
        prochaine = {'cle': gate['cle'],
                     'bloquante': bool(suivante.bloquant and not gate['satisfait']),
                     'raisons': list(gate['raisons'])}
    etape = {'cle': courante.cle, 'libelle': courante.libelle} if courante else None
    return etape, prochaine


def etat_acompte(inst):
    """``{exige, encaisse}`` : exigé = réglage société allumé ET devis lié."""
    exige = bool(inst.devis_id) and acompte_exige_par_societe(inst.company)
    return {'exige': exige, 'encaisse': _acompte_paye(inst, inst.company)}


def etat_chantier(inst, aujourdhui=None):
    """La fiche compacte d'UN chantier (``assistant_chantier_etat.json``) :
    prêt à poser et pourquoi (UN calcul du besoin matériel, via
    ``approvisionnement_chantier``), matériel en quantités, acompte, pose,
    étape suivante, ``a_faire`` et liens."""
    from .models import Installation
    from .selectors import approvisionnement_chantier
    aujourdhui = aujourdhui or datetime.date.today()
    appro = approvisionnement_chantier(inst)
    materiel = _materiel(appro)
    pose = poses_par_chantier(inst.company_id, [inst.pk]).get(inst.pk)
    acompte = etat_acompte(inst)
    blocages = blocages_du_chantier(
        inst, pose, aujourdhui, acompte['exige'] and not acompte['encaisse'])
    etape, prochaine = _etapes(inst)
    canon = Installation.canonical_statut(inst.statut)
    return {
        'id': inst.pk,
        'reference': inst.reference,
        'client_nom': _client_nom(inst),
        'statut': canon,
        'statut_libelle': dict(Installation.Statut.choices).get(canon, canon),
        'annule': bool(inst.annule),
        'etape_courante': etape,
        'planning': _planning(inst, pose),
        'pret_a_poser': bool(appro['resume']['pret_a_poser']),
        'raisons': list(appro['resume']['raisons']),
        'materiel': materiel,
        'acompte': acompte,
        'prochaine_etape': prochaine,
        'a_faire': a_faire(inst, blocages, materiel['nb_manques']),
        'lien': lien_chantier(inst.pk),
        'liens': {
            'chantier': lien_chantier(inst.pk),
            'approvisionnement': LIEN_APPRO,
            'intervention_pose': f'/interventions?id={pose.pk}' if pose else None,
        },
    }


def brief_chantiers(user, aujourdhui):
    """Bloc ``chantiers`` du point du matin (contrat
    ``crm/contract_samples/assistant_digest_matin.json``, ``vague2``) :
    ``{'bloques': {'total', 'lignes'}, 'poses_semaine': {'total', 'lignes'},
    'lien'}`` — chaque ligne EXACTEMENT une ligne de
    ``assistant_chantiers.json``, :data:`LIGNES_BRIEF` au plus par liste ;
    bloqués SANS le besoin matériel ; poses de la semaine de ``aujourdhui``.
    Portée de ``user`` (``chantiers_visibles``). ``None`` — la clé du matin est
    alors ABSENTE — sans société ou sans lecture du module installations
    (un lecteur entré par l'octroi ``ventes_voir`` compris, comme les
    libellés). L'interrupteur copilote reste la décision de l'appelant."""
    from authentication.permissions import peut_lire_module

    from .selectors import chantiers_visibles
    if (getattr(user, 'company_id', None) is None
            or not peut_lire_module(user, 'installations')):
        return None
    base = chantiers_visibles(user).select_related('client', 'technicien_responsable')
    bloques = liste_chantiers(base, user.company, vue='bloques',
                              limite=LIGNES_BRIEF, aujourdhui=aujourdhui)
    semaine = liste_chantiers(base, user.company, vue='poses_semaine',
                              limite=LIGNES_BRIEF, aujourdhui=aujourdhui)
    return {
        'bloques': {'total': bloques['total'], 'lignes': bloques['lignes']},
        'poses_semaine': {'total': semaine['total'], 'lignes': semaine['lignes']},
        'lien': LIEN_LISTE,
    }


# ── Suggestion de créneau : portée de l'utilisateur ─────────────────────────

def suggerer_creneau_visible(user, *, chantier_id, **criteres):
    """``selectors.suggerer_creneau`` pour un chantier que ``user`` peut voir.
    Un chantier hors de sa portée répond comme un chantier inconnu (aucune
    proposition, aucun indice d'existence, aucun planning d'une autre équipe)."""
    from . import selectors

    if not selectors.chantiers_visibles(user).filter(pk=chantier_id).exists():
        return {'chantier_id': chantier_id, 'propositions': []}
    return selectors.suggerer_creneau(user.company, chantier_id=chantier_id, **criteres)

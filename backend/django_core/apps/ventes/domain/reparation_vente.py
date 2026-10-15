"""Réparer un lead à PLUSIEURS ventes en vigueur (VNT47, D-VNT-4 / D-VNT-5).

Une vente en vigueur = un devis accepté, dernier accepté de sa chaîne de
révision (``selectors.devis_signes_en_vigueur``). Un lead n'en garde qu'UNE :
la commande ``reparer_vente_active`` appelle :func:`reparer_vente_active`,
qui applique DANS CET ORDRE (ordre vérifié R3-A) :

1. les saisies de paiement des factures à annuler sont annulées comme
   erreurs de saisie (``annuler_saisie_paiement``, AFAC17 / D-AFAC-C2) quand
   le paiement réellement reçu est donné ; un paiement déjà remis en banque
   reste et sa facture est annulée avec ``garder_en_avance`` (VNT12) ;
2. les factures vivantes des AUTRES ventes (et de la vente gardée quand
   l'acompte est refait) sont annulées PAR AVOIR (``annuler_facture``,
   VNT11) — jamais supprimées ;
3. chaque autre vente est dés-acceptée (``annuler_acceptation`` : chantier
   annulé, contrat SAV désactivé, commission gardée tant que la vente gardée
   est acceptée) puis ARCHIVÉE (``is_active`` faux, note « doublon de
   vente ») — jamais « refusée », jamais ``superseded_by``, signature gardée ;
4-5. l'acompte de la vente gardée est refait au montant tapé :
   ``facturer_vente(nature='acompte')`` écrit l'échéancier (VNT28) puis émet
   la facture et l'encaisse (VNT30 : avances gardées d'abord, complément).

Tout tient dans UNE transaction ; le DRY-RUN (défaut) la ROULE EN ARRIÈRE
(aucune écriture, aucun ``on_commit`` : 0 webhook, 0 mail). Toutes les
lectures sont bornées à ``company=lead.company`` ET ``lead=lead``. Règle #4 :
aucun statut de devis écrit hors des services existants.
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from core.money import quantize_mad

ZERO = Decimal('0')
MOTIF = 'réparation : doublon de vente'
DRAPEAU_ENVOYEE = '--avoir-meme-si-envoyee'


class ReparationRefusee(Exception):
    """Refus nommé : rien n'est écrit (``message`` en français)."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _mad(valeur):
    return f'{quantize_mad(Decimal(str(valeur or 0))):.2f}'


def montant_saisi(brut, nom):
    """Un montant MAD > 0 tapé en ligne de commande (virgule acceptée)."""
    try:
        valeur = Decimal(str(brut).strip().replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ReparationRefusee(f'{nom} invalide : « {brut} ».')
    if not valeur.is_finite() or valeur <= 0:
        raise ReparationRefusee(f'{nom} invalide : « {brut} ».')
    return quantize_mad(valeur)


# ── Lectures ─────────────────────────────────────────────────────────────────

def ventes_en_vigueur(company, lead_id):
    """Les ventes en vigueur du lead (devis, triés par pk), société bornée."""
    from ..selectors import devis_signes_en_vigueur
    return list(devis_signes_en_vigueur(company, lead_ids=[lead_id])
                .select_related('company', 'lead').order_by('pk'))


def _resume_vente(devis):
    """Une vente pour ``--lister`` : chaîne, prix, factures vivantes, BC."""
    from ..models import BonCommande
    from ..utils.options import option_totaux
    from ..vente_facturation import chaine_vente, factures_de_la_vente
    chaine = chaine_vente(devis)
    bcs = (BonCommande.objects.filter(
        company_id=devis.company_id, devis_id__in=[d.pk for d in chaine])
        .exclude(statut=BonCommande.Statut.ANNULE).order_by('pk'))
    return {
        'id': devis.pk, 'reference': devis.reference,
        'version': devis.version, 'ttc': _mad(option_totaux(devis)['ttc']),
        'date_acceptation': devis.date_acceptation,
        'chaine': [d.reference for d in chaine],
        'factures': [f'{f.reference} {f.statut} {_mad(f.total_ttc)}'
                     for f in factures_de_la_vente(devis)],
        'bons_commande': [bc.reference for bc in bcs],
    }


def leads_a_ventes_multiples(company=None):
    """Les leads ayant > 1 vente en vigueur (``company=None`` : toutes les
    sociétés), triés par (société, lead) — ce que Reda lance d'abord."""
    from ..selectors import devis_signes_en_vigueur
    groupes = {}
    for d in (devis_signes_en_vigueur(company).filter(lead__isnull=False)
              .select_related('company', 'lead').order_by('pk')):
        groupes.setdefault((d.company_id, d.lead_id), []).append(d)
    sortie = []
    for (company_id, lead_id), ventes in sorted(groupes.items()):
        if len(ventes) < 2:
            continue
        sortie.append({'company': ventes[0].company, 'lead_id': lead_id,
                       'lead': str(ventes[0].lead),
                       'ventes': [_resume_vente(v) for v in ventes]})
    return sortie


def _lignes_factures(company_id, lead_id):
    from ..models import Facture
    lignes = []
    factures = (Facture.objects.filter(company_id=company_id)
                .filter(Q(devis__lead_id=lead_id) | Q(lead_id=lead_id))
                .distinct().order_by('pk')
                .prefetch_related('paiements', 'avoirs'))
    for f in factures:
        lignes.append(f'facture {f.reference} ({f.type_facture}) {f.statut} '
                      f'TTC {_mad(f.total_ttc)} payé {_mad(f.montant_paye)}')
        for p in sorted(f.paiements.all(), key=lambda p: p.pk):
            lignes.append(f'  paiement #{p.pk} {_mad(p.montant)} {p.mode} '
                          f'{p.date_paiement} {p.statut}')
        for a in sorted(f.avoirs.all(), key=lambda a: a.pk):
            lignes.append(f'  avoir {a.reference} ({a.type}) {a.statut} '
                          f'{_mad(a.total_ttc)}')
    return lignes


def _lignes_avances(company_id, client_ids):
    from ..models import Paiement
    avances = (Paiement.objects.filter(company_id=company_id,
                                       facture__isnull=True,
                                       client_id__in=client_ids)
               .order_by('pk'))
    return [f'avance #{p.pk} {_mad(p.montant)} {p.mode} {p.date_paiement} '
            f'{p.statut} disponible {_mad(p.montant_disponible)}'
            for p in avances]


def _lignes_vente_gardee(garde):
    from ..vente_facturation import etat_vente
    garde.refresh_from_db()
    echeancier = garde.echeancier or 'conditions de la société'
    etat = etat_vente(garde)
    lignes = [f'échéancier {garde.reference} : {echeancier}',
              f"vente {garde.reference} : prix {etat['prix_convenu_ttc']} "
              f"émis {etat['emis_ttc']} payé {etat['paye_ttc']} reste à "
              f"facturer {etat['reste_a_facturer_ttc']}"]
    lignes += [f"  prochaine échéance {e['libelle']} {e['montant_ttc']}"
               for e in etat['prochaines_echeances']]
    return lignes


def photographier(company, lead_id, garde):
    """L'état lisible du lead (lignes de texte) : devis, ventes en vigueur,
    factures + paiements + avoirs, avances, échéancier, ``etat_vente``."""
    from ..models import Devis
    from ..utils.options import option_totaux
    vigueur = {d.pk for d in ventes_en_vigueur(company, lead_id)}
    lignes = []
    devis = list(Devis.objects.filter(company=company, lead_id=lead_id)
                 .order_by('pk'))
    for d in devis:
        lignes.append(
            f'devis {d.reference} (id {d.pk}) V{d.version} {d.statut} '
            f"actif={'oui' if d.is_active else 'non'} "
            f'remplacé_par={d.superseded_by_id or "-"} '
            f"TTC {_mad(option_totaux(d)['ttc'])}"
            + (' — VENTE EN VIGUEUR' if d.pk in vigueur else ''))
    lignes += _lignes_factures(company.pk, lead_id)
    clients = {d.client_id for d in devis if d.client_id}
    lignes += _lignes_avances(company.pk, clients)
    return lignes + _lignes_vente_gardee(garde)


# ── Contrôles (avant toute écriture) ─────────────────────────────────────────

def _factures_cibles(vente):
    """Les factures VIVANTES de la vente (toute la chaîne) ; une consolidée
    (devis hors chaîne) est refusée : elle porte d'autres ventes."""
    from ..vente_facturation import chaine_vente, factures_de_la_vente
    ids = {d.pk for d in chaine_vente(vente)}
    factures = factures_de_la_vente(vente)
    hors = [f.reference for f in factures if f.devis_id not in ids]
    if hors:
        raise ReparationRefusee(
            f"Facture consolidée {', '.join(hors)} sur la vente "
            f'{vente.reference} : elle porte d\'autres ventes, traitez-la à '
            'la main.')
    return factures


def _controler_autre(autre, garde):
    """Refus nommés : variante du même groupe, BC non annulé."""
    from ..models import BonCommande
    from ..selectors import racine_groupe
    from ..vente_facturation import chaine_vente
    if racine_groupe(autre).pk == racine_groupe(garde).pk:
        raise ReparationRefusee(
            f'{autre.reference} et {garde.reference} sont deux variantes du '
            'même groupe : choisissez la variante par l\'acceptation, pas '
            'par cette commande.')
    bc = (BonCommande.objects.filter(
        company_id=autre.company_id,
        devis_id__in=[d.pk for d in chaine_vente(autre)])
        .exclude(statut=BonCommande.Statut.ANNULE).order_by('pk').first())
    if bc is not None:
        raise ReparationRefusee(
            f'Le bon de commande {bc.reference} de {autre.reference} n\'est '
            "pas annulé : annulez-le d'abord.")


def _envoyee(facture):
    """Vrai si la facture est partie chez le client : e-mail sortant envoyé
    ou lien de partage déjà consulté."""
    from ..models import EmailLog, ShareLink
    if EmailLog.objects.filter(
            company_id=facture.company_id, facture_id=facture.pk,
            direction=EmailLog.Direction.SORTANT,
            statut=EmailLog.Statut.ENVOYE).exists():
        return True
    return ShareLink.objects.filter(
        company_id=facture.company_id, facture_id=facture.pk).filter(
        Q(first_viewed_at__isnull=False) | Q(view_count__gt=0)).exists()


def _controler_envois(factures, avoir_meme_si_envoyee):
    envoyees = [f.reference for f in factures if _envoyee(f)]
    if envoyees and not avoir_meme_si_envoyee:
        raise ReparationRefusee(
            f"Facture envoyée au client ({', '.join(envoyees)}) : son "
            'annulation passe par un avoir que le client verra. Confirmez '
            f'avec {DRAPEAU_ENVOYEE}.')


def preparer(*, lead_id, garder_id, acompte=None, paiement=None,
             avoir_meme_si_envoyee=False):
    """Lit et contrôle la réparation ; rend le plan (ou ``None`` si le lead
    n'a déjà qu'une vente en vigueur : no-op). Lève ``ReparationRefusee``."""
    from ..models import Devis
    garde = (Devis.objects.select_related('company', 'lead')
             .filter(pk=garder_id, lead_id=lead_id).first())
    if garde is None:
        raise ReparationRefusee(
            f'Le devis {garder_id} n\'appartient pas au lead {lead_id}.')
    if paiement is not None and acompte is None:
        raise ReparationRefusee(
            'Le paiement reçu se donne avec --refaire-acompte.')
    if paiement is not None and paiement['montant'] > acompte:
        raise ReparationRefusee(
            "Le paiement reçu dépasse l'acompte à refaire.")
    ventes = ventes_en_vigueur(garde.company, lead_id)
    if garde.pk not in {v.pk for v in ventes}:
        raise ReparationRefusee(
            f'{garde.reference} n\'est pas une vente en vigueur du lead '
            f'{lead_id} : choisissez-en une avec --lister.')
    autres = [v for v in ventes if v.pk != garde.pk]
    if not autres:
        return None
    cibles = []
    for autre in autres:
        _controler_autre(autre, garde)
        cibles += _factures_cibles(autre)
    if acompte is not None:
        cibles += _factures_cibles(garde)
    _controler_envois(cibles, avoir_meme_si_envoyee)
    return {'garde': garde, 'autres': autres, 'factures': cibles,
            'acompte': acompte, 'paiement': paiement}


# ── Écritures (dans la transaction de :func:`reparer_vente_active`) ─────────

def _annuler_saisies(plan, user, etapes):
    """(1) Les saisies comptées des factures à annuler sont annulées comme
    erreurs de saisie ; un paiement remis en banque reste (repli VNT12)."""
    from ..models import Paiement
    from .encaissements import (
        CorrectionPaiementRefusee, annuler_saisie_paiement)
    recu = plan['paiement']
    if recu is None:
        return
    for f in plan['factures']:
        for p in f.paiements.order_by('pk'):
            if p.statut in Paiement.STATUTS_NON_COMPTES or p.montant <= 0:
                continue
            motif = (f'saisi {_mad(p.montant)} ≠ {recu["mode"]} reçu '
                     f'{_mad(recu["montant"])} — {MOTIF}')
            try:
                annuler_saisie_paiement(paiement=p, motif=motif, user=user)
            except CorrectionPaiementRefusee as exc:
                if exc.code != 'paiement_remis_en_banque':
                    raise ReparationRefusee(exc.detail)
                etapes.append(f'(1) paiement #{p.pk} remis en banque : gardé '
                              'en avance à l\'annulation de '
                              f'{f.reference}')
                continue
            etapes.append(f'(1) saisie #{p.pk} {_mad(p.montant)} annulée '
                          f'sur {f.reference} ({motif})')


def _annuler_factures(plan, user, etapes):
    """(2) Chaque facture vivante est annulée par avoir ; l'argent encore
    porté devient une avance client. Rend le total gardé en avance."""
    from ..models import Facture
    from .annulation_facture import (
        GARDER_EN_AVANCE, AnnulationRefusee, annuler_facture)
    garde = plan['garde']
    avances = ZERO
    for f in plan['factures']:
        f = Facture.objects.get(pk=f.pk, company_id=garde.company_id)
        paye = Decimal(str(f.montant_paye))
        directive = {'action': GARDER_EN_AVANCE} if paye > 0 else None
        try:
            f = annuler_facture(
                f, user=user, directive=directive,
                motif=f'Annulation de {f.reference} — {MOTIF} '
                      f'(vente gardée {garde.reference})')
        except AnnulationRefusee as exc:
            raise ReparationRefusee(
                f"{f.reference} : {exc.corps.get('detail', '')}")
        avoir = getattr(f, 'avoir_annulation', None)
        etapes.append(
            f'(2) {f.reference} annulée'
            + (f' par l\'avoir {avoir.reference}' if avoir else '')
            + (f' — {_mad(paye)} gardés en avance' if paye > 0 else ''))
        avances += paye if paye > 0 else ZERO
    return avances


def _archiver_autres(plan, user, etapes):
    """(3) Dés-acceptation (effets défaits) puis archivage de chaque autre
    vente ; jamais « refusé », jamais ``superseded_by``."""
    from .. import activity
    from ..models import Devis
    from .cycle_vie import AnnulationAcceptationBloquee, annuler_acceptation
    garde = plan['garde']
    for autre in plan['autres']:
        motif = f'{MOTIF} — vente gardée {garde.reference}'
        try:
            annuler_acceptation(devis=autre, user=user, motif=motif)
        except AnnulationAcceptationBloquee as exc:
            raise ReparationRefusee(
                f'{autre.reference} : dés-acceptation impossible — '
                f'{exc.message}')
        Devis.objects.filter(pk=autre.pk, company_id=garde.company_id
                             ).update(is_active=False)
        activity.log_devis_note(
            autre, user,
            f'Archivé — {MOTIF} : la vente en vigueur du lead est '
            f'{garde.reference}. La preuve de signature est conservée.')
        etapes.append(f'(3) {autre.reference} dés-acceptée et archivée')


def _refaire_acompte(plan, user, avances, etapes):
    """(4)(5) Échéancier écrit puis acompte émis et encaissé (VNT28/VNT30) :
    avances gardées d'abord, complément = paiement reçu − avances."""
    from .facturation_vente import FacturationVenteRefusee, facturer_vente
    acompte, recu = plan['acompte'], plan['paiement']
    saisis = []
    if recu is not None and recu['montant'] - avances > 0:
        saisis = [{'montant': str(recu['montant'] - avances),
                   'date_paiement': recu['date'].isoformat(),
                   'mode_paiement': recu['mode'],
                   'reference': recu.get('reference') or ''}]
    try:
        facture, crees = facturer_vente(
            plan['garde'], nature='acompte', user=user,
            montant_ttc=str(acompte), emettre=True, paiements=saisis,
            utiliser_avances=avances > 0)
    except FacturationVenteRefusee as exc:
        raise ReparationRefusee(
            f"Acompte refusé : {exc.corps.get('detail', '')}")
    etapes.append(f'(4) échéancier de {plan["garde"].reference} écrit '
                  f'(acompte {_mad(acompte)} MAD)')
    etapes.append(
        f'(5) {facture.reference} émise {_mad(facture.total_ttc)} TTC '
        f'(HT {_mad(facture.montant_ht)} / TVA {_mad(facture.montant_tva)}),'
        f' {len(crees)} paiement(s) saisi(s), statut {facture.statut}')


def _verifier_cible(plan):
    """Post-condition : la vente gardée est la SEULE en vigueur du lead."""
    garde = plan['garde']
    restantes = [v.reference for v in
                 ventes_en_vigueur(garde.company, garde.lead_id)]
    if restantes != [garde.reference]:
        raise ReparationRefusee(
            'Après réparation, ventes encore en vigueur : '
            f"{', '.join(restantes)} — rien n'est écrit.")


def _executer(plan, user):
    etapes = []
    _annuler_saisies(plan, user, etapes)
    avances = _annuler_factures(plan, user, etapes)
    _archiver_autres(plan, user, etapes)
    if plan['acompte'] is not None:
        _refaire_acompte(plan, user, avances, etapes)
    _verifier_cible(plan)
    from .. import activity
    activity.log_devis_note(
        plan['garde'], user,
        f"Réparation — {MOTIF} : {', '.join(a.reference for a in plan['autres'])}"
        ' archivée(s) ; cette vente est la seule en vigueur du lead.')
    return etapes


def reparer_vente_active(*, lead_id, garder_id, user, acompte=None,
                         paiement=None, avoir_meme_si_envoyee=False,
                         appliquer=False):
    """Rend ``{statut, message, etapes, avant, apres}`` ; ``statut`` ∈
    ``rien_a_faire`` | ``dry_run`` | ``applique``. DRY-RUN : la transaction
    est roulée en arrière (rien n'est écrit, aucun ``on_commit``)."""
    plan = preparer(lead_id=lead_id, garder_id=garder_id, acompte=acompte,
                    paiement=paiement,
                    avoir_meme_si_envoyee=avoir_meme_si_envoyee)
    if plan is None:
        return {'statut': 'rien_a_faire', 'etapes': [], 'avant': [],
                'apres': [],
                'message': (f'Rien à réparer : le devis {garder_id} est déjà '
                            f'la seule vente en vigueur du lead {lead_id}.')}
    garde = plan['garde']
    if user is None or (user.company_id != garde.company_id
                        and not user.is_superuser):
        raise ReparationRefusee(
            "L'utilisateur doit appartenir à la société du lead.")
    with transaction.atomic():
        avant = photographier(garde.company, lead_id, garde)
        etapes = _executer(plan, user)
        apres = photographier(garde.company, lead_id, garde)
        if not appliquer:
            transaction.set_rollback(True)
    return {'statut': 'applique' if appliquer else 'dry_run',
            'etapes': etapes, 'avant': avant, 'apres': apres,
            'message': ('Réparation appliquée.' if appliquer else
                        'DRY-RUN : rien n\'a été écrit (relancez avec '
                        '--appliquer).')}

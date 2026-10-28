"""Facturer la vente — LE point d'écriture devis → facture (Groupe VNT).

VNT26 — ``facturer_vente(devis, *, nature, user, …)`` : UN service qui sait
la nature de la facture (``acompte`` | ``intermediaire`` | ``solde`` |
``complete``, l'énumération ``Facture.TypeFacture``) et un montant libre
(contrat ``contract_samples/devis_facturer.json``). Toute facture naît
BROUILLON (« BROUILLON-<id> », D-VNT-1) depuis ``plan_facturation`` (LA
lecture de la vente, ``vente_facturation.py``) : aucun numéro consommé,
aucune sortie de stock (elle suit l'ÉMISSION, VNT21) ; « une vente se
facture une fois » est tenu à l'émission (VNT20).

Refus : :class:`FacturationVenteRefusee` porte ``corps`` (``{detail, code,
…}`` au format du contrat — 409 ``version_remplacee`` de VNT24 repris tel
quel) et ``status`` (400 / 409) ; la vue les rend sans les reformuler.

Propriétaire : facturation (J5). Aucun import de ``stock`` / ``crm`` /
``installations`` / ``sav`` ``.models`` (ADEV71) ; chaque lecture est bornée
à ``company=devis.company_id`` ; jamais ré-exporté par
``apps.facturation.services``. Règle #4 : aucun statut de devis écrit.
"""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import transaction

#: Les natures d'une facture de vente (``Facture.TypeFacture``).
NATURES = ('acompte', 'intermediaire', 'solde', 'complete')
CENT = Decimal('0.01')


class FacturationVenteRefusee(Exception):
    """Refus de « Facturer la vente » : ``corps`` = ``{detail, code, …}``
    (contrat ``devis_facturer.json``), ``status`` = 400 / 403 / 409."""

    def __init__(self, detail, *, code=None, status=400, **extra):
        super().__init__(detail)
        self.status = status
        self.corps = {'detail': detail}
        if code:
            self.corps['code'] = code
        self.corps.update(extra)


def _q(valeur):
    return Decimal(str(valeur)).quantize(CENT, rounding=ROUND_HALF_UP)


def _conflit(code, detail, **extra):
    return FacturationVenteRefusee(detail, code=code, status=409, **extra)


def _exiger_vente_en_jeu(devis):
    """409 hors devis accepté (état du document) ; 409 ``version_remplacee`` (corps unique de
    VNT24, tête de chaîne en ``successeur``) pour une version inactive."""
    if devis.statut != 'accepte':
        raise FacturationVenteRefusee(
            'Seul un devis accepté se facture : ce devis est au statut '
            f'« {devis.get_statut_display()} ».', status=409)
    if not devis.is_active:
        from .modifiabilite import corps_version_remplacee
        corps = corps_version_remplacee(devis)
        raise _conflit(corps['code'], corps['detail'],
                       successeur=corps['successeur'])


def _montant_demande(prix_ttc, montant_ttc, pourcentage):
    """Le TTC demandé (``montant_ttc`` XOR ``pourcentage`` du prix convenu),
    ``None`` si aucun ; 400 ``montant_invalide`` sinon."""
    if montant_ttc in (None, '') and pourcentage in (None, ''):
        return None
    if montant_ttc not in (None, '') and pourcentage not in (None, ''):
        raise FacturationVenteRefusee(
            'Montant invalide : donnez un montant OU un pourcentage.',
            code='montant_invalide')
    try:
        brut = Decimal(str(montant_ttc if montant_ttc not in (None, '')
                           else pourcentage).replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise FacturationVenteRefusee('Montant invalide.',
                                      code='montant_invalide')
    if not brut.is_finite() or brut <= 0 or (
            montant_ttc in (None, '') and brut > 100):
        raise FacturationVenteRefusee('Montant invalide.',
                                      code='montant_invalide')
    return _q(brut if montant_ttc not in (None, '')
              else Decimal(str(prix_ttc)) * brut / 100)


def _facture_du_plan(plan, facture_id):
    return next((f for f, _r in plan['factures_parts']
                 if f.pk == facture_id), None)


def _tranche_cible(plan, nature, cle_attendue):
    """La tranche à facturer (``plan['prochaine']``) — refus nommés : 409
    ``tranche_deja_creee`` (la clé attendue est déjà couverte),
    ``tranche_en_brouillon`` (une tranche ANTÉRIEURE attend son émission),
    ``cle_inattendue`` (le plan a changé) ; 400 ``rien_a_facturer``."""
    tranches = plan['tranches']
    if cle_attendue and any(t['cle'] == cle_attendue
                            and t['statut'] != 'a_faire' for t in tranches):
        raise _conflit('tranche_deja_creee',
                       'Cette tranche est déjà facturée.')
    prochaine = plan['prochaine']
    if prochaine is None:
        raise FacturationVenteRefusee(
            "Il n'y a plus rien à facturer sur cette vente.",
            code='rien_a_facturer')
    avant = tranches[:tranches.index(prochaine)]
    brouillon = next((t for t in avant if t['statut'] == 'brouillon'), None)
    if brouillon is not None:
        f = _facture_du_plan(plan, brouillon['facture_id'])
        raise _conflit(
            'tranche_en_brouillon',
            f"La tranche « {brouillon['libelle']} » est encore en brouillon "
            ': émettez-la avant de facturer la suivante.',
            facture={'id': brouillon['facture_id'],
                     'reference': getattr(f, 'reference', '')})
    if (cle_attendue and cle_attendue != prochaine['cle']) \
            or str(prochaine['type']) != nature:
        raise _conflit('cle_inattendue',
                       'Le plan a changé : rechargez avant de facturer.',
                       cle_attendue=prochaine['cle'])
    return prochaine


def _paniers(devis):
    from apps.ventes.utils.options import option_totaux
    return [{'taux': b['taux'], 'base_ht': b['base_ht'],
             'montant': b['montant']}
            for b in (option_totaux(devis).get('tva_par_taux') or [])]


def montants_au_prorata(devis, plan, ttc):
    """(ht, tva, ventilation) d'un TTC libre au prorata du prix convenu (la
    formule de ``plan_facturation`` pour une tranche à faire) : HT =
    q(HT convenu × TTC / TTC convenu), TVA = TTC − HT, ventilation par taux
    au centime (``ventilation_document_fige``, None à un seul taux)."""
    prix = plan['prix_convenu_ttc']
    ht = _q(plan['prix_convenu_ht'] * (ttc / prix)) if prix > 0 else ttc
    tva = ttc - ht
    paniers = _paniers(devis)
    if len(paniers) < 2:
        return ht, tva, None
    from apps.facturation.totaux import ventilation_document_fige
    return ht, tva, ventilation_document_fige(paniers, ttc=ttc, ht=ht,
                                              tva=tva)


def _tranche_au_montant(devis, plan, tranche, ttc):
    """La tranche du plan portée à ``ttc`` (montant tapé, D-VNT-3) : la
    DERNIÈRE vaut le reste exact ; aucune ne dépasse le reste à facturer."""
    if ttc is None or ttc == tranche['montant_ttc']:
        return tranche
    if tranche['is_last']:
        raise FacturationVenteRefusee(
            f"La dernière tranche vaut le reste : {tranche['montant_ttc']} "
            'MAD.', code='montant_invalide')
    if ttc > plan['reste_a_facturer']:
        raise FacturationVenteRefusee(
            'Le montant dépasse le reste à facturer.',
            code='montant_depasse_reste')
    ht, tva, vent = montants_au_prorata(devis, plan, ttc)
    prix = plan['prix_convenu_ttc']
    return dict(tranche, montant_ttc=ttc, ht=ht, tva=tva,
                ventilation_tva=vent,
                pourcentage=_q(ttc / prix * 100) if prix > 0 else tranche[
                    'pourcentage'])


def _revue_initiale(devis, user):
    """XFAC18 — revue active et créateur hors palier responsable/admin ⇒ la
    facture naît « à valider » (même règle que ``FactureViewSet``)."""
    from apps.parametres.models import CompanyProfile
    from apps.ventes.models import Facture
    from authentication.models import CustomUser
    profil = CompanyProfile.get(company=devis.company)
    if getattr(profil, 'revue_factures_active', False) and getattr(
            user, 'menu_tier', None) not in (CustomUser.ROLE_ADMIN,
                                             CustomUser.ROLE_RESPONSABLE):
        return {'revue_statut': Facture.RevueStatut.A_VALIDER}
    return {}


def _inserer_facture(**champs):
    """LA porte ``Facture.objects.create`` du module (PA4)."""
    from apps.ventes.models import Facture
    return Facture.objects.create(**champs)


def _champs_tranche(devis, tranche, user, libelle):
    """Champs d'un brouillon de tranche : en-tête du devis (retenue, réf.
    client — ATOT4), destinataire (tiers payeur CIQ213), échéance déclarée
    (CIQ212), montants et ventilation du plan, clé de tranche (ATOT5)."""
    from apps.ventes.models import Facture
    from apps.ventes.utils.echeancier import blended_tva_pct, libelle_tranche
    from .facturation_ops import entete_facture_depuis_devis
    destinataire = devis.client
    if tranche.get('payeur') == 'tiers':
        destinataire = getattr(devis, 'tiers_payeur', None)
        if destinataire is None:
            raise FacturationVenteRefusee(
                'Cette tranche est réglée par un organisme financeur : '
                'renseignez le tiers payeur du devis avant de la facturer.')
    champs = entete_facture_depuis_devis(devis, ttc=tranche['montant_ttc'])
    champs.pop('taux_tva', None)
    if tranche.get('delai_reglement_jours') is not None:
        from datetime import timedelta
        from django.utils import timezone
        champs['date_echeance'] = timezone.localdate() + timedelta(
            days=int(tranche['delai_reglement_jours']))
    champs.update(_revue_initiale(devis, user))
    champs.update(
        devis=devis, client=destinataire, company_id=devis.company_id,
        statut=Facture.Statut.BROUILLON, type_facture=tranche['type'],
        pourcentage=tranche['pourcentage'],
        libelle=libelle or libelle_tranche(tranche),
        montant_ht=tranche['ht'], montant_tva=tranche['tva'],
        montant_ttc=tranche['montant_ttc'], taux_tva=blended_tva_pct(devis),
        ventilation_tva=tranche['ventilation_tva'],
        cle_tranche=tranche['cle'], created_by=user)
    return champs


def creer_brouillon_tranche(devis, tranche, user, libelle=None):
    """Crée le BROUILLON « BROUILLON-<id> » de ``tranche`` (jamais émis).

    VNT27 — l'INSERT vit dans un savepoint : deux requêtes qui ont lu le
    même plan heurtent ``uq_facture_tranche_vivante`` (devis, clé) ; la
    seconde rend 409 ``tranche_deja_creee``, jamais un 500."""
    from django.db import IntegrityError

    from apps.ventes.utils.company_settings import create_provisoire
    champs = _champs_tranche(devis, tranche, user, libelle)
    try:
        with transaction.atomic():
            return create_provisoire(
                lambda ref: _inserer_facture(reference=ref, **champs))
    except IntegrityError:
        raise _conflit('tranche_deja_creee',
                       'Cette tranche est déjà facturée.')


def verrouiller_vente(devis):
    """VNT27 — verrou ordonné (pk croissant, ``of=('self',)``) sur la
    RACINE de la chaîne ET la version facturée : ``reviser_devis`` verrouille
    la version, ``accept_devis`` la racine — un geste concurrent attend ici
    au lieu de passer entre la lecture de ``is_active`` et l'INSERT. Rend
    les devis verrouillés (relus en base), triés par pk. À appeler dans une
    transaction."""
    from django.db.models import Q

    from apps.ventes.models import Devis
    from apps.ventes.vente_facturation import chaine_vente
    racine = chaine_vente(devis)[0]
    return list(Devis.objects.select_for_update(of=('self',))
                .filter(company_id=devis.company_id)
                .filter(Q(pk=racine.pk) | Q(pk=devis.pk)).order_by('pk'))


def _facturer_tranche(devis, plan, nature, *, user, montant, cle_attendue,
                      libelle):
    """Natures ``intermediaire`` / ``solde`` : la prochaine tranche du plan."""
    tranche = _tranche_cible(plan, nature, cle_attendue)
    tranche = _tranche_au_montant(devis, plan, tranche, montant)
    return creer_brouillon_tranche(devis, tranche, user, libelle)


# ── VNT28 — l'acompte libre (D-VNT-3, arbitrage 9) ───────────────────────────

def _entrees_echeancier(devis):
    """Les entrées STOCKÉES de l'échéancier (copies) ; à défaut (aucun
    échéancier propre exploitable) celles des conditions du jour, à la forme
    de ``figer_echeancier``."""
    from apps.ventes.utils.echeancier import (
        UNITE_PCT, EcheancierInvalide, tranches_normalisees,
        valider_echeancier)
    propre = devis.echeancier
    if isinstance(propre, list) and propre:
        try:
            if valider_echeancier(propre, controler_somme=False):
                return [dict(e) for e in propre]
        except EcheancierInvalide:
            pass
    entrees = []
    for t in tranches_normalisees(devis):
        entree = {'type': t['key'], 'libelle': t['libelle'],
                  'pct_or_montant': float(t['valeur']),
                  'unite': t.get('unite') or UNITE_PCT}
        if t.get('jalon'):
            entree['jalon'] = t['jalon']
        entrees.append(entree)
    return entrees


def _placer_acompte(entrees, plan, montant, cle_attendue):
    """Pose l'acompte ``montant`` (MAD) dans ``entrees`` ; rend son rang.
    Acompte à faire / en brouillon : sa tranche passe en MAD. Acompte ÉMIS :
    une tranche ``acompte#n`` est insérée après lui, seulement si
    ``cle_attendue`` la nomme (jamais tant que l'acompte n'est pas émis)."""
    from apps.ventes.utils.echeancier import (
        UNITE_MONTANT, cles_tranches, valider_echeancier)
    acomptes = [i for i, t in enumerate(plan['tranches'])
                if str(t['type']) == 'acompte']
    k = acomptes[-1] if acomptes else None
    neuve = {'type': 'acompte', 'libelle': 'Acompte',
             'unite': UNITE_MONTANT, 'pct_or_montant': float(montant)}
    if k is None or plan['tranches'][k]['statut'] == 'emise':
        rang = 0 if k is None else k + 1
        entrees.insert(rang, neuve)
        cle = cles_tranches(valider_echeancier(
            entrees, controler_somme=False))[rang]
        if k is not None and cle_attendue != cle:
            raise _conflit(
                'tranche_deja_creee',
                "L'acompte est déjà émis : un acompte supplémentaire se "
                f'demande sous la clé « {cle} ».')
    else:
        rang = k
        if cle_attendue and cle_attendue != plan['tranches'][k]['cle']:
            raise _conflit('cle_inattendue',
                           'Le plan a changé : rechargez avant de facturer.',
                           cle_attendue=plan['tranches'][k]['cle'])
        entrees[k] = dict(entrees[k], unite=UNITE_MONTANT,
                          pct_or_montant=float(montant))
    if rang == len(entrees) - 1:
        entrees.append({'type': 'solde', 'libelle': 'Solde',
                        'unite': UNITE_MONTANT, 'pct_or_montant': 0})
    return rang


def ecrire_echeancier_depuis_acompte(devis, montant, *, user=None,
                                     plan=None, cle_attendue=None):
    """L'ÉCRIVAIN UNIQUE de l'échéancier par l'acompte libre (D-VNT-3,
    arbitrage 9 ; VNT67 le réutilise) : [acompte A en MAD, intermédiaires
    en % inchangées, dernière = reste en MAD] (Σ = TTC), même sur un devis
    ACCEPTÉ, contrôlé par ``controler_echeancier_vente`` (VNT25 : tranches
    émises intouchées) et tracé « Corrigé après acceptation ». Rend la clé
    de la tranche d'acompte."""
    from apps.ventes.models import Devis
    from apps.ventes.utils.echeancier import cles_tranches, valider_echeancier
    from apps.ventes.vente_facturation import plan_facturation
    from .modifiabilite import (
        EcheancierRefuse, consigner_correction_apres_envoi,
        controler_echeancier_vente)
    plan = plan or plan_facturation(devis)
    avant = devis.echeancier
    entrees = _entrees_echeancier(devis)
    rang = _placer_acompte(entrees, plan, montant, cle_attendue)
    try:
        entrees = controler_echeancier_vente(devis, entrees,
                                             figer_brouillons=False)
    except EcheancierRefuse as exc:
        corps = exc.corps()
        raise FacturationVenteRefusee(corps.pop('detail'), status=exc.status,
                                      **corps)
    if entrees != avant:
        Devis.objects.filter(pk=devis.pk, company_id=devis.company_id
                             ).update(echeancier=entrees)
        devis.echeancier = entrees
        consigner_correction_apres_envoi(
            devis, user=user, objet='echeancier',
            resume=f'échéancier — acompte {_q(montant)} MAD',
            apres_acceptation=True)
    return cles_tranches(valider_echeancier(
        entrees, controler_somme=False))[rang]


def _editer_brouillon(facture, tranche, user, libelle):
    """Le brouillon d'acompte existant prend le nouveau montant (AMET4 :
    jamais un second brouillon) ; chatter « Montant modifié »."""
    from apps.ventes.models import FactureActivity
    from apps.ventes.utils.echeancier import libelle_tranche
    from .facturation_ops import entete_facture_depuis_devis
    if facture.lignes.exists():
        raise _conflit(
            'tranche_en_brouillon',
            "Le brouillon d'acompte porte des lignes : modifiez-le depuis "
            'la facture.',
            facture={'id': facture.pk, 'reference': facture.reference})
    ancien = facture.total_ttc
    entete = entete_facture_depuis_devis(facture.devis,
                                         ttc=tranche['montant_ttc'])
    for champ in ('retenue_garantie_mad', 'conditions_paiement'):
        if champ in entete:
            setattr(facture, champ, entete[champ])
    facture.montant_ttc = tranche['montant_ttc']
    facture.montant_ht, facture.montant_tva = tranche['ht'], tranche['tva']
    facture.ventilation_tva = tranche['ventilation_tva']
    facture.pourcentage = tranche['pourcentage']
    facture.libelle = libelle or libelle_tranche(tranche)
    facture.cle_tranche = tranche['cle']
    facture.save()
    if ancien == tranche['montant_ttc']:
        return facture
    FactureActivity.objects.create(
        company_id=facture.company_id, facture=facture, user=user,
        kind=FactureActivity.Kind.MODIFICATION, field='montant_ttc',
        field_label='montant_ttc', old_value=str(ancien),
        new_value=str(tranche['montant_ttc']),
        body=(f'Montant modifié sur le brouillon : montant_ttc {ancien} '
              f"-> {tranche['montant_ttc']}."))
    return facture


def _facturer_acompte(devis, plan, *, user, montant, cle_attendue, libelle):
    """Nature ``acompte`` : l'échéancier est réécrit par l'acompte tapé,
    puis le brouillon d'acompte est MODIFIÉ (sinon créé) au même montant."""
    from apps.ventes.vente_facturation import plan_facturation
    prix = plan['prix_convenu_ttc']
    if montant is None:
        premiere = next((t for t in plan['tranches']
                         if str(t['type']) == 'acompte'
                         and t['statut'] != 'emise'), None)
        if premiere is None or premiere['montant_ttc'] <= 0:
            raise FacturationVenteRefusee('Montant invalide.',
                                          code='montant_invalide')
        montant = premiere['montant_ttc']
    if montant >= prix:
        raise FacturationVenteRefusee(
            'Le montant dépasse le reste à facturer.',
            code='montant_depasse_reste')
    cle = ecrire_echeancier_depuis_acompte(
        devis, montant, user=user, plan=plan, cle_attendue=cle_attendue)
    plan = plan_facturation(devis)
    tranche = next(t for t in plan['tranches'] if t['cle'] == cle)
    ht, tva, vent = montants_au_prorata(devis, plan, montant)
    tranche = dict(tranche, montant_ttc=montant, ht=ht, tva=tva,
                   ventilation_tva=vent, pourcentage=_q(montant / prix * 100))
    if tranche['statut'] == 'brouillon':
        return _editer_brouillon(
            _facture_du_plan(plan, tranche['facture_id']), tranche, user,
            libelle)
    return creer_brouillon_tranche(devis, tranche, user, libelle)


# ── VNT29 — la facture COMPLÈTE ──────────────────────────────────────────────

def _creer_brouillon_complet(devis, user, libelle):
    """Brouillon COMPLET (100 %, panier du devis recopié par
    ``copier_devis_sur_facture``) ; rattaché au BC du devis s'il n'a encore
    aucune facture."""
    from apps.ventes.models import BonCommande, Facture
    from apps.ventes.utils.company_settings import create_provisoire
    from .facturation_ops import (
        copier_devis_sur_facture, entete_facture_depuis_devis)
    bc = BonCommande.objects.filter(
        devis=devis, company_id=devis.company_id).first()
    if bc is not None and (
            bc.statut == BonCommande.Statut.ANNULE
            or Facture.objects.filter(bon_commande=bc).exists()):
        bc = None
    champs = dict(entete_facture_depuis_devis(devis),
                  **_revue_initiale(devis, user))
    champs.update(devis=devis, bon_commande=bc, client=devis.client,
                  company_id=devis.company_id,
                  statut=Facture.Statut.BROUILLON,
                  type_facture=Facture.TypeFacture.COMPLETE, created_by=user)
    if libelle:
        champs['libelle'] = libelle
    facture = create_provisoire(
        lambda ref: _inserer_facture(reference=ref, **champs))
    return copier_devis_sur_facture(facture, devis)


def _facturer_complete(devis, plan, *, user, remplacer_brouillons, libelle):
    """Nature ``complete`` : 409 ``deja_facture`` si une facture ÉMISE existe
    sur la vente ; 409 ``brouillons_a_remplacer`` (+ liste) tant que des
    brouillons existent sans confirmation ; confirmés, ils sont retirés par
    ``retirer_brouillons_de_la_vente`` (annulés, jamais supprimés)."""
    from apps.ventes.vente_facturation import STATUT_BROUILLON, STATUTS_EMIS
    factures = [f for f, _r in plan['factures_parts']]
    emises = [f for f in factures if f.statut in STATUTS_EMIS]
    if emises:
        raise _conflit(
            'deja_facture',
            'Cette vente est déjà facturée par '
            + ', '.join(f.reference for f in emises)
            + ' : une facture complète ne peut plus être créée (corrigez par un avoir).')
    brouillons = [f for f in factures if f.statut == STATUT_BROUILLON]
    if brouillons and not remplacer_brouillons:
        raise _conflit(
            'brouillons_a_remplacer',
            'Des brouillons existent : confirmez leur remplacement.',
            brouillons=[{'id': f.pk, 'reference': f.reference,
                         'total_ttc': str(_q(f.total_ttc))}
                        for f in brouillons])
    if brouillons:
        from .annulation_facture import retirer_brouillons_de_la_vente
        retirer_brouillons_de_la_vente(
            devis, user=user, motif='Remplacé par la facture complète')
    return _creer_brouillon_complet(devis, user, libelle)


# ── VNT30 — émettre, encaisser, utiliser les avances ─────────────────────────

def _paiements_saisis(paiements):
    """Les paiements DÉJÀ reçus (0 à 5 lignes, ``valider_paiements_saisis``
    de « Facturer ») ; 400 ``paiements_invalides`` sinon."""
    from .facturation_ops import FacturationRefusee, valider_paiements_saisis
    try:
        return valider_paiements_saisis(paiements or [])
    except FacturationRefusee as exc:
        raise FacturationVenteRefusee(exc.motif, code='paiements_invalides')


def _emettre(facture, user, override_credit=False):
    """Numéro légal + sortie de stock U9 par LE service d'émission (AUD101,
    VNT21) ; refus traduits (403 ``credit_hold``). ``override_credit``
    (responsable/admin, comme ``generer-facture``) : le blocage crédit
    XFAC28 est passé outre ET journalisé (``verifier_credit_hold``)."""
    from .facturation_ops import (
        EmissionRefusee, StockInsuffisantError, emettre_facture)
    from .recouvrement import CreditHoldError, verifier_credit_hold
    try:
        if override_credit and facture.client_id:
            verifier_credit_hold(
                facture.client, override=True, user=user,
                chatter_target=facture.devis if facture.devis_id else None,
                contexte='facturer la vente')
        emettre_facture(facture, user=user, source='facturer_vente',
                        verifier_credit=not override_credit)
    except EmissionRefusee as exc:
        raise FacturationVenteRefusee(exc.motif)
    except StockInsuffisantError as exc:
        raise FacturationVenteRefusee(exc.message)
    except CreditHoldError as exc:
        raise FacturationVenteRefusee(
            f'Le client est en blocage crédit : {exc.motif}. Un '
            'responsable/admin peut passer outre avec `override_credit: '
            'true`.', code='credit_hold', status=403)


def _motif(exc):
    detail = getattr(exc, 'motif', None) or getattr(exc, 'detail', exc)
    if isinstance(detail, dict):
        detail = next(iter(detail.values()), '')
    if isinstance(detail, (list, tuple)):
        detail = detail[0] if detail else ''
    return str(detail)


def _avances_du_client(facture):
    """Avances NON affectées (XFAC1) du client de la facture, même société,
    encaissées, les plus anciennes d'abord."""
    from apps.ventes.models import Paiement
    avances = (Paiement.objects.filter(
        company_id=facture.company_id, client_id=facture.client_id,
        facture__isnull=True)
        .exclude(statut__in=Paiement.STATUTS_NON_COMPTES)
        .order_by('date_paiement', 'pk'))
    return [a for a in avances if a.montant_disponible > 0]


def _encaisser(facture, *, user, saisis, utiliser_avances):
    """VNT30 — sur la facture ÉMISE : les avances du client se ventilent
    d'abord (``ventiler_avance``), les paiements saisis complètent
    (``encaisser_sur_facture``, le code de ``enregistrer-paiement``) ;
    Σ > total ⇒ 400 ``paiements_invalides``. Renvoie les paiements créés."""
    from rest_framework.exceptions import ValidationError
    from .encaissements import (
        EncaissementRefuse, encaisser_sur_facture, ventiler_avance)
    facture.refresh_from_db()
    total = _q(facture.total_ttc)
    avances = _avances_du_client(facture) if utiliser_avances else []
    reste = total
    ventilees = []
    for a in avances:
        part = min(_q(a.montant_disponible), reste)
        if part > 0:
            ventilees.append((a, part))
            reste -= part
    somme = sum((p['montant'] for p in saisis), Decimal('0'))
    if somme - reste > CENT:
        raise FacturationVenteRefusee(
            'Les paiements saisis dépassent le montant de la facture.',
            code='paiements_invalides')
    crees = []
    try:
        for avance, part in ventilees:
            ventiler_avance(paiement=avance, facture=facture, montant=part,
                            user=user)
        for donnees in saisis:
            facture, paiement = encaisser_sur_facture(
                facture=facture, donnees=donnees, user=user)
            crees.append(paiement)
    except (EncaissementRefuse, ValueError, ValidationError) as exc:
        raise FacturationVenteRefusee(_motif(exc),
                                      code='paiements_invalides')
    return crees


def facturer_vente(devis, *, nature, user, montant_ttc=None,
                   pourcentage=None, cle_attendue=None, libelle=None,
                   emettre=False, paiements=None, remplacer_brouillons=False,
                   utiliser_avances=False, override_credit=False):
    """« Facturer la vente » de ``devis`` (D-VNT-1/3, contrat
    ``devis_facturer.json``). Renvoie ``(facture, [paiements créés])`` ;
    lève :class:`FacturationVenteRefusee` (rien n'est écrit).
    ``override_credit`` : passe outre le blocage crédit à l'émission."""
    from apps.ventes.vente_facturation import plan_facturation
    if nature not in NATURES:
        raise FacturationVenteRefusee(
            'Nature inconnue : acompte, intermediaire, solde ou complete.')
    with transaction.atomic():
        # VNT27 — tout se relit SOUS le verrou (is_active, statut, plan).
        devis = next(d for d in verrouiller_vente(devis) if d.pk == devis.pk)
        _exiger_vente_en_jeu(devis)
        plan = plan_facturation(devis)
        montant = _montant_demande(plan['prix_convenu_ttc'], montant_ttc,
                                   pourcentage)
        saisis = _paiements_saisis(paiements)
        options = {'user': user, 'montant': montant,
                   'cle_attendue': cle_attendue, 'libelle': libelle}
        if nature == 'acompte':
            facture = _facturer_acompte(devis, plan, **options)
        elif nature == 'complete':
            facture = _facturer_complete(
                devis, plan, user=user, libelle=libelle,
                remplacer_brouillons=bool(remplacer_brouillons))
        else:
            facture = _facturer_tranche(devis, plan, nature, **options)
        crees = []
        # VNT30 — des paiements ou des avances à utiliser ⇒ émission d'abord.
        if emettre or saisis or utiliser_avances:
            _emettre(facture, user, override_credit=bool(override_credit))
            crees = _encaisser(facture, user=user, saisis=saisis,
                               utiliser_avances=bool(utiliser_avances))
            facture.refresh_from_db()
    return facture, crees


# ── VNT62 — l'acompte AUTOMATIQUE de l'acceptation (AMET2 + AMET4) ──────────

def acompte_a_l_acceptation(devis, user):
    """VNT62 (D-SIGN-AUTO = a) — appelé par ``accept_devis`` APRÈS le commit
    du statut (jamais pour un avenant négocié) : l'échéancier est FIGÉ
    (``figer_echeancier``, idempotent — un échéancier propre n'est jamais
    réécrit) puis le BROUILLON d'acompte de la première tranche est créé
    (``creer_brouillon_tranche`` : « BROUILLON-<id> », aucun numéro, aucune
    émission). Jamais un deuxième : une tranche d'acompte déjà couverte
    (brouillon ou émise, toute la chaîne de versions) ne crée rien.

    L'échéancier figé reste en % (l'acompte n'est PAS réécrit en MAD ici :
    seule une saisie « Facturer l'acompte » le fait, en modifiant CE
    brouillon). Best-effort : un incident est journalisé, jamais remonté
    (la vente est déjà acceptée). Rend la facture créée ou ``None``."""
    import logging

    from apps.ventes.utils.echeancier import figer_echeancier
    from apps.ventes.vente_facturation import plan_facturation
    try:
        with transaction.atomic():
            figer_echeancier(devis)
            tranches = plan_facturation(devis)['tranches']
            premiere = tranches[0] if tranches else None
            if (premiere is None or str(premiere['type']) != 'acompte'
                    or premiere['statut'] != 'a_faire'
                    or premiere['montant_ttc'] <= 0):
                return None
            return creer_brouillon_tranche(devis, premiere, user)
    except Exception:  # noqa: BLE001 — best-effort, journalisé (D-ENF22-BLE001)
        logger = logging.getLogger('apps.ventes.services')
        logger.exception(
            "VNT62 : brouillon d'acompte automatique non créé (devis %s)",
            getattr(devis, 'reference', '?'))
        return None


def retirer_acompte_automatique(devis, *, user):
    """VNT62 — la dés-acceptation annule d'abord le brouillon d'acompte
    automatique de ``devis`` (« BROUILLON-<id> », nature acompte, aucun
    paiement compté) par ``annuler_facture`` : jamais supprimé, aucun avoir
    (référence provisoire). Toute autre facture reste et bloque comme avant.
    À appeler DANS la transaction de la dés-acceptation (un blocage ensuite
    l'annule avec elle). Rend les factures annulées."""
    from core.numbering import est_reference_provisoire

    from apps.ventes.models import Facture, Paiement
    from .annulation_facture import annuler_facture
    retirees = []
    for facture in (Facture.objects.filter(
            company_id=devis.company_id, devis_id=devis.pk,
            statut=Facture.Statut.BROUILLON, type_facture='acompte')
            .order_by('pk')):
        if not est_reference_provisoire(facture.reference):
            continue
        if any(p.statut not in Paiement.STATUTS_NON_COMPTES
               for p in facture.paiements.all()):
            continue
        retirees.append(annuler_facture(
            facture, user=user, motif="Acceptation annulée — brouillon "
                                      "d'acompte automatique retiré."))
    return retirees


# ── VNT66 — réécrire l'échéancier d'une vente (contrat devis_echeancier.json) ─

def modifier_echeancier_vente(devis, tranches, *, user):
    """VNT66 — ``PUT devis/<id>/echeancier/`` : REMPLACE le plan de tranches
    du devis (brouillon, envoyé ou ACCEPTÉ) par LE geste ÉCHÉANCIER de VNT25
    (``modifiabilite.controler_echeancier_vente`` : Σ des tranches non
    dernières ≤ prix convenu, tout-% = 100, dernière = reste, tranches déjà
    couvertes — émises ou brouillon — inchangées). Sous le verrou de la
    chaîne ; sur un accepté, la correction est tracée « après acceptation ».

    Refus : :class:`FacturationVenteRefusee` au corps du contrat (400
    ``echeancier_invalide`` / ``somme_invalide``, 409 ``tranche_facturee``
    + ``tranche``, 409 devis hors jeu ``{detail, statut,
    revision_possible}``). Rend le devis relu. Aucun statut écrit (règle #4).
    """
    from apps.ventes.models import Devis
    from .modifiabilite import (
        DevisNonModifiable, EcheancierRefuse,
        consigner_correction_apres_envoi, controler_echeancier_vente)
    with transaction.atomic():
        devis = next(d for d in verrouiller_vente(devis) if d.pk == devis.pk)
        try:
            entrees = controler_echeancier_vente(devis, tranches)
        except DevisNonModifiable as exc:
            raise FacturationVenteRefusee(
                exc.detail, status=409, statut=exc.statut,
                revision_possible=exc.revision_possible)
        except EcheancierRefuse as exc:
            corps = exc.corps()
            raise FacturationVenteRefusee(corps.pop('detail'),
                                          status=exc.status, **corps)
        if entrees != devis.echeancier:
            Devis.objects.filter(pk=devis.pk, company_id=devis.company_id
                                 ).update(echeancier=entrees)
            devis.echeancier = entrees
            consigner_correction_apres_envoi(
                devis, user=user, objet='echeancier',
                resume='échéancier modifié',
                apres_acceptation=devis.statut == 'accepte')
    return devis


# ── VNT67 — le TTC d'un BROUILLON de tranche (D-VNT-1 « modifient librement ») ─

def modifier_montant_tranche(facture, montant_ttc, *, user):
    """VNT67 — ``POST factures/<id>/montant-tranche/`` : le brouillon de
    tranche prend ``montant_ttc`` ; HT / TVA / ventilation au prorata du prix
    convenu (``montants_au_prorata``) et l'échéancier RÉÉCRIT (Σ = TTC) :
    l'acompte par l'écrivain unique de VNT28
    (``ecrire_echeancier_depuis_acompte``, via ``_facturer_acompte``), une
    tranche intermédiaire passe en MAD de même (dernière = reste, contrôle
    ``controler_echeancier_vente``). Refus : 409 ``facture_emise`` (seul un
    brouillon change de montant — une émise se corrige par avoir), 409
    ``pas_une_tranche`` (api-fuzz-full 27/10 : c'est la facture STOCKÉE qui
    s'oppose, ENF11), 400 ``montant_invalide`` pour un montant illisible et 409
    ``montant_invalide`` pour un montant ≥ au prix convenu (la dernière tranche
    vaut le reste : refus d'état). Aucun statut écrit (règle #4). Rend la
    facture relue."""
    from apps.ventes.models import Devis
    from apps.ventes.utils.echeancier import UNITE_MONTANT
    from apps.ventes.vente_facturation import plan_facturation
    from .modifiabilite import (
        EcheancierRefuse, consigner_correction_apres_envoi,
        controler_echeancier_vente)
    if facture.statut != 'brouillon':
        raise _conflit('facture_emise',
                       'Seul un brouillon change de montant : cette facture '
                       'est émise — corrigez-la par un avoir.')
    if not facture.devis_id or not facture.cle_tranche \
            or facture.type_facture == 'complete':
        raise _conflit('pas_une_tranche',
                       "Cette facture n'est pas une tranche d'échéancier.")
    with transaction.atomic():
        devis = next(d for d in verrouiller_vente(facture.devis)
                     if d.pk == facture.devis_id)
        _exiger_vente_en_jeu(devis)
        plan = plan_facturation(devis)
        montant = _montant_demande(plan['prix_convenu_ttc'], montant_ttc,
                                   None)
        if montant is None:
            raise FacturationVenteRefusee('Montant invalide.',
                                          code='montant_invalide')
        if montant >= plan['prix_convenu_ttc']:
            raise _conflit('montant_invalide', (
                'Montant invalide : une tranche intermédiaire reste sous le '
                'prix convenu (la dernière tranche vaut le reste).'))
        if facture.type_facture == 'acompte':
            return _facturer_acompte(
                devis, plan, user=user, montant=montant,
                cle_attendue=facture.cle_tranche, libelle=None)
        cles = [t['cle'] for t in plan['tranches']]
        if facture.cle_tranche not in cles[:-1]:
            raise FacturationVenteRefusee(
                'La dernière tranche vaut le reste : son montant ne se '
                'modifie pas.', code='montant_invalide')
        entrees = _entrees_echeancier(devis)
        k = cles.index(facture.cle_tranche)
        entrees[k] = dict(entrees[k], unite=UNITE_MONTANT,
                          pct_or_montant=float(montant))
        try:
            entrees = controler_echeancier_vente(devis, entrees,
                                                 figer_brouillons=False)
        except EcheancierRefuse as exc:
            corps = exc.corps()
            raise FacturationVenteRefusee(corps.pop('detail'),
                                          status=exc.status, **corps)
        Devis.objects.filter(pk=devis.pk, company_id=devis.company_id
                             ).update(echeancier=entrees)
        devis.echeancier = entrees
        consigner_correction_apres_envoi(
            devis, user=user, objet='echeancier',
            resume=f'échéancier — {facture.libelle} {montant} MAD',
            apres_acceptation=True)
        ht, tva, vent = montants_au_prorata(devis, plan, montant)
        tranche = next(t for t in plan_facturation(devis)['tranches']
                       if t['cle'] == facture.cle_tranche)
        prix = plan['prix_convenu_ttc']
        return _editer_brouillon(facture, dict(
            tranche, montant_ttc=montant, ht=ht, tva=tva,
            ventilation_tva=vent, pourcentage=_q(montant / prix * 100)),
            user, None)

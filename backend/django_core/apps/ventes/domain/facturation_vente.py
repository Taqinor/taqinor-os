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
    """400 hors devis accepté ; 409 ``version_remplacee`` (corps unique de
    VNT24, tête de chaîne en ``successeur``) pour une version inactive."""
    if devis.statut != 'accepte':
        raise FacturationVenteRefusee(
            'Seul un devis accepté se facture : ce devis est au statut '
            f'« {devis.get_statut_display()} ».')
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
    ht = _q(plan['prix_convenu_ht'] * ttc / prix) if prix > 0 else ttc
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
    """Crée le BROUILLON « BROUILLON-<id> » de ``tranche`` (jamais émis)."""
    from apps.ventes.utils.company_settings import create_provisoire
    champs = _champs_tranche(devis, tranche, user, libelle)
    return create_provisoire(
        lambda ref: _inserer_facture(reference=ref, **champs))


def _facturer_tranche(devis, plan, nature, *, user, montant, cle_attendue,
                      libelle):
    """Natures ``intermediaire`` / ``solde`` : la prochaine tranche du plan."""
    tranche = _tranche_cible(plan, nature, cle_attendue)
    tranche = _tranche_au_montant(devis, plan, tranche, montant)
    return creer_brouillon_tranche(devis, tranche, user, libelle)


def facturer_vente(devis, *, nature, user, montant_ttc=None,
                   pourcentage=None, cle_attendue=None, libelle=None,
                   emettre=False, paiements=None, remplacer_brouillons=False,
                   utiliser_avances=False):
    """« Facturer la vente » de ``devis`` (D-VNT-1/3, contrat
    ``devis_facturer.json``). Renvoie ``(facture, [paiements créés])`` ;
    lève :class:`FacturationVenteRefusee` (rien n'est écrit)."""
    from apps.ventes.vente_facturation import plan_facturation
    if nature not in NATURES:
        raise FacturationVenteRefusee(
            'Nature inconnue : acompte, intermediaire, solde ou complete.')
    with transaction.atomic():
        _exiger_vente_en_jeu(devis)
        plan = plan_facturation(devis)
        montant = _montant_demande(plan['prix_convenu_ttc'], montant_ttc,
                                   pourcentage)
        if nature not in ('intermediaire', 'solde'):
            raise FacturationVenteRefusee(
                f'La nature « {nature} » arrive avec VNT28/VNT29.')
        facture = _facturer_tranche(
            devis, plan, nature, user=user, montant=montant,
            cle_attendue=cle_attendue, libelle=libelle)
    return facture, []

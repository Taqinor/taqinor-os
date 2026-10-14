"""Négociation d'une vente acceptée — Groupe VNT (« Prix négocié », avenant).

Une vente acceptée ne se double pas : un lead porte AU PLUS UNE vente en
vigueur (D-VNT). Un prix renégocié passe par « Prix négocié » (V2 de révision
créée ET acceptée en un geste) ou par « Réviser » — jamais par une seconde
chaîne de devis acceptée à côté de la première (389 acceptée à côté de 388).

Ce module n'écrit AUCUN statut lui-même (règle #4) : il porte les GARDES et
les LECTURES de la négociation ; la bascule reste le seul ``accept_devis``.
Lectures cross-app : aucune (tout est dans ``apps.ventes``). Imports
fonction-locaux : ``cycle_vie`` importe ce module au moment de l'appel.
"""
import logging

logger = logging.getLogger("apps.ventes.services")

#: VNT54 — code machine du 409 (liste FERMÉE ``codes_409`` du contrat
#: ``proposal_accept.json`` ; ``erreurs_409`` de ``devis_prix_negocie.json``).
CODE_VENTE_ACTIVE_EXISTANTE = 'vente_active_existante'

#: VNT54 — message NEUTRE pour le client (lien public, portail) : contrat
#: ``proposal_accept.json`` → ``reponses_409.vente_active_existante``. Aucune
#: référence interne n'est exposée au client.
VENTE_ACTIVE_REFUS_CLIENT = (
    "Cette proposition ne peut pas être signée en l'état : contactez votre "
    'conseiller.')


def vente_active_hors_chaine(devis):
    """VNT54 — la vente en vigueur du lead de ``devis`` qui n'est PAS dans sa
    chaîne de révision (ni ``devis`` lui-même, ni une version qu'il remplace),
    ou ``None``. Un devis sans lead n'a pas de garde (rien à comparer).

    Lecture : ``devis_signes_en_vigueur`` (LA définition de « vente en
    vigueur », VNT22) moins ``devis_predecesseurs_revision_ids`` (une V2 de
    révision remplace sa V1, elle ne la double pas). Une VARIANTE créée depuis
    une vente acceptée n'est pas un prédécesseur : elle est refusée."""
    lead_id = getattr(devis, 'lead_id', None)
    if not lead_id or getattr(devis, 'company_id', None) is None:
        return None
    from apps.ventes.selectors import (
        devis_predecesseurs_revision_ids, devis_signes_en_vigueur)
    exclus = set(devis_predecesseurs_revision_ids(devis)) | {devis.pk}
    return (devis_signes_en_vigueur(devis.company, lead_ids=[lead_id])
            .exclude(pk__in=exclus).order_by('pk').first())


def garde_vente_unique(devis, *, user):
    """VNT54 — LA garde « une vente en vigueur par lead » des trois portes
    d'acceptation (vue interne, lien public, portail), posée par
    ``accept_devis`` sous son verrou, AVANT toute écriture.

    Lève ``AcceptError(conflict=True, code='vente_active_existante')`` portant
    ``vente_active = {id, reference}`` ; le message est NEUTRE pour le client
    (``_acceptation_par_le_client``) et dit en interne quel geste utiliser."""
    from apps.ventes.domain.cycle_vie import (
        AcceptError, _acceptation_par_le_client)
    existante = vente_active_hors_chaine(devis)
    if existante is None:
        return
    if _acceptation_par_le_client(user):
        message = VENTE_ACTIVE_REFUS_CLIENT
    else:
        message = (
            f'Ce lead a déjà une vente en vigueur ({existante.reference}). '
            f'Utilisez « Prix négocié » ou « Réviser » sur '
            f'{existante.reference}.')
    exc = AcceptError(message, conflict=True,
                      code=CODE_VENTE_ACTIVE_EXISTANTE)
    exc.vente_active = {'id': existante.pk,
                        'reference': existante.reference}
    logger.info('VNT54: acceptation de %s refusée — vente en vigueur %s '
                'sur le même lead.', getattr(devis, 'reference', '?'),
                existante.reference)
    raise exc


# ── VNT58 — l'aperçu « Prix négocié » (lecture pure) ─────────────────────────

#: Messages des refus — contrat ``devis_prix_negocie.json`` (``erreurs_400`` /
#: ``erreurs_409``), repris tels quels.
REFUS_PRIX_NEGOCIE = {
    'saisie_vide': 'Indiquez un prix TTC ou une remise.',
    'saisie_double': 'Indiquez le prix TTC OU la remise, pas les deux.',
    'prix_non_rond': 'Le prix négocié doit être un montant rond.',
    'prix_superieur': 'Le prix négocié dépasse le prix actuel du devis.',
    'prix_identique': 'Le prix négocié est identique au prix actuel.',
    'prix_inatteignable': 'Ce prix ne peut pas être atteint exactement.',
    'approbation_requise': (
        "Cette remise demande l'approbation d'un responsable."),
    'avoir_a_confirmer': 'Un avoir sera émis : confirmez pour continuer.',
    'pas_une_vente_active': "Ce devis n'est pas une vente active.",
}


class PrixNegocieRefuse(Exception):
    """VNT58 — refus de l'aperçu / de l'application d'un prix négocié :
    ``code`` (liste FERMÉE du contrat), ``statut_http`` (400 ou 409) et le
    corps exact à rendre (:meth:`corps`)."""

    def __init__(self, code, *, statut_http=400, detail=None, **extra):
        self.code = code
        self.statut_http = statut_http
        self.detail = detail or REFUS_PRIX_NEGOCIE[code]
        self.extra = extra
        super().__init__(self.detail)

    def corps(self):
        return {'detail': self.detail, 'code': self.code, **self.extra}


def _txt(valeur):
    from decimal import Decimal, ROUND_HALF_UP
    return '{:.2f}'.format(Decimal(str(valeur)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP))


def _saisie(prix_ttc, remise_pct):
    """(prix, remise) en Decimal — exactement UNE des deux saisies."""
    from decimal import Decimal, InvalidOperation

    def _lu(valeur):
        if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
            return None
        try:
            return Decimal(str(valeur).strip().replace(',', '.'))
        except (InvalidOperation, ValueError):
            raise PrixNegocieRefuse('saisie_vide')
    prix, remise = _lu(prix_ttc), _lu(remise_pct)
    if prix is None and remise is None:
        raise PrixNegocieRefuse('saisie_vide')
    if prix is not None and remise is not None:
        raise PrixNegocieRefuse('saisie_double')
    return prix, remise


def _exiger_vente_active(devis, etat):
    """409 ``version_remplacee`` (corps unique de ``modifiabilite``) ou
    ``pas_une_vente_active`` : seule la TÊTE acceptée d'une vente sans
    révision en cours se négocie."""
    from apps.ventes.domain.modifiabilite import (
        CODE_VERSION_REMPLACEE, corps_version_remplacee)
    from apps.ventes.models import Devis
    if not devis.is_active or not etat['est_tete']:
        corps = corps_version_remplacee(devis)
        raise PrixNegocieRefuse(
            CODE_VERSION_REMPLACEE, statut_http=409, detail=corps['detail'],
            successeur=corps['successeur'])
    if (devis.statut != Devis.Statut.ACCEPTE
            or etat['revision_en_cours'] is not None):
        raise PrixNegocieRefuse('pas_une_vente_active', statut_http=409)


def apercu_prix_negocie(devis, *, prix_ttc=None, remise_pct=None, user=None,
                        exiger_confirmation=False, confirmer_avoir=False):
    """VNT58 — l'aperçu « Prix négocié » d'une vente acceptée (LECTURE PURE :
    rien n'est écrit). Forme ``reponse_apercu_200`` du contrat
    ``devis_prix_negocie.json`` ; un refus lève :class:`PrixNegocieRefuse`.

    * saisie : exactement un de ``prix_ttc`` / ``remise_pct`` ;
    * prix TTC : multiple de 100 MAD × N propriétés (le palier ARRONDI-100
      est par villa), inférieur au prix actuel ; la remise est la plus RONDE
      qui l'atteint exactement (:func:`noyau_totaux.remise_pour_ttc`), sinon
      ``prix_inatteignable`` + les deux prix atteignables voisins ;
    * approbation T17 de la nouvelle remise (un administrateur approuve
      implicitement ; l'aperçu n'écrit rien) ;
    * effets lus sur :func:`etat_vente` (aucune somme refaite ici) :
      brouillons à retirer, factures émises reprises, écart, régularisation
      (avoir quand l'émis net dépasse le nouveau prix — ``exiger_confirmation``
      sans ``confirmer_avoir`` ⇒ ``avoir_a_confirmer``), reste à facturer.

    Rend aussi, hors contrat (préfixe ``_``), la remise en Decimal
    (``_remise``) que l'application réutilise sans recalcul."""
    from decimal import Decimal

    from apps.ventes.domain.noyau_totaux import (
        _canonical_totaux, remise_pour_ttc, totaux_multi_proprietes)
    from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS
    from apps.ventes.domain.tarification import (
        RemiseNonApprouvee, exiger_approbation_remise)
    from apps.ventes.multivilla import nombre_proprietes
    from apps.ventes.selectors import etat_vente
    from apps.ventes.utils.options import option_lines

    prix, remise = _saisie(prix_ttc, remise_pct)
    etat = etat_vente(devis, user)
    _exiger_vente_active(devis, etat)

    n = nombre_proprietes(devis)
    actuel = Decimal(etat['prix_convenu_ttc'])
    lignes = option_lines(devis)

    if prix is not None:
        if prix % (PAS_ARRONDI_DEVIS * n):
            raise PrixNegocieRefuse('prix_non_rond')
        if prix > actuel:
            raise PrixNegocieRefuse('prix_superieur')
        if prix == actuel:
            raise PrixNegocieRefuse('prix_identique')
        solution = remise_pour_ttc(lignes, prix / n,
                                   fallback_taux=devis.taux_tva,
                                   arrondi_pas=PAS_ARRONDI_DEVIS)
        if not solution['atteint']:
            voisins = [v for v in (solution['voisin_bas'],
                                   solution['voisin_haut']) if v]
            raise PrixNegocieRefuse(
                'prix_inatteignable',
                prix_atteignables=[_txt(v['ttc'] * n) for v in voisins])
        remise = solution['remise_pct']
        nouveau = prix
    else:
        if remise < 0 or remise > 100:
            raise PrixNegocieRefuse('saisie_vide')
        nouveau = totaux_multi_proprietes(_canonical_totaux(
            lignes, remise_globale_pct=remise, fallback_taux=devis.taux_tva,
            arrondi_pas=PAS_ARRONDI_DEVIS), n)['ttc']
        if nouveau > actuel:
            raise PrixNegocieRefuse('prix_superieur')
        if nouveau == actuel:
            raise PrixNegocieRefuse('prix_identique')

    try:
        exiger_approbation_remise(devis, user, remise_globale=remise,
                                  enregistrer=False)
    except RemiseNonApprouvee:
        raise PrixNegocieRefuse('approbation_requise')

    brouillons = [f for f in etat['factures'] if f['statut'] == 'brouillon']
    emises = [f for f in etat['factures']
              if f['statut'] in ('emise', 'payee', 'en_retard')]
    emis = Decimal(etat['emis_ttc'])
    avoir = emis - nouveau if emis > nouveau else Decimal('0')
    if avoir > 0 and exiger_confirmation and not confirmer_avoir:
        raise PrixNegocieRefuse('avoir_a_confirmer')
    reste = nouveau - emis if nouveau > emis else Decimal('0')
    return {
        'devis_v2': {'id': None, 'reference': None,
                     'version': (devis.version or 1) + 1},
        'remise_pct': _txt(remise),
        'total_ttc': _txt(nouveau),
        'factures_annulees': [{'reference': f['reference']}
                              for f in brouillons],
        'factures_reprises': [{'reference': f['reference'],
                               'total_ttc': f['total_ttc']} for f in emises],
        'ecart_ttc': _txt(nouveau - actuel),
        'regularisation': {'type': 'avoir' if avoir > 0 else 'aucune',
                           'montant': _txt(avoir)},
        'reste_a_facturer': _txt(reste),
        '_remise': remise,
    }

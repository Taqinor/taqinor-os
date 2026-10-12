"""Négociation d'une vente signée (Groupe VNT, D-VNT-2) — une vente par lead.

VNT54 — ``garde_vente_unique`` : ``accept_devis`` (les trois portes : vue
interne, lien public, portail) refuse une DEUXIÈME vente en vigueur sur un lead
quand le devis accepté n'appartient pas à la chaîne de RÉVISION de la vente en
vigueur (``superseded_by`` — une variante, sœur du même groupe
``version_parent``, est une autre chaîne). Rien n'est écrit (règle #4) : la
garde lève avant toute bascule de statut, sous le verrou d'``accept_devis``.

VNT58 — ``apercu_prix_negocie`` (lecture PURE, rien n'est écrit) : contrôles
d'entrée, solveur de remise (``noyau_totaux.remise_pour_ttc``, VNT49), effets
financiers LUS sur ``vente_facturation.etat_vente`` (aucune 9e somme).

VNT59 — ``appliquer_prix_negocie`` : V2 créée ET acceptée en un geste (canal
``avenant_negocie`` : ni signature, ni PDF scellé, ni e-mail, ni CAPI —
``effets_apres_acceptation``), brouillons de la vente retirés (annulés, jamais
supprimés), rattachement STRICT (tout ou rien).

VNT61 — ``etat_avenant`` / ``signer_avenant`` : un avenant accepté en interne se
signe par le lien client — une ``DevisSignature`` (empreinte + PDF signé), sans
changer le statut ni émettre le moindre événement (règle #4).

Ordre de chargement : ce module importe ``cycle_vie`` (``AcceptError``) ;
``cycle_vie`` ne l'importe qu'à l'APPEL (import fonction-local), jamais au
chargement — aucun cycle.
"""
import logging

from apps.ventes.domain import cycle_vie as _cycle_vie

logger = logging.getLogger("apps.ventes.services")

#: Code machine du 409 (contrats ``proposal_accept.json`` ``codes_409`` et
#: ``devis_prix_negocie.json`` ``erreurs_409``).
CODE_VENTE_ACTIVE_EXISTANTE = 'vente_active_existante'

#: Message NEUTRE pour le client (lien public, portail) — contrat
#: ``proposal_accept.json`` ``reponses_409.vente_active_existante`` : aucune
#: référence interne exposée.
VENTE_ACTIVE_REFUS_CLIENT = (
    "Cette proposition ne peut pas être signée en l'état : contactez votre "
    'conseiller.')


class VenteActiveExistante(_cycle_vie.AcceptError):
    """VNT54 — 409 ``vente_active_existante`` ; ``vente_active`` =
    ``{id, reference}`` de la vente en vigueur (rendu par la vue interne)."""

    def __init__(self, message, vente_active):
        super().__init__(message, conflict=True,
                         code=CODE_VENTE_ACTIVE_EXISTANTE)
        self.vente_active = vente_active


def vente_active_hors_chaine(devis):
    """La vente en vigueur du lead de ``devis`` qui n'est PAS dans sa chaîne
    de révision (``devis`` et les versions qu'il remplace), ou ``None``.
    Lead absent ⇒ ``None`` (aucune règle par lead sans lead)."""
    if not getattr(devis, 'lead_id', None):
        return None
    from apps.ventes.selectors import (
        devis_predecesseurs_revision_ids, devis_signes_en_vigueur)
    chaine = set(devis_predecesseurs_revision_ids(devis)) | {devis.pk}
    return (devis_signes_en_vigueur(devis.company_id,
                                    lead_ids=[devis.lead_id])
            .exclude(pk__in=chaine).order_by('pk').first())


def garde_vente_unique(devis, *, user):
    """VNT54 — lève ``VenteActiveExistante`` si le lead porte déjà une vente
    en vigueur hors de la chaîne de ``devis``. Message interne (« Utilisez
    « Prix négocié » ou « Réviser » sur <ref> ») ou neutre pour le client
    (``_acceptation_par_le_client``)."""
    autre = vente_active_hors_chaine(devis)
    if autre is None:
        return
    if _cycle_vie._acceptation_par_le_client(user):
        message = VENTE_ACTIVE_REFUS_CLIENT
    else:
        message = (
            f'Une vente active existe déjà pour ce lead : {autre.reference}. '
            f'Utilisez « Prix négocié » ou « Réviser » sur {autre.reference}.')
    raise VenteActiveExistante(
        message, {'id': autre.pk, 'reference': autre.reference})


# ── VNT58 — aperçu « Prix négocié » (lecture pure) ───────────────────────────

class PrixNegocieErreur(Exception):
    """Refus de « Prix négocié » au format du contrat ``devis_prix_negocie.json``
    (``erreurs_400`` / ``erreurs_409``) : ``corps`` = ``{detail, code, …}``,
    ``statut_http`` = 400 ou 409."""

    def __init__(self, code, detail, statut_http=400, **extra):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.statut_http = statut_http
        self.corps = {'detail': detail, 'code': code, **extra}


def _txt(valeur):
    from decimal import Decimal
    return f'{Decimal(str(valeur)):.2f}'


def _decimal_saisi(valeur, champ):
    from decimal import Decimal, InvalidOperation
    try:
        return Decimal(str(valeur).replace(' ', '').replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise PrixNegocieErreur(
            'saisie_vide', f'Valeur invalide pour {champ}.') from None


def _vide(valeur):
    return valeur is None or str(valeur).strip() == ''


def _lignes_option(devis, option=None):
    """Les lignes de l'option retenue (UNE villa) — celles que la chaîne
    canonique (``option_totaux``) met en prix ; ``option`` impose l'option
    (la V2 d'un avenant suit l'option ACCEPTÉE de la V1)."""
    from apps.ventes.utils.options import (
        filter_lines_for_option, has_two_options, lignes_avec_produit,
        option_effective)
    lignes = list(lignes_avec_produit(devis))
    option = option if option is not None else option_effective(devis)
    if option and has_two_options(devis):
        lignes = filter_lines_for_option(lignes, option)
    return lignes


def _garde_vente_active(devis):
    """409 au format VNT24 (version remplacée) ou ``pas_une_vente_active``."""
    if not devis.is_active:
        from apps.ventes.domain.modifiabilite import corps_version_remplacee
        corps = dict(corps_version_remplacee(devis))
        raise PrixNegocieErreur(corps.pop('code'), corps.pop('detail'), 409,
                                **corps)
    if devis.statut != devis.Statut.ACCEPTE:
        raise PrixNegocieErreur(
            'pas_une_vente_active', "Ce devis n'est pas une vente active.", 409)


def _prix_cible(devis, lignes, prix_ttc, remise_pct, n):
    """Le TTC visé (Decimal) depuis la saisie (prix OU remise)."""
    from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS
    from apps.ventes.domain.noyau_totaux import _canonical_totaux
    if _vide(prix_ttc) and _vide(remise_pct):
        raise PrixNegocieErreur('saisie_vide',
                                'Indiquez un prix TTC ou une remise.')
    if not _vide(prix_ttc) and not _vide(remise_pct):
        raise PrixNegocieErreur(
            'saisie_double', 'Indiquez le prix TTC OU la remise, pas les deux.')
    if not _vide(prix_ttc):
        return _decimal_saisi(prix_ttc, 'le prix')
    remise = _decimal_saisi(remise_pct, 'la remise')
    if not 0 <= remise <= 100:
        raise PrixNegocieErreur('saisie_vide', 'Remise hors de 0-100 %.')
    return _canonical_totaux(
        lignes, remise_globale_pct=remise, fallback_taux=devis.taux_tva,
        arrondi_pas=PAS_ARRONDI_DEVIS)['ttc'] * n


def _garde_approbation(devis, user, remise):
    """T17 sur la remise NÉGOCIÉE (aperçu : rien n'est consigné)."""
    from apps.ventes.domain.tarification import (
        RemiseNonApprouvee, exiger_approbation_remise)
    try:
        exiger_approbation_remise(devis, user, remise_globale=remise,
                                  enregistrer=False)
    except RemiseNonApprouvee as exc:
        raise PrixNegocieErreur('approbation_requise', exc.message) from exc


def _solveur(devis, lignes, prix, n):
    """La remise la plus ronde qui rend ``prix`` (VNT49), sinon 400
    ``prix_inatteignable`` avec les deux prix atteignables voisins."""
    from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS
    from apps.ventes.domain.noyau_totaux import remise_pour_ttc
    sol = remise_pour_ttc(lignes, prix / n, fallback_taux=devis.taux_tva,
                          arrondi_pas=PAS_ARRONDI_DEVIS)
    if not sol['atteint']:
        voisins = [v for v in (sol['voisins'] or {}).values() if v]
        raise PrixNegocieErreur(
            'prix_inatteignable', 'Ce prix ne peut pas être atteint exactement.',
            prix_atteignables=sorted(_txt(v['ttc'] * n) for v in voisins))
    return sol['remise_pct']


def apercu_prix_negocie(devis, *, prix_ttc=None, remise_pct=None, user=None,
                        confirmer_avoir=False):
    """VNT58 — ce que « Prix négocié » ferait, SANS rien écrire.

    Contrôles (``PrixNegocieErreur``) : 409 version remplacée / pas une vente
    active ; 400 ``saisie_vide``, ``saisie_double``, ``prix_non_rond`` (multiple
    de 100 × N propriétés), ``prix_superieur``, ``prix_identique``,
    ``prix_inatteignable`` (+ ``prix_atteignables``), ``approbation_requise``
    (T17, rien consigné), ``avoir_a_confirmer`` (l'émis dépasse le nouveau
    prix, ``confirmer_avoir`` faux). Rend la forme ``reponse_apercu_200`` :
    ``devis_v2`` (id/référence nuls), ``remise_pct``, ``total_ttc``,
    ``factures_annulees`` (brouillons de la vente), ``factures_reprises``
    (émises), ``ecart_ttc``, ``regularisation``, ``reste_a_facturer`` — le
    prix convenu et l'émis sont LUS sur ``etat_vente`` (aucune 9e somme)."""
    from decimal import Decimal

    from apps.ventes.domain.argent import PAS_ARRONDI_DEVIS
    from apps.ventes.multivilla import nombre_proprietes
    from apps.ventes.vente_facturation import STATUTS_EMIS, etat_vente

    _garde_vente_active(devis)
    n = max(int(nombre_proprietes(devis) or 1), 1)
    lignes = _lignes_option(devis)
    prix = _prix_cible(devis, lignes, prix_ttc, remise_pct, n)
    if prix <= 0 or prix % (PAS_ARRONDI_DEVIS * n) != 0:
        raise PrixNegocieErreur(
            'prix_non_rond', 'Le prix négocié doit être un montant rond.',
            multiple=_txt(PAS_ARRONDI_DEVIS * n))
    etat = etat_vente(devis, user)
    actuel = Decimal(etat['prix_convenu_ttc'])
    if prix > actuel:
        raise PrixNegocieErreur(
            'prix_superieur', 'Le prix négocié dépasse le prix actuel du devis.')
    if prix == actuel:
        raise PrixNegocieErreur(
            'prix_identique', 'Le prix négocié est identique au prix actuel.')
    remise = _solveur(devis, lignes, prix, n)
    _garde_approbation(devis, user, remise)
    factures = [f for f in etat['factures'] if f['nature'] != 'consolidee']
    emis = Decimal(etat['emis_ttc'])
    avoir = emis - prix if emis > prix else Decimal('0')
    if avoir > 0 and not confirmer_avoir:
        raise PrixNegocieErreur(
            'avoir_a_confirmer', 'Un avoir sera émis : confirmez pour continuer.',
            montant_avoir=_txt(avoir))
    return {
        'devis_v2': {'id': None, 'reference': None,
                     'version': (devis.version or 1) + 1},
        'remise_pct': _txt(remise),
        'total_ttc': _txt(prix),
        'factures_annulees': [{'reference': f['reference']} for f in factures
                              if f['statut'] == 'brouillon'],
        'factures_reprises': [{'reference': f['reference'],
                               'total_ttc': f['total_ttc']} for f in factures
                              if f['statut'] in STATUTS_EMIS],
        'ecart_ttc': _txt(prix - actuel),
        'regularisation': {'type': 'avoir' if avoir > 0 else 'aucune',
                           'montant': _txt(avoir)},
        'reste_a_facturer': _txt(prix - emis if prix > emis else 0),
    }


# ── VNT59 — appliquer « Prix négocié » (un geste, tout ou rien) ──────────────

#: Canal d'acceptation de l'avenant négocié (D-VNT-2) : aucune signature,
#: aucun PDF scellé, aucun e-mail, aucun CAPI.
CANAL_AVENANT_NEGOCIE = 'avenant_negocie'


def effets_apres_acceptation(devis, *, user, lignes=None, ip=None,
                             user_agent='', canal=''):
    """Les entrées-sorties d'APRÈS le commit d'``accept_devis`` (déplacées,
    VNT59) : PDF scellé (QJ22), rafraîchissement ``fichier_pdf`` (QX9),
    e-mails d'acceptation (QJ10), CAPI SignedQuote (QJ9/VNT52). Best-effort,
    jamais bloquantes. Lues sur ``cycle_vie`` à l'appel : un ``mock.patch``
    posé sur ``cycle_vie._store_signed_pdf`` / ``_send_acceptance_emails``
    reste honoré. L'avenant négocié (``CANAL_AVENANT_NEGOCIE``) n'en a AUCUN."""
    if canal == CANAL_AVENANT_NEGOCIE:
        return
    from apps.ventes.domain import capi_signee
    _cycle_vie._store_signed_pdf(devis=devis)
    try:
        devis.refresh_from_db(fields=['fichier_pdf'])
    except Exception:  # noqa: BLE001 — best-effort
        pass
    try:
        _cycle_vie._send_acceptance_emails(devis=devis, user=user,
                                           lignes=lignes)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ10: _send_acceptance_emails échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)
    try:
        capi_signee.emettre_signed_quote_vente(
            devis=devis, ip=ip, user_agent=user_agent)
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning('QJ9: _fire_capi_signed_quote échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def _creer_v2(v1, user):
    """« Réviser » sous le geste ; un double clic (V1 déjà remplacée) rend
    LA forme 409 ``version_remplacee`` (VNT24, ``successeur`` = tête)."""
    from apps.ventes.domain.revision import RevisionError, reviser_devis
    try:
        return reviser_devis(v1, user=user)
    except RevisionError as exc:
        extra = ({'successeur': exc.successeur}
                 if exc.code == 'version_remplacee' else {})
        raise PrixNegocieErreur(exc.code or 'statut', exc.message, 409,
                                **extra) from exc


def _poser_remise(v2, v1, prix, n):
    """La remise la plus ronde qui rend ``prix`` sur les lignes de la V2
    (option de la V1), écrite sur la V2 BROUILLON puis VÉRIFIÉE au centime
    sur la chaîne canonique — jamais un prix approché."""
    from decimal import Decimal
    from apps.ventes.utils.options import option_totaux
    option = v1.option_acceptee or ''
    remise = _solveur(v2, _lignes_option(v2, option), prix, n)
    v2.remise_globale = remise
    v2.save(update_fields=['remise_globale'])
    if Decimal(str(option_totaux(v2, option=option)['ttc'])) != prix:
        raise PrixNegocieErreur(
            'prix_inatteignable', 'Ce prix ne peut pas être atteint exactement.',
            prix_atteignables=[])
    return remise


def _accepter_avenant(v2, v1, user):
    """``accept_devis`` canal ``avenant_negocie`` ; ses refus deviennent des
    ``PrixNegocieErreur`` (409 ``vente_active_existante`` avec la vente)."""
    nom = (v1.accepte_par_nom or '').strip()
    try:
        return _cycle_vie.accept_devis(
            devis=v2, user=user, idempotent_reaccept=False,
            nom=f'{nom} — avenant négocié' if nom else 'Avenant négocié',
            option=v1.option_acceptee or '', canal=CANAL_AVENANT_NEGOCIE)
    except VenteActiveExistante as exc:
        raise PrixNegocieErreur(exc.code, exc.message, 409,
                                vente_active=exc.vente_active) from exc
    except _cycle_vie.AcceptError as exc:
        raise PrixNegocieErreur(exc.code or 'statut', exc.message,
                                409 if exc.conflict else 400) from exc


def appliquer_prix_negocie(devis, *, prix_ttc=None, remise_pct=None, user,
                           confirmer_avoir=False):
    """VNT59 (D-VNT-2) — « Prix négocié » sur une vente ACCEPTÉE, en UN geste
    et en UNE transaction (tout ou rien) : contrôles de l'aperçu (VNT58),
    ``reviser_devis`` → remise (solveur VNT49, vérifiée) → ``accept_devis``
    canal ``avenant_negocie`` (garde « une vente par lead » VNT54 comprise ;
    ``accepte_par_nom`` « … — avenant négocié ») → brouillons de la vente
    ANNULÉS par ``retirer_brouillons_de_la_vente`` (jamais supprimés) →
    ``rattacher_aval_financier_revision`` STRICT (un incident annule tout).
    Aucun statut écrit hors ``accept_devis`` (règle #4). Lève
    ``PrixNegocieErreur`` (400/409, rien d'écrit) ; rend la forme
    ``reponse_appliquer_201`` du contrat ``devis_prix_negocie.json``."""
    from decimal import Decimal

    from django.db import transaction

    from apps.ventes.domain.annulation_facture import (
        retirer_brouillons_de_la_vente)
    from apps.ventes.domain.revision import rattacher_aval_financier_revision
    from apps.ventes.multivilla import nombre_proprietes

    apercu = apercu_prix_negocie(devis, prix_ttc=prix_ttc,
                                 remise_pct=remise_pct, user=user,
                                 confirmer_avoir=confirmer_avoir)
    prix = Decimal(apercu['total_ttc'])
    n = max(int(nombre_proprietes(devis) or 1), 1)
    with transaction.atomic():
        v2 = _creer_v2(devis, user)
        remise = _poser_remise(v2, devis, prix, n)
        v2 = _accepter_avenant(v2, devis, user)
        annulees = retirer_brouillons_de_la_vente(
            v2, user=user, motif=f'Prix négocié — remplacé par {v2.reference}')
        rattacher_aval_financier_revision(v2, user=user)
    return dict(apercu, devis_v2={'id': v2.pk, 'reference': v2.reference,
                                  'version': v2.version},
                remise_pct=_txt(remise),
                factures_annulees=[{'reference': f.reference}
                                   for f in annulees])


# ── VNT61 — l'avenant se signe au lien client, sans statut ni événement ──────

def etat_avenant(devis):
    """``{a_signer, remplace: {reference}, signe_le}`` quand ``devis`` est un
    AVENANT (accepté, prédécesseur de révision accepté — ``predecesseur_
    accepte``), ``None`` sinon (fragments ``exemple_avenant_*`` du contrat
    ``proposal_data.json``)."""
    if getattr(devis, 'pk', None) is None or \
            devis.statut != devis.Statut.ACCEPTE:
        return None
    from apps.ventes.models import DevisSignature
    from apps.ventes.selectors import predecesseur_accepte
    remplace = predecesseur_accepte(devis)
    if remplace is None:
        return None
    signature = DevisSignature.objects.filter(devis=devis).first()
    return {'a_signer': signature is None,
            'remplace': {'reference': remplace.reference},
            'signe_le': (signature.signed_at.isoformat()
                         if signature is not None and signature.signed_at
                         else None)}


def signer_avenant(devis, *, nom, ip=None, user_agent='', consentement=True,
                   signature_image='', signed_at_client=None, on_behalf_of='',
                   entreprise=None):
    """VNT61 — la signature CLIENT d'un avenant déjà accepté en interne :
    ``DevisSignature`` (empreinte du contenu) puis exemplaire PDF signé. AUCUN
    statut écrit, AUCUN ``devis_accepted`` / CAPI / webhook / e-mail.
    Idempotent : une 2e soumission n'écrit rien (la première fait foi). Rend
    la réponse ``avenant_signe.reponse_200`` du contrat ``proposal_accept``."""
    from django.db import transaction
    from apps.ventes import activity
    etat = etat_avenant(devis)
    if etat is not None and etat['a_signer']:
        with transaction.atomic():
            type(devis).objects.select_for_update().filter(pk=devis.pk).first()
            _cycle_vie._create_esign_record(
                devis=devis, nom=nom, ip=ip, user_agent=user_agent,
                consentement=consentement, signature_image=signature_image,
                signed_at_client=signed_at_client, on_behalf_of=on_behalf_of,
                entreprise=entreprise)
            activity.log_devis_note(
                devis, None, f'Avenant signé en ligne par {nom}'
                + (f' — IP {ip}' if ip else '') + '.')
        _cycle_vie._store_signed_pdf(devis=devis)
        etat = etat_avenant(devis)
    return {'detail': 'Avenant accepté. Merci !',
            'reference': devis.reference, 'statut': devis.statut,
            'accepte_par_nom': devis.accepte_par_nom,
            'avenant_signe': {'signe_le': (etat or {}).get('signe_le')}}

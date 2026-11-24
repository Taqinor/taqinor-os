"""Écritures du dossier contractuel (docs/contrats/conception.md § 5).

Toute écriture passe ici : préparer le dossier (cinq brouillons, idempotent),
l'annuler, modifier un brouillon, émettre, rouvrir, signer (sur place ou sur
papier), enregistrer le modèle de la société. Un refus d'état lève
``ErreurActe`` (``code`` + ``detail`` français, statut HTTP).

Garanties tenues : la société vient toujours du chantier (jamais d'une
requête) ; un acte n'est jamais supprimé ; un acte signé garde sa preuve ; le
dépôt en GED et le partage au portail sont best-effort (journalisés) — leur
panne ne fait jamais perdre une émission ni une signature.
"""
import base64
import binascii
import hashlib
import json
import logging
from datetime import datetime, time

from django.db import transaction
from django.utils import timezone

from . import contenu as K
from . import types as T

logger = logging.getLogger(__name__)

TAILLE_MAX_SIGNATURE = 2 * 1024 * 1024
PREFIXE_SIGNATURE = 'data:image/png;base64,'


class ErreurActe(Exception):
    """Refus d'un geste sur un acte : ``code`` du contrat d'API, ``detail``
    français, ``statut_http`` (409 refus d'état, 400 corps invalide)."""

    def __init__(self, code, detail, statut_http=409):
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.statut_http = statut_http


def _modele_acte():
    from ..models import ActeContractuel
    return ActeContractuel


# ── Préparer / annuler le dossier ───────────────────────────────────────────

def preparer_dossier(chantier, user=None):
    """Crée les cinq brouillons du chantier s'ils manquent, rétablit les actes
    annulés (chantier non annulé), aligne la référence des brouillons.
    Idempotent. Rend la liste des actes du dossier."""
    if chantier is None or chantier.company_id is None:
        return []
    from ..models import ActeContractuel
    user = user if getattr(user, 'pk', None) else None
    with transaction.atomic():
        for type_acte, variante, _rang in T.LIGNES_DOSSIER:
            reference = K.reference_acte(type_acte, chantier.reference,
                                         chantier.pk)
            acte, cree = ActeContractuel.objects.get_or_create(
                company=chantier.company, chantier=chantier, type=type_acte,
                variante=variante,
                defaults={'reference': reference, 'created_by': user})
            if cree:
                continue
            champs = []
            if acte.statut == T.ANNULE and not chantier.annule:
                acte.statut = acte.statut_avant_annulation or T.BROUILLON
                acte.statut_avant_annulation = ''
                acte.motif_annulation = ''
                champs += ['statut', 'statut_avant_annulation',
                           'motif_annulation']
            if acte.statut == T.BROUILLON and acte.reference != reference:
                acte.reference = reference
                champs.append('reference')
            if champs:
                acte.save(update_fields=champs + ['updated_at'])
                if acte.statut == T.EMIS:
                    remettre_au_portail(acte)
    return list(ActeContractuel.objects.filter(
        company=chantier.company, chantier=chantier).order_by('id'))


def annuler_dossier(chantier, motif=''):
    """Les actes non signés du chantier passent « annulé » (jamais
    supprimés, statut d'avant gardé) ; un acte signé reste signé. Rend le
    nombre d'actes annulés."""
    if chantier is None or chantier.company_id is None:
        return 0
    Acte = _modele_acte()
    nb = 0
    with transaction.atomic():
        qs = (Acte.objects.select_for_update()
              .filter(company=chantier.company, chantier=chantier)
              .exclude(statut__in=(T.SIGNE, T.ANNULE)))
        for acte in qs:
            etait_emis = acte.statut == T.EMIS
            acte.statut_avant_annulation = acte.statut
            acte.statut = T.ANNULE
            acte.motif_annulation = (motif or '')[:255]
            acte.save(update_fields=['statut', 'statut_avant_annulation',
                                     'motif_annulation', 'updated_at'])
            if etait_emis:
                retirer_du_portail(acte)
            nb += 1
    return nb


def remettre_au_portail(acte):
    """Un acte émis rétabli (ré-acceptation) est de nouveau partagé au
    portail du client. Best-effort."""
    if not acte.chantier.client_id:
        return
    for langue in T.LANGUES:
        document = document_ged(acte, langue)
        if document is None:
            continue
        try:
            from apps.ged import services as ged_services
            ged_services.partager_document_avec_client_portail(
                document, acte.chantier.client_id)
        except Exception:  # noqa: BLE001 — partage best-effort
            logger.exception('contrats : partage portail impossible '
                             '(acte %s, %s)', acte.pk, langue)


def retirer_du_portail(acte):
    """Retire du portail client le PDF (français et arabe) d'un acte qui
    n'est plus en vigueur (rouvert, annulé) : le client ne voit jamais un
    acte annulé ni deux livraisons contradictoires. Le document reste en GED
    (l'historique ne se supprime pas). Best-effort."""
    for langue in T.LANGUES:
        document = document_ged(acte, langue)
        if document is None:
            continue
        try:
            from apps.ged import services as ged_services
            ged_services.retirer_partage_client_portail(document)
        except Exception:  # noqa: BLE001 — partage best-effort
            logger.exception('contrats : retrait du portail impossible '
                             '(acte %s, %s)', acte.pk, langue)


# ── Gardes ──────────────────────────────────────────────────────────────────

def _verrouiller(acte):
    # ``of=('self',)`` : verrou sur l'acte seul — Postgres refuse FOR UPDATE
    # sur le côté nullable d'une jointure externe (devis, client).
    return (_modele_acte().objects.select_for_update(of=('self',))
            .select_related('chantier', 'chantier__devis',
                            'chantier__client', 'chantier__company')
            .get(pk=acte.pk))


def _garde_chantier(acte):
    if acte.chantier.annule or acte.statut == T.ANNULE:
        raise ErreurActe(T.CODE_CHANTIER_ANNULE, 'Chantier annulé')


def _garde_brouillon(acte):
    if acte.statut == T.SIGNE:
        raise ErreurActe(T.CODE_DEJA_SIGNE, 'Cet acte est déjà signé.')
    if acte.statut != T.BROUILLON:
        raise ErreurActe(T.CODE_ACTE_FIGE,
                         'Cet acte est émis : rouvrez-le pour le modifier.')


def jumelle_emise(acte):
    """La variante jumelle d'une livraison est-elle émise ou signée ?"""
    if acte.type != T.LIVRAISON:
        return False
    return _modele_acte().objects.filter(
        company=acte.company_id, chantier=acte.chantier_id, type=T.LIVRAISON,
        statut__in=(T.EMIS, T.SIGNE)).exclude(pk=acte.pk).exists()


def motif_refus_emission(acte, lecture, *, jumelle=None):
    """``(code, detail)`` qui empêche l'émission d'un brouillon, ou None —
    la même règle sert ``peut_emettre`` (``jumelle`` : déjà connue de
    l'appelant, sinon lue)."""
    from .rendu import composants as C
    vente = lecture.vente()
    if vente is None:
        return (T.CODE_SANS_DEVIS,
                "Ce chantier n'a pas de devis accepté : le prix et "
                "l'échéancier sont à préciser.")
    if acte.type == T.CLOTURE:
        reste = K.reste_du(vente)
        if reste and reste > 0:
            return (T.CODE_SOLDE_NON_REGLE,
                    f'Le prix n\'est pas réglé en totalité : '
                    f'{C.montant(reste)} restent dus. Enregistrez le paiement '
                    f'du solde avant d\'émettre le quitus.')
    manque = K.paiement_suppose(acte, vente)
    if manque:
        # Signée, cette version vaut reçu contre la société : jamais sur une
        # supposition.
        return (T.CODE_PAIEMENT_NON_ENREGISTRE,
                f"Cette version dit que {C.montant(manque['cible'])} sont "
                f"réglés, mais l'ERP n'a enregistré que "
                f"{C.montant(manque['paye'])} de paiements. Enregistrez les "
                f"paiements reçus avant de l'émettre, ou émettez la version "
                f"« reste à régler ».")
    if jumelle_emise(acte) if jumelle is None else jumelle:
        return (T.CODE_ETAT,
                "L'autre version de la livraison est déjà émise : rouvrez-la "
                "d'abord.")
    figes = K.montants_figes(acte, lecture)
    if figes:
        return (T.CODE_MONTANT_FIGE, K.message_montants_figes(figes))
    return None


# ── Modifier ────────────────────────────────────────────────────────────────

def modifier(acte, surcharges, user=None, langue='fr'):
    """Applique des personnalisations à un BROUILLON : chaque section reçue
    remplace la sienne, ``None`` la remet au défaut. Les articles et le quitus
    reçus sont la liste que l'écran affichait, corrigée : la correction est
    rejouée sur les gabarits de ce qui était affiché
    (``contenu.personnaliser``), pour qu'un texte corrigé ne fige jamais une
    valeur de la vente et qu'un article non touché suive les options."""
    try:
        propre = K.valider_surcharges(acte.type, surcharges, langue)
    except K.ContenuInvalide as exc:
        raise ErreurActe(T.CODE_CONTENU_INVALIDE, str(exc), 400)
    with transaction.atomic():
        acte = _verrouiller(acte)
        _garde_chantier(acte)
        _garde_brouillon(acte)
        champ = 'surcharges_ar' if langue == 'ar' else 'surcharges'
        setattr(acte, champ, K.personnaliser(acte, propre, langue))
        acte.save(update_fields=[champ, 'updated_at'])
    return acte


# ── Émettre / rouvrir ───────────────────────────────────────────────────────

def _json_canonique(contenu):
    return json.dumps(contenu, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':')).encode('utf-8')


def empreinte(contenu):
    """SHA-256 du JSON canonique d'un contenu figé (clés triées)."""
    return hashlib.sha256(_json_canonique(contenu or {})).hexdigest()


def emettre(acte, user=None):
    """Brouillon → émis : fige le contenu français et sa traduction arabe,
    rend et dépose les deux PDF en GED, les partage au portail du client.
    Rend ``(acte, avertissements)``."""
    with transaction.atomic():
        if acte.type == T.LIVRAISON:
            # Les deux variantes verrouillées (ordre stable) AVANT le
            # contrôle de la jumelle : deux émissions simultanées ne peuvent
            # pas passer chacune de leur côté.
            list(_modele_acte().objects.select_for_update()
                 .filter(company=acte.company_id, chantier=acte.chantier_id,
                         type=T.LIVRAISON)
                 .order_by('pk').values_list('pk', flat=True))
        acte = _verrouiller(acte)
        _garde_chantier(acte)
        _garde_brouillon(acte)
        lecture = K.Lecture(acte.chantier)
        refus = motif_refus_emission(acte, lecture)
        if refus:
            raise ErreurActe(*refus)
        acte.contenu = K.construire_contenu(acte, 'fr', lecture)
        acte.contenu_ar = K.construire_contenu(acte, 'ar', lecture)
        acte.statut = T.EMIS
        acte.emis_le = timezone.now()
        acte.emis_par = user if getattr(user, 'pk', None) else None
        acte.save(update_fields=['contenu', 'contenu_ar', 'statut', 'emis_le',
                                 'emis_par', 'updated_at'])
    return acte, deposer_pdfs(acte, user)


def rouvrir(acte, user=None):
    """Émis (non signé) → brouillon ; la ré-émission portera ``version + 1``."""
    from ..models import ActeContractuel
    with transaction.atomic():
        acte = (ActeContractuel.objects.select_for_update(of=('self',))
                .select_related('chantier').get(pk=acte.pk))
        _garde_chantier(acte)
        if acte.statut == T.SIGNE:
            raise ErreurActe(T.CODE_DEJA_SIGNE,
                             'Cet acte est signé : il ne se rouvre pas.')
        if acte.statut != T.EMIS:
            raise ErreurActe(T.CODE_ETAT, "Cet acte n'est pas émis.")
        acte.statut = T.BROUILLON
        acte.contenu = None
        acte.contenu_ar = None
        acte.emis_le = None
        acte.emis_par = None
        acte.version += 1
        acte.save(update_fields=['statut', 'contenu', 'contenu_ar', 'emis_le',
                                 'emis_par', 'version', 'updated_at'])
        retirer_du_portail(acte)
    return acte


# ── Signer ──────────────────────────────────────────────────────────────────

def _valider_trace(signature):
    if not isinstance(signature, str) or not signature.startswith(
            PREFIXE_SIGNATURE):
        raise ErreurActe(T.CODE_CONTENU_INVALIDE,
                         'Signature : image PNG attendue (data:image/png;base64,…).',
                         400)
    if len(signature) > TAILLE_MAX_SIGNATURE:
        raise ErreurActe(T.CODE_CONTENU_INVALIDE,
                         'Signature : image trop lourde.', 400)
    try:
        octets = base64.b64decode(signature[len(PREFIXE_SIGNATURE):],
                                  validate=True)
    except (binascii.Error, ValueError):
        raise ErreurActe(T.CODE_CONTENU_INVALIDE,
                         'Signature : image illisible.', 400)
    if not octets.startswith(b'\x89PNG'):
        raise ErreurActe(T.CODE_CONTENU_INVALIDE,
                         'Signature : image PNG attendue.', 400)


def _valider_nom(nom):
    nom = (nom or '').strip() if isinstance(nom, str) else ''
    if not nom:
        raise ErreurActe(T.CODE_CONTENU_INVALIDE,
                         'Le nom du signataire est obligatoire.', 400)
    return nom[:150]


def _garde_signature(acte):
    _garde_chantier(acte)
    if acte.statut == T.SIGNE:
        raise ErreurActe(T.CODE_DEJA_SIGNE, 'Cet acte est déjà signé.')
    if acte.type == T.CLOTURE:
        raise ErreurActe(T.CODE_ETAT,
                         "Le quitus se remet au client : il ne se signe pas.")
    if acte.statut != T.EMIS:
        raise ErreurActe(T.CODE_ETAT,
                         "Émettez l'acte avant de le faire signer.")


def _poser_signature(acte, *, nom, image, mode, signe_le, user, ip, agent,
                     lieu=''):
    fr = acte.contenu or {}
    ar = acte.contenu_ar or {}
    sha = empreinte(fr)
    sha_ar = empreinte(ar) if ar else ''
    jour = timezone.localtime(signe_le).date().isoformat()
    trace = (f' · empreinte {sha[:16]}' if mode == 'sur_place'
             else f' · signé sur papier · empreinte {sha[:16]}')
    signature = {'image': image or None, 'nom': nom, 'signe_le': jour,
                 'preuve': trace}
    for contenu in (fr, ar):
        if not contenu:
            continue
        contenu.setdefault('signatures', {})['client'] = dict(signature)
        if lieu:
            contenu['lieu'] = lieu
    acte.contenu = fr
    acte.contenu_ar = ar or None
    acte.statut = T.SIGNE
    acte.signe_le = signe_le
    acte.signataire_nom = nom
    acte.signature_client = image or ''
    acte.mode_signature = mode
    acte.preuve = {
        'empreinte_sha256': sha, 'empreinte_sha256_ar': sha_ar,
        'ip': (ip or '')[:64], 'agent': (agent or '')[:300],
        'utilisateur_id': getattr(user, 'pk', None), 'mode': mode,
        'enregistre_le': timezone.now().isoformat(),
    }
    acte.save(update_fields=[
        'contenu', 'contenu_ar', 'statut', 'signe_le', 'signataire_nom',
        'signature_client', 'mode_signature', 'preuve', 'updated_at'])


def signer_sur_place(acte, *, signature_client, signataire_nom, lieu='',
                     user=None, ip='', agent=''):
    """Émis → signé, signature tracée sur place. Rend
    ``(acte, avertissements)``."""
    _valider_trace(signature_client)
    nom = _valider_nom(signataire_nom)
    lieu = (lieu or '').strip()[:120] if isinstance(lieu, str) else ''
    with transaction.atomic():
        acte = _verrouiller(acte)
        _garde_signature(acte)
        _poser_signature(acte, nom=nom, image=signature_client,
                         mode='sur_place', signe_le=timezone.now(), user=user,
                         ip=ip, agent=agent, lieu=lieu)
    return acte, deposer_pdfs(acte, user)


def marquer_signe_papier(acte, *, signataire_nom, signe_le=None, user=None,
                         ip='', agent=''):
    """Émis → signé, signature sur papier (date du jour par défaut). Rend
    ``(acte, avertissements)``."""
    nom = _valider_nom(signataire_nom)
    quand = timezone.now()
    if signe_le not in (None, ''):
        jour = K._date(signe_le) if isinstance(signe_le, str) else None
        if jour is None or len(signe_le) != 10:
            raise ErreurActe(T.CODE_CONTENU_INVALIDE,
                             'Date de signature : AAAA-MM-JJ attendue.', 400)
        if jour > timezone.localdate():
            raise ErreurActe(T.CODE_CONTENU_INVALIDE,
                             'La date de signature ne peut pas être future.',
                             400)
        quand = timezone.make_aware(datetime.combine(jour, time(12, 0)))
    with transaction.atomic():
        acte = _verrouiller(acte)
        _garde_signature(acte)
        _poser_signature(acte, nom=nom, image='', mode='papier',
                         signe_le=quand, user=user, ip=ip, agent=agent)
    return acte, deposer_pdfs(acte, user)


# ── GED et portail ──────────────────────────────────────────────────────────

def source_ged(acte, langue='fr'):
    gabarit = T.SOURCE_GED_AR if langue == 'ar' else T.SOURCE_GED
    return gabarit.format(type=acte.type)


def document_ged(acte, langue='fr'):
    """Document GED de l'acte (hors corbeille) ou None."""
    try:
        from apps.ged import services as ged_services
        document = ged_services.find_document_by_source(
            acte.company, source_type=source_ged(acte, langue),
            source_id=acte.pk)
    except Exception:  # noqa: BLE001 — lecture GED best-effort
        logger.warning('contrats : lecture GED impossible (acte %s)',
                       acte.pk, exc_info=True)
        return None
    if document is None or getattr(document, 'supprime_le', None):
        return None
    return document


def deposer_pdfs(acte, user=None):
    """Rend les PDF figés (français et arabe), les dépose en GED (nouvelle
    version si le contenu a changé) et les partage au portail du client.
    Best-effort : rend la liste des avertissements (vide si tout est passé)."""
    from .rendu import pdf_de
    avertissements = []
    for langue, contenu in (('fr', acte.contenu), ('ar', acte.contenu_ar)):
        if not contenu:
            continue
        suffixe = ' (traduction arabe)' if langue == 'ar' else ''
        try:
            pdf = pdf_de(contenu)
        except Exception:  # noqa: BLE001 — l'acte reste émis / signé
            logger.exception('contrats : rendu PDF impossible (acte %s, %s)',
                             acte.pk, langue)
            avertissements.append(
                f'Le PDF{suffixe} n\'a pas pu être produit : réessayez le '
                f'téléchargement.')
            continue
        avertissements += _deposer_langue(acte, langue, contenu, pdf, user)
    return avertissements


def _deposer_langue(acte, langue, contenu, pdf, user=None):
    """Dépose le PDF figé d'une langue en GED (marqué de la version, du statut
    et de l'empreinte du contenu) et le partage au portail. Best-effort :
    rend les avertissements."""
    from apps.documents.builders import GED_CABINET_CHANTIERS
    chantier = acte.chantier
    suffixe = ' (traduction arabe)' if langue == 'ar' else ''
    try:
        from apps.ged import services as ged_services
        nom = f'{T.TITRES[acte.type]} {acte.reference}{suffixe}'
        fichier = acte.reference + ('-ar' if langue == 'ar' else '')
        document, _cree = ged_services.deposit_document(
            company=acte.company, nom=nom,
            source_type=source_ged(acte, langue), source_id=acte.pk,
            contenu_bytes=pdf, mime='application/pdf',
            filename=f'{fichier}.pdf', cabinet_nom=GED_CABINET_CHANTIERS,
            folder_nom=chantier.reference or f'Chantier {chantier.pk}',
            description='Acte du dossier contractuel, figé.',
            created_by=user if getattr(user, 'pk', None) else None,
            versionner_si_modifie=True)
        document.custom_data = {
            **(document.custom_data or {}),
            'acte_statut': acte.statut, 'acte_version': acte.version,
            'empreinte_sha256': empreinte(contenu), 'langue': langue}
        document.save(update_fields=['custom_data'])
    except Exception:  # noqa: BLE001 — l'acte reste émis / signé
        logger.exception('contrats : dépôt GED impossible (acte %s, %s)',
                         acte.pk, langue)
        return [f'Le PDF{suffixe} n\'a pas pu être rangé dans les documents '
                f'du chantier : l\'acte reste '
                f'{acte.get_statut_display().lower()}.']
    if chantier.client_id:
        try:
            ged_services.partager_document_avec_client_portail(
                document, chantier.client_id)
        except Exception:  # noqa: BLE001 — partage best-effort
            logger.exception('contrats : partage portail impossible '
                             '(acte %s, %s)', acte.pk, langue)
            return [f'Le PDF{suffixe} n\'a pas pu être partagé sur l\'espace '
                    f'du client.']
    return []


def document_a_jour(document, acte, contenu):
    """Le document GED porte-t-il le PDF de CE contenu figé (même empreinte,
    même version, même statut) ? Un dépôt raté laisse en GED l'ancienne
    version : elle n'est alors jamais servie."""
    marque = getattr(document, 'custom_data', None) or {}
    return (marque.get('empreinte_sha256') == empreinte(contenu)
            and marque.get('acte_version') == acte.version
            and marque.get('acte_statut') == acte.statut)


def pdf_de_l_acte(acte, langue='fr'):
    """Octets PDF servis. Acte émis ou signé : le PDF rangé en GED s'il est
    bien celui du contenu figé ; sinon (dépôt raté, stockage muet) le contenu
    figé est re-rendu et le dépôt retenté. Brouillon : le rendu vivant."""
    from .rendu import pdf_de
    contenu = (acte.contenu_ar if langue == 'ar' else acte.contenu) \
        if acte.statut in (T.EMIS, T.SIGNE) else None
    if not contenu:
        return pdf_de(K.contenu_de(acte, langue))
    document = document_ged(acte, langue)
    if document is not None and document_a_jour(document, acte, contenu):
        from apps.documents.builders import _octets_en_vigueur
        try:
            octets = _octets_en_vigueur(document)
        except Exception:  # noqa: BLE001 — repli : rendu du contenu figé
            logger.warning('contrats : octets GED illisibles (acte %s)',
                           acte.pk, exc_info=True)
            octets = None
        if octets:
            return octets
    pdf = pdf_de(contenu)
    if document is None or not document_a_jour(document, acte, contenu):
        _deposer_langue(acte, langue, contenu, pdf)
    return pdf


# ── Modèle de la société ────────────────────────────────────────────────────

#: Sections qui ne passent jamais au modèle : elles décrivent CE chantier.
_HORS_MODELE = frozenset({'lieu', 'date_document', 'livraison', 'reception',
                          'conditions_particulieres', 'reserves'})


def _valeurs_du_chantier(contenus):
    """Textes propres à ce chantier (montants, références, noms, dates) : un
    texte qui en cite un ne devient jamais un modèle de la société."""
    from .rendu import composants as C
    valeurs = set()
    for contenu in contenus:
        langue = contenu.get('langue', 'fr')
        montants = [contenu['prix'].get('total_ttc'), contenu['prix'].get('total_ht')]
        montants += [t.get('montant_ttc') for t in contenu.get('echeancier') or []]
        montants += [v for k, v in (contenu.get('paiement') or {}).items()
                     if k not in T.CLES_PAIEMENT_TEXTE and isinstance(v, str)]
        for m in montants:
            if K._d(m):
                valeurs.add(C.nombre(m, 2))
        for v in (contenu['reference'], contenu['chantier'].get('reference'),
                  contenu['chantier'].get('devis_reference'),
                  contenu['client'].get('nom_complet'),
                  C.date_longue(contenu['chantier'].get('devis_accepte_le'),
                                langue=langue),
                  C.date_longue((contenu.get('delais') or {}).get(
                      'date_limite'), langue=langue)):
            if v:
                valeurs.add(v)
    return valeurs


def _cite(texte, valeurs):
    return any(v in str(texte) for v in valeurs)


def _modele_de_langue(acte, langue, valeurs, ignores):
    surcharges = (acte.surcharges_ar if langue == 'ar' else acte.surcharges) or {}
    sortie = {}
    effectifs = None
    for section, valeur in surcharges.items():
        if section in _HORS_MODELE:
            continue
        if section in ('articles', 'quitus') and effectifs is None:
            # Les textes effectifs, en gabarits contre les textes par
            # défaut : les valeurs de ce chantier y sont des repères ; un
            # texte dont le TEXTE TAPÉ cite encore ce chantier n'est pas
            # repris.
            effectifs = K.textes_pour_modele(acte, langue)
        if section == 'articles':
            gardes = []
            for e in effectifs['articles']:
                if 'paragraphes' in e and _cite(K.texte_litteral(
                        [e['titre']] + e['paragraphes']), valeurs):
                    titre = effectifs['titres'].get(e['cle']) or e['cle']
                    ignores.append(f'article « {titre} »')
                    if e.get('base'):
                        gardes.append({'cle': e['cle']})
                    continue
                gardes.append(e)
            sortie[section] = gardes
        elif section == 'quitus':
            quitus = effectifs['quitus']
            if quitus is None:
                continue
            if _cite(K.texte_litteral(quitus), valeurs):
                ignores.append(T.LIBELLES_SECTIONS.get(section, section))
                continue
            sortie[section] = quitus
        elif section == 'garanties':
            pose = [g for g in valeur if g.get('cle') == 'installation']
            if pose:
                sortie[section] = pose
        elif section == 'delais':
            if valeur.get('detail'):
                sortie[section] = {'detail': valeur['detail']}
        elif section in ('titre', 'conseils_intro', 'entretien', 'constats',
                         'conseils'):
            if _cite(json.dumps(valeur, ensure_ascii=False), valeurs):
                ignores.append(T.LIBELLES_SECTIONS.get(section, section))
                continue
            sortie[section] = valeur
        elif section in ('echeancier_textes', 'paiement'):
            sortie[section] = valeur
        elif langue == 'fr':
            sortie[section] = valeur
    return sortie


def enregistrer_modele(acte, user=None):
    """Les sections de texte de l'acte deviennent le modèle de la société pour
    ce type d'acte (Directeur). Un texte qui cite ce chantier (montant,
    référence, nom, date) n'est pas repris. Rend le message à afficher."""
    from ..models import ModeleActe
    lecture = K.Lecture(acte.chantier)
    contenus = [K.construire_contenu(acte, 'fr', lecture),
                K.construire_contenu(acte, 'ar', lecture)]
    valeurs = _valeurs_du_chantier(contenus)
    ignores = []
    fr = _modele_de_langue(acte, 'fr', valeurs, ignores)
    ar = _modele_de_langue(acte, 'ar', valeurs, ignores)
    ModeleActe.objects.update_or_create(
        company=acte.company, type=acte.type,
        defaults={'surcharges': fr, 'surcharges_ar': ar,
                  'updated_by': user if getattr(user, 'pk', None) else None})
    message = (f'Modèle enregistré : les prochains actes « '
               f'{T.TITRES[acte.type]} » partiront de ces textes.')
    if ignores:
        message += (' Non repris, car ils citent ce chantier : '
                    + ', '.join(dict.fromkeys(ignores)) + '.')
    return message

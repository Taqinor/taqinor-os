"""SPL138 — l'envoi du devis (lien client, courriel, WhatsApp, PDF partagé,
lecture client, supérieur), déplacement pur depuis ``views/devis.py`` :
corps octet-identiques, routes inchangées.

Les imports function-locaux des corps restent dans les corps (les
``mock.patch`` ``apps.ventes.services.*`` / ``apps.ventes.utils.pdf.*``
n'interceptent qu'ainsi).
"""
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from ..models import Devis
from authentication.permissions import IsAnyRole, IsResponsableOrAdmin
from ..utils.client_links import chemin_proposition


def _gamme_envoi_payload(devis):
    """GAMME — bloc « envoi à la carte » pour la modale d'envoi de l'ERP.

    ``None`` quand le devis n'appartient pas à une paire de gammes : la modale
    d'envoi reste alors strictement celle d'aujourd'hui. Sinon : le libellé de
    CHAQUE gamme, laquelle est recommandée et le mode d'envoi courant (défaut
    « les_deux » — décision fondateur)."""
    from ..services import gamme_envoi, gamme_info, gamme_soeur
    soeur = gamme_soeur(devis)
    if soeur is None:
        return None
    ici, la_soeur = gamme_info(devis), gamme_info(soeur)
    recommandee = (la_soeur.get('nom') if la_soeur.get('recommandee')
                   else ici.get('nom'))
    return {
        'envoi': gamme_envoi(devis),
        'nom': ici.get('nom') or '',
        'soeur_nom': la_soeur.get('nom') or '',
        'soeur_reference': soeur.reference,
        'recommandee': recommandee or '',
    }


def _appliquer_gamme_envoi(devis, mode):
    """GAMME — applique le mode d'envoi demandé (no-op hors paire de gammes)."""
    from ..services import regler_envoi_gamme
    return regler_envoi_gamme(devis, mode)


class _RemiseEnvoiRefusee(APIException):
    """QJR539 — 400 ``{detail}`` : garde de remise T17 d'un envoi."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = 'remise_non_approuvee'


def _exiger_remise_envoi(devis, user, *, enregistrer=True):
    """QJR539 — garde de remise T17 d'un VRAI envoi (lien client, courriel,
    aperçu/commit WhatsApp), appelée AVANT tout effet de bord ; lève
    ``_RemiseEnvoiRefusee`` (400 ``{detail}``). Ne juge que les devis encore
    envoyables (brouillon, envoyé). ``enregistrer=False`` : un aperçu n'écrit
    pas l'approbation implicite d'un admin."""
    from ..services import RemiseNonApprouvee, exiger_approbation_remise
    if devis.statut not in ('brouillon', 'envoye'):
        return
    try:
        exiger_approbation_remise(devis, user, enregistrer=enregistrer)
    except RemiseNonApprouvee as erreur:
        raise _RemiseEnvoiRefusee(erreur.message)


class DevisEnvoiActionsMixin:
    """SPL138 — actions d'envoi de ``DevisViewSet`` (mixin, aucune base)."""

    @action(detail=True, methods=['post'], url_path='share-link',
            permission_classes=[IsResponsableOrAdmin])
    def share_link(self, request, pk=None):
        """B2 — frappe (ou réutilise) un lien public de proposition pour ce
        devis. Permet au site de (re)générer le lien de proposition d'un devis
        existant lors de la livraison. Le devis est déjà borné à la société de
        l'utilisateur par ``get_queryset`` (autre société → 404).

        L-NIV (24/08/2026) — ``niveau`` (« standard » | « confiance ») et
        ``otp_lecture`` (bool) sont optionnels dans le corps : le commercial
        RÉVOQUE ou change le niveau d'un lien EXISTANT sans jamais régénérer
        le jeton (le lien déjà envoyé au client continue de fonctionner).
        Absents du corps → valeurs du lien inchangées (déjà posées, ou les
        défauts du modèle sur un lien fraîchement créé).

        L-SECT (24/08/2026) — ``sections`` (dict {clé: bool}) dit CE QUE le
        client reçoit sur sa page devis, choisi dans le dialogue « Envoyer au
        client ». Mêmes garanties : optionnel, révocable, jeton inchangé.

        QJ-FUNNEL (fondateur 09/09/2026 — « le lead reste en Contacté, il ne
        passe jamais à Devis envoyé ») — ``envoi: true`` (optionnel) dit que
        CE POST est un ENVOI au client (copier le lien pour l'envoyer,
        WhatsApp par devis) et non un aperçu interne ni un simple réglage
        niveau/OTP/sections : le devis passe alors brouillon → « envoyé » via
        ``mark_devis_sent`` — LE chemin unique U4/QJ14, déjà celui de l'email
        et de la barre WhatsApp multi-devis — dont l'événement ``devis_sent``
        avance le funnel du lead vers QUOTE_SENT et démarre la cadence
        après-devis. Idempotent (un devis déjà envoyé/accepté ne bouge pas) ;
        absent/false → comportement d'avant, byte-identique."""
        from ..models import ShareLink
        devis = self.get_object()
        # QJR539 — garde T17 AVANT tout effet d'un ENVOI (gamme, mint, statut).
        if request.data.get('envoi'):
            _exiger_remise_envoi(devis, request.user)
        # GAMME — le mode d'envoi (« seule » / « les_deux ») accompagne le lien
        # quand le vendeur le précise ; absent du corps → mode déjà posé.
        _appliquer_gamme_envoi(devis, request.data.get('gamme_envoi'))
        # QJ-FUNNEL — AVANT le mint : si l'envoi est refusé, l'erreur nommée
        # part au commercial et aucun lien ne sort de ce POST.
        if request.data.get('envoi'):
            from ..services import mark_devis_sent
            mark_devis_sent(devis=devis, user=request.user)
        link = ShareLink.for_devis(devis)
        # L-NIV — ne touche jamais au jeton : simple mise à jour de champs sur
        # le lien déjà résolu (créé ou réutilisé) ci-dessus.
        champs_modifies = []
        niveau = request.data.get('niveau')
        if niveau is not None:
            if niveau not in dict(ShareLink.NIVEAU_CHOICES):
                return Response(
                    {'detail': "niveau invalide (attendu : 'standard' ou "
                               "'confiance')."},
                    status=status.HTTP_400_BAD_REQUEST)
            if link.niveau != niveau:
                link.niveau = niveau
                champs_modifies.append('niveau')
        if 'otp_lecture' in request.data:
            otp_lecture = bool(request.data.get('otp_lecture'))
            if link.otp_lecture != otp_lecture:
                link.otp_lecture = otp_lecture
                champs_modifies.append('otp_lecture')
        # L-SECT (24/08/2026) — sections servies au client, choisies dans le
        # dialogue « Envoyer au client ». Whitelist STRICTE de clés + valeurs
        # BOOLÉENNES seulement : rien d'autre n'entre en base. Absent du corps
        # → sections du lien inchangées (comportement d'aujourd'hui).
        if 'sections' in request.data:
            brut = request.data.get('sections')
            if not isinstance(brut, dict):
                return Response(
                    {'detail': 'sections invalide (objet attendu).'},
                    status=status.HTTP_400_BAD_REQUEST)
            inconnues = sorted(set(brut) - set(ShareLink.SECTIONS_CLES))
            if inconnues:
                return Response(
                    {'detail': 'sections invalide — clés inconnues : '
                               + ', '.join(inconnues) + '.'},
                    status=status.HTTP_400_BAD_REQUEST)
            non_bool = sorted(k for k, v in brut.items() if not isinstance(v, bool))
            if non_bool:
                return Response(
                    {'detail': 'sections invalide — valeurs booléennes '
                               'attendues : ' + ', '.join(non_bool) + '.'},
                    status=status.HTTP_400_BAD_REQUEST)
            if (link.sections or {}) != brut:
                link.sections = brut
                champs_modifies.append('sections')
        if champs_modifies:
            link.save(update_fields=champs_modifies)
        # L-INTPREV (fondateur 25/08/2026) — second lien « aperçu interne » :
        # même page, même construction de chemin (``chemin_proposition``),
        # jeton différent. ``jeton_interne_effectif`` génère paresseusement
        # celui d'un très étroit lien préexistant qui aurait échappé au
        # backfill de la migration 0103 (garde défensive — le cas normal
        # porte déjà un jeton interne, posé par le default du champ ou par ce
        # backfill).
        token_interne = link.jeton_interne_effectif()
        return Response(
            {'token': link.token, 'path': chemin_proposition(devis, link.token),
             'token_interne': token_interne,
             'path_interne': chemin_proposition(devis, token_interne),
             'gamme': _gamme_envoi_payload(devis),
             'niveau': link.niveau, 'otp_lecture': link.otp_lecture,
             'sections': link.sections or {}},
            status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='envoyer-email',
            permission_classes=[IsResponsableOrAdmin])
    def envoyer_email(self, request, pk=None):
        """QJ14 — Envoie la proposition (PDF premium + lien tokenisé) au client
        par email, consigne l'envoi dans EmailLog et marque le devis « envoyé »
        via mark_devis_sent (règle #4 — seul chemin de transition brouillon→envoyé).

        Body (tous optionnels) :
          - ``to_email``  : adresse destinataire (défaut : client.email)
          - ``sujet``     : objet de l'email (défaut : modèle FR)
          - ``corps``     : corps de l'email (défaut : modèle FR)
          - ``pdf_mode``  : « full » | « onepage » (défaut : « full »)

        Idempotent : un devis déjà « envoyé » (ou plus avancé) ne régresse pas
        — l'email est tout de même envoyé mais mark_devis_sent ne re-stampe pas.

        Retourne l'EmailLog id + statut + le statut courant du devis.
        """
        from ..models import ShareLink
        from ..services import mark_devis_sent
        from ..quote_engine import clean_pdf_options, generate_premium_devis_pdf
        from ..utils.pdf import download_pdf

        devis = self.get_object()
        # QJR539 — garde T17 AVANT tout effet (gamme, PDF, lien, `_send`).
        _exiger_remise_envoi(devis, request.user)
        to_email = (request.data.get('to_email') or '').strip() or None
        sujet = (request.data.get('sujet') or '').strip() or None
        corps = (request.data.get('corps') or '').strip() or None
        pdf_mode = (request.data.get('pdf_mode') or 'full').strip()
        # GAMME — mode d'envoi « à la carte », réglé au moment de l'envoi.
        # UN PDF = UNE GAMME : la pièce jointe reste le PDF de CE devis, jamais
        # un PDF fusionné des deux gammes (chaque gamme a le sien).
        _appliquer_gamme_envoi(devis, request.data.get('gamme_envoi'))
        # QJR668 — la pièce jointe est rendue AVANT ``mark_devis_sent`` : les
        # clauses/CGV de l'affaire sont gelées dès maintenant pour y figurer.
        if devis.statut == devis.Statut.BROUILLON:
            from ..domain.envoi import figer_clauses_devis
            figer_clauses_devis(devis)

        # Génère le PDF premium (persist=False — rendu à la volée, pas de
        # remplacement du fichier stocké : le moteur rend seulement).
        attachment = None
        attachment_name = None
        # ADEV68 — le lien de proposition est créé AVANT le rendu et son jeton
        # passé au moteur : la pièce jointe d'un devis encore brouillon (rendue
        # juste avant ``mark_devis_sent``) imprime CE lien, alors que le
        # moteur ne frappe plus de lien pour un brouillon.
        link = ShareLink.for_devis(devis)
        try:
            opts = clean_pdf_options({'pdf_mode': pdf_mode,
                                      'share_token': link.token})
            key = generate_premium_devis_pdf(devis.id, opts, persist=False)
            attachment = download_pdf(key)
            attachment_name = f'Devis_{devis.reference}.pdf'
        except Exception:  # noqa: BLE001 — PDF indisponible n'empêche pas l'envoi
            pass

        # Ajoute le lien de proposition tokenisé dans le corps si fourni.
        proposal_url = chemin_proposition(devis, link.token)
        # ZSAL5 — gabarit ``envoi_devis`` (EmailTemplate) : sujet/corps
        # explicitement fournis dans le corps de requête restent prioritaires
        # (comportement historique) ; sinon on rend le gabarit effectif de la
        # société (défaut = texte historique byte-identique tant que non édité).
        if not sujet or not corps:
            from apps.parametres.models_email import EmailTemplate
            client = devis.client
            nom_client = ''
            civilite = ''
            if client:
                nom_client = f"{client.nom} {getattr(client, 'prenom', '') or ''}".strip()
                civilite = getattr(client, 'civilite', '') or ''
            # ``{nom}`` porte le salut complet ("Bonjour X," / "Bonjour,")
            # pour préserver EXACTEMENT le rendu historique par défaut.
            salut = f'Bonjour {nom_client},' if nom_client else 'Bonjour,'
            # XSAL17 — {lien_rdv} : résolu paresseusement, jamais de
            # BookingLink créé si le gabarit effectif ne référence pas le
            # placeholder (évite un jeton inutile à chaque envoi de devis).
            lien_rdv = ''
            if devis.lead_id and '{lien_rdv}' in EmailTemplate.get_template(
                    devis.company, 'envoi_devis')['corps']:
                try:
                    from apps.crm.services import public_booking_url
                    lien_rdv = public_booking_url(devis.lead, request=request)
                except Exception:  # noqa: BLE001 — jamais bloquer l'envoi
                    lien_rdv = ''
            rendu = EmailTemplate.render(
                devis.company, 'envoi_devis',
                civilite=civilite, nom=salut,
                reference=devis.reference or '', lien=proposal_url,
                validite=(devis.date_validite.strftime('%d/%m/%Y')
                          if devis.date_validite else ''),
                lien_rdv=lien_rdv,
            )
            sujet = sujet or rendu['sujet']
            corps = corps or rendu['corps']

        # Envoi + EmailLog via le service centralisé. attach_pdf=False car on
        # a déjà le contenu — on passe attachment/attachment_name directement.
        from ..email_service import _send, _from_email, _chatter_note
        from ..models import EmailLog  # noqa: F811 — local import shadows class-level

        client = devis.client
        dest = (to_email or (getattr(client, 'email', '') or '')).strip()
        reference = devis.reference or ''
        if not sujet:
            sujet = f'Votre devis {reference}'

        log = EmailLog(
            company=devis.company,
            direction=EmailLog.Direction.SORTANT,
            client=client,
            devis=devis,
            to_email=dest, from_email=_from_email(),
            sujet=(sujet or '')[:300], corps=corps,
            reference=reference[:80],
            piece_jointe=(attachment_name or '')[:255],
            created_by=request.user if getattr(request.user, 'is_authenticated', False) else None,
        )

        if not dest:
            log.statut = EmailLog.Statut.ECHEC
            log.erreur = 'Aucune adresse email destinataire.'
            log.save()
            return Response(
                {'detail': log.erreur, 'log_id': log.id, 'statut': 'echec'},
                status=status.HTTP_400_BAD_REQUEST)

        ok, err = _send(dest, sujet, corps, attachment, attachment_name)
        log.statut = EmailLog.Statut.ENVOYE if ok else EmailLog.Statut.ECHEC
        log.erreur = err
        log.save()

        etat = 'envoyé' if ok else "échec d'envoi"
        _chatter_note(devis, f"Email du devis {reference} — {etat} (à {dest}).", request.user)

        # QJR519 — un email en ÉCHEC ne marque JAMAIS le devis envoyé (ni
        # date_envoi, ni devis_sent → funnel, ni cadence) : 502 explicite,
        # EmailLog ECHEC et note chatter ci-dessus conservés.
        if not ok:
            devis.refresh_from_db(fields=['statut'])
            return Response({
                'detail': f'Échec envoi email : {err}',
                'log_id': log.id,
                'email_statut': log.statut,
                'devis_statut': devis.statut,
            }, status=status.HTTP_502_BAD_GATEWAY)

        # Marque le devis « envoyé » via le seul chemin autorisé (règle #4).
        # Idempotent : un devis déjà envoyé/accepté/refusé n'est pas régressé.
        mark_devis_sent(devis=devis, user=request.user)

        # ZSAL5 — reflet de l'envoi dans le chatter du LEAD lié (best-effort,
        # jamais un import des models crm depuis ventes).
        if ok and devis.lead_id:
            try:
                from apps.crm.services import noter_devis_envoye
                noter_devis_envoye(reference, devis.lead)
            except Exception:  # noqa: BLE001 — best-effort, ne bloque jamais l'envoi
                pass

        return Response({
            'detail': f'Email envoyé à {dest}.' if ok else f'Échec envoi email : {err}',
            'log_id': log.id,
            'email_statut': log.statut,
            'devis_statut': devis.statut,
            'proposal_path': proposal_url,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='lecture-client',
            permission_classes=[IsResponsableOrAdmin])
    def lecture_client(self, request, pk=None):
        """ANALYT1 (audit item 64, 26/08/2026) — « Lecture par le client » :
        combien de VISITES DISTINCTES chaque section de la proposition
        publique a reçues, et l'alerte de friction si une section a été
        RELUE au-delà du seuil (``ShareLink.friction_alert``).

        Réservé responsable/admin (VX199 — voir ``get_permissions`` ci-
        dessus) : ce sont des analytics INTERNES (temps/visites du client sur
        sa propre proposition) — jamais montrées au client, jamais une
        promesse de conversion, juste un signal « ce client relit, un appel
        peut aider ». Lecture PURE sur le ``ShareLink`` le plus récent du
        devis, borné à sa société (déjà scopée par ``get_object()``).
        ``sections``/``friction`` vides ⇒ aucun beacon reçu pour ce devis."""
        from ..models import ShareLink

        devis = self.get_object()
        link = (ShareLink.objects
                .filter(devis=devis, company=devis.company)
                .order_by('-id').first())
        return Response({
            'sections': link.visites_par_section if link else {},
            'friction': link.friction_alert if link else None,
        })

    @action(detail=True, methods=['post'], url_path='whatsapp-preview',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp_preview(self, request, pk=None):
        """QX22be — PRÉVISUALISATION WhatsApp (lecture seule) : construit le lien
        wa.me + le message SANS marquer le devis « envoyé ».

        Le vendeur ouvre la modale d'envoi (aperçu) puis clique le lien wa.me
        pour VRAIMENT envoyer (l'action ``whatsapp`` marque alors « envoyé »).
        Ouvrir puis fermer la modale ne doit JAMAIS créer un devis fantôme
        « envoyé » dont l'horloge de validité a démarré. Aucune transition de
        statut, aucune écriture (hormis le ShareLink réutilisé, idempotent)."""
        from ..utils.phone import normalize_phone_e164
        from ..utils.whatsapp import (
            build_single_devis_whatsapp, build_wa_url, devis_recipient_phone,
        )

        devis = self.get_object()
        # QJR539 — garde T17 : l'aperçu précède un envoi, il est refusé
        # d'emblée (sans écrire l'approbation implicite d'un admin).
        _exiger_remise_envoi(devis, request.user, enregistrer=False)
        phone = devis_recipient_phone(devis)
        if not normalize_phone_e164(phone):
            return Response(
                {'detail': 'Numéro de téléphone invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        langue = request.data.get('langue')
        if langue is None:
            lead = getattr(devis, 'lead', None)
            langue = (getattr(lead, 'langue_preferee', None) or 'fr'
                      if lead is not None else 'fr')
        message, link = build_single_devis_whatsapp(request, devis, langue)
        # PAS de mark_devis_sent, PAS de chatter : simple aperçu.
        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'url': link['url'],
            'devis_statut': devis.statut,  # inchangé
            'preview': True,
            # GAMME — de quoi afficher le choix « envoyer cette gamme seule /
            # envoyer les deux » dans la modale d'envoi. ``None`` quand le
            # devis n'a pas de gamme sœur (modale inchangée).
            'gamme': _gamme_envoi_payload(devis),
        })

    @action(detail=True, methods=['post'], url_path='whatsapp',
            permission_classes=[IsResponsableOrAdmin])
    def whatsapp(self, request, pk=None):
        """QG8 — « Envoyer » un devis = le flux WhatsApp des leads.

        Miroir de ``crm.LeadViewSet.whatsapp_devis`` au niveau du devis :
          * construit un lien wa.me PRÊT à envoyer (n'envoie rien — le commercial
            appuie lui-même sur Envoyer) ;
          * le {lien} est un lien public tokenisé (30 j) vers le PDF CLIENT du
            devis — jamais de prix d'achat ni de marge (règle #4 : le moteur ne
            fait que rendre) ;
          * marque le devis « envoyé » via ``mark_devis_sent`` (U4 — le SEUL
            chemin de transition brouillon→envoyé) et fait avancer le funnel
            (→ QUOTE_SENT) via l'événement domaine ``devis_sent`` ;
          * idempotent, ne dégrade JAMAIS un devis accepté/refusé/expiré.

        Le destinataire vient du client, sinon du lead (WhatsApp puis
        téléphone). Body optionnel : ``langue`` (défaut : langue du lead, sinon
        « fr »). La société est déjà bornée par ``get_queryset``.
        """
        from ..utils.phone import normalize_phone_e164
        from ..utils.whatsapp import (
            build_single_devis_whatsapp, build_wa_url, devis_recipient_phone,
        )
        from ..services import mark_devis_sent

        devis = self.get_object()
        # QJR539 — garde T17 AVANT tout effet (gamme, lien, statut).
        _exiger_remise_envoi(devis, request.user)
        phone = devis_recipient_phone(devis)
        if not normalize_phone_e164(phone):
            return Response(
                {'detail': 'Numéro de téléphone invalide.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        langue = request.data.get('langue')
        if langue is None:
            lead = getattr(devis, 'lead', None)
            langue = (getattr(lead, 'langue_preferee', None) or 'fr'
                      if lead is not None else 'fr')
        # GAMME — le MODE D'ENVOI est réglé À L'ENVOI et vit sur le devis
        # (``etude_params['gamme']['envoi']``), des deux côtés de la paire.
        # Absent du corps → le mode déjà posé (défaut « les_deux »).
        _appliquer_gamme_envoi(devis, request.data.get('gamme_envoi'))
        message, link = build_single_devis_whatsapp(request, devis, langue)

        # U4 — partager le devis le marque « envoyé » (idempotent, jamais de
        # régression accepté/refusé/expiré). Le funnel avance via devis_sent.
        mark_devis_sent(devis=devis, user=request.user)

        # Trace l'action au chatter du devis (même app — autorisé). L'audit
        # transverse passe par le bus core.events (contrat d'import M4 : ventes
        # n'importe jamais apps.audit directement), jamais par un appel direct.
        from .. import activity
        activity.log_devis_note(
            devis, request.user,
            f'Lien WhatsApp du devis {devis.reference} préparé.')

        return Response({
            'wa_url': build_wa_url(phone, message),
            'phone': phone, 'message': message, 'url': link['url'],
            'devis_statut': devis.statut,
        })

    @action(detail=True, methods=['post'], url_path='pdf-partage',
            permission_classes=[IsResponsableOrAdmin])
    def pdf_partage(self, request, pk=None):
        """QJR659 (décision fondateur 01/10) — le PDF du devis a été partagé
        par la feuille de partage native (``navigator.share`` résolu) : cela
        vaut ENVOI, comme copier le lien client (D-QJR5-3).

        Ce n'est PAS un « marquer envoyé » nu : la garde de remise T17
        (QJR539) passe AVANT tout effet (400 ``{detail}``, le devis reste
        brouillon), puis ``mark_devis_sent`` — le seul chemin brouillon →
        envoyé (idempotent, ne régresse jamais un accepté/refusé/expiré,
        funnel via ``devis_sent``). Aucun lien client n'est minté. Le
        frontend ne l'appelle ni sur AbortError ni sur le repli
        téléchargement."""
        from ..services import mark_devis_sent
        from .. import activity

        devis = self.get_object()
        _exiger_remise_envoi(devis, request.user)
        etait_brouillon = devis.statut == Devis.Statut.BROUILLON
        mark_devis_sent(devis=devis, user=request.user)
        if etait_brouillon:
            activity.log_devis_note(
                devis, request.user,
                f'PDF du devis {devis.reference} partagé (feuille de partage).')
        return Response({'devis_statut': devis.statut})

    @action(detail=True, methods=['post'], url_path='contacter-superieur',
            permission_classes=[IsResponsableOrAdmin])
    def contacter_superieur(self, request, pk=None):
        """QJ28 — « Contacter mon supérieur » : notifie le SUPÉRIEUR du vendeur
        sur ce devis (action MANUELLE — un bouton, jamais automatique).

        Destinataires : le ``supervisor`` du créateur du devis (repli : le
        vendeur courant), sinon les managers de repli de la société
        (« Commercial responsable » / « Directeur ») — jamais le vendeur
        lui-même. La notification passe par ``notify()`` (event
        ``devis_superior_contact_requested``) et porte un lien vers le devis.
        Aucun statut n'est touché (règle #4). La société vient TOUJOURS du
        devis (déjà borné à la société du user par ``get_queryset``).

        Body optionnel : ``message`` (max 500 caractères).
        """
        devis = self.get_object()
        handler = devis.created_by or request.user
        from apps.crm.services import user_and_superior_recipients
        recipients = [
            u for u in user_and_superior_recipients(handler, devis.company)
            if u.pk not in {handler.pk, request.user.pk}
        ]
        if not recipients:
            return Response(
                {'detail': (
                    'Aucun supérieur à notifier : définissez un superviseur '
                    'dans Paramètres → Équipe, ou un rôle « Commercial '
                    'responsable » / « Directeur ».')},
                status=status.HTTP_400_BAD_REQUEST)

        message = (str(request.data.get('message') or '')).strip()[:500]
        client_nom = str(devis.client) if devis.client_id else ''
        body_parts = [
            f'{request.user.username} demande votre avis sur le devis '
            f'{devis.reference}'
            + (f' (client : {client_nom})' if client_nom else '') + '.']
        if message:
            body_parts.append(f'Message : « {message} »')

        from apps.notifications.services import notify_many
        notify_many(
            recipients,
            'devis_superior_contact_requested',
            f'Avis demandé — devis {devis.reference}',
            body='\n'.join(body_parts),
            link=f'/ventes/devis?devis={devis.pk}',
            company=devis.company,
        )
        from .. import activity
        activity.log_devis_note(
            devis, request.user,
            'Supérieur notifié pour avis sur ce devis.'
            + (f' Message : « {message} »' if message else ''))
        return Response({
            'detail': 'Votre supérieur a été notifié.',
            'recipients': [u.username for u in recipients],
        })

    @action(detail=True, methods=['get'],
            url_path='superior-contact-status',
            permission_classes=[IsAnyRole])
    def superior_contact_status(self, request, pk=None):
        """VX215 — boucle de retour « pris en charge » (version lecture
        seule) : après « Contacter mon supérieur » (ci-dessus), l'ÉMETTEUR
        voit si sa demande a été VUE — sans jamais lire le CONTENU des
        notifications d'autrui, seulement l'état `read`/lecteur de CETTE
        demande précise (scopée à ce devis + cet événement). Zéro nouveau
        modèle : relit directement les `Notification` déjà créées par
        `contacter_superieur` (même société, même `link`)."""
        devis = self.get_object()
        from apps.notifications.selectors import superior_contact_status
        link = f'/ventes/devis?devis={devis.pk}'
        return Response(superior_contact_status(devis.company, link))

"""Notifications de réactivité (speed-to-lead) (SPL16, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
from .leads_attribution import responsable_leads_pro
from .leads_socle import lead_notification_recipients
from .models import Lead
from .visites import avec_direction, historique_appareil, resume_historique_fr


def _build_lead_wa_reply_url(lead):
    """Construit un lien wa.me « répondre maintenant » vers le prospect du lead.

    Utilise le numéro WhatsApp du lead (sinon son téléphone). Renvoie l'URL
    ou None si aucun numéro n'est disponible. Best-effort — jamais d'exception.
    """
    try:
        import urllib.parse
        phone_raw = (
            getattr(lead, 'whatsapp', None)
            or getattr(lead, 'telephone', None)
            or ''
        )
        # ACRM39 — normaliseur sanctionné (E.164) : un numéro français reste
        # 33…, « +212 (0)6… » perd son zéro ; non normalisable ⇒ pas de lien
        # (jamais un numéro inventé).
        from apps.ventes.utils.phone import normalize_phone_e164
        digits = normalize_phone_e164(phone_raw)
        if not digits:
            return None
        nom = (
            (getattr(lead, 'nom', '') or '').strip()
            or 'votre client'
        )
        # Message pré-rempli court — le vendeur personnalise avant d'envoyer.
        text = urllib.parse.quote(f'Bonjour {nom}, je vous contacte suite à votre demande.')
        return f'https://wa.me/{digits}?text={text}'
    except Exception:
        return None


def notify_new_lead(lead, *, sous_seuil=False) -> None:
    """QJ2 (a) — Notifie le responsable du lead à la CRÉATION d'un nouveau lead.

    Événement de speed-to-lead : le owner du lead est notifié dès l'arrivée du
    lead (webhook site web ou création manuelle). La notification porte un lien
    wa.me « répondre maintenant » vers le prospect. Best-effort : jamais
    d'exception propagée — un échec de notification ne doit pas casser le flux
    de création.

    Multi-tenant : le owner est résolu depuis le lead (server-side, jamais du
    corps de requête). QJ27 : le supérieur du owner (``supervisor``) est aussi
    notifié — repli sur les managers société (« Commercial responsable » /
    « Directeur ») quand le owner ou son supérieur manque. Aucun destinataire
    résolvable → no-op.

    ``sous_seuil`` (18/08/2026 — le site transmet désormais les leads sous le
    seuil de facture, `qualified: false`) : le lead est notifié comme les
    autres — jamais silencieux, il est bien arrivé — mais le titre et le corps
    portent la mention « (sous le seuil) », pour que le commercial arbitre en
    VOYANT la notification et non après avoir décroché. Le défaut ``False``
    laisse tous les autres appelants (création manuelle, imports) inchangés.

    T-TRACE (25/08/2026) — DEUX ajouts, tous deux additifs :
      · la DIRECTION est systématiquement ajoutée aux destinataires
        (« always add the director in the notifications ») ;
      · quand l'appareil du demandeur a un historique de visites RÉEL, le
        corps le dit (« A visité le site N fois avant sa demande … ») — c'est
        exactement ce que le fondateur a demandé de voir. Sans historique,
        la phrase est simplement absente : jamais « 0 visite ».
    """
    try:
        recipients = avec_direction(
            lead_notification_recipients(lead),
            getattr(lead, 'company', None))
        # CIQ416 (D-CIQ-20) — un lead PRO se dit pro dès le titre, et son
        # responsable désigné est ajouté aux destinataires.
        segment = getattr(lead, 'type_installation', None)
        pro = segment in (Lead.TypeInstallation.COMMERCIAL,
                          Lead.TypeInstallation.INDUSTRIEL)
        if pro:
            recipients = _avec_responsable_pro(recipients, lead)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Nouveau prospect'
        wa_url = _build_lead_wa_reply_url(lead)
        suffixe = ' (sous le seuil)' if sous_seuil else ''
        body_parts = [f'Un nouveau lead vient d\'arriver : {nom}{suffixe}.']
        if pro:
            body_parts.extend(lignes_notification_pro(lead))
        if sous_seuil:
            body_parts.append(
                'Facture déclarée sous le seuil de 1 000 MAD — à traiter '
                'en second, après les leads au-dessus du seuil.')
        historique = resume_historique_fr(
            historique_appareil(getattr(lead, 'company', None),
                                getattr(lead, 'appareil_id', '')),
            avant_demande=True)
        if historique:
            body_parts.append(historique)
        # L-DESSIN (fondateur 25/08/2026 : « when the client draws his roof i
        # still do not receive the drawing ») — la notification d'arrivée DIT
        # désormais qu'un tracé accompagne la demande. Sans contour, la phrase
        # est simplement absente : jamais « 0 point », jamais un tracé annoncé
        # qui n'existe pas.
        contour = getattr(lead, 'roof_outline', None)
        if isinstance(contour, list) and len(contour) >= 3:
            body_parts.append(
                f'Le client a DESSINÉ le contour de son toit '
                f'({len(contour)} points) — visible sur la fiche, '
                'section « Toiture & site ».')
        if wa_url:
            body_parts.append(f'Répondre maintenant : {wa_url}')
        titre = (f'Nouveau lead PRO ({segment}) : {nom}{suffixe}' if pro
                 else f'Nouveau lead : {nom}{suffixe}')
        notify_many(
            recipients,
            'lead_new',
            titre,
            body='\n'.join(body_parts),
            link=f'/crm/leads?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QJ2: notify_new_lead échoué pour lead #%s : %s',
            getattr(lead, 'pk', '?'), exc)


def _avec_responsable_pro(recipients, lead):
    """CIQ416 — ajoute le responsable des leads pro aux destinataires (sans
    doublon). Best-effort : un profil absent ne change rien."""
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.objects.filter(
        company_id=getattr(lead, 'company_id', None)).first()
    responsable = responsable_leads_pro(
        profile, {'type_installation': lead.type_installation})
    liste = list(recipients or [])
    if responsable is not None and responsable.pk not in {
            getattr(u, 'pk', None) for u in liste}:
        liste.append(responsable)
    return liste


def _montant_fr(valeur):
    from decimal import Decimal
    nombre = Decimal(str(valeur))
    if nombre == nombre.to_integral_value():
        return f'{int(nombre):,}'.replace(',', ' ')
    return f'{nombre:,.2f}'.replace(',', ' ').replace('.', ',')


def lignes_notification_pro(lead):
    """CIQ416 — le corps d'un lead PRO : catégorie, facture ou kWh DÉCLARÉS
    (jamais une estimation) et tension si elle est déclarée. Une donnée
    absente n'écrit aucune ligne."""
    lignes = []
    categorie = getattr(lead, 'categorie_commerciale', None)
    if categorie:
        libelle = dict(Lead.CategorieCommerciale.choices).get(
            categorie, categorie)
        lignes.append(f'Activité : {libelle}.')
    elif getattr(lead, 'secteur_industriel', None):
        lignes.append(f'Activité : {lead.secteur_industriel}.')
    tranche = getattr(lead, 'facture_tranche_declaree', None)
    kwh = (getattr(lead, 'conso_mensuelle_kwh', None)
           or getattr(lead, 'bill_kwh', None))
    if getattr(lead, 'facture_hiver', None):
        lignes.append('Facture déclarée : '
                      f'{_montant_fr(lead.facture_hiver)} MAD/mois.')
    elif isinstance(tranche, dict) and tranche.get('libelle'):
        lignes.append(f'Facture déclarée : « {tranche["libelle"]} ».')
    if kwh:
        lignes.append(f'Consommation déclarée : {_montant_fr(kwh)} kWh/mois.')
    tension = getattr(lead, 'tension_raccordement', None)
    if (tension in ('bt', 'mt')
            and getattr(lead, 'tension_source', None)
            != 'site_defaut_visible'):
        lignes.append('Raccordement : ' + (
            'moyenne tension (MT).' if tension == 'mt'
            else 'basse tension (BT).'))
    return lignes


def notify_devis_opened(devis_reference: str, lead, *, ip='',
                        appareil_id='', reprise=False) -> None:
    """QJ2 (b) — Notifie le responsable du lead à l'ouverture du devis.

    QJ1bis (fondateur 07/09/2026) — ``reprise=True`` : ce n'est plus la
    première ouverture mais un RETOUR du client sur sa proposition ; même
    notification, formulée « a rouvert » — le fondateur veut être prévenu à
    CHAQUE visite, pas seulement la première.

    Complémente noter_devis_ouvert (QJ1) : en plus de la note chatter, envoie
    une notification in-app + Web Push au owner du lead, avec un lien wa.me
    « répondre maintenant » vers le prospect. QJ27 : le supérieur du owner est
    aussi notifié (repli managers société quand owner/supervisor manque).
    Best-effort — jamais d'exception propagée.

    T-TRACE (25/08/2026) — ``ip`` et ``appareil_id`` sont FACULTATIFS (les
    appelants qui ne les connaissent pas restent inchangés) et lus CÔTÉ
    SERVEUR par l'appelant, jamais d'un corps de requête. Quand ils sont
    fournis, le corps dit d'OÙ vient l'ouverture et si l'appareil était DÉJÀ
    connu — le premier indice qu'un « client » qui ouvre est en fait un
    visiteur déjà vu ailleurs. La DIRECTION est toujours destinataire.

    QJEQUIPE3 (16/09/2026) — le lien pointe l'écran VISITEURS filtré sur ce
    lead (``/crm/visiteurs?lead=<pk>``), c'est-à-dire l'historique de ses
    accès : quand/depuis quoi/combien de temps il a lu, et le bouton pour
    marquer l'appareil « équipe » si l'ouverture vient en fait de nous. La
    liste des leads ne montrait rien de tout cela — et comme la cloche
    regroupe les notifications par ``link`` (VX208), « devis ouvert » s'y
    fondait dans « nouveau lead », qui porte le même lien.
    """
    try:
        company = getattr(lead, 'company', None)
        recipients = avec_direction(
            lead_notification_recipients(lead), company)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Votre client'
        wa_url = _build_lead_wa_reply_url(lead)
        verbe = 'a rouvert' if reprise else "vient d'ouvrir"
        body_parts = [f'{nom} {verbe} le devis {devis_reference}.']
        if ip:
            body_parts.append(f'Ouverture depuis l’adresse IP {ip}.')
        if appareil_id:
            # « Connu » = cet appareil a DÉJÀ laissé une trace avant cette
            # ouverture-ci (l'ouverture elle-même est déjà enregistrée quand
            # on arrive ici : un appareil vu pour la 1re fois n'a donc qu'UNE
            # seule visite).
            historique = historique_appareil(company, appareil_id)
            visites = (historique or {}).get('visites') or 0
            if visites > 1:
                body_parts.append('Appareil DÉJÀ connu de nos surfaces.')
                resume = resume_historique_fr(historique)
                if resume:
                    body_parts.append(resume)
            else:
                body_parts.append('Appareil jamais vu auparavant.')
        if wa_url:
            body_parts.append(f'Répondre maintenant : {wa_url}')
        notify_many(
            recipients,
            'devis_opened',
            (f'Devis {devis_reference} rouvert par le client' if reprise
             else f'Devis {devis_reference} ouvert par le client'),
            body='\n'.join(body_parts),
            link=f'/crm/visiteurs?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QJ2: notify_devis_opened échoué pour lead #%s devis %s : %s',
            getattr(lead, 'pk', '?'), devis_reference, exc)

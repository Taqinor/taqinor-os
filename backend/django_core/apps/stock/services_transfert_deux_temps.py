"""NTRET7 — Transfert inter-magasins en DEUX TEMPS (expédition / réception).

``transfer_stock`` (N15) déplace tout en une fois : correct pour un
mouvement instantané, faux pour un camion. Ce module ajoute le cycle réel :

  demande  → la marchandise est encore à la source, rien n'a bougé ;
  expédié  → la SOURCE décrémente, la destination n'a rien reçu ;
  reçu     → la DESTINATION incrémente de ce qui a été COMPTÉ, l'écart
             éventuel est journalisé (jamais absorbé en silence).

Le chemin DIRECT historique n'est pas touché : ses transferts naissent
``statut=RECU`` (défaut du champ) et ne passent jamais par ici.

Un bon de transfert PDF (SKU + quantités attendues + code-barres du bon)
accompagne l'expédition.
"""
import logging

logger = logging.getLogger(__name__)

# Écart de réception : consigné comme AJUSTEMENT motivé sur la destination.
MOTIF_ECART = 'Écart de réception sur bon de transfert'


def creer_demande_transfert(*, company, user, produit_id, source_id,
                            destination_id, quantite, note=''):
    """Ouvre un transfert EN DEUX TEMPS (rien n'a encore bougé).

    La référence ``TRF-YYYYMM-NNNN`` est posée côté serveur, race-safe
    (``core.numbering`` via ``create_with_reference``) — jamais un
    ``count()+1``.
    """
    from django.db import transaction

    from apps.ventes.utils.references import create_with_reference

    from .models import EmplacementStock, Produit, TransfertStock

    try:
        quantite = int(quantite)
    except (TypeError, ValueError):
        raise ValueError('Quantité invalide.')
    if quantite <= 0:
        raise ValueError('La quantité doit être positive.')
    if str(source_id) == str(destination_id):
        raise ValueError(
            'La source et la destination doivent être différentes.')

    produit = Produit.objects.filter(id=produit_id, company=company).first()
    if produit is None:
        raise ValueError('Produit introuvable dans cette société.')
    emplacements = {
        e.id: e for e in EmplacementStock.objects.filter(
            company=company, archived=False)}
    try:
        source = emplacements[int(source_id)]
        destination = emplacements[int(destination_id)]
    except (KeyError, TypeError, ValueError):
        raise ValueError('Emplacement introuvable dans cette société.')

    with transaction.atomic():
        def _creer(reference):
            return TransfertStock.objects.create(
                company=company, produit=produit, source=source,
                destination=destination, quantite=quantite,
                statut=TransfertStock.Statut.DEMANDE, reference=reference,
                note=(note or '').strip(), created_by=user)

        transfert = create_with_reference(
            TransfertStock, 'TRF', company, _creer)
    logger.info('NTRET7 demande de transfert %s (%d x produit=%s)',
                transfert.reference, quantite, produit.id)
    return transfert


def expedier_transfert(transfert, user):
    """Départ du camion : la SOURCE décrémente, la destination attend."""
    from django.db import transaction

    from .models import StockEmplacement, TransfertStock

    if transfert.statut != TransfertStock.Statut.DEMANDE:
        raise ValueError(
            'Seul un transfert DEMANDÉ peut être expédié.')

    with transaction.atomic():
        source = transfert.source
        if not source.is_principal:
            ligne, _ = StockEmplacement.objects.select_for_update(
            ).get_or_create(
                produit=transfert.produit, emplacement=source,
                defaults={'company': transfert.company, 'quantite': 0})
            if ligne.quantite < transfert.quantite:
                raise ValueError(
                    f'Quantité insuffisante à « {source.nom} » '
                    f'({ligne.quantite} disponible).')
            ligne.quantite -= transfert.quantite
            ligne.save(update_fields=['quantite'])
        transfert.statut = TransfertStock.Statut.EXPEDIE
        transfert.expedie_par = user
        from django.utils import timezone
        transfert.date_expedition = timezone.now()
        transfert.save(update_fields=[
            'statut', 'expedie_par', 'date_expedition'])
    return transfert


def receptionner_transfert(transfert, user, *, quantite_recue=None):
    """Arrivée : la DESTINATION incrémente de ce qui est RÉELLEMENT compté.

    Un écart (manquant ou surplus) est journalisé dans la note du transfert
    ET tracé par un ``MouvementStock`` AJUSTEMENT motivé — jamais absorbé en
    silence.
    """
    from django.db import transaction
    from django.utils import timezone

    from .models import MouvementStock, StockEmplacement, TransfertStock

    if transfert.statut != TransfertStock.Statut.EXPEDIE:
        raise ValueError('Seul un transfert EXPÉDIÉ peut être réceptionné.')

    if quantite_recue is None:
        quantite_recue = transfert.quantite
    try:
        quantite_recue = int(quantite_recue)
    except (TypeError, ValueError):
        raise ValueError('Quantité reçue invalide.')
    if quantite_recue < 0:
        raise ValueError('La quantité reçue ne peut pas être négative.')

    with transaction.atomic():
        destination = transfert.destination
        if not destination.is_principal and quantite_recue:
            ligne, _ = StockEmplacement.objects.get_or_create(
                produit=transfert.produit, emplacement=destination,
                defaults={'company': transfert.company, 'quantite': 0})
            ligne.quantite += quantite_recue
            ligne.save(update_fields=['quantite'])

        ecart = quantite_recue - transfert.quantite
        if ecart:
            # L'écart change le TOTAL de la société : il est tracé comme un
            # ajustement motivé, jamais dissimulé dans la ventilation.
            produit = transfert.produit
            produit.refresh_from_db()
            qte_avant = produit.quantite_stock
            qte_apres = qte_avant + ecart
            MouvementStock.objects.create(
                company=transfert.company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT,
                quantite=abs(ecart), quantite_avant=qte_avant,
                quantite_apres=qte_apres, reference=transfert.reference,
                note=(f'{MOTIF_ECART} {transfert.reference} : '
                      f'{quantite_recue} reçu(s) pour {transfert.quantite} '
                      f'expédié(s).'),
                created_by=user)
            produit.quantite_stock = qte_apres
            produit.save(update_fields=['quantite_stock'])

        transfert.quantite_recue = quantite_recue
        transfert.statut = TransfertStock.Statut.RECU
        transfert.recu_par = user
        transfert.date_reception = timezone.now()
        champs = ['quantite_recue', 'statut', 'recu_par', 'date_reception']
        if ecart:
            transfert.note = (
                f'{(transfert.note or "").strip()}\n{MOTIF_ECART} : '
                f'{ecart:+d} unité(s).').strip()
            champs.append('note')
        transfert.save(update_fields=champs)
    logger.info('NTRET7 reception transfert %s recu=%d ecart=%d',
                transfert.reference, quantite_recue,
                quantite_recue - transfert.quantite)
    return transfert


def render_bon_transfert_html(transfert):
    """Bon de transfert imprimable (SKU + quantités attendues + code-barres).

    Construit ici, en Python (même pratique que ``labels.py``) ; le
    code-barres réutilise ``labels.code128b_svg`` — aucune dépendance
    ajoutée.
    """
    from apps.ventes.utils.pdf import _company_context

    from .labels import code128b_svg

    def _esc(value):
        return (str(value if value is not None else '')
                .replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))

    ctx = _company_context(company=transfert.company)
    reference = transfert.reference or f'TRF-{transfert.id}'
    code_svg = code128b_svg(reference)
    produit = transfert.produit

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Bon de transfert</title>
<style>
  @page {{ size: A4; margin: 15mm; }}
  body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10pt;
          color: #111; }}
  h1 {{ font-size: 15pt; margin: 0 0 1mm; }}
  .meta {{ font-size: 9pt; color: #555; margin: 0 0 6mm; }}
  table {{ width: 100%; border-collapse: collapse; margin: 5mm 0; }}
  th, td {{ border: 0.3mm solid #666; padding: 1.8mm 2mm; text-align: left; }}
  th {{ background: #eee; font-size: 8.5pt; text-transform: uppercase; }}
  .num {{ text-align: right; }}
  .code {{ margin: 4mm 0; }}
  .signatures {{ display: flex; gap: 6mm; margin-top: 10mm; }}
  .signature {{ flex: 1; border-top: 0.3mm solid #333; padding-top: 2mm;
                font-size: 8.5pt; color: #444; }}
</style></head>
<body>
  <div><strong>{_esc(ctx.get('entreprise_nom'))}</strong></div>
  <h1>Bon de transfert {_esc(reference)}</h1>
  <p class="meta">
    De : {_esc(getattr(transfert.source, 'nom', ''))} &mdash;
    Vers : {_esc(getattr(transfert.destination, 'nom', ''))} &mdash;
    Statut : {_esc(transfert.get_statut_display())}
  </p>
  <div class="code">{code_svg}</div>
  <table>
    <thead><tr>
      <th>SKU</th><th>Désignation</th>
      <th class="num">Quantité attendue</th><th class="num">Quantité reçue</th>
    </tr></thead>
    <tbody><tr>
      <td>{_esc(getattr(produit, 'sku', '') or '')}</td>
      <td>{_esc(getattr(produit, 'nom', '') or '')}</td>
      <td class="num">{_esc(transfert.quantite)}</td>
      <td class="num">{_esc(
          transfert.quantite_recue
          if transfert.quantite_recue is not None else '')}</td>
    </tr></tbody>
  </table>
  <div class="signatures">
    <div class="signature">Signature expéditeur</div>
    <div class="signature">Signature transporteur</div>
    <div class="signature">Signature réceptionnaire</div>
  </div>
</body></html>"""


def generate_bon_transfert_pdf(transfert):
    """Rend le bon de transfert et renvoie les octets (jamais stocké)."""
    from apps.ventes.utils.pdf import _html_to_pdf
    return _html_to_pdf(render_bon_transfert_html(transfert))

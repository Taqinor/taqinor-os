"""Endpoint PUBLIC (sans login) — portail fournisseur en lecture seule
(XPUR22).

Accès uniquement via le jeton ``PortailFournisseurToken`` (long,
imprévisible, révocable/expirant — mêmes garanties que
``ventes.ShareLink``/``sav.Ticket.share_token``). Un jeton donne accès aux
documents d'UN SEUL fournisseur — jamais ceux d'un autre fournisseur, jamais
de marge. Le fournisseur peut :
  * consulter ses BCF en cours, réceptions, factures (statut de paiement) ;
  * confirmer un BCF + proposer une date d'arrivée (préserve la date
    demandée d'origine — OTD, XPUR7).

Protections : X-Robots-Tag noindex sur chaque réponse ; throttle cache-based
par IP + jeton (sans dépendance externe).
"""
from rest_framework import status
from rest_framework.decorators import (
    api_view, permission_classes, throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle


class PortailFournisseurThrottle(SimpleRateThrottle):
    """Limite le débit du portail fournisseur par IP + jeton (cache-based,
    sans dépendance externe)."""
    scope = 'stock_portail_fournisseur'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '')
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope, 'ident': f'{ident}:{token}',
        }


def _noindex(response):
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def _not_found():
    return _noindex(Response(
        {'detail': "Ce lien du portail fournisseur est invalide, révoqué "
                   "ou expiré."},
        status=status.HTTP_404_NOT_FOUND,
    ))


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([PortailFournisseurThrottle])
def portail_fournisseur_documents_view(request, token):
    """XPUR22 — documents (BCF/réceptions/factures) DU SEUL fournisseur
    porteur de ce jeton. 404 sans fuite de données si le jeton est invalide,
    révoqué ou expiré."""
    from .services import (
        resoudre_token_portail_fournisseur, portail_fournisseur_documents,
    )
    token_obj = resoudre_token_portail_fournisseur(token)
    if token_obj is None:
        return _not_found()
    return _noindex(Response(portail_fournisseur_documents(token_obj)))


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PortailFournisseurThrottle])
def portail_fournisseur_confirmer_bcf_view(request, token, bcf_id):
    """XPUR22 — le fournisseur confirme un BCF et propose une date
    d'arrivée. Corps : ``{"date_confirmee_fournisseur": "YYYY-MM-DD",
    "numero_confirmation_fournisseur": "..."}``. Isolation stricte : le BCF
    doit appartenir au fournisseur porteur du jeton (sinon 404, jamais
    d'accès croisé)."""
    from .services import (
        resoudre_token_portail_fournisseur, confirmer_bcf_portail_fournisseur,
    )
    token_obj = resoudre_token_portail_fournisseur(token)
    if token_obj is None:
        return _not_found()

    date_confirmee = request.data.get('date_confirmee_fournisseur')
    if not date_confirmee:
        return _noindex(Response(
            {'detail': 'date_confirmee_fournisseur est requise.'},
            status=status.HTTP_400_BAD_REQUEST))

    try:
        bc = confirmer_bcf_portail_fournisseur(
            token_obj, bcf_id, date_confirmee=date_confirmee,
            numero_confirmation=request.data.get(
                'numero_confirmation_fournisseur', ''))
    except ValueError:
        return _not_found()

    return _noindex(Response({
        'id': bc.id, 'reference': bc.reference,
        'date_confirmee_fournisseur': bc.date_confirmee_fournisseur,
        'numero_confirmation_fournisseur':
            bc.numero_confirmation_fournisseur,
    }))


# ─────────────────────────────────────────────────────────────────────────────
# XPOS17 — Fiche produit PUBLIQUE showroom (QR de l'étiquette « showroom »).
# Le QR imprimé en magasin pointe ici : la fiche du produit exposé par
# l'e-catalogue tokenisé FG214 (specs, prix TTC, garantie, disponibilité
# indicative — JAMAIS prix_achat), avec les deux CTA : « Demander un devis »
# (XPOS14 — POST vers l'endpoint e-catalogue existant) et « Être rappelé »
# (QJ27 — crée un lead via crm.services, même chemin dédupliqué que le
# livechat/e-catalogue, jamais un 2ᵉ chemin de création).
# ─────────────────────────────────────────────────────────────────────────────

class ShowroomPublicThrottle(SimpleRateThrottle):
    """Limite le débit de la fiche showroom par IP + jeton (cache-based)."""
    scope = 'stock_showroom_public'
    rate = '30/minute'

    def get_rate(self):
        return self.rate

    def get_cache_key(self, request, view):
        token = (view.kwargs or {}).get('token', '')
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope, 'ident': f'{ident}:{token}',
        }


def _produit_du_catalogue(token, produit_id):
    """Résout (catalogue, produit) STRICTEMENT : jeton valide/actif/non
    expiré (via compta.selectors — jamais son modèle importé) ET produit
    exposé par CE catalogue ET appartenant à la société du catalogue.
    Renvoie (None, None) sinon — l'appelant répond 404 sans fuite."""
    from apps.compta.selectors import ecatalogue_public_par_token
    from .models import Produit
    cat = ecatalogue_public_par_token(token)
    if cat is None:
        return None, None
    try:
        pid = int(produit_id)
    except (TypeError, ValueError):
        return None, None
    if pid not in (cat.produit_ids or []):
        return cat, None
    produit = Produit.objects.filter(
        company_id=cat.company_id, id=pid).first()
    return cat, produit


def _fiche_produit_data(cat, produit):
    """Données publiques de la fiche : specs + prix TTC + garantie +
    disponibilité INDICATIVE (jamais le compte exact, jamais prix_achat)."""
    try:
        fiche = produit.fiche_technique
    except Exception:  # noqa: BLE001 — OneToOne absent
        fiche = None
    specs = {}
    if fiche is not None:
        for champ in ('pmax_wc', 'voc_v', 'isc_a', 'vmp_v', 'imp_a',
                      'rendement_pct'):
            val = getattr(fiche, champ, None)
            if val is not None:
                specs[champ] = str(val)
    path_base = (f'/api/django/public/stock/showroom/{cat.token}'
                 f'/produit/{produit.id}/')
    return {
        'catalogue': {'titre': cat.titre},
        'produit': {
            'id': produit.id,
            'nom': produit.nom,
            'sku': produit.sku or '',
            'description': produit.description or '',
            'marque': produit.marque or '',
            'garantie': produit.garantie or '',
            'prix_ttc': str(produit.prix_vente),
            'disponibilite': (
                'En stock' if (produit.quantite_stock or 0) > 0
                else 'Sur commande'),
            'specs': specs,
        },
        'cta': {
            # XPOS14 — panier « Demander un devis » de l'e-catalogue public.
            'demander_devis_url': (
                f'/api/django/public/ecatalogue/{cat.token}/demander-devis/'),
            # QJ27 — « Être rappelé » (fiche showroom, ci-dessous).
            'etre_rappele_url': path_base + 'etre-rappele/',
        },
    }


_SHOWROOM_CSS = (
    'body { font-family: Helvetica, Arial, sans-serif; margin: 0;'
    ' padding: 16px; max-width: 480px; margin-inline: auto;'
    ' color: #16324f; }'
    'h1 { font-size: 1.25rem; margin: 0 0 4px; }'
    '.marque { color: #667; font-size: .9rem; }'
    '.prix { font-size: 1.5rem; font-weight: 700; margin: 12px 0 2px; }'
    '.dispo { display: inline-block; padding: 2px 10px;'
    ' border-radius: 999px; background: #e8f5ee; color: #17714b;'
    ' font-size: .8rem; }'
    '.desc { margin: 12px 0; font-size: .95rem; white-space: pre-line; }'
    '.garantie { font-size: .85rem; color: #445; }'
    '.specs { width: 100%; border-collapse: collapse; margin: 10px 0;'
    ' font-size: .85rem; }'
    '.specs td { border-bottom: 1px solid #eee; padding: 4px 2px; }'
    'form { margin-top: 16px; border-top: 1px solid #eee;'
    ' padding-top: 12px; }'
    'input { width: 100%; box-sizing: border-box; padding: 10px;'
    ' margin: 4px 0; border: 1px solid #ccd; border-radius: 8px; }'
    'button { width: 100%; padding: 12px; margin-top: 8px; border: 0;'
    ' border-radius: 8px; font-weight: 600; cursor: pointer; }'
    '.btn-devis { background: #f59e0b; color: #fff; }'
    '.btn-rappel { background: #16324f; color: #fff; }'
    '.msg { margin-top: 10px; font-size: .9rem; }'
)

_SHOWROOM_JS = """
async function go(mode) {
  const nom = document.getElementById('nom').value.trim();
  const tel = document.getElementById('tel').value.trim();
  const hp = document.getElementById('site_web').value;
  const msg = document.getElementById('msg');
  if (!nom || !tel) {
    msg.textContent = 'Indiquez votre nom et votre téléphone.';
    return;
  }
  const cfg = window.SHOWROOM;
  const url = mode === 'devis' ? cfg.devisUrl : cfg.rappelUrl;
  const body = mode === 'devis'
    ? { nom: nom, telephone: tel, site_web: hp,
        lignes: [{ produit: cfg.produitId, quantite: 1 }] }
    : { nom: nom, telephone: tel, site_web: hp };
  try {
    const r = await fetch(url, { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body) });
    const d = await r.json();
    msg.textContent = d.detail
      || 'Votre demande a bien été transmise. Merci.';
  } catch (e) {
    msg.textContent = 'Une erreur est survenue. Réessayez.';
  }
}
"""


def _fiche_produit_html(data):
    """Petite page HTML autonome (aucun asset externe) pour le scan
    showroom : fiche + formulaire commun aux deux CTA. Libellés français."""
    import json as _json
    p = data['produit']
    cta = data['cta']

    def esc(v):
        return (str(v or '')
                .replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))

    specs_rows = ''.join(
        f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>'
        for k, v in (p.get('specs') or {}).items())
    specs_html = (
        f'<table class="specs">{specs_rows}</table>' if specs_rows else '')
    marque_ref = esc(p['marque']) + (
        f' · réf. {esc(p["sku"])}' if p['sku'] else '')
    garantie_html = (
        f'Garantie : {esc(p["garantie"])}' if p['garantie'] else '')
    cfg = _json.dumps({
        'devisUrl': cta['demander_devis_url'],
        'rappelUrl': cta['etre_rappele_url'],
        'produitId': p['id'],
    })
    return (
        '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,'
        ' initial-scale=1">'
        '<meta name="robots" content="noindex, nofollow">'
        f'<title>{esc(p["nom"])}</title>'
        f'<style>{_SHOWROOM_CSS}</style></head><body>'
        f'<h1>{esc(p["nom"])}</h1>'
        f'<div class="marque">{marque_ref}</div>'
        f'<div class="prix">{esc(p["prix_ttc"])} DH TTC</div>'
        f'<span class="dispo">{esc(p["disponibilite"])}</span>'
        f'<div class="desc">{esc(p["description"])}</div>'
        f'{specs_html}'
        f'<div class="garantie">{garantie_html}</div>'
        '<form id="f" onsubmit="return false">'
        '<input id="nom" placeholder="Votre nom" autocomplete="name">'
        '<input id="tel" placeholder="Votre téléphone" autocomplete="tel">'
        '<input id="site_web" style="display:none" tabindex="-1"'
        ' autocomplete="off">'
        '<button class="btn-devis" onclick="go(\'devis\')">'
        'Demander un devis</button>'
        '<button class="btn-rappel" onclick="go(\'rappel\')">'
        'Être rappelé</button>'
        '<div class="msg" id="msg"></div>'
        '</form>'
        f'<script>window.SHOWROOM = {cfg};{_SHOWROOM_JS}</script>'
        '</body></html>'
    )


@api_view(['GET'])
@permission_classes([AllowAny])
@throttle_classes([ShowroomPublicThrottle])
def fiche_produit_showroom_view(request, token, produit_id):
    """XPOS17 — fiche produit PUBLIQUE (QR showroom). HTML par défaut
    (scan téléphone) ; ``?sortie=json`` pour les données brutes. 404 sans
    fuite si le jeton est invalide/expiré ou si le produit n'est pas exposé
    par CE catalogue. Aucun prix interne (prix_achat/marge) n'est exposé."""
    from django.http import HttpResponse

    cat, produit = _produit_du_catalogue(token, produit_id)
    if cat is None or produit is None:
        return _not_found()
    data = _fiche_produit_data(cat, produit)
    if request.query_params.get('sortie') == 'json':
        return _noindex(Response(data))
    response = HttpResponse(
        _fiche_produit_html(data), content_type='text/html; charset=utf-8')
    return _noindex(response)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ShowroomPublicThrottle])
def fiche_produit_etre_rappele_view(request, token, produit_id):
    """XPOS17 — CTA « Être rappelé » de la fiche showroom (flux
    contact-request QJ27) : crée/dédupe un lead CRM via le chemin EXISTANT
    ``crm.services.create_lead_from_livechat`` (jamais un 2ᵉ chemin de
    création), transcript = produit scanné. Honeypot ``site_web`` : un bot
    qui le remplit voit un 201 factice sans rien créer."""
    cat, produit = _produit_du_catalogue(token, produit_id)
    if cat is None or produit is None:
        return _not_found()

    # Honeypot — succès factice pour les bots.
    if (request.data.get('site_web') or '').strip():
        return _noindex(Response(
            {'detail': 'Votre demande a bien été transmise. Merci.'},
            status=status.HTTP_201_CREATED))

    nom = (str(request.data.get('nom') or '')).strip()[:255]
    telephone = (str(request.data.get('telephone') or '')).strip()[:20]
    email = (str(request.data.get('email') or '')).strip()[:254]
    if not nom or not (telephone or email):
        return _noindex(Response(
            {'detail': 'Nom et téléphone ou email requis.'},
            status=status.HTTP_400_BAD_REQUEST))

    transcript = (
        f'Être rappelé — fiche showroom « {produit.nom} » '
        f'(e-catalogue « {cat.titre} »).')
    from apps.crm.services import create_lead_from_livechat
    create_lead_from_livechat(
        company=cat.company, nom=nom, telephone=telephone, email=email,
        transcript_text=transcript)
    return _noindex(Response(
        {'detail': 'Votre demande a bien été transmise. '
                   'Nous vous rappelons très vite.'},
        status=status.HTTP_201_CREATED))

/**
 * Base de l'API ERP des proxys same-origin (ENF19 : une seule copie, partagée avec `_proxy.ts`) :
 * PUBLIC_API_BASE runtime (cf.env) OU build, sinon https://api.taqinor.ma.
 */
import * as cf from 'cloudflare:workers';
import { lireCookie } from '../../lib/visite';

const API_BASE_PAR_DEFAUT = 'https://api.taqinor.ma';

/**
 * ADEP103 (D-ADEP-103 = c) — en-têtes d'IP visiteur de TOUT relais Worker → API (une seule copie).
 * L'origine ne croit `X-Forwarded-For` que s'il arrive avec `X-Taqinor-Relais` = `RELAIS_API_SECRET`
 * (secret Worker posé au tableau de bord Cloudflare, même valeur dans le .env du serveur) : les plages
 * Cloudflare sont partagées par tous les comptes, l'IP seule ne prouve plus rien. Secret absent →
 * en-têtes d'IP seuls (comportement d'avant). IP non déterminable (`''`/`'unknown'`) → aucun en-tête.
 */
export function entetesIpVisiteur(ip: string): Record<string, string> {
  if (!ip || ip === 'unknown') return {};
  const secret = ((cf.env ?? {}) as { RELAIS_API_SECRET?: string }).RELAIS_API_SECRET?.trim();
  return {
    'X-Forwarded-For': ip,
    'CF-Connecting-IP': ip,
    ...(secret ? { 'X-Taqinor-Relais': secret } : {}),
  };
}

export function resolveApiBase(): string {
  const runtimeEnv = (cf.env ?? {}) as { PUBLIC_API_BASE?: string };
  const depuisRuntime = runtimeEnv.PUBLIC_API_BASE?.trim();
  const depuisBuild = (import.meta.env.PUBLIC_API_BASE as string | undefined)?.trim();
  return depuisRuntime || depuisBuild || API_BASE_PAR_DEFAUT;
}

// ── ASEC53 (C-ASEC-025, D-ASEC-3) — la preuve OTP de LECTURE par navigateur ──
//
// Contrat partagé ASEC1 : `backend/django_core/apps/ventes/contract_samples/proposition_otp_preuve.json`.
// La vérification d'un code de lecture rend une PREUVE opaque propre au navigateur qui l'a
// saisi ; ce socle (partagé avec `_proxy.ts`, ENF19) la range dans un cookie httpOnly (jamais lisible par le JavaScript de la
// page, jamais dans un corps JSON ni une URL) puis la relaie, en en-tête, sur chaque appel
// serveur → ERP de la proposition (rendu SSR + proxys). Une seule copie (ACAL345).

/** Nom du cookie httpOnly qui porte la preuve (contrat ASEC1 `regles.cookie`). */
export const COOKIE_PREUVE = 'tq_prop_preuve';
/** En-tête relayé à l'ERP (contrat ASEC1 `regles.en_tete`). */
export const EN_TETE_PREUVE = 'X-Proposition-Preuve';
/** Base64 url-safe sans remplissage, bornée : tout autre contenu de cookie n'est jamais relayé. */
const FORME_PREUVE = /^[A-Za-z0-9_-]{16,256}$/;
/** Durée plafond du cookie (s) : jamais plus que la fenêtre serveur d'aujourd'hui (1 h). */
const MAX_AGE_PREUVE = 3600;

/** La preuve lue dans un en-tête `Cookie`, ou `''` (absente ou mal formée). */
export function preuveDuCookie(cookieHeader: string | null | undefined): string {
  const brute = lireCookie(cookieHeader, COOKIE_PREUVE);
  return typeof brute === 'string' && FORME_PREUVE.test(brute) ? brute : '';
}

/**
 * En-tête `X-Proposition-Preuve` à relayer à l'ERP depuis la requête entrante (ou son en-tête
 * `Cookie`) ; `{}` sans preuve valable — un navigateur non vérifié n'envoie rien, l'ERP répond
 * alors 403 `otp_required` sur un lien `otp_lecture` (inchangé sur un lien sans code).
 */
export function entetePreuve(source: Request | string | null | undefined): Record<string, string> {
  const cookies = source instanceof Request ? source.headers.get('cookie') : source;
  const preuve = preuveDuCookie(cookies);
  return preuve ? { [EN_TETE_PREUVE]: preuve } : {};
}

/**
 * `Set-Cookie` à poser après une vérification RÉUSSIE (`{ verifie: true, preuve, expire_dans }`,
 * contrat ASEC1 `exemple`) ; `null` pour toute autre réponse. HttpOnly ; Secure ; SameSite=Lax ;
 * Path=/ ; Max-Age = `expire_dans` (borné à 1 h).
 */
export function cookieDePreuve(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null;
  const { verifie, preuve, expire_dans: expireDans } = payload as Record<string, unknown>;
  if (verifie !== true || typeof preuve !== 'string' || !FORME_PREUVE.test(preuve)) return null;
  const duree = typeof expireDans === 'number' && Number.isFinite(expireDans) ? Math.floor(expireDans) : 0;
  if (duree <= 0) return null;
  return `${COOKIE_PREUVE}=${preuve}; Max-Age=${Math.min(duree, MAX_AGE_PREUVE)}; Path=/; HttpOnly; Secure; SameSite=Lax`;
}

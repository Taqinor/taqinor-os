/**
 * Base de l'API ERP des proxys same-origin (ENF19 : une seule copie, partagée avec `_proxy.ts`) :
 * PUBLIC_API_BASE runtime (cf.env) OU build, sinon https://api.taqinor.ma.
 */
import * as cf from 'cloudflare:workers';

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

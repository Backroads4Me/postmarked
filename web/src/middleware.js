import { defineMiddleware } from 'astro:middleware';
import { apiUrl } from './lib/api.js';

// The API sets security headers on its own /api/* and /media/* responses
// (SecurityHeadersMiddleware in api/app/main.py). This app serves the HTML
// pages itself, so they get their headers here. CSP is limited to
// frame-ancestors: React islands, Google Maps, and Tailwind's injected
// inline styles all need wider sources than a default-src policy allows.
const PAGE_SECURITY_HEADERS = {
  'strict-transport-security': 'max-age=31536000; includeSubDomains',
  'x-content-type-options': 'nosniff',
  'x-frame-options': 'DENY',
  'referrer-policy': 'strict-origin-when-cross-origin',
  'permissions-policy': 'geolocation=(), microphone=(), camera=(), interest-cohort=()',
  'content-security-policy': "frame-ancestors 'none'",
};

function withSecurityHeaders(response) {
  for (const [name, value] of Object.entries(PAGE_SECURITY_HEADERS)) {
    if (!response.headers.has(name)) response.headers.set(name, value);
  }
  return response;
}

export const onRequest = defineMiddleware(async (context, next) => {
  const { pathname } = context.url;

  if (pathname.startsWith('/api/') || pathname.startsWith('/media/')) {
    return proxyApiRequest(context);
  }

  if (!pathname.startsWith('/admin')) {
    return withSecurityHeaders(await next());
  }

  const cookie = context.request.headers.get('cookie') || '';
  const loginUrl = new URL('/auth/login', context.url);
  loginUrl.searchParams.set('next', pathname);

  try {
    const res = await fetch(apiUrl('/api/users/me'), {
      headers: cookie ? { cookie } : {},
    });
    if (res.status === 401 || res.status === 403) {
      return withSecurityHeaders(context.redirect(loginUrl.pathname + loginUrl.search, 302));
    }
    if (!res.ok) {
      return withSecurityHeaders(context.redirect(loginUrl.pathname + loginUrl.search, 302));
    }

    const user = await res.json();
    if (user?.role !== 'admin') {
      return withSecurityHeaders(context.redirect('/', 302));
    }
  } catch (e) {
    console.error('Admin middleware auth check failed', e);
    return withSecurityHeaders(context.redirect(loginUrl.pathname + loginUrl.search, 302));
  }

  return withSecurityHeaders(await next());
});

async function proxyApiRequest(context) {
  const upstream = new URL(context.url.pathname + context.url.search, apiUrl('/'));
  const headers = new Headers(context.request.headers);
  headers.delete('host');
  headers.delete('content-length');

  const init = {
    method: context.request.method,
    headers,
    redirect: 'manual',
  };

  if (context.request.method !== 'GET' && context.request.method !== 'HEAD') {
    init.body = context.request.body;
    init.duplex = 'half';
  }

  const response = await fetch(upstream, init);
  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete('content-encoding');
  // Preserve content-length on range responses (206) — iOS Safari requires it
  // to buffer video. Only strip it on full responses where chunked encoding is safe.
  if (response.status !== 206) {
    responseHeaders.delete('content-length');
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders,
  });
}

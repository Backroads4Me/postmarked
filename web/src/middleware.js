import { defineMiddleware } from 'astro:middleware';
import { apiUrl } from './lib/api.js';

export const onRequest = defineMiddleware(async (context, next) => {
  const { pathname } = context.url;

  if (pathname.startsWith('/api/') || pathname.startsWith('/media/')) {
    return proxyApiRequest(context);
  }

  if (!pathname.startsWith('/admin')) {
    return next();
  }

  const cookie = context.request.headers.get('cookie') || '';
  const loginUrl = new URL('/auth/login', context.url);
  loginUrl.searchParams.set('next', pathname);

  try {
    const res = await fetch(apiUrl('/api/users/me'), {
      headers: cookie ? { cookie } : {},
    });
    if (res.status === 401 || res.status === 403) {
      return context.redirect(loginUrl.pathname + loginUrl.search, 302);
    }
    if (!res.ok) {
      return context.redirect(loginUrl.pathname + loginUrl.search, 302);
    }

    const user = await res.json();
    if (user?.role !== 'admin') {
      return context.redirect('/', 302);
    }
  } catch (e) {
    console.error('Admin middleware auth check failed', e);
    return context.redirect(loginUrl.pathname + loginUrl.search, 302);
  }

  return next();
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

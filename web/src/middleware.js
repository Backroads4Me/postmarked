import { defineMiddleware } from 'astro:middleware';
import { apiUrl } from './lib/api.js';

export const onRequest = defineMiddleware(async (context, next) => {
  const { pathname } = context.url;
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

/** Keep the beta application journey across sign-in, without external redirects. */
export function authReturnTo(params: URLSearchParams): string {
  return params.get('next') === '/beta' ? '/beta' : '/home';
}

export function authPageLink(path: '/login' | '/register', params: URLSearchParams): string {
  return authReturnTo(params) === '/beta' ? path + '?next=%2Fbeta' : path;
}

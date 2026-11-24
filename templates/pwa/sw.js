/* Service worker do Elo Industrial.

   O que ele faz:
   - guarda no aparelho o visual do site (CSS, JS e ícones), para o app abrir rápido;
   - se não houver internet, mostra uma página "sem conexão" em vez do erro do navegador.

   O que ele NÃO faz, de propósito:
   - não guarda páginas do site (negociações, recibos, resultados): são dados da empresa e
     ficariam no aparelho depois do "Sair". Quem abre o app sem internet vê só o aviso;
   - não mexe em formulários (POST), na IA, no admin, nem em nada de outro endereço. */

const VERSAO = '{{ versao }}';
const CACHE = `elo-${VERSAO}`;
const PAGINA_OFFLINE = '{{ pagina_offline }}';
const ARQUIVOS = [PAGINA_OFFLINE{% for arquivo in arquivos %}, '{{ arquivo }}'{% endfor %}];

self.addEventListener('install', (evento) => {
  evento.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ARQUIVOS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (evento) => {
  evento.waitUntil(
    caches.keys()
      .then((nomes) => Promise.all(
        nomes.filter((n) => n.startsWith('elo-') && n !== CACHE).map((n) => caches.delete(n))
      ))
      .then(() => self.clients.claim())
  );
});

// Arquivos estáticos: responde com o que já tem e atualiza em segundo plano,
// assim uma mudança no CSS aparece na visita seguinte sem precisar limpar nada.
function estaticoComAtualizacao(requisicao) {
  return caches.open(CACHE).then((cache) =>
    cache.match(requisicao).then((guardado) => {
      const rede = fetch(requisicao).then((resposta) => {
        if (resposta.ok) cache.put(requisicao, resposta.clone());
        return resposta;
      });
      return guardado || rede;
    })
  );
}

self.addEventListener('fetch', (evento) => {
  const requisicao = evento.request;
  if (requisicao.method !== 'GET') return;

  const url = new URL(requisicao.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith('/static/')) {
    evento.respondWith(estaticoComAtualizacao(requisicao).catch(() => caches.match(requisicao)));
    return;
  }

  if (requisicao.mode === 'navigate') {
    evento.respondWith(
      fetch(requisicao).catch(() => caches.match(PAGINA_OFFLINE))
    );
  }
});

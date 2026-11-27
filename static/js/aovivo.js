// Atualização automática: a página pergunta ao servidor, a cada poucos segundos, se algo mudou.
// Se mudou, busca a si mesma de novo e troca só os trechos que mudaram (nunca o campo de digitar mensagem).
(function () {
  if (!document.body.classList.contains('logado')) return;

  const INTERVALO = 3000;          // 3 segundos
  const INTERVALO_MAXIMO = 15000;  // se a conexão cair, vai espaçando as tentativas

  const detalhe = document.querySelector('[data-ao-vivo="negociacao"]');
  const lista = document.querySelector('[data-ao-vivo="lista"]');
  const alvo = detalhe || lista;
  const meta = document.querySelector('meta[name="ao-vivo-url"]');
  const url = detalhe ? detalhe.dataset.versaoUrl : (meta ? meta.content : null);
  if (!url) return;

  let versao = alvo ? alvo.dataset.versao : null;
  let falhas = 0;
  let parado = false;
  let ocupado = false;
  let temporizador = null;

  const ponto = document.getElementById('ao-vivo-ponto');
  function marcarConexao(ok) {
    if (!ponto) return;
    ponto.classList.toggle('off', !ok);
    ponto.textContent = ok ? 'Ao vivo' : 'Reconectando...';
  }

  // ---- contador de pendências no menu (em todas as páginas) ----
  function atualizarContador(n) {
    document.querySelectorAll('[data-nav-negociacoes]').forEach((link) => {
      let marca = link.querySelector('.contador');
      if (!n) { if (marca) marca.remove(); return; }
      if (!marca) {
        marca = document.createElement(link.closest('.abas-app') ? 'b' : 'span');
        marca.className = 'contador';
        marca.title = 'Aguardando uma ação sua';
        (link.querySelector('span') || link).append(' ', marca);
      }
      marca.textContent = n;
    });
  }

  // ---- troca de trechos ----
  function trocar(id, novoDoc) {
    const atual = document.getElementById(id);
    const novo = novoDoc.getElementById(id);
    if (atual && novo) atual.innerHTML = novo.innerHTML;
  }

  function atualizarNegociacao(novoDoc) {
    const lista = document.getElementById('neg-mensagens');
    const antes = new Set(Array.from(lista.children).map((li) => li.dataset.id));
    const noFim = lista.scrollHeight - lista.scrollTop - lista.clientHeight < 80;

    trocar('neg-painel', novoDoc);
    trocar('neg-mensagens', novoDoc);

    const selo = document.getElementById('neg-selo');
    const novoSelo = novoDoc.getElementById('neg-selo');
    if (selo && novoSelo) { selo.className = novoSelo.className; selo.textContent = novoSelo.textContent; }

    // negociação encerrada ou concluída: o formulário de mensagem some
    const compor = document.getElementById('neg-compor');
    if (compor && !novoDoc.getElementById('neg-compor')) compor.remove();

    Array.from(lista.children).forEach((li) => {
      if (!antes.has(li.dataset.id)) li.classList.add('nova');
    });
    if (noFim) lista.scrollTop = lista.scrollHeight;
  }

  async function atualizarPagina() {
    const resp = await fetch(location.href, { credentials: 'same-origin', cache: 'no-store' });
    if (!resp.ok || resp.redirected) { parado = true; return; }   // saiu da conta ou perdeu acesso
    const novoDoc = new DOMParser().parseFromString(await resp.text(), 'text/html');
    const novoAlvo = novoDoc.querySelector('[data-ao-vivo]');
    if (!novoAlvo) return;
    if (detalhe) atualizarNegociacao(novoDoc); else trocar('lista-ao-vivo', novoDoc);
    versao = novoAlvo.dataset.versao;   // a versão do que está na tela agora
  }

  // ---- ciclo ----
  async function perguntar() {
    if (parado || ocupado || document.hidden) return agendar();
    ocupado = true;
    try {
      const resp = await fetch(url, { credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' } });
      if ([401, 403, 404].includes(resp.status)) { parado = true; return; }
      if (!resp.ok) throw new Error('http ' + resp.status);
      const dados = await resp.json();
      falhas = 0;
      marcarConexao(true);
      atualizarContador(dados.pendencias);
      if (alvo && dados.v !== versao) await atualizarPagina();
    } catch (e) {
      falhas += 1;
      marcarConexao(false);
    } finally {
      ocupado = false;
      agendar();
    }
  }

  function agendar() {
    clearTimeout(temporizador);
    if (parado) return;
    temporizador = setTimeout(perguntar, Math.min(INTERVALO * Math.max(1, falhas), INTERVALO_MAXIMO));
  }

  // ao abrir a página, mostra a mensagem mais recente
  const msgs = document.getElementById('neg-mensagens');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;

  document.addEventListener('visibilitychange', () => { if (!document.hidden) { clearTimeout(temporizador); perguntar(); } });
  agendar();
})();

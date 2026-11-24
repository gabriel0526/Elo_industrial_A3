// Deixa o site funcionar como app: registra o service worker e oferece a instalação.
(function () {
  // 1) service worker (só funciona em HTTPS ou em localhost)
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => { /* sem suporte: o site segue normal */ });
    });
  }

  const jaInstalado = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  if (jaInstalado) return;

  // 2) Android e computador (Chrome, Edge): o navegador avisa quando dá para instalar
  const botao = document.getElementById('instalar-app');
  let convite = null;
  window.addEventListener('beforeinstallprompt', (evento) => {
    evento.preventDefault();
    convite = evento;
    if (botao) botao.hidden = false;
  });
  if (botao) {
    botao.addEventListener('click', async () => {
      if (!convite) return;
      convite.prompt();
      await convite.userChoice;
      convite = null;
      botao.hidden = true;
    });
  }
  window.addEventListener('appinstalled', () => { if (botao) botao.hidden = true; });

  // 3) iPhone e iPad (Safari): não existe botão de instalar, só o menu Compartilhar
  const dica = document.getElementById('dica-ios');
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const safari = /safari/i.test(navigator.userAgent) && !/crios|fxios|edgios/i.test(navigator.userAgent);
  if (dica && ios && safari) dica.hidden = false;
})();

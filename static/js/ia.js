// Botões de IA do Elo Industrial.
// Dois usos: preencher o formulário de material e sugerir mensagem na negociação.
(function () {
  const botao = document.getElementById('ia-botao');
  if (!botao) return;

  const caixa = botao.closest('[data-url]');
  const status = document.getElementById('ia-status');
  const csrf = document.querySelector('input[name=csrfmiddlewaretoken]');

  function avisar(texto, erro) {
    status.textContent = texto;
    status.className = erro ? 'erro' : '';
  }

  async function chamar(corpo) {
    const resp = await fetch(caixa.dataset.url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf ? csrf.value : '',
      },
      body: JSON.stringify(corpo),
    });
    let dados = {};
    try { dados = await resp.json(); } catch (e) { /* resposta que não é JSON */ }
    if (!resp.ok) throw new Error(dados.erro || 'Não foi possível usar a IA agora.');
    return dados;
  }

  async function executar(montarCorpo, aplicar) {
    botao.disabled = true;
    avisar('Pensando...', false);
    try {
      aplicar(await chamar(montarCorpo()));
    } catch (e) {
      avisar(e.message, true);
    } finally {
      botao.disabled = false;
    }
  }

  // 1) formulário de material
  if (caixa.hasAttribute('data-ia-material')) {
    const texto = document.getElementById('ia-texto');
    botao.addEventListener('click', () => executar(
      () => ({ texto: texto.value }),
      (dados) => {
        let preenchidos = 0;
        Object.entries(dados.campos).forEach(([nome, valor]) => {
          const campo = document.getElementById('id_' + nome);
          if (!campo) return;
          campo.value = valor;
          campo.classList.add('preenchido-ia');
          campo.dispatchEvent(new Event('change', { bubbles: true }));
          preenchidos += 1;
        });
        avisar(preenchidos + ' campos preenchidos. Confira antes de salvar.', false);
      }
    ));
  }

  // 2) mensagem na negociação
  if (caixa.hasAttribute('data-ia-mensagem')) {
    const instrucao = document.getElementById('ia-instrucao');
    const mensagem = document.getElementById('id_texto');
    botao.addEventListener('click', () => executar(
      () => ({ instrucao: instrucao.value }),
      (dados) => {
        mensagem.value = dados.texto;
        mensagem.focus();
        avisar('Rascunho pronto. Edite se quiser e clique em Enviar.', false);
      }
    ));
  }
})();

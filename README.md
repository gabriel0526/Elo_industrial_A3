# Elo Industrial

Marketplace B2B de resíduos industriais: empresas que geram sobra de material encontram quem precisa dele como insumo.

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Abra http://127.0.0.1:8000

Para acessar o painel administrativo: `python manage.py createsuperuser` e depois http://127.0.0.1:8000/admin

## Dados de exemplo

```bash
python manage.py popular_exemplo
```

Cria 6 empresas, 7 anúncios e 2 negociações (uma aberta e uma concluída, com recibo). Todas usam a senha `exemplo12345`
(e-mail da Marcenaria: `marcenariaboamadeira@exemplo.com`).

## Resultados (Etapa 5)

Menu **Resultados**. Mostra, só com negociações concluídas da sua empresa: quantidade, empresas parceiras, material
entregue e recebido (kg e toneladas), receita, gasto, doações, quebra por categoria e por mês, e as últimas concluídas.
- **Período:** 30 dias, 90 dias, 12 meses ou tudo.
- **Estimativa de economia:** opcional. Você informa quanto pagava para descartar 1 tonelada e o painel calcula o custo
  de descarte evitado (material que você entregou x esse valor) somado à receita. Sem esse valor não há estimativa,
  porque a plataforma não tem como saber o seu custo. O valor não é salvo.
- **CSV:** botão "Baixar histórico", abre direto no Excel. Nomes que começam com `=`, `+`, `-` ou `@` recebem um
  apóstrofo para não virarem fórmula.
- Não há tabela nova: tudo é calculado na hora a partir das negociações, então não precisa de `migrate`.

## Versão app (Etapa 6)

O site é um **PWA**: instalável no celular, abre em tela cheia com ícone próprio, e no celular a navegação
vira uma barra de abas embaixo (Buscar, Negociações, Resultados, Painel).

**Instalar**
- Android (Chrome): botão "Instalar o app" no rodapé do site, ou menu do navegador > Instalar app.
- iPhone (Safari): Compartilhar > Adicionar à Tela de Início.
- Computador (Chrome/Edge): ícone de instalar na barra de endereço.

**Requisitos:** o navegador só instala PWA em **HTTPS** (ou em `localhost`, que só vale no próprio computador).
Para testar no celular, use o link `...app.github.dev` do Codespaces com a porta 8000 em visibilidade **Pública**.

**O que fica salvo no aparelho:** só o visual do site (CSS, JS, ícones) e uma página "sem conexão". Páginas com
dados da empresa nunca são guardadas, para não ficarem no aparelho depois do "Sair". O app precisa de internet.

**Arquivos:** `pwa/` (manifesto, service worker e página offline), `static/icons/` (ícones, gerados por
`python scripts/gerar_icones.py`), `static/js/pwa.js` (registro e botão de instalar).
Se mudar muito o visual, troque `PWA_VERSION` em `config/settings.py` para os aparelhos baixarem tudo de novo.

**Não é app de loja:** não vai para Play Store nem App Store. Se um dia for preciso, dá para empacotar este mesmo
site (Capacitor, ou TWA no Android) sem reescrever nada.

## Etapas

- [x] Etapa 1: site base (cadastro, login, cadastro de materiais)
- [x] Etapa 2: busca com filtros e match por regras (distância, volume, modalidade, frequência)
- [x] Etapa 3: negociação (proposta, contraproposta, conversa) e recibo digital
- [x] Etapa 4: IA (preencher anúncio por texto livre e sugerir mensagem na negociação)
- [x] Etapa 5: painel de resultados (histórico, volume, valores, estimativa de economia e CSV)
- [x] Etapa 6: versão app (PWA instalável no celular)


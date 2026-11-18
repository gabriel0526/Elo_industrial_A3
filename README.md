# Elo Industrial

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

## IA (Etapa 4)

Usa a API do Claude (Anthropic). Sem chave, o site funciona normalmente e os botões de IA não aparecem.

1. Crie uma chave em https://console.anthropic.com (a API tem cobrança própria, separada da assinatura do Claude.ai).
2. Copie `.env.example` para `.env` e cole a chave em `ANTHROPIC_API_KEY`.
   No Codespaces também dá para guardar a chave em *Settings > Codespaces > Secrets*.
3. `pip install -r requirements.txt` e reinicie o servidor.

Onde aparece:
- **Novo material:** caixa "Descreva com suas palavras" preenche o formulário.
- **Negociação:** botão "Sugerir mensagem com IA" gera um rascunho no campo de mensagem.

A IA só sugere: nada é salvo ou enviado sem a pessoa revisar. O limite padrão é 30 usos por hora por usuário
(`IA_LIMITE_POR_HORA`). O modelo padrão é `claude-haiku-5-5` (`CLAUDE_MODEL` para trocar).

## Testes

```bash
python manage.py test
```

## Etapas

- [x] Etapa 1: site base (cadastro, login, cadastro de materiais)
- [x] Etapa 2: busca com filtros e match por regras (distância, volume, modalidade, frequência)
- [x] Etapa 3: negociação (proposta, contraproposta, conversa) e recibo digital
- [x] Etapa 4: IA (preencher anúncio por texto livre e sugerir mensagem na negociação)
- [ ] Etapa 5: painel de histórico e economia
- [ ] Etapa 6: versão app

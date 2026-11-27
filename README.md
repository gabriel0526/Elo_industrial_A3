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


**Instalar**
- Android: botão "Instalar o app" no rodapé do site, ou menu do navegador > Instalar app.
- iPhone : Compartilhar > Adicionar à Tela de Início.
- Computador ícone de instalar na barra de endereço.



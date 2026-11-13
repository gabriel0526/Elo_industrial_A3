# Elo Industrial

so uma breve explicacção de como acessar
## rodar

```bash
python -m venv .venv
source .venv/bin/activate        # no Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Abra http://127.0.0.1:8000

p acessar o painel administrativo: `python manage.py createsuperuser` e depois http://127.0.0.1:8000/admin

## exemplo

```bash
python manage.py popular_exemplo
```

ja cria 6 empresas e 7 anúncios. Todas usam a senha `exemplo12345`
(e-mail da Marcenaria: `marcenariaboamadeira@exemplo.com`).

## estestes

```bash
python manage.py test
```

## to dividindo por etapas, ate agora so consgui essas, fica a vontade pra fazer qualquer alteração que achar melhor

- [x] etapa 1: site base (cadastro, login, cadastro de materiais)
- [x] etapa 2: busca com filtros e match por regras (distância, volume, modalidade, frequência)
- [ ] etapa 3: negociação e recibo
- [ ] etapa 4: IA
- [ ] etapa 5: painel de histórico e economia
- [ ] etapa 6: versão app

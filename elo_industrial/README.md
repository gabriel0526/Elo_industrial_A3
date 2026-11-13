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

Cria 6 empresas e 7 anúncios. Todas usam a senha `exemplo12345`
(e-mail da Marcenaria: `marcenariaboamadeira@exemplo.com`).

## Testes

```bash
python manage.py test
```

## Etapas

- [x] Etapa 1: site base (cadastro, login, cadastro de materiais)
- [x] Etapa 2: busca com filtros e match por regras (distância, volume, modalidade, frequência)
- [ ] Etapa 3: negociação e recibo
- [ ] Etapa 4: IA
- [ ] Etapa 5: painel de histórico e economia
- [ ] Etapa 6: versão app

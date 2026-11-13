from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from contas.models import Empresa

from .geo import coordenadas, distancia_km
from .match import combinacoes_para
from .models import Material


def criar_empresa(nome, cidade='Recife', estado='PE'):
    usuario = get_user_model().objects.create_user(
        username=f'{nome}@teste.com', email=f'{nome}@teste.com', password='senha-segura-123'
    )
    return Empresa.objects.create(
        usuario=usuario, nome=nome, tipo='ambos', cidade=cidade, estado=estado
    )


def criar_material(empresa, **extra):
    dados = dict(
        intencao='oferta', categoria='madeira', titulo='Apara de madeira',
        quantidade=Decimal('300'), unidade='kg', frequencia='semanal', modalidade='venda',
    )
    dados.update(extra)
    return Material.objects.create(empresa=empresa, **dados)


class GeoTests(SimpleTestCase):
    def test_coordenadas_ignoram_acento_e_maiuscula(self):
        self.assertEqual(coordenadas('RECIFE', 'pe'), coordenadas('Recife', 'PE'))
        self.assertEqual(coordenadas('Vitoria de Santo Antao', 'PE'), coordenadas('Vitória de Santo Antão', 'PE'))

    def test_cidade_desconhecida(self):
        self.assertIsNone(coordenadas('Cidade Inventada', 'PE'))

    def test_distancia_recife_caruaru(self):
        km = distancia_km(coordenadas('Recife', 'PE'), coordenadas('Caruaru', 'PE'))
        self.assertTrue(110 < km < 130)


class MatchTests(TestCase):
    def setUp(self):
        self.marcenaria = criar_empresa('marcenaria')
        self.briquete = criar_empresa('briquete', cidade='Olinda')
        self.oferta = criar_material(self.marcenaria)

    def test_combina_oferta_com_procura_da_mesma_categoria(self):
        procura = criar_material(self.briquete, intencao='procura', titulo='Preciso de madeira')
        resultado = combinacoes_para(self.oferta)
        self.assertEqual([r.material for r in resultado], [procura])
        self.assertGreaterEqual(resultado[0].pontuacao, 90)
        self.assertTrue(resultado[0].motivos)

    def test_categoria_diferente_nao_combina(self):
        criar_material(self.briquete, intencao='procura', categoria='metal')
        self.assertEqual(combinacoes_para(self.oferta), [])

    def test_mesma_empresa_nao_combina_consigo(self):
        criar_material(self.marcenaria, intencao='procura')
        self.assertEqual(combinacoes_para(self.oferta), [])

    def test_anuncio_inativo_nao_combina(self):
        criar_material(self.briquete, intencao='procura', ativo=False)
        self.assertEqual(combinacoes_para(self.oferta), [])

    def test_mais_proximo_pontua_mais(self):
        longe = criar_empresa('longe', cidade='Petrolina')
        perto = criar_material(self.briquete, intencao='procura')
        distante = criar_material(longe, intencao='procura')
        resultado = combinacoes_para(self.oferta)
        self.assertEqual(resultado[0].material, perto)
        self.assertGreater(resultado[0].pontuacao, resultado[1].pontuacao if len(resultado) > 1 else -1)
        self.assertNotIn(distante, [r.material for r in resultado[:1]])

    def test_tonelada_e_kg_sao_comparaveis(self):
        criar_material(self.briquete, intencao='procura', quantidade=Decimal('0.3'), unidade='t')
        resultado = combinacoes_para(self.oferta)
        self.assertIn('volume muito parecido', resultado[0].motivos)


class BuscaTests(TestCase):
    def setUp(self):
        self.a = criar_empresa('empresaa')
        self.b = criar_empresa('empresab', cidade='Salvador', estado='BA')
        criar_material(self.a, titulo='Apara de madeira')
        criar_material(self.a, titulo='Sobra de tecido', categoria='tecido')
        criar_material(self.b, titulo='Sucata de aço', categoria='metal', intencao='procura')
        criar_material(self.b, titulo='Material escondido', ativo=False)

    def titulos(self, resp):
        return sorted(m.titulo for m in resp.context['pagina'])

    def test_lista_so_ativos(self):
        resp = self.client.get(reverse('buscar'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.titulos(resp)), 3)
        self.assertNotIn('Material escondido', self.titulos(resp))

    def test_filtros(self):
        url = reverse('buscar')
        self.assertEqual(self.titulos(self.client.get(url, {'categoria': 'metal'})), ['Sucata de aço'])
        self.assertEqual(self.titulos(self.client.get(url, {'intencao': 'procura'})), ['Sucata de aço'])
        self.assertEqual(self.titulos(self.client.get(url, {'q': 'tecido'})), ['Sobra de tecido'])
        self.assertEqual(self.titulos(self.client.get(url, {'estado': 'BA'})), ['Sucata de aço'])
        self.assertEqual(len(self.titulos(self.client.get(url, {'cidade': 'recife'}))), 2)

    def test_sem_resultado_mostra_mensagem(self):
        resp = self.client.get(reverse('buscar'), {'q': 'inexistente'})
        self.assertContains(resp, 'Nenhum material encontrado')

    def test_ordenar_por_proximos_usa_empresa_logada(self):
        self.client.force_login(self.a.usuario)
        resp = self.client.get(reverse('buscar'), {'ordem': 'proximos'})
        lista = list(resp.context['pagina'])
        self.assertEqual(lista[-1].titulo, 'Sucata de aço')  # Salvador fica por último
        self.assertIsNotNone(lista[0].distancia)

    def test_paginacao(self):
        for i in range(12):
            criar_material(self.a, titulo=f'Lote {i}')
        resp = self.client.get(reverse('buscar'))
        self.assertEqual(len(resp.context['pagina']), 10)
        self.assertEqual(len(self.client.get(reverse('buscar'), {'pagina': 2}).context['pagina']), 5)

    def test_detalhe_mostra_combinacoes(self):
        oferta = criar_material(self.a, titulo='Oferta de PET', categoria='plastico')
        criar_material(self.b, titulo='Quero PET', categoria='plastico', intencao='procura')
        resp = self.client.get(reverse('material_detalhe', args=[oferta.pk]))
        self.assertContains(resp, 'Quero PET')

    def test_painel_mostra_quantidade_de_combinacoes(self):
        criar_material(self.b, titulo='Quero madeira', intencao='procura')
        self.client.force_login(self.a.usuario)
        resp = self.client.get(reverse('painel'))
        self.assertContains(resp, '1 combinação')

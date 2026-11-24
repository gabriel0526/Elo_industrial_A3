import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import resultados as calculo
from .models import Negociacao
from .tests import criar_empresa, criar_material


class FormatoTests(TestCase):
    def test_massa_em_kg_ou_toneladas(self):
        self.assertEqual(calculo.formatar_massa(Decimal('300')), '300 kg')
        self.assertEqual(calculo.formatar_massa(Decimal('12.5')), '12,50 kg')
        self.assertEqual(calculo.formatar_massa(Decimal('1250')), '1,25 t')
        self.assertEqual(calculo.formatar_massa(Decimal('0')), '0 kg')

    def test_reais_no_padrao_brasileiro(self):
        self.assertEqual(calculo.formatar_reais(Decimal('1234.5')), 'R$ 1.234,50')
        self.assertEqual(calculo.formatar_reais(Decimal('0')), 'R$ 0,00')

    def test_ler_valor_digitado(self):
        self.assertEqual(calculo.ler_valor('180,50'), Decimal('180.50'))
        self.assertEqual(calculo.ler_valor('1.250,5'), Decimal('1250.50'))
        self.assertEqual(calculo.ler_valor('R$ 90'), Decimal('90.00'))
        for ruim in ('', 'abc', '-3', '0', 'NaN', 'Infinity', '99999999'):
            self.assertIsNone(calculo.ler_valor(ruim), ruim)

    def test_unidades_que_nao_sao_massa(self):
        self.assertIsNone(calculo.massa_em_kg(Decimal('5'), 'm3'))
        self.assertEqual(calculo.massa_em_kg(Decimal('2'), 't'), Decimal('2000'))


class BaseResultados(TestCase):
    def setUp(self):
        self.marcenaria = criar_empresa('marcenaria')
        self.briquete = criar_empresa('briquete', cidade='Olinda')
        self.intrusa = criar_empresa('intrusa')
        self.outra = criar_empresa('outra')

    def concluir(self, fornecedora, receptora, quantidade, preco, unidade='kg', modalidade='venda',
                 categoria='madeira', titulo='Apara'):
        """Passa pelo fluxo de verdade: proposta, aceite e confirmação das duas partes."""
        material = criar_material(
            fornecedora, quantidade=Decimal('100000'), unidade=unidade, modalidade=modalidade,
            categoria=categoria, titulo=titulo, frequencia='mensal',
            preco=None if modalidade == 'doacao' else Decimal('1.00'),
        )
        neg = Negociacao.objects.create(
            material=material, proponente=receptora, quantidade=quantidade,
            preco=None if modalidade == 'doacao' else Decimal(preco), modalidade=modalidade,
            ultima_alteracao_por=receptora,
        )
        neg.aceitar(fornecedora)
        neg.confirmar_entrega(fornecedora)
        neg.confirmar_entrega(receptora)
        neg.refresh_from_db()
        return neg


class CalculoTests(BaseResultados):
    def dados(self, empresa, periodo='tudo', custo=None):
        return calculo.calcular(empresa, calculo.concluidas(empresa, periodo), custo)

    def test_soma_so_o_que_foi_concluido_e_separa_os_papeis(self):
        self.concluir(self.marcenaria, self.briquete, Decimal('100'), '0.45')            # 45,00
        self.concluir(self.marcenaria, self.briquete, Decimal('2'), '0', unidade='t', modalidade='doacao')
        # aberta, não conta
        material = criar_material(self.marcenaria, titulo='Ainda aberta')
        Negociacao.objects.create(
            material=material, proponente=self.briquete, quantidade=Decimal('10'),
            preco=Decimal('1'), ultima_alteracao_por=self.briquete,
        )

        forn = self.dados(self.marcenaria)
        self.assertEqual(forn['total'], 2)
        self.assertEqual(forn['parceiras'], 1)
        self.assertEqual(forn['desviado'], '2,10 t')
        self.assertEqual(forn['recebido'], '0 kg')
        self.assertEqual(forn['receita'], 'R$ 45,00')
        self.assertEqual(forn['gasto'], 'R$ 0,00')
        self.assertEqual(forn['doacoes_dadas'], 1)

        recep = self.dados(self.briquete)
        self.assertEqual(recep['recebido'], '2,10 t')
        self.assertEqual(recep['gasto'], 'R$ 45,00')
        self.assertEqual(recep['doacoes_recebidas'], 1)

    def test_m3_e_unidades_ficam_fora_da_massa(self):
        self.concluir(self.marcenaria, self.briquete, Decimal('12'), '5', unidade='m3')
        self.concluir(self.marcenaria, self.briquete, Decimal('40'), '2', unidade='un')
        dados = self.dados(self.marcenaria)
        self.assertEqual(dados['desviado'], '0 kg')
        self.assertIn('12 m³', dados['outras_unidades'])
        self.assertIn('40 un', dados['outras_unidades'])

    def test_economia_so_com_custo_informado(self):
        self.concluir(self.marcenaria, self.briquete, Decimal('2000'), '0.10')           # 2 t, receita 200,00
        self.assertIsNone(self.dados(self.marcenaria)['economia'])
        eco = self.dados(self.marcenaria, custo=Decimal('100'))['economia']
        self.assertEqual(eco['evitado'], 'R$ 200,00')
        self.assertEqual(eco['total'], 'R$ 400,00')

    def test_economia_nao_aparece_para_quem_so_recebeu(self):
        self.concluir(self.marcenaria, self.briquete, Decimal('500'), '0.10')
        self.assertIsNone(self.dados(self.briquete, custo=Decimal('100'))['economia'])

    def test_periodo_filtra_pela_data_de_conclusao(self):
        antiga = self.concluir(self.marcenaria, self.briquete, Decimal('100'), '1')
        Negociacao.objects.filter(pk=antiga.pk).update(concluida_em=timezone.now() - timedelta(days=200))
        self.concluir(self.marcenaria, self.briquete, Decimal('50'), '1')
        self.assertEqual(self.dados(self.marcenaria, '90')['total'], 1)
        self.assertEqual(self.dados(self.marcenaria, '365')['total'], 2)
        self.assertEqual(self.dados(self.marcenaria, 'tudo')['total'], 2)
        self.assertEqual(self.dados(self.marcenaria, 'invalido')['total'], 1)  # cai no período padrão

    def test_categorias_e_meses(self):
        self.concluir(self.marcenaria, self.briquete, Decimal('100'), '1', categoria='madeira')
        self.concluir(self.marcenaria, self.briquete, Decimal('100'), '1', categoria='madeira')
        self.concluir(self.marcenaria, self.briquete, Decimal('100'), '1', categoria='metal')
        dados = self.dados(self.marcenaria)
        self.assertEqual(dados['categorias'][0]['nome'], 'Madeira')
        self.assertEqual(dados['categorias'][0]['negociacoes'], 2)
        self.assertEqual(dados['categorias'][0]['largura'], 100)
        self.assertEqual(len(dados['meses']), 1)
        self.assertEqual(dados['meses'][0]['negociacoes'], 3)

    def test_sem_negociacoes_nao_quebra(self):
        dados = self.dados(self.marcenaria)
        self.assertEqual(dados['total'], 0)
        self.assertEqual(dados['categorias'], [])
        self.assertEqual(dados['meses'], [])


class ViewResultadosTests(BaseResultados):
    def test_exige_login(self):
        self.assertEqual(self.client.get(reverse('resultados')).status_code, 302)
        self.assertEqual(self.client.get(reverse('resultados_exportar')).status_code, 302)

    def test_pagina_mostra_numeros_da_propria_empresa(self):
        self.concluir(self.marcenaria, self.briquete, Decimal('100'), '0.45')
        self.concluir(self.intrusa, self.outra, Decimal('5000'), '1')   # de outras empresas
        self.client.force_login(self.marcenaria.usuario)
        resp = self.client.get(reverse('resultados'), {'periodo': 'tudo'})
        self.assertContains(resp, 'R$ 45,00')
        self.assertContains(resp, '100 kg')
        self.assertNotContains(resp, 'R$ 5.000,00')
        self.assertNotContains(resp, 'intrusa')

    def test_estado_vazio(self):
        self.client.force_login(self.marcenaria.usuario)
        self.assertContains(self.client.get(reverse('resultados')), 'Nenhuma negociação concluída')

    def test_custo_invalido_mostra_aviso(self):
        self.concluir(self.marcenaria, self.briquete, Decimal('2000'), '0.10')
        self.client.force_login(self.marcenaria.usuario)
        resp = self.client.get(reverse('resultados'), {'periodo': 'tudo', 'custo': 'abc'})
        self.assertContains(resp, 'Não entendi o valor por tonelada')
        self.assertNotContains(resp, 'Estimativa de economia')

    def test_custo_valido_mostra_estimativa(self):
        self.concluir(self.marcenaria, self.briquete, Decimal('2000'), '0.10')
        self.client.force_login(self.marcenaria.usuario)
        resp = self.client.get(reverse('resultados'), {'periodo': 'tudo', 'custo': '100'})
        self.assertContains(resp, 'Estimativa de economia')
        self.assertContains(resp, 'R$ 200,00')


class ExportarCsvTests(BaseResultados):
    def ler(self, resp):
        texto = resp.content.decode('utf-8-sig')
        return list(csv.reader(io.StringIO(texto), delimiter=';'))

    def test_csv_tem_so_as_minhas_negociacoes(self):
        self.concluir(self.marcenaria, self.briquete, Decimal('100'), '0.45')
        self.concluir(self.intrusa, self.outra, Decimal('9'), '1')
        self.client.force_login(self.marcenaria.usuario)
        resp = self.client.get(reverse('resultados_exportar'), {'periodo': 'tudo'})
        self.assertTrue(resp['Content-Type'].startswith('text/csv'))
        self.assertTrue(resp.content.startswith(b'\xef\xbb\xbf'))
        linhas = self.ler(resp)
        self.assertEqual(len(linhas), 2)                       # cabeçalho + 1
        self.assertEqual(linhas[0][0], 'Recibo')
        self.assertEqual(linhas[1][4], 'Fornecedora')
        self.assertEqual(linhas[1][5], 'briquete')
        self.assertEqual(linhas[1][11], '45,00')

    def test_nome_de_empresa_nao_vira_formula(self):
        perigosa = criar_empresa('=SOMA(1;1)')
        self.concluir(self.marcenaria, perigosa, Decimal('10'), '1')
        self.client.force_login(self.marcenaria.usuario)
        linhas = self.ler(self.client.get(reverse('resultados_exportar'), {'periodo': 'tudo'}))
        self.assertEqual(linhas[1][5], "'=SOMA(1;1)")

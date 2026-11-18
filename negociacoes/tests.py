from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase
from django.urls import reverse

from contas.models import Empresa
from materiais.models import Material

from .models import AcaoInvalida, Negociacao, Recibo


def criar_empresa(nome, cidade='Recife', estado='PE'):
    usuario = get_user_model().objects.create_user(
        username=f'{nome}@teste.com', email=f'{nome}@teste.com', password='senha-segura-123'
    )
    return Empresa.objects.create(usuario=usuario, nome=nome, tipo='ambos', cidade=cidade, estado=estado)


def criar_material(empresa, **extra):
    dados = dict(
        intencao='oferta', categoria='madeira', titulo='Apara de madeira',
        quantidade=Decimal('300'), unidade='kg', frequencia='unica', modalidade='venda',
        preco=Decimal('0.50'),
    )
    dados.update(extra)
    return Material.objects.create(empresa=empresa, **dados)


TERMOS = {'quantidade': '100', 'preco': '0.45', 'modalidade': 'venda', 'retirada': 'receptora'}


class BaseNegociacao(TestCase):
    def setUp(self):
        self.marcenaria = criar_empresa('marcenaria')   # dona do anúncio de oferta
        self.briquete = criar_empresa('briquete', cidade='Olinda')
        self.oferta = criar_material(self.marcenaria)

    def propor(self, empresa=None, material=None, **termos):
        self.client.force_login((empresa or self.briquete).usuario)
        material = material or self.oferta
        return self.client.post(
            reverse('negociacao_nova', args=[material.pk]), {**TERMOS, 'mensagem': 'Olá!', **termos}
        )

    def abrir(self):
        self.propor()
        return Negociacao.objects.get()


class PropostaTests(BaseNegociacao):
    def test_proposta_cria_negociacao_e_historico(self):
        resp = self.propor()
        neg = Negociacao.objects.get()
        self.assertRedirects(resp, reverse('negociacao_detalhe', args=[neg.pk]))
        self.assertEqual(neg.status, 'aberta')
        self.assertEqual(neg.ultima_alteracao_por, self.briquete)
        self.assertEqual(neg.mensagens.count(), 2)  # aviso do sistema + mensagem

    def test_nao_negocia_com_o_proprio_anuncio(self):
        self.propor(empresa=self.marcenaria)
        self.assertEqual(Negociacao.objects.count(), 0)

    def test_nao_abre_duas_negociacoes_no_mesmo_anuncio(self):
        self.propor()
        self.propor()
        self.assertEqual(Negociacao.objects.count(), 1)

    def test_quantidade_maior_que_o_anuncio_e_recusada(self):
        resp = self.propor(quantidade='999')
        self.assertContains(resp, 'disponíveis')
        self.assertEqual(Negociacao.objects.count(), 0)

    def test_venda_exige_preco_e_doacao_ignora(self):
        self.propor(preco='')
        self.assertEqual(Negociacao.objects.count(), 0)
        self.propor(modalidade='doacao', preco='9.99')
        self.assertIsNone(Negociacao.objects.get().preco)

    def test_anuncio_inativo_nao_recebe_proposta(self):
        self.oferta.ativo = False
        self.oferta.save()
        resp = self.propor()
        self.assertEqual(resp.status_code, 404)

    def test_exige_login(self):
        resp = self.client.get(reverse('negociacao_nova', args=[self.oferta.pk]))
        self.assertEqual(resp.status_code, 302)


class FluxoTests(BaseNegociacao):
    def test_papeis_em_oferta_e_em_procura(self):
        neg = self.abrir()
        self.assertEqual(neg.fornecedora, self.marcenaria)
        self.assertEqual(neg.receptora, self.briquete)
        procura = criar_material(self.briquete, intencao='procura', titulo='Procuro madeira')
        self.propor(empresa=self.marcenaria, material=procura)
        neg2 = Negociacao.objects.get(material=procura)
        self.assertEqual(neg2.fornecedora, self.marcenaria)
        self.assertEqual(neg2.receptora, self.briquete)

    def test_so_a_outra_parte_aceita(self):
        neg = self.abrir()
        with self.assertRaises(AcaoInvalida):
            neg.aceitar(self.briquete)  # quem propôs não aceita a própria proposta
        neg.aceitar(self.marcenaria)
        self.assertEqual(neg.status, 'aceita')

    def test_contraproposta_inverte_quem_pode_aceitar(self):
        neg = self.abrir()
        self.client.force_login(self.marcenaria.usuario)
        self.client.post(
            reverse('negociacao_alterar', args=[neg.pk]),
            {'quantidade': '80', 'preco': '0.60', 'modalidade': 'venda', 'retirada': 'fornecedora'},
        )
        neg.refresh_from_db()
        self.assertEqual(neg.quantidade, Decimal('80'))
        self.assertEqual(neg.ultima_alteracao_por, self.marcenaria)
        with self.assertRaises(AcaoInvalida):
            neg.aceitar(self.marcenaria)
        neg.aceitar(self.briquete)
        self.assertEqual(neg.status, 'aceita')

    def test_total_e_calculado(self):
        neg = self.abrir()
        self.assertEqual(neg.total, Decimal('45.00'))

    def test_recusar_e_cancelar(self):
        neg = self.abrir()
        neg.encerrar(self.marcenaria)
        self.assertEqual(neg.status, 'recusada')
        self.propor()
        neg2 = Negociacao.objects.exclude(pk=neg.pk).get()
        neg2.encerrar(self.briquete)
        self.assertEqual(neg2.status, 'cancelada')

    def test_nao_altera_depois_de_aceitar(self):
        neg = self.abrir()
        neg.aceitar(self.marcenaria)
        with self.assertRaises(AcaoInvalida):
            neg.alterar_termos(self.briquete, Decimal('1'), Decimal('1'), 'venda', 'receptora', '')

    def test_recibo_so_depois_das_duas_confirmacoes(self):
        neg = self.abrir()
        neg.aceitar(self.marcenaria)
        neg.confirmar_entrega(self.marcenaria)
        neg.refresh_from_db()
        self.assertEqual(neg.status, 'aceita')
        self.assertFalse(Recibo.objects.exists())
        neg.confirmar_entrega(self.briquete)
        neg.refresh_from_db()
        self.assertEqual(neg.status, 'concluida')
        recibo = Recibo.objects.get()
        self.assertEqual(recibo.valor_total, Decimal('45.00'))
        self.assertEqual(recibo.fornecedora_nome, 'marcenaria')
        self.assertTrue(recibo.codigo.startswith('EI-'))

    def test_confirmar_exige_negociacao_aceita(self):
        neg = self.abrir()
        with self.assertRaises(AcaoInvalida):
            neg.confirmar_entrega(self.briquete)

    def test_entrega_unica_baixa_estoque_e_desativa_quando_zera(self):
        neg = self.abrir()  # 100 de 300 kg
        neg.aceitar(self.marcenaria)
        neg.confirmar_entrega(self.marcenaria)
        neg.confirmar_entrega(self.briquete)
        self.oferta.refresh_from_db()
        self.assertEqual(self.oferta.quantidade, Decimal('200'))
        self.assertTrue(self.oferta.ativo)

        self.propor(quantidade='200')
        neg2 = Negociacao.objects.exclude(pk=neg.pk).get()
        neg2.aceitar(self.marcenaria)
        neg2.confirmar_entrega(self.marcenaria)
        neg2.confirmar_entrega(self.briquete)
        self.oferta.refresh_from_db()
        self.assertEqual(self.oferta.quantidade, 0)
        self.assertFalse(self.oferta.ativo)

    def test_anuncio_recorrente_nao_baixa_estoque(self):
        semanal = criar_material(self.marcenaria, frequencia='semanal', titulo='Semanal')
        self.propor(material=semanal)
        neg = Negociacao.objects.get(material=semanal)
        neg.aceitar(self.marcenaria)
        neg.confirmar_entrega(self.marcenaria)
        neg.confirmar_entrega(self.briquete)
        semanal.refresh_from_db()
        self.assertEqual(semanal.quantidade, Decimal('300'))
        self.assertTrue(semanal.ativo)

    def test_anuncio_com_negociacao_nao_pode_ser_apagado(self):
        self.abrir()
        with self.assertRaises(ProtectedError):
            self.oferta.delete()
        self.client.force_login(self.marcenaria.usuario)
        self.client.post(reverse('material_excluir', args=[self.oferta.pk]))
        self.assertTrue(Material.objects.filter(pk=self.oferta.pk).exists())


class AcessoTests(BaseNegociacao):
    def test_terceira_empresa_nao_ve_nem_age(self):
        neg = self.abrir()
        intrusa = criar_empresa('intrusa')
        self.client.force_login(intrusa.usuario)
        self.assertEqual(self.client.get(reverse('negociacao_detalhe', args=[neg.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('negociacao_aceitar', args=[neg.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('negociacao_mensagem', args=[neg.pk]), {'texto': 'oi'}).status_code, 404)
        neg.refresh_from_db()
        self.assertEqual(neg.status, 'aberta')

    def test_acoes_exigem_post(self):
        neg = self.abrir()
        self.client.force_login(self.marcenaria.usuario)
        self.assertEqual(self.client.get(reverse('negociacao_aceitar', args=[neg.pk])).status_code, 405)

    def test_recibo_so_para_as_partes(self):
        neg = self.abrir()
        neg.aceitar(self.marcenaria)
        neg.confirmar_entrega(self.marcenaria)
        neg.confirmar_entrega(self.briquete)
        recibo = Recibo.objects.get()
        self.client.force_login(self.briquete.usuario)
        self.assertContains(self.client.get(reverse('recibo', args=[recibo.pk])), recibo.codigo)
        self.client.force_login(criar_empresa('intrusa').usuario)
        self.assertEqual(self.client.get(reverse('recibo', args=[recibo.pk])).status_code, 404)

    def test_usuario_sem_empresa_nao_quebra(self):
        admin = get_user_model().objects.create_superuser('admin', 'a@a.com', 'senha-segura-123')
        self.client.force_login(admin)
        for nome in ('painel', 'negociacoes_lista'):
            self.assertRedirects(self.client.get(reverse(nome)), reverse('home'))


class MensagemEPendenciaTests(BaseNegociacao):
    def test_enviar_mensagem(self):
        neg = self.abrir()
        self.client.force_login(self.marcenaria.usuario)
        self.client.post(reverse('negociacao_mensagem', args=[neg.pk]), {'texto': 'Retirada na quinta?'})
        self.assertTrue(neg.mensagens.filter(texto='Retirada na quinta?', autor=self.marcenaria).exists())
        self.assertContains(self.client.get(reverse('negociacao_detalhe', args=[neg.pk])), 'Retirada na quinta?')

    def test_negociacao_encerrada_nao_aceita_mensagem(self):
        neg = self.abrir()
        neg.encerrar(self.marcenaria)
        self.client.force_login(self.briquete.usuario)
        self.client.post(reverse('negociacao_mensagem', args=[neg.pk]), {'texto': 'ainda aí?'})
        self.assertFalse(neg.mensagens.filter(texto='ainda aí?').exists())

    def test_pendencias_acompanham_de_quem_e_a_vez(self):
        neg = self.abrir()
        qs = Negociacao.objects
        self.assertEqual(qs.pendentes_de(self.marcenaria).count(), 1)  # precisa responder
        self.assertEqual(qs.pendentes_de(self.briquete).count(), 0)    # aguardando
        neg.aceitar(self.marcenaria)
        self.assertEqual(qs.pendentes_de(self.marcenaria).count(), 1)  # confirmar entrega
        self.assertEqual(qs.pendentes_de(self.briquete).count(), 1)
        neg.confirmar_entrega(self.marcenaria)
        self.assertEqual(qs.pendentes_de(self.marcenaria).count(), 0)
        self.assertEqual(qs.pendentes_de(self.briquete).count(), 1)

    def test_contador_aparece_no_menu(self):
        self.abrir()
        self.client.force_login(self.marcenaria.usuario)
        self.assertContains(self.client.get(reverse('home')), 'class="contador"')

    def test_lista_agrupa_por_situacao(self):
        self.abrir()
        self.client.force_login(self.marcenaria.usuario)
        resp = self.client.get(reverse('negociacoes_lista'))
        self.assertEqual(len(resp.context['aguardando']), 1)
        self.assertEqual(len(resp.context['andamento']), 0)
        self.client.force_login(self.briquete.usuario)
        resp = self.client.get(reverse('negociacoes_lista'))
        self.assertEqual(len(resp.context['andamento']), 1)

    def test_detalhe_do_anuncio_mostra_botao_certo(self):
        url = reverse('material_detalhe', args=[self.oferta.pk])
        self.assertContains(self.client.get(url), 'Entre para fazer uma proposta')
        self.client.force_login(self.briquete.usuario)
        self.assertContains(self.client.get(url), 'Fazer proposta')
        self.client.force_login(self.marcenaria.usuario)
        self.assertNotContains(self.client.get(url), 'Fazer proposta')
        self.abrir()
        self.client.force_login(self.briquete.usuario)
        self.assertContains(self.client.get(url), 'Ver minha negociação')

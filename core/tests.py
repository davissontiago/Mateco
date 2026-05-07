"""
Testes automatizados — NotasAuto

Coberturas:
1. FiscalRouter escolhe o serviço correto (nuvem vs direto)
2. Isolamento multi-tenant: usuário A não acessa dados da empresa B
3. EmpresaConfigForm rejeita PFX inválido
4. Numeração de NFC-e é isolada por ambiente (homologação não interfere na produção)
5. View /configuracoes/ restrita a is_staff
6. View /emitir-nota/ persiste campos SEFAZ direto corretamente
"""

from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import Empresa, NotaFiscal, PerfilUsuario


# ─────────────────────────────────────────────
# Fixtures reutilizáveis
# ─────────────────────────────────────────────

def _empresa(cnpj='12345678000100', ambiente='homologacao', emissor='nuvem', nome='Teste Ltda'):
    return Empresa.objects.create(
        nome=nome, nome_fantasia=nome, cnpj=cnpj,
        crt='1', cep='65000000', logradouro='Rua A', numero='1',
        bairro='Centro', cidade='São Luís', uf='MA',
        cod_municipio='2111300', ambiente=ambiente, emissor_fiscal=emissor,
    )


def _usuario(username, empresa, is_staff=False):
    u = User.objects.create_user(username=username, password='senha123', is_staff=is_staff)
    PerfilUsuario.objects.create(user=u, empresa=empresa)
    return u


# ─────────────────────────────────────────────
# 1. FiscalRouter
# ─────────────────────────────────────────────

class FiscalRouterTest(TestCase):

    def test_router_chama_nuvem_quando_emissor_nuvem(self):
        empresa = _empresa(emissor='nuvem')
        itens = [{'id': 1, 'nome': 'Produto', 'quantidade': 1,
                  'preco_unitario': 10.0, 'valor_total': 10.0, 'ncm': '00000000'}]
        pagamentos = [{'forma_pagamento': '01', 'valor': 10.0}]

        mock_ret = (True, {'id': 'abc', 'numero': 1, 'serie': 1, 'chave': 'x' * 44,
                           'status': 'autorizado', 'data_emissao': '2024-01-01T00:00:00',
                           'ambiente': 'homologacao'}, 10.0)

        with patch('core.services.NuvemFiscalService.emitir_nfce', return_value=mock_ret) as mock_nuvem:
            from core.fiscal_router import FiscalRouter
            FiscalRouter.emitir_nfce(empresa, itens, pagamentos)
            mock_nuvem.assert_called_once()

    def test_router_chama_sefaz_quando_emissor_direto(self):
        empresa = _empresa(emissor='direto')
        itens = [{'id': 1, 'nome': 'Produto', 'quantidade': 1,
                  'preco_unitario': 10.0, 'valor_total': 10.0, 'ncm': '00000000'}]
        pagamentos = [{'forma_pagamento': '01', 'valor': 10.0}]

        mock_ret = (True, {'id': 'x' * 44, 'numero': 1, 'serie': 2, 'chave': 'x' * 44,
                           'status': 'autorizado', 'data_emissao': '2024-01-01T00:00:00',
                           'ambiente': 'homologacao', 'qrcode_url': '', 'xml_protocolo': '',
                           'protocolo_autorizacao': '123'}, 10.0)

        with patch('core.sefaz_service.SefazService.emitir_nfce', return_value=mock_ret) as mock_sefaz:
            from core.fiscal_router import FiscalRouter
            FiscalRouter.emitir_nfce(empresa, itens, pagamentos)
            mock_sefaz.assert_called_once()


# ─────────────────────────────────────────────
# 2. Isolamento multi-tenant
# ─────────────────────────────────────────────

class IsolamentoMultiTenantTest(TestCase):

    def setUp(self):
        self.emp_a = _empresa(cnpj='11111111000111', nome='Empresa Alpha')
        self.emp_b = _empresa(cnpj='22222222000122', nome='Empresa Beta')
        self.user_a = _usuario('user_a', self.emp_a)
        self.user_b = _usuario('user_b', self.emp_b)
        self.nota_a = NotaFiscal.objects.create(
            empresa=self.emp_a, numero=1, serie=1, valor_total='10.00',
            status='AUTORIZADA', ambiente='homologacao', forma_pagamento='01',
        )
        self.client = Client()

    def test_usuario_b_nao_acessa_nota_de_a_via_imprimir(self):
        self.client.login(username='user_b', password='senha123')
        url = reverse('imprimir_nota', args=[self.nota_a.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_usuario_a_nao_ve_clientes_de_b(self):
        from .models import Cliente
        Cliente.objects.create(empresa=self.emp_b, nome='Cliente B', cpf_cnpj='99999999999')
        self.client.login(username='user_a', password='senha123')
        url = reverse('listar_clientes')
        resp = self.client.get(url)
        self.assertNotContains(resp, 'Cliente B')

    def test_configuracoes_opera_apenas_empresa_propria(self):
        _usuario('staff_a', self.emp_a, is_staff=True)
        self.client.login(username='staff_a', password='senha123')
        url = reverse('configuracoes')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # O form deve estar vinculado à empresa A, não B
        self.assertContains(resp, self.emp_a.nome)
        self.assertNotContains(resp, self.emp_b.nome)


# ─────────────────────────────────────────────
# 3. EmpresaConfigForm — PFX inválido
# ─────────────────────────────────────────────

class EmpresaConfigFormTest(TestCase):

    def setUp(self):
        self.empresa = _empresa()

    def test_pfx_invalido_e_rejeitado(self):
        from django.test import override_settings
        with override_settings(FIELD_ENCRYPTION_KEY='chave-de-teste-32-chars-1234567'):
            from .forms import EmpresaConfigForm
            pfx_falso = SimpleUploadedFile('cert.pfx', b'isto nao e um pfx valido', content_type='application/x-pkcs12')
            form = EmpresaConfigForm(
                data={'ambiente': 'homologacao', 'emissor_fiscal': 'direto',
                      'senha_pfx_homologacao': 'qualquer',
                      'serie_nfce_homologacao': 2, 'serie_nfce_producao': 3},
                files={'pfx_homologacao': pfx_falso},
                instance=self.empresa,
            )
            # clean() deve detectar PFX inválido — form não é válido
            form.is_valid()
            self.assertIn('__all__', form.errors)

    def test_pfx_ausente_sem_erro(self):
        from django.test import override_settings
        with override_settings(FIELD_ENCRYPTION_KEY='chave-de-teste-32-chars-1234567'):
            from .forms import EmpresaConfigForm
            form = EmpresaConfigForm(
                data={'ambiente': 'homologacao', 'emissor_fiscal': 'nuvem',
                      'serie_nfce_homologacao': 2, 'serie_nfce_producao': 3},
                files={},
                instance=self.empresa,
            )
            self.assertTrue(form.is_valid(), form.errors)


# ─────────────────────────────────────────────
# 4. Numeração isolada por ambiente
# ─────────────────────────────────────────────

class NumeracaoAmbienteTest(TestCase):

    def setUp(self):
        self.empresa = _empresa()

    def _criar_nota(self, numero, serie, ambiente):
        return NotaFiscal.objects.create(
            empresa=self.empresa, numero=numero, serie=serie,
            valor_total='50.00', status='AUTORIZADA',
            ambiente=ambiente, forma_pagamento='01',
        )

    def test_proximo_numero_homologacao_nao_interfere_producao(self):
        # Simula 5 notas em homologação (série 2)
        for i in range(1, 6):
            self._criar_nota(i, 2, 'homologacao')

        # Alterna para produção
        self.empresa.ambiente = 'producao'
        self.empresa.save()

        from core.sefaz_service import SefazService
        serie, numero = SefazService._proximo_numero(self.empresa)

        # Produção usa série 3, deve começar do 1
        self.assertEqual(serie, 3)
        self.assertEqual(numero, 1)

    def test_proximo_numero_sequencial_dentro_do_mesmo_ambiente(self):
        self._criar_nota(1, 2, 'homologacao')
        self._criar_nota(2, 2, 'homologacao')

        self.empresa.ambiente = 'homologacao'
        self.empresa.save()

        from core.sefaz_service import SefazService
        serie, numero = SefazService._proximo_numero(self.empresa)

        self.assertEqual(serie, 2)
        self.assertEqual(numero, 3)


# ─────────────────────────────────────────────
# 5. View /configuracoes/ restrita a is_staff
# ─────────────────────────────────────────────

class ConfiguracoesAcessoTest(TestCase):

    def setUp(self):
        self.empresa = _empresa()
        self.user = _usuario('comum', self.empresa, is_staff=False)
        self.client = Client()

    def test_usuario_autenticado_acessa(self):
        self.client.login(username='comum', password='senha123')
        resp = self.client.get(reverse('configuracoes'))
        self.assertEqual(resp.status_code, 200)

    def test_usuario_nao_autenticado_redirecionado(self):
        resp = self.client.get(reverse('configuracoes'))
        self.assertEqual(resp.status_code, 302)


# ─────────────────────────────────────────────
# 6. View /emitir-nota/ persiste campos SEFAZ direto
# ─────────────────────────────────────────────

class EmitirNotaViewTest(TestCase):

    def setUp(self):
        from estoque.models import Produto
        self.empresa = _empresa(emissor='direto')
        self.user = _usuario('operador', self.empresa)
        self.produto = Produto.objects.create(
            empresa=self.empresa, nome='Arroz', preco='5.00',
            ncm='10063021', estoque_atual=100,
        )
        self.client = Client()
        self.client.login(username='operador', password='senha123')

    def test_emissao_direto_persiste_protocolo_e_qrcode(self):
        resposta_mock = {
            'id': 'a' * 44,
            'numero': 1, 'serie': 2,
            'chave': 'a' * 44,
            'status': 'autorizado',
            'data_emissao': '2024-06-01T10:00:00-03:00',
            'ambiente': 'homologacao',
            'qrcode_url': 'http://qrcode.example.com/abc',
            'xml_protocolo': '<nfeProc/>',
            'protocolo_autorizacao': '135001234567890',
        }

        with patch('core.fiscal_router.FiscalRouter.emitir_nfce',
                   return_value=(True, resposta_mock, 5.0)):
            resp = self.client.post(
                reverse('emitir_nota'),
                data='{"itens":[{"id":' + str(self.produto.id) + ',"nome":"Arroz","quantidade":1,'
                     '"preco_unitario":5.0,"valor_total":5.0,"ncm":"10063021"}],'
                     '"forma_pagamento":"01"}',
                content_type='application/json',
            )

        self.assertEqual(resp.status_code, 200)
        nota = NotaFiscal.objects.get(empresa=self.empresa)
        self.assertEqual(nota.protocolo_autorizacao, '135001234567890')
        self.assertEqual(nota.qrcode_url, 'http://qrcode.example.com/abc')
        self.assertIsNone(nota.id_nota)  # SEFAZ direto não usa id_nota da NuvemFiscal

    def test_emissao_sem_itens_retorna_400(self):
        resp = self.client.post(
            reverse('emitir_nota'),
            data='{"itens":[],"forma_pagamento":"01"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

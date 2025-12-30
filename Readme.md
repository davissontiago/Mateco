# Mateco Sistemas - PDV e Controle de Estoque

Sistema de Gestão (ERP) focado em emissão de notas fiscais (NFC-e) e controle de estoque, desenvolvido com Django e arquitetado para Deploy Serverless na Vercel.

## 🚀 Tecnologias
- **Backend:** Python 3.12, Django 5.x
- **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
- **Banco de Dados:** SQLite (Desenvolvimento) / PostgreSQL (Produção/Neon/Supabase)
- **Integração Fiscal:** API Nuvem Fiscal
- **Deploy:** Vercel (Serverless)

---

## 📂 Estrutura do Projeto

Entenda como o código está organizado para facilitar a manutenção e evolução do sistema:

### 🔹 Aplicações (Backend)
* **`core/`**: O coração do sistema.
    * `models.py`: Define a `NotaFiscal`.
    * `views.py`: Controla as páginas (Home, PDV, Histórico) e a API do carrinho.
    * `services.py`: Contém a lógica pesada de comunicação com a **API da Nuvem Fiscal**.
    * `utils.py`: Algoritmo do "Carrinho Inteligente" (simulação de valores).
* **`estoque/`**: Gestão de inventário.
    * `models.py`: Define o `Produto` (Preço, NCM, Estoque).
    * `management/commands/`: Scripts personalizados (ex: importação de CSV).
* **`setup/`**: Configurações globais do Django.
    * `settings.py`: Configurações de banco, segurança, apps e variáveis de ambiente.
    * `urls.py`: Roteamento principal (mapa de URLs do site).

### 🔹 Frontend & Arquivos Estáticos
* **`templates/`**: Arquivos HTML (Páginas).
    * `base.html`: Esqueleto do site (Menu, Rodapé, Imports).
    * `emitir.html`: Tela do PDV (Ponto de Venda).
* **`static/`**: Arquivos de estilo e scripts.
    * `css/style.css`: Estilos globais e cores da marca.
    * `css/emitir.css`: Estilos específicos do PDV e modais.
    * `js/emitir.js`: Lógica de interação do PDV, busca e chamadas de API.
* **`staticfiles/`**: Pasta gerada automaticamente (não edite aqui!) onde o Django reúne os arquivos para o deploy na Vercel.

---

## 🛠️ Comandos Principais (Glossário)

Lista dos comandos essenciais para operar e manter o sistema via terminal:

### 1. Inicialização e Execução
* **`python manage.py runserver`**
    * **O que faz:** Inicia o servidor de desenvolvimento no seu computador.
    * **Quando usar:** Sempre que for programar ou testar o site localmente.

### 2. Banco de Dados
* **`python manage.py makemigrations`**
    * **O que faz:** Cria um arquivo de "rascunho" com as mudanças que você fez nos `models.py`.
    * **Quando usar:** Sempre que criar uma nova tabela ou adicionar um campo novo (ex: adicionar `cpf` no Cliente).
* **`python manage.py migrate`**
    * **O que faz:** Aplica os rascunhos (migrations) no banco de dados real, criando ou alterando as tabelas.
    * **Quando usar:** Logo após rodar o `makemigrations` ou ao baixar o projeto pela primeira vez.

### 3. Deploy e Arquivos Estáticos
* **`python manage.py collectstatic`**
    * **O que faz:** Copia todos os arquivos das pastas `static/` para a pasta `staticfiles/`.
    * **Por que é vital:** A Vercel (produção) não lê a pasta `static` original, ela só lê a `staticfiles`. Se você alterar o CSS e não rodar esse comando, o site em produção ficará desatualizado ou "quebrado".

### 4. Administração e Utilitários
* **`python manage.py createsuperuser`**
    * **O que faz:** Cria o login de administrador mestre.
    * **Quando usar:** Para acessar o painel `/admin` e gerenciar usuários ou ver o banco de dados visualmente.
* **`python manage.py importar_csv`**
    * **O que faz:** Comando personalizado criado para ler o arquivo `Produtos.csv` na raiz e alimentar o banco de dados.
    * **Quando usar:** Para atualizar o estoque em massa ou cadastrar produtos novos via planilha.

---

## ⚙️ Variáveis de Ambiente (.env)

Para o sistema funcionar, crie um arquivo `.env` na raiz com as seguintes chaves:

```env
SECRET_KEY=sua_chave_secreta_django
DEBUG=True
DATABASE_URL=url_do_seu_banco_postgres (opcional em dev)

# Integração Nuvem Fiscal
NUVEM_CLIENT_ID=seu_client_id
NUVEM_CLIENT_SECRET=seu_client_secret

# Dados da Empresa (Multi-Empresa)
CNPJ_EMITENTE=00000000000000
IE_EMITENTE=000000000
EMPRESA_NOME=Mateco Material de Construção
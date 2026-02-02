# 🛒 Mateco - Sistema de Gestão para Varejo (SaaS)

> Sistema web de gestão para varejo com emissão fiscal integrada, hospedado em arquitetura serverless.

![Status](https://img.shields.io/badge/Status-Em_Produção-brightgreen) ![Deploy](https://img.shields.io/badge/Deploy-Vercel-black) ![Python](https://img.shields.io/badge/Python-3.x-blue) ![Django](https://img.shields.io/badge/Django-5.0-green)

![Dashboard de para emissão das notas fiscais](static/img/emitir.png)

![Relatório da emissão das notas ficais](static/img/historico.png)

## 🎯 Sobre o Projeto

O **Mateco** é uma solução leve e moderna para o varejo (papelarias, lojas de construção, mercados), focada na agilidade do ponto de venda e na emissão fiscal descomplicada. 

O sistema resolve o problema de infraestrutura local cara: ele roda 100% na nuvem (Vercel), permitindo gestão de qualquer lugar sem servidores físicos na loja.

### 🚀 Diferenciais Técnicos

* **Arquitetura Serverless (Vercel):** Configurado via `vercel.json` para rodar em ambiente Python serverless, garantindo escalabilidade automática e baixo custo.
* **Emissão Fiscal via API:** Integração direta com a **NuvemFiscal** usando a biblioteca `requests`. O sistema envia os dados da venda e recebe o PDF/XML autorizado em tempo real, sem necessidade de DLLs ou instaladores locais.
* **Interface Administrativa Personalizada:** Utiliza `django-admin-interface` para entregar um painel de gestão limpo e profissional para o usuário final.

## ✨ Funcionalidades

* **Frente de Caixa (PDV):** Interface ágil para lançamento de vendas.
* **Emissão de NFC-e:** Geração e armazenamento de notas fiscais.
* **Gestão de Estoque:** Controle de entradas, saídas e cadastro de produtos.
* **Dashboard:** Visualização rápida de métricas de vendas.

## 🛠️ Tecnologias Utilizadas

* **Backend:** Python, Django 5.0
* **Hospedagem:** Vercel (Runtime Python)
* **Integração Fiscal:** API REST NuvemFiscal
* **Banco de Dados:** SQLite (Dev) / PostgreSQL (Prod)
* **Frontend:** Django Templates + Bootstrap

## 📂 Estrutura do Projeto

* `core/`: Núcleo do sistema (Serviços de API NuvemFiscal, Lógica de Negócio).
* `estoque/`: Gestão de produtos e inventário.
* `setup/`: Configurações do Django e WSGI.
* `vercel.json`: Configuração de deploy para a infraestrutura Vercel.

## 🔧 Como Executar Localmente

1. **Clone o repositório**
   ```bash
   git clone [https://github.com/davissontiago/mateco.git](https://github.com/davissontiago/mateco.git)
   cd mateco
2. **Instale as dependências**

    ```bash
    pip install -r requirements.txt

3. **Configure as Variáveis** Crie um arquivo .env com suas credenciais (Secret Key Django, Credenciais NuvemFiscal).

4. **Execute as migrações e o servidor**

    ```bash
    python manage.py migrate
    python manage.py runserver

 ## Desenvolvido por Dávisson Tiago 👨‍💻

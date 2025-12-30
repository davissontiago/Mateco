/**
 * ============================================================================
 * MATECO SISTEMAS - CONTROLE DO PDV (PONTO DE VENDA)
 * * Este arquivo gerencia toda a interatividade da tela de emissão:
 * 1. Busca dinâmica de produtos.
 * 2. Gerenciamento do array 'carrinho' (adicionar/remover).
 * 3. Simulação de valores (Algoritmo do Carrinho Inteligente).
 * 4. Comunicação com a API para emissão da nota fiscal.
 * ============================================================================
 */

// ============================================================================
// 1. VARIÁVEIS GLOBAIS E SELETORES DOM
// ============================================================================

let carrinho = [];                  // Armazena os itens atuais da venda
let produtoSelecionadoTemp = null;  // Armazena temporariamente o produto clicado na busca

// Elementos principais da interface
const buscaInput = document.getElementById('buscaInput');
const listaSugestoes = document.getElementById('listaSugestoes');
const modalQtd = document.getElementById('modalQuantidade');

// ============================================================================
// 2. LÓGICA DE BUSCA E AUTOCOMPLETE
// ============================================================================

/**
 * Escuta o evento de digitação no campo de busca.
 * Faz requisições à API apenas se houver mais de 2 caracteres.
 */
buscaInput.addEventListener('input', async (e) => {
    const termo = e.target.value;
    
    // Limpa sugestões se o termo for muito curto
    if (termo.length < 2) { 
        listaSugestoes.style.display = 'none'; 
        return; 
    }

    // Busca produtos no backend
    const res = await fetch(`/api/produtos/?q=${termo}`);
    const produtos = await res.json();

    listaSugestoes.innerHTML = '';
    
    // Renderiza a lista de sugestões
    if (produtos.length > 0) {
        listaSugestoes.style.display = 'block';
        produtos.forEach(prod => {
            const div = document.createElement('div');
            div.className = 'sugestao-item';
            div.innerHTML = `
                <div style="flex:1">
                    <div style="font-weight:bold">${prod.nome}</div>
                    <small style="color:#777">R$ ${prod.preco_unitario.toFixed(2)}</small>
                </div>
                <div style="font-weight:bold; color:#2980b9">+</div>
            `;
            // Define ação de clique para abrir modal de quantidade
            div.onclick = () => { abrirModalQtd(prod); };
            listaSugestoes.appendChild(div);
        });
    } else {
        listaSugestoes.style.display = 'none';
    }
});

/**
 * Fecha a lista de sugestões se o usuário clicar fora do input de busca.
 */
document.addEventListener('click', (e) => {
    if (e.target !== buscaInput) listaSugestoes.style.display = 'none';
});

// ============================================================================
// 3. GERENCIAMENTO DE MODAIS (QUANTIDADE)
// ============================================================================

/**
 * Abre o modal para definir a quantidade do produto selecionado.
 * @param {Object} prod - O objeto produto vindo da API.
 */
function abrirModalQtd(prod) {
    produtoSelecionadoTemp = prod;
    document.getElementById('nomeProdModal').innerText = prod.nome;
    document.getElementById('qtdInputModal').value = 1; 

    listaSugestoes.style.display = 'none'; 
    modalQtd.showModal();

    // Dá foco no input de quantidade após o modal abrir
    setTimeout(() => document.getElementById('qtdInputModal').focus(), 100);
}

/**
 * Fecha o modal de quantidade e limpa o estado temporário.
 */
function fecharModalQtd() {
    modalQtd.close();
    produtoSelecionadoTemp = null;
    buscaInput.value = ''; 
}

/**
 * Adiciona o produto ao carrinho com a quantidade informada no modal.
 */
function confirmarAdicaoManual() {
    if (!produtoSelecionadoTemp) return;

    const qtd = parseInt(document.getElementById('qtdInputModal').value);
    if (isNaN(qtd) || qtd <= 0) {
        alert("Quantidade inválida");
        return;
    }

    carrinho.push({
        id: produtoSelecionadoTemp.id,
        nome: produtoSelecionadoTemp.nome,
        preco_unitario: produtoSelecionadoTemp.preco_unitario,
        quantidade: qtd,
        valor_total: produtoSelecionadoTemp.preco_unitario * qtd,
        ncm: produtoSelecionadoTemp.ncm
    });

    atualizarCarrinho();
    fecharModalQtd();
}

// ============================================================================
// 4. CARRINHO INTELIGENTE E SIMULAÇÃO
// ============================================================================

/**
 * Preenche o valor restante para atingir a meta (Valor Alvo).
 * Mantém os itens que já estão no carrinho.
 */
async function completarValor() {
    const valorAlvo = parseFloat(document.getElementById('valorAlvoInput').value);
    const totalAtual = calcularTotal();

    if (isNaN(valorAlvo) || valorAlvo <= totalAtual) {
        alert("A meta deve ser maior que o total atual."); return;
    }

    const falta = valorAlvo - totalAtual;
    
    // Feedback visual no botão
    const btn = document.querySelector('.btn-completar');
    const txtOriginal = btn.innerText;
    btn.innerText = "⏳...";
    btn.disabled = true;

    try {
        const res = await fetch(`/api/produtos/?simular=true&valor=${falta}`);
        const data = await res.json();
        
        if (data.error) { alert(data.error); return; }
        
        // Adiciona os itens simulados ao carrinho existente
        data.itens.forEach(item => carrinho.push(item));
        atualizarCarrinho();
    } catch (e) {
        alert("Erro de conexão.");
    } finally {
        btn.innerText = txtOriginal;
        btn.disabled = false;
    }
}

/**
 * Limpa o carrinho atual e refaz a simulação do zero para o valor alvo.
 */
async function refazerSimulacao() {
    const valorAlvo = parseFloat(document.getElementById('valorAlvoInput').value);
    if (isNaN(valorAlvo) || valorAlvo <= 0) { alert("Digite uma meta para refazer."); return; }
    
    carrinho = [];
    atualizarCarrinho();
    await completarValor();
}

/**
 * Gera um carrinho completo baseado no painel de "Valor Alvo" (Aba 2).
 */
async function gerarCarrinhoInteligente() {
    const valorAlvo = parseFloat(document.getElementById('valor-alvo').value);

    if (isNaN(valorAlvo) || valorAlvo <= 0) {
        alert("Por favor, digite um valor válido para gerar o carrinho.");
        return;
    }

    const btn = document.querySelector('#painel-valor .btn-adicionar');
    const txtOriginal = btn.innerText;
    btn.innerText = "⏳...";
    btn.disabled = true;

    try {
        const res = await fetch(`/api/produtos/?simular=true&valor=${valorAlvo}`);
        const data = await res.json();

        if (data.error) {
            alert(data.error);
            return;
        }

        carrinho = data.itens;
        atualizarCarrinho();

    } catch (e) {
        console.error("Erro na simulação:", e);
        alert("Erro ao conectar com o servidor.");
    } finally {
        btn.innerText = "⚡Gerar";
        btn.disabled = false;
    }
}

// ============================================================================
// 5. GERENCIAMENTO DO CARRINHO (CRUD)
// ============================================================================

/**
 * Renderiza o carrinho na tela HTML e atualiza os totais.
 * Controla também o estado do botão "Emitir" (habilitado/desabilitado).
 */
function atualizarCarrinho() {
    const divCarrinho = document.getElementById('carrinhoVisual');
    const totalDisplay = document.getElementById('totalDisplay');
    const btnEmitir = document.getElementById('btnEmitir');

    // Estado Vazio
    if (carrinho.length === 0) {
        divCarrinho.innerHTML = '<div style="text-align: center; color: #bbb; padding: 30px 0;">🛒 Seu carrinho está vazio</div>';
        totalDisplay.innerText = "R$ 0,00";
        btnEmitir.disabled = true;
        btnEmitir.style.background = "#bdc3c7";
        return;
    }

    // Renderização dos Itens
    divCarrinho.innerHTML = '';
    let total = 0;

    carrinho.forEach((item, index) => {
        total += item.valor_total;
        divCarrinho.innerHTML += `
            <div class="item-carrinho">
                <div class="item-info">
                    <strong>${item.quantidade}x</strong> ${item.nome}
                </div>
                <div class="item-valor">R$ ${item.valor_total.toFixed(2)}</div>
                <button class="btn-remover" onclick="removerItem(${index})">×</button>
            </div>
        `;
    });

    // Rola o carrinho para o final para mostrar o último item adicionado
    divCarrinho.scrollTop = divCarrinho.scrollHeight;
    
    totalDisplay.innerText = "R$ " + total.toFixed(2);
    btnEmitir.disabled = false;
    btnEmitir.style.background = "#27ae60"; // Mantém a cor original verde se houver itens
}

/**
 * Remove um item específico do carrinho pelo índice.
 */
function removerItem(index) {
    carrinho.splice(index, 1);
    atualizarCarrinho();
}

/**
 * Esvazia completamente o carrinho após confirmação.
 */
function limparCarrinho() {
    if (confirm("Limpar todo o carrinho?")) {
        carrinho = [];
        atualizarCarrinho();
    }
}

/**
 * Função auxiliar para somar o valor total do carrinho.
 */
function calcularTotal() {
    return carrinho.reduce((acc, item) => acc + item.valor_total, 0);
}

// ============================================================================
// 6. EMISSÃO DE NOTA FISCAL
// ============================================================================

/**
 * Abre o modal de confirmação final antes de enviar para a API.
 * Exibe o total e a forma de pagamento selecionada.
 */
function emitirNota() {
    const modalConfirm = document.getElementById('modalConfirmacao');
    const valorDisplay = document.getElementById('valorConfirmacaoModal');
    const pagDisplay = document.getElementById('pagamentoConfirmacaoModal');
    const selectPag = document.getElementById('forma_pagamento');

    const textoPagamento = selectPag.options[selectPag.selectedIndex].text;

    valorDisplay.innerText = "Total: R$ " + calcularTotal().toFixed(2);
    pagDisplay.innerText = "Forma: " + textoPagamento;

    modalConfirm.showModal();

    // Define o evento de clique do botão "Confirmar" dentro do modal
    document.getElementById('btnConfirmarFinal').onclick = function () {
        modalConfirm.close();
        processarEnvioReal(); 
    };
}

/**
 * Envia os dados para o backend (Django) -> Nuvem Fiscal.
 * Processa a resposta e atualiza a UI com Sucesso (Link PDF) ou Erro.
 */
async function processarEnvioReal() {
    const btn = document.getElementById('btnEmitir');
    const statusDiv = document.getElementById('status');
    const formaPagamento = document.getElementById('forma_pagamento').value;

    statusDiv.innerHTML = '';

    btn.disabled = true; btn.innerText = "🚀 Enviando...";

    try {
        const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        const res = await fetch('/emitir-nota/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({
                itens: carrinho,
                forma_pagamento: formaPagamento
            })
        });
        const data = await res.json();

        if (res.ok) {
            // Sucesso: Mostra link para download do PDF
            statusDiv.innerHTML = `
        <div class="sucesso-msg" style="position: relative;">
            <span onclick="this.parentElement.remove()" style="position: absolute; right: 10px; top: 5px; cursor: pointer; font-weight: bold;">×</span>
            <h3>✅ Nota Autorizada!</h3>
            <a href="/imprimir-nota/${data.id_nota}/" target="_blank" class="btn-pdf">
                📄 BAIXAR / IMPRIMIR PDF
            </a>
        </div>`;
            carrinho = [];
            atualizarCarrinho();
        } else {
            // Erro validado pelo backend
            statusDiv.innerHTML = `
                <div class="alerta-personalizado alerta-erro">
                    <span class="btn-fechar-alerta" onclick="this.parentElement.remove()">×</span>
                    <h3>❌ Erro: ${data.mensagem}</h3>
                </div>`;
        }
    } catch (e) {
        // Erro de rede ou exceção não tratada
        statusDiv.innerHTML = `<div class="alerta-personalizado alerta-erro"><h3>⚠️ Erro de comunicação</h3></div>`;
    } finally {
        btn.innerText = "EMITIR NOTA";
        if (carrinho.length > 0) btn.disabled = false;
    }
}

// ============================================================================
// 7. CONTROLE DE INTERFACE (ABAS)
// ============================================================================

/**
 * Alterna entre o modo "Manual" (Busca) e "Valor Alvo" (Simulação).
 * @param {string} modo - 'manual' ou 'valor'.
 */
function mudarModo(modo) {
    const btnManual = document.getElementById('btn-manual');
    const btnValor = document.getElementById('btn-valor');
    const painelManual = document.getElementById('painel-manual');
    const painelValor = document.getElementById('painel-valor');

    if (modo === 'manual') {
        btnManual.classList.add('ativo');
        btnValor.classList.remove('ativo');
        painelManual.classList.remove('hidden');
        painelValor.classList.add('hidden');

        // Pequeno delay para garantir que o elemento está visível antes do foco
        setTimeout(() => {
            const el = document.getElementById('buscaInput');
            if (el) el.focus();
        }, 100);
    } else {
        btnManual.classList.remove('ativo');
        btnValor.classList.add('ativo');
        painelManual.classList.add('hidden');
        painelValor.classList.remove('hidden');

        setTimeout(() => {
            const el = document.getElementById('valor-alvo');
            if (el) el.focus();
        }, 100);
    }
}
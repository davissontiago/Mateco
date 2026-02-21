/**
 * ============================================================================
 * MATECO SISTEMAS - CONTROLE DO PDV (PONTO DE VENDA) - MODO MANUAL
 * * Este arquivo gerencia a tela de emissão manual:
 * 1. Busca dinâmica de produtos via autocomplete.
 * 2. Gerenciamento do array 'carrinho' (adicionar/remover/limpar).
 * 3. Comunicação com a API para emissão da nota fiscal.
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

// Foca no input de busca assim que a página carrega
window.onload = () => {
    if(buscaInput) buscaInput.focus();
};

// ============================================================================
// 2. LÓGICA DE BUSCA E AUTOCOMPLETE
// ============================================================================

/**
 * Escuta o evento de digitação no campo de busca.
 * Faz requisições à API apenas se houver mais de 2 caracteres.
 */
if (buscaInput) {
    buscaInput.addEventListener('input', async (e) => {
        const termo = e.target.value;

        // Limpa sugestões se o termo for muito curto
        if (termo.length < 2) {
            listaSugestoes.style.display = 'none';
            return;
        }

        try {
            // Busca produtos no backend (Django)
            const res = await fetch(`/api/produtos/?q=${termo}`);
            if (!res.ok) throw new Error('Erro na busca');
            
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
                            <small style="color:#777">R$ ${prod.preco_unitario.toFixed(2)} | Est: ${prod.estoque}</small>
                        </div>
                        <div style="font-weight:bold; color:#2980b9; font-size: 1.2em;">+</div>
                    `;
                    // Define ação de clique para abrir modal de quantidade
                    div.onclick = () => { abrirModalQtd(prod); };
                    listaSugestoes.appendChild(div);
                });
            } else {
                listaSugestoes.innerHTML = '<div style="padding: 10px; color: #999; text-align: center;">Nenhum produto encontrado.</div>';
                listaSugestoes.style.display = 'block';
            }
        } catch (error) {
            console.error("Falha ao buscar produtos", error);
        }
    });
}

/**
 * Fecha a lista de sugestões se o utilizador clicar fora do input de busca.
 */
document.addEventListener('click', (e) => {
    if (e.target !== buscaInput && listaSugestoes) {
        listaSugestoes.style.display = 'none';
    }
});

// ============================================================================
// 3. GERENCIAMENTO DE MODAIS (QUANTIDADE E ADIÇÃO)
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
    setTimeout(() => {
        const qtdInput = document.getElementById('qtdInputModal');
        qtdInput.focus();
        qtdInput.select(); // Seleciona o número '1' para facilitar a substituição
    }, 100);
}

/**
 * Fecha o modal de quantidade e limpa o estado temporário.
 */
function fecharModalQtd() {
    modalQtd.close();
    produtoSelecionadoTemp = null;
    buscaInput.value = '';
    buscaInput.focus(); // Devolve o foco à busca para o próximo item
}

/**
 * Adiciona o produto ao carrinho com a quantidade informada no modal.
 */
function confirmarAdicaoManual() {
    if (!produtoSelecionadoTemp) return;

    const qtd = parseFloat(document.getElementById('qtdInputModal').value);
    
    if (isNaN(qtd) || qtd <= 0) {
        alert("Quantidade inválida");
        return;
    }

    // Verifica se o item já existe no carrinho para apenas somar a quantidade
    const indexExistente = carrinho.findIndex(item => item.id === produtoSelecionadoTemp.id);

    if (indexExistente !== -1) {
        carrinho[indexExistente].quantidade += qtd;
        carrinho[indexExistente].valor_total = carrinho[indexExistente].quantidade * carrinho[indexExistente].preco_unitario;
    } else {
        carrinho.push({
            id: produtoSelecionadoTemp.id,
            nome: produtoSelecionadoTemp.nome,
            preco_unitario: produtoSelecionadoTemp.preco_unitario,
            quantidade: qtd,
            valor_total: produtoSelecionadoTemp.preco_unitario * qtd,
            ncm: produtoSelecionadoTemp.ncm
        });
    }

    atualizarCarrinho();
    fecharModalQtd();
}

// Permite confirmar a quantidade pressionando a tecla "Enter"
document.getElementById('qtdInputModal')?.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') {
        confirmarAdicaoManual();
    }
});


// ============================================================================
// 4. GERENCIAMENTO DO CARRINHO (CRUD E VISUAL)
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
        divCarrinho.innerHTML = '<div style="text-align: center; color: #bbb; padding: 30px 0;">Seu carrinho está vazio 🛒</div>';
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
                <button class="btn-remover" onclick="removerItem(${index})" title="Remover item">×</button>
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
 * Esvazia completamente o carrinho após confirmação do utilizador.
 */
function limparCarrinho() {
    if (carrinho.length === 0) return;
    
    if (confirm("Tem a certeza que deseja limpar todo o carrinho?")) {
        carrinho = [];
        atualizarCarrinho();
        buscaInput.focus();
    }
}

/**
 * Função auxiliar para somar o valor total do carrinho.
 */
function calcularTotal() {
    return carrinho.reduce((acc, item) => acc + item.valor_total, 0);
}

// ============================================================================
// 5. EMISSÃO DE NOTA FISCAL (ENVIO PARA A API)
// ============================================================================

/**
 * Abre o modal de confirmação final antes de enviar para o Django.
 * Exibe o total e a forma de pagamento selecionada para evitar erros.
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
 * Processa a resposta e atualiza a Interface com Sucesso (Link PDF) ou Erro.
 */
async function processarEnvioReal() {
    const btn = document.getElementById('btnEmitir');
    const statusDiv = document.getElementById('status');
    const formaPagamento = document.getElementById('forma_pagamento').value;
    const clienteSelect = document.getElementById('cliente-select');
    
    const clienteId = (clienteSelect && clienteSelect.value !== "") ? clienteSelect.value : null;

    statusDiv.innerHTML = '';
    btn.disabled = true; 
    btn.innerText = "🚀 A Emitir...";

    try {
        const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        // Dispara o pedido para o Django
        const res = await fetch('/emitir-nota/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json', 
                'X-CSRFToken': csrftoken 
            },
            body: JSON.stringify({
                itens: carrinho,
                forma_pagamento: formaPagamento,
                cliente_id: clienteId 
            })
        });
        
        const data = await res.json();

        // Tratamento da Resposta
        if (res.ok) {
            statusDiv.innerHTML = `
                <div class="sucesso-msg" style="position: relative;">
                    <span onclick="this.parentElement.remove()" style="position: absolute; right: 10px; top: 5px; cursor: pointer; font-weight: bold; font-size: 1.2em;">×</span>
                    <h3>✅ Nota Autorizada com Sucesso!</h3>
                    <a href="/imprimir-nota/${data.id_nota}/" target="_blank" class="btn-pdf">
                        📄 BAIXAR / IMPRIMIR PDF
                    </a>
                </div>`;
            
            // Limpa a tela para a próxima venda
            carrinho = [];
            atualizarCarrinho();
            if(clienteSelect) clienteSelect.value = ""; // Reseta o cliente
            buscaInput.focus();
            
        } else {
            statusDiv.innerHTML = `
                <div class="alerta-personalizado alerta-erro">
                    <span class="btn-fechar-alerta" onclick="this.parentElement.remove()">×</span>
                    <h3>❌ Erro na Emissão:</h3>
                    <p>${data.mensagem}</p>
                </div>`;
        }
    } catch (e) {
        statusDiv.innerHTML = `
            <div class="alerta-personalizado alerta-erro">
                <span class="btn-fechar-alerta" onclick="this.parentElement.remove()">×</span>
                <h3>⚠️ Erro de comunicação com o servidor.</h3>
                <p>Verifique a sua internet e tente novamente.</p>
            </div>`;
    } finally {
        btn.innerText = "EMITIR NOTA";
        if (carrinho.length > 0) btn.disabled = false;
    }
}
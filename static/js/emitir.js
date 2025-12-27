let carrinho = [];
let produtoSelecionadoTemp = null; // Guarda o produto enquanto escolhe qtd

const buscaInput = document.getElementById('buscaInput');
const listaSugestoes = document.getElementById('listaSugestoes');
const modalQtd = document.getElementById('modalQuantidade');

// --- LÓGICA DE BUSCA ---
buscaInput.addEventListener('input', async (e) => {
    const termo = e.target.value;
    if (termo.length < 2) { listaSugestoes.style.display = 'none'; return; }

    const res = await fetch(`/api/produtos/?q=${termo}`);
    const produtos = await res.json();

    listaSugestoes.innerHTML = '';
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
            // Ao clicar, abre o modal em vez de adicionar direto
            div.onclick = () => { abrirModalQtd(prod); };
            listaSugestoes.appendChild(div);
        });
    } else {
        listaSugestoes.style.display = 'none';
    }
});

document.addEventListener('click', (e) => {
    if (e.target !== buscaInput) listaSugestoes.style.display = 'none';
});

// --- LÓGICA DO MODAL DE QUANTIDADE ---
function abrirModalQtd(prod) {
    produtoSelecionadoTemp = prod;
    document.getElementById('nomeProdModal').innerText = prod.nome;
    document.getElementById('qtdInputModal').value = 1; // Reseta para 1

    listaSugestoes.style.display = 'none'; // Esconde sugestões
    modalQtd.showModal();

    // Foca no campo de quantidade para digitar direto
    setTimeout(() => document.getElementById('qtdInputModal').focus(), 100);
}

function fecharModalQtd() {
    modalQtd.close();
    produtoSelecionadoTemp = null;
    buscaInput.value = ''; // Limpa a busca
}

function confirmarAdicaoManual() {
    if (!produtoSelecionadoTemp) return;

    const qtd = parseInt(document.getElementById('qtdInputModal').value);
    if (isNaN(qtd) || qtd <= 0) {
        alert("Quantidade inválida");
        return;
    }

    // Adiciona ao carrinho com a quantidade escolhida
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

// --- RESTANTE DA LÓGICA (Simulação, Emissão) ---
async function completarValor() {
    const valorAlvo = parseFloat(document.getElementById('valorAlvoInput').value);
    const totalAtual = calcularTotal();

    if (isNaN(valorAlvo) || valorAlvo <= totalAtual) {
        alert("A meta deve ser maior que o total atual."); return;
    }

    const falta = valorAlvo - totalAtual;
    const btn = document.querySelector('.btn-completar');
    const txtOriginal = btn.innerText;
    btn.innerText = "⏳...";
    btn.disabled = true;

    try {
        const res = await fetch(`/api/produtos/?simular=true&valor=${falta}`);
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        data.itens.forEach(item => carrinho.push(item));
        atualizarCarrinho();
    } catch (e) {
        alert("Erro de conexão.");
    } finally {
        btn.innerText = txtOriginal;
        btn.disabled = false;
    }
}

async function refazerSimulacao() {
    const valorAlvo = parseFloat(document.getElementById('valorAlvoInput').value);
    if (isNaN(valorAlvo) || valorAlvo <= 0) { alert("Digite uma meta para refazer."); return; }
    carrinho = [];
    atualizarCarrinho();
    await completarValor();
}

function atualizarCarrinho() {
    const divCarrinho = document.getElementById('carrinhoVisual');
    const totalDisplay = document.getElementById('totalDisplay');
    const btnEmitir = document.getElementById('btnEmitir');

    if (carrinho.length === 0) {
        divCarrinho.innerHTML = '<div style="text-align: center; color: #bbb; padding: 30px 0;">🛒 Seu carrinho está vazio</div>';
        totalDisplay.innerText = "R$ 0,00";
        btnEmitir.disabled = true;
        btnEmitir.style.background = "#bdc3c7";
        return;
    }

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

    divCarrinho.scrollTop = divCarrinho.scrollHeight;
    totalDisplay.innerText = "R$ " + total.toFixed(2);
    btnEmitir.disabled = false;
    btnEmitir.style.background = "#27ae60";
}

function removerItem(index) {
    carrinho.splice(index, 1);
    atualizarCarrinho();
}

function limparCarrinho() {
    if (confirm("Limpar todo o carrinho?")) {
        carrinho = [];
        atualizarCarrinho();
    }
}

function calcularTotal() {
    return carrinho.reduce((acc, item) => acc + item.valor_total, 0);
}

// PARTE 1: Apenas prepara e abre o modal
function emitirNota() {
    const modalConfirm = document.getElementById('modalConfirmacao');
    const valorDisplay = document.getElementById('valorConfirmacaoModal');
    const pagDisplay = document.getElementById('pagamentoConfirmacaoModal');
    const selectPag = document.getElementById('forma_pagamento');

    // Texto da forma de pagamento selecionada
    const textoPagamento = selectPag.options[selectPag.selectedIndex].text;

    valorDisplay.innerText = "Total: R$ " + calcularTotal().toFixed(2);
    pagDisplay.innerText = "Forma: " + textoPagamento;

    modalConfirm.showModal();

    // Quando clicar em confirmar dentro do modal, chama o envio real
    document.getElementById('btnConfirmarFinal').onclick = function () {
        modalConfirm.close();
        processarEnvioReal(); // Chama a função com a sua lógica original
    };
}

// PARTE 2: Sua lógica original de envio (preservando todos os nomes de variáveis)
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
            statusDiv.innerHTML = `
                <div class="alerta-personalizado alerta-erro">
                    <span class="btn-fechar-alerta" onclick="this.parentElement.remove()">×</span>
                    <h3>❌ Erro: ${data.mensagem}</h3>
                </div>`;
        }
    } catch (e) {
        statusDiv.innerHTML = `<div class="alerta-personalizado alerta-erro"><h3>⚠️ Erro de comunicação</h3></div>`;
    } finally {
        btn.innerText = "EMITIR NOTA";
        if (carrinho.length > 0) btn.disabled = false;
    }
}

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
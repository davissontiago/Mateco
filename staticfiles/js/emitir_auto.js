/**
 * ============================================================================
 * MATECO SISTEMAS - EMISSÃO EM LOTE COM NAVEGAÇÃO (CARRINHO INTELIGENTE)
 * ============================================================================
 */

let lotesDeNotas = []; 
let modoVisualizacao = 'lista'; // Pode ser 'lista' ou 'detalhe'
let notaAtualIndex = 0; // Controla qual bolinha/nota está selecionada

// ============================================================================
// 1. ALGORITMO E GERAÇÃO DO ESBOÇO
// ============================================================================

function dividirValorAleatoriamente(total, qtd) {
    let partes = [];
    let soma = 0;
    let pesos = Array.from({length: qtd}, () => Math.random() * 0.5 + 0.5); 
    let pesoTotal = pesos.reduce((a, b) => a + b, 0);

    for(let i = 0; i < qtd - 1; i++) {
        let valorFracao = Math.floor((pesos[i] / pesoTotal) * total * 100) / 100;
        partes.push(valorFracao);
        soma += valorFracao;
    }
    
    let ultimaNota = Math.round((total - soma) * 100) / 100;
    partes.push(ultimaNota);
    return partes;
}

function agruparItens(itens) {
    const agrupado = {};
    itens.forEach(item => {
        if (agrupado[item.id]) {
            agrupado[item.id].quantidade += item.quantidade;
            agrupado[item.id].valor_total += item.valor_total;
        } else {
            agrupado[item.id] = { ...item }; // Copia o item para não alterar o original
        }
    });
    return Object.values(agrupado); // Devolve a lista limpa e agrupada
}

async function gerarEsboçoLote() {
    const inputTotal = document.getElementById('valor-total').value;
    const inputQtd = document.getElementById('qtd-notas').value;
    const valorTotal = parseFloat(inputTotal);
    const qtdNotas = parseInt(inputQtd);

    if (isNaN(valorTotal) || valorTotal <= 0 || isNaN(qtdNotas) || qtdNotas <= 0) {
        alert("Preencha o valor total e a quantidade de notas corretamente."); return;
    }
    if (qtdNotas > 20) { alert("Limite o lote a 20 notas por vez."); return; }

    const btnGerar = document.getElementById('btn-gerar');
    btnGerar.innerText = "⏳ A Simular..."; btnGerar.disabled = true;

    const valoresAlvo = dividirValorAleatoriamente(valorTotal, qtdNotas);
    
    try {
        const promessas = valoresAlvo.map(async (valor, index) => {
            const res = await fetch(`/api/produtos/?simular=true&valor=${valor}`);
            const data = await res.json();
            
            // --- NOVA LÓGICA: Agrupa os itens antes de salvar na nota ---
            const itensLimpos = agruparItens(data.itens || []);

            return {
                numero: index + 1,
                valor_alvo: valor,
                carrinho: itensLimpos, 
                valor_real: data.total || 0,
                status: 'pendente', 
                mensagem: '',
                id_nota_nuvem: null
            };
        });

        lotesDeNotas = await Promise.all(promessas);
        
        modoVisualizacao = 'lista'; 
        notaAtualIndex = 0;
        renderizarInterfaceLote();

    } catch (error) {
        alert("Erro ao simular o lote.");
    } finally {
        btnGerar.innerText = "Gerar Esboço"; btnGerar.disabled = false;
    }
}

// ============================================================================
// 2. CONTROLE DE NAVEGAÇÃO (BOLINHAS E SETAS)
// ============================================================================

function alternarModoVisualizacao() {
    modoVisualizacao = (modoVisualizacao === 'lista') ? 'detalhe' : 'lista';
    renderizarInterfaceLote();
}

function irParaNota(index) {
    notaAtualIndex = index;
    modoVisualizacao = 'detalhe'; // Força abrir os detalhes da nota clicada
    renderizarInterfaceLote();
}

// ============================================================================
// 3. ATUALIZAÇÃO DA INTERFACE (MÁQUINA DE ESTADOS)
// ============================================================================

function renderizarInterfaceLote() {
    const msgVazio = document.getElementById('msg-vazio');
    const controles = document.getElementById('controles-lote');
    const conteudo = document.getElementById('conteudo-lote');
    const totalDisplay = document.getElementById('totalDisplay');
    const btnEmitir = document.getElementById('btnEmitir');
    const containerBolinhas = document.getElementById('container-bolinhas');
    
    const rodape = document.getElementById('rodape-emissao'); 
    
    // Captura os contentores pais para remover os limites deles também
    const caixaCarrinho = conteudo.closest('.carrinho');
    const containerPdv = conteudo.closest('.container-pdv');

    // ESTADO VAZIO
    if (lotesDeNotas.length === 0) {
        msgVazio.style.display = 'block';
        controles.classList.add('hidden');
        conteudo.classList.add('hidden');
        rodape.classList.remove('hidden');
        totalDisplay.innerText = "R$ 0,00";
        btnEmitir.disabled = true; btnEmitir.style.background = "#bdc3c7";
        return;
    }

    // ESTADO PREENCHIDO
    msgVazio.style.display = 'none';
    controles.classList.remove('hidden');
    conteudo.classList.remove('hidden');

    let somaRealLote = 0;
    containerBolinhas.innerHTML = '';

    // Renderiza as Bolinhas
    lotesDeNotas.forEach((nota, index) => {
        somaRealLote += nota.valor_real;
        let classeBolinha = `bolinha ${nota.status}`;
        if (index === notaAtualIndex && modoVisualizacao === 'detalhe') classeBolinha += ' ativa';

        containerBolinhas.innerHTML += `
            <div class="${classeBolinha}" onclick="irParaNota(${index})" title="Ver Nota #${nota.numero}">
                ${nota.numero}
            </div>
        `;
    });

    // Controla botão Emitir
    const temPendente = lotesDeNotas.some(n => n.status === 'pendente' || n.status === 'erro');
    if (temPendente) {
        btnEmitir.disabled = false; btnEmitir.style.background = "#27ae60"; btnEmitir.innerText = "EMITIR TODAS AS NOTAS";
    } else {
        btnEmitir.disabled = true; btnEmitir.style.background = "#bdc3c7"; btnEmitir.innerText = "✅ PROCESSO FINALIZADO";
    }
    totalDisplay.innerText = "R$ " + somaRealLote.toFixed(2);

    conteudo.innerHTML = '';
    
    if (modoVisualizacao === 'lista') {
        rodape.classList.remove('hidden'); 
        
        // --- RESTAURA LIMITES DA LISTA ---
        conteudo.style.maxHeight = '400px';
        conteudo.style.overflowY = 'auto';
        
        // Remove completamente as alterações feitas pela vista de detalhes
        // O valor vazio ('') apaga o estilo inline e faz o navegador voltar a ler o seu CSS.
        conteudo.style.height = ''; 
        
        if (caixaCarrinho) {
            caixaCarrinho.style.maxHeight = '';
            caixaCarrinho.style.overflow = '';
            caixaCarrinho.style.height = '';
        }
        if (containerPdv) {
            containerPdv.style.maxHeight = '';
            containerPdv.style.overflow = '';
            containerPdv.style.height = '';
            containerPdv.style.paddingBottom = '';
        }
        
        renderizarVistaLista(conteudo);
    } else {
        rodape.classList.add('hidden'); 
        
        // --- QUEBRA TODOS OS LIMITES DE ALTURA (Força Crescimento Livre) ---
        conteudo.style.maxHeight = 'none';
        conteudo.style.overflow = 'visible';
        conteudo.style.height = 'auto';
        
        // Remove limites das caixas pai, caso o CSS global esteja a bloqueá-las
        if (caixaCarrinho) {
            caixaCarrinho.style.maxHeight = 'none';
            caixaCarrinho.style.overflow = 'visible';
            caixaCarrinho.style.height = 'auto';
        }
        if (containerPdv) {
            containerPdv.style.maxHeight = 'none';
            containerPdv.style.overflow = 'visible';
            containerPdv.style.height = 'auto';
            containerPdv.style.paddingBottom = '100px'; // Garante espaço no final da página
        }
        
        renderizarVistaDetalhe(conteudo);
    }
}

function renderizarVistaLista(container) {
    // Restaura o tamanho fixo (400px) e a barra de rolagem interna apenas para a vista de Lista
    container.style.maxHeight = '400px'; 
    container.style.overflowY = 'auto';
    
    let html = '<div class="lote-lista">';
    lotesDeNotas.forEach((nota, index) => {
        let statusHtml = `<span class="lote-status">Pendente</span>`;
        let classCard = '';
        
        if (nota.status === 'emitindo') statusHtml = `<span class="lote-status status-emitindo">⏳ Emitindo...</span>`;
        else if (nota.status === 'sucesso') { statusHtml = `<span class="lote-status status-sucesso">✅ Autorizada</span>`; classCard = 'sucesso'; }
        else if (nota.status === 'erro') { statusHtml = `<span class="lote-status status-erro">❌ Falhou</span>`; classCard = 'erro'; }

        html += `
            <div class="lote-item ${classCard}" onclick="irParaNota(${index})">
                <div class="lote-info">
                    <strong>Nota #${nota.numero}</strong>
                    <span style="font-size:0.85em; color:#888;">${nota.carrinho.length} produtos inseridos</span>
                    <span style="color: #e74c3c; font-size: 0.8em;">${nota.mensagem}</span>
                </div>
                <div style="text-align: right;">
                    <div style="font-weight: bold; color: #2c3e50;">R$ ${nota.valor_real.toFixed(2)}</div>
                    ${statusHtml}
                </div>
            </div>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

function renderizarVistaDetalhe(container) {
    const nota = lotesDeNotas[notaAtualIndex];
    
    let linkPdf = nota.status === 'sucesso' ? `<br><a href="/imprimir-nota/${nota.id_nota_nuvem}/" target="_blank" style="color: #2980b9; font-size: 0.9em; text-decoration: underline; font-weight: bold;">📄 Abrir PDF</a>` : '';
    
    // --- NOVA LÓGICA: Soma todas as quantidades usando reduce() ---
    const qtdTotalItens = nota.carrinho.reduce((acumulador, item) => acumulador + item.quantidade, 0);
    
    let html = `
        <div class="nota-detalhe-header">
            <h3 style="margin:0; color:#333;">Detalhes da Nota #${nota.numero}</h3>
            <div style="font-size: 1.5em; font-weight: bold; color: #27ae60; margin: 5px 0;">
                R$ ${nota.valor_real.toFixed(2)}
                <span style="font-size: 0.6em; color: #888; font-weight: normal; margin-left: 10px;">
                    (${qtdTotalItens} unidades)
                </span>
            </div>
            ${linkPdf}
        </div>
        
        <div style="border: 1px solid #eee; border-radius: 8px; border-bottom: none; margin-bottom: 20px;">
            <table class="tabela-itens" style="margin-top: 0; width: 100%; border-collapse: collapse;">
                <thead style="background: #f4f6f8; border-bottom: 2px solid #ddd;">
                    <tr>
                        <th style="width: 50px; padding: 12px 10px;">Qtd</th>
                        <th style="padding: 12px 10px;">Produto</th>
                        <th style="text-align: right; padding: 12px 10px;">Total Item</th>
                    </tr>
                </thead>
                <tbody>
    `;

    nota.carrinho.forEach(item => {
        html += `
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;"><strong>${item.quantidade}x</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">${item.nome}</td>
                <td style="text-align: right; color:#555; padding: 10px; border-bottom: 1px solid #eee;">R$ ${item.valor_total.toFixed(2)}</td>
            </tr>
        `;
    });

    html += `</tbody></table></div>`;
    container.innerHTML = html;
}

function limparLote() {
    if (lotesDeNotas.length === 0) return;
    if (confirm("Apagar este esboço e começar de novo?")) {
        lotesDeNotas = [];
        document.getElementById('valor-total').value = '';
        document.getElementById('qtd-notas').value = '';
        renderizarInterfaceLote();
    }
}

// ============================================================================
// 4. EMISSÃO SEQUENCIAL
// ============================================================================

// ============================================================================
// MODAL DE CONFIRMAÇÃO
// ============================================================================
function abrirModalConfirmacao() {
    // Filtra apenas as notas que ainda não foram emitidas com sucesso
    const notasPendentes = lotesDeNotas.filter(n => n.status === 'pendente' || n.status === 'erro');
    if (notasPendentes.length === 0) return;

    // Soma o valor apenas do que será emitido
    const totalSoma = notasPendentes.reduce((acc, n) => acc + n.valor_real, 0);

    // --- NOVA LÓGICA: Captura o texto da forma de pagamento selecionada ---
    const selectPag = document.getElementById('forma_pagamento');
    const textoPagamento = selectPag.options[selectPag.selectedIndex].text;

    // Atualiza a tela do modal
    document.getElementById('qtdModalConfirmacao').innerText = notasPendentes.length;
    document.getElementById('valorModalConfirmacao').innerText = "Total: R$ " + totalSoma.toFixed(2);
    document.getElementById('pagamentoModalConfirmacao').innerText = "Pagamento: " + textoPagamento; // Injeta o texto

    document.getElementById('modalConfirmacaoLote').showModal();
}

function fecharModalConfirmacao() {
    const modal = document.getElementById('modalConfirmacaoLote');
    if (modal) modal.close();
}

async function iniciarEmissaoLote() {
   // Esconde a janelinha bonita antes de começar a trabalhar
    fecharModalConfirmacao();

    // FORÇA VOLTAR PARA A VISTA DE LISTA PARA ACOMPANHAR O PROCESSO
    modoVisualizacao = 'lista';
    renderizarInterfaceLote();

    const formaPagamento = document.getElementById('forma_pagamento').value;
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    for (let i = 0; i < lotesDeNotas.length; i++) {
        let nota = lotesDeNotas[i];

        if (nota.status === 'sucesso') continue;

        nota.status = 'emitindo';
        renderizarInterfaceLote(); // O renderizador agora pinta a bolinha de laranja piscando

        try {
            const res = await fetch('/emitir-nota/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                body: JSON.stringify({ itens: nota.carrinho, forma_pagamento: formaPagamento, cliente_id: null })
            });
            const data = await res.json();

            if (res.ok) {
                nota.status = 'sucesso';
                nota.id_nota_nuvem = data.id_nota;
                nota.mensagem = '';
            } else {
                nota.status = 'erro';
                nota.mensagem = data.mensagem;
            }
        } catch (e) {
            nota.status = 'erro';
            nota.mensagem = "Falha de rede.";
        }

        renderizarInterfaceLote(); // O renderizador pinta a bolinha de Verde ou Vermelho
    }
    
    document.getElementById('valor-total').value = '';
    document.getElementById('qtd-notas').value = '';
}
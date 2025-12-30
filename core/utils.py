import random
from typing import List, Tuple, Dict, Any

def simular_carrinho_inteligente(valor_alvo: float, produtos_disponiveis: List[Any]) -> Tuple[List[Dict[str, Any]], float]:
    """
    Gera uma lista aleatória de produtos cujo valor total se aproxima de um valor alvo.
    
    A lógica utiliza pesos para favorecer quantidades menores (mais realistas) e 
    filtra produtos que ainda cabem no orçamento restante durante a iteração.

    Args:
        valor_alvo (float): O valor total aproximado que o carrinho deve atingir.
        produtos_disponiveis (List): Lista ou QuerySet de objetos do tipo Produto.

    Returns:
        tuple: (lista_de_itens: list, total_final: float)
            - lista_de_itens: Dicionários com id, nome, preco_unitario, quantidade, valor_total e ncm.
            - total_final: Soma real de todos os itens sorteados.
    """
    lista_simulada = []
    total_atual = 0.0

    # Definição de probabilidades para as quantidades (favorece 1 unidade com 50% de chance)
    opcoes_qtd = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    pesos_qtd  = [50, 15, 10, 5, 5, 3, 3, 3, 3, 3] 

    while total_atual < valor_alvo:
        falta = valor_alvo - total_atual
        
        # Filtra apenas produtos com preço inferior ao valor restante (que cabem no carrinho)
        produtos_que_cabem = [p for p in produtos_disponiveis if float(p.preco) <= falta]
        
        if produtos_que_cabem:
            # Seleção aleatória do produto
            prod = random.choice(produtos_que_cabem)
            preco = float(prod.preco)
            
            # Sorteio da quantidade baseado nos pesos e limite orçamentário
            qtd_sorteada = random.choices(opcoes_qtd, weights=pesos_qtd, k=1)[0]
            max_que_cabe = int(falta // preco)
            
            # Garante que a quantidade não ultrapasse o valor alvo e seja no mínimo 1
            quantidade_final = min(qtd_sorteada, max_que_cabe)
            if quantidade_final < 1: 
                quantidade_final = 1
        else:
            # Caso nenhum produto caiba exatamente, adiciona o primeiro da lista para encerrar o loop
            prod = produtos_disponiveis[0] 
            preco = float(prod.preco)
            quantidade_final = 1

        total_item = preco * quantidade_final
        
        # Montagem do dicionário de dados do item
        lista_simulada.append({
            'id': prod.id,
            'nome': prod.nome,
            'preco_unitario': preco,
            'quantidade': quantidade_final,
            'valor_total': total_item,
            'ncm': prod.ncm
        })
        
        total_atual += total_item
    
    return lista_simulada, total_atual
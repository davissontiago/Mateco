# core/utils.py
import random

def simular_carrinho_inteligente(valor_alvo, produtos_disponiveis):
    """
    Recebe um valor alvo e uma lista de produtos (QuerySet ou Lista).
    Retorna uma lista de dicionários com os itens para compor o valor.
    """
    lista_simulada = []
    total_atual = 0.0

    # Pesos para dar mais realismo (preferir quantidades menores)
    opcoes_qtd = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    pesos_qtd  = [50, 15, 10, 5, 5, 3, 3, 3, 3, 3] 

    while total_atual < valor_alvo:
        falta = valor_alvo - total_atual
        
        # Filtra apenas produtos que cabem no valor restante
        produtos_que_cabem = [p for p in produtos_disponiveis if float(p.preco) <= falta]
        
        if produtos_que_cabem:
            prod = random.choice(produtos_que_cabem)
            preco = float(prod.preco)
            
            # Decide a quantidade (sem estourar o valor)
            qtd_sorteada = random.choices(opcoes_qtd, weights=pesos_qtd, k=1)[0]
            max_que_cabe = int(falta // preco)
            quantidade_final = min(qtd_sorteada, max_que_cabe)
            if quantidade_final < 1: quantidade_final = 1
        else:
            # Se nenhum produto couber (sobra de centavos), pega o mais barato ou o primeiro
            prod = produtos_disponiveis[0] 
            preco = float(prod.preco)
            quantidade_final = 1

        total_item = preco * quantidade_final
        
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
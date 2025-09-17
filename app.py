import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import json
from datetime import datetime
import re

app = Flask(__name__)
CORS(app)

# Configuração da API DataJud
DATAJUD_API_KEY = os.environ.get('DATAJUD_API_KEY', 'cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw==')
DATAJUD_BASE_URL = "https://api-publica.datajud.cnj.jus.br"

# Mapeamento de tribunais
TRIBUNAIS = {
    "01": "api_publica_trf1", "02": "api_publica_trf2", "03": "api_publica_trf3",
    "04": "api_publica_trf4", "05": "api_publica_trf5", "06": "api_publica_trf6",
    "08": "api_publica_tjsp", "19": "api_publica_tjrj", "13": "api_publica_tjmg",
    "21": "api_publica_tjrs", "16": "api_publica_tjpr", "24": "api_publica_tjsc"
}

def extrair_numero_processo(texto ):
    texto_limpo = re.sub(r'[^\d\-\.]', '', texto)
    padrao = r'\d{7}-?\d{2}\.?\d{4}\.?\d{1}\.?\d{2}\.?\d{4}'
    match = re.search(padrao, texto_limpo)
    if match:
        return re.sub(r'[\-\.]', '', match.group())
    return None

def determinar_tribunal(numero_processo):
    if len(numero_processo) != 20:
        return None
    codigo_tribunal = numero_processo[12:14]
    return TRIBUNAIS.get(codigo_tribunal, "api_publica_tjsp")

def consultar_processo_datajud(numero_processo, tribunal_alias):
    try:
        url = f"{DATAJUD_BASE_URL}/{tribunal_alias}/_search"
        headers = {
            "Authorization": f"APIKey {DATAJUD_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": {
                "match": {
                    "numeroProcesso": numero_processo
                }
            }
        }
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Erro ao consultar DataJud: {e}")
        return None

def formatar_resposta_processo(dados_processo):
    if not dados_processo or dados_processo.get('hits', {}).get('total', {}).get('value', 0) == 0:
        return "❌ Processo não encontrado ou não disponível para consulta pública."
    
    processo = dados_processo['hits']['hits'][0]['_source']
    numero = processo.get('numeroProcesso', 'N/A')
    classe = processo.get('classe', {}).get('nome', 'N/A')
    tribunal = processo.get('tribunal', 'N/A')
    orgao_julgador = processo.get('orgaoJulgador', {}).get('nome', 'N/A')
    data_ajuizamento = processo.get('dataAjuizamento', 'N/A')
    
    if data_ajuizamento != 'N/A':
        try:
            data_obj = datetime.fromisoformat(data_ajuizamento.replace('Z', '+00:00'))
            data_ajuizamento = data_obj.strftime('%d/%m/%Y')
        except:
            pass
    
    movimentos = processo.get('movimentos', [])
    ultimos_movimentos = []
    
    for movimento in sorted(movimentos, key=lambda x: x.get('dataHora', ''), reverse=True)[:3]:
        nome = movimento.get('nome', 'N/A')
        data_hora = movimento.get('dataHora', 'N/A')
        
        if data_hora != 'N/A':
            try:
                data_obj = datetime.fromisoformat(data_hora.replace('Z', '+00:00'))
                data_formatada = data_obj.strftime('%d/%m/%Y às %H:%M')
            except:
                data_formatada = data_hora
        else:
            data_formatada = 'N/A'
            
        ultimos_movimentos.append(f"• {nome}\n  📅 {data_formatada}")
    
    resposta = f"""📋 **CONSULTA PROCESSUAL**

🔢 **Número:** {numero}
⚖️ **Classe:** {classe}
🏛️ **Tribunal:** {tribunal}
📍 **Órgão Julgador:** {orgao_julgador}
📅 **Data de Ajuizamento:** {data_ajuizamento}

📈 **ÚLTIMOS MOVIMENTOS:**
{chr(10).join(ultimos_movimentos)}

---
ℹ️ Dados obtidos do DataJud/CNJ
🕐 Consulta realizada em {datetime.now().strftime('%d/%m/%Y às %H:%M')}"""

    return resposta

@app.route('/')
def home():
    return jsonify({
        "status": "ok",
        "message": "Serviço de integração DataJud-BotConversa funcionando",
        "endpoints": [
            "/api/datajud/webhook/consulta-processo",
            "/api/datajud/test"
        ]
    })

@app.route('/api/datajud/webhook/consulta-processo', methods=['POST'])
def webhook_consulta_processo():
    try:
        data = request.get_json()
        texto_mensagem = data.get('message', {}).get('text', '') or data.get('text', '')
        
        numero_processo = extrair_numero_processo(texto_mensagem)
        
        if not numero_processo:
            return jsonify({
                "success": False,
                "message": "❌ Número de processo não identificado. Por favor, envie apenas o número do processo (ex: 1234567-89.2023.4.01.1234)."
            })
        
        tribunal_alias = determinar_tribunal(numero_processo)
        
        if not tribunal_alias:
            return jsonify({
                "success": False,
                "message": "❌ Não foi possível identificar o tribunal. Verifique o número do processo."
            })
        
        dados_processo = consultar_processo_datajud(numero_processo, tribunal_alias)
        resposta_formatada = formatar_resposta_processo(dados_processo)
        
        return jsonify({
            "success": True,
            "message": resposta_formatada,
            "processo_numero": numero_processo,
            "tribunal": tribunal_alias
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"❌ Erro interno do servidor: {str(e)}"
        }), 500

@app.route('/api/datajud/test', methods=['GET'])
def test_endpoint():
    return jsonify({
        "status": "ok",
        "message": "Serviço de integração DataJud-BotConversa funcionando",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

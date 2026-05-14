import os
import json
import base64
import tempfile
import httpx

from fastapi import FastAPI, Request, HTTPException
from groq import Groq
import anthropic
from gerar_orcamento import gerar_pdf

# ─────────────────────────────────────────
# CONFIGURAÇÕES via variáveis de ambiente
# ─────────────────────────────────────────
NUMERO_AMIGO      = os.getenv("NUMERO_AMIGO", "")
SEU_NUMERO        = os.getenv("SEU_NUMERO",   "")
EVOLUTION_URL     = os.getenv("EVOLUTION_URL", "")
EVOLUTION_KEY     = os.getenv("EVOLUTION_KEY", "")
INSTANCIA         = os.getenv("INSTANCIA",     "teste")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY",  "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo_campos.jpg")

# Contador de orçamentos (em memória — reinicia com o servidor)
# Para persistência real, use um arquivo ou banco de dados
_contador = {"valor": 0}

def proximo_numero() -> str:
    _contador["valor"] += 1
    from datetime import date
    ano = date.today().year
    return f"{_contador['valor']:03d}/{ano}"

# ─────────────────────────────────────────

app        = FastAPI()
groq_cli   = Groq(api_key=GROQ_API_KEY)
claude_cli = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ══════════════════════════════════════════
# WEBHOOK — ponto de entrada
# ══════════════════════════════════════════
@app.post("/webhook")
async def webhook(req: Request):
    try:
        data = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")

    # DEBUG
    print(f"DEBUG EVENT: {data.get('event')}")
    sender_debug = data.get("data", {}).get("key", {}).get("remoteJid", "N/A")
    print(f"DEBUG SENDER: {sender_debug}")
    print(f"DEBUG NUMERO_AMIGO: {NUMERO_AMIGO}")

    if data.get("event") != "messages.upsert":
        print(f"IGNORADO evento: {data.get('event')}")
        return {"status": "ignorado"}

    msg_data = data.get("data", {})
    key      = msg_data.get("key", {})
    msg      = msg_data.get("message", {})
    sender   = key.get("remoteJid", "")

    if key.get("fromMe"):
        return {"status": "mensagem própria ignorada"}

    # WhatsApp pode omitir o 9º dígito — checa as duas formas
    numero_curto = NUMERO_AMIGO[:4] + NUMERO_AMIGO[5:]  # remove o 9 da posição 4
    if NUMERO_AMIGO not in sender and numero_curto not in sender:
        print(f"BLOQUEADO sender={sender}")
        return {"status": "número não autorizado"}

    print(f"✅ Mensagem recebida de {sender}")

    # ── Áudio ──────────────────────────────
    if "audioMessage" in msg:
        texto = await processar_audio(msg_data)

    # ── Texto ──────────────────────────────
    elif "conversation" in msg:
        texto = msg["conversation"]

    elif "extendedTextMessage" in msg:
        texto = msg["extendedTextMessage"].get("text", "")

    else:
        return {"status": "tipo de mensagem não suportado"}

    if not texto:
        return {"status": "sem texto para processar"}

    # Só processa se começar com "bot -"
    if not texto.lower().startswith("bot -"):
        print(f"⚠️ Ignorado (sem prefixo 'bot -'): {texto[:60]}")
        return {"status": "mensagem ignorada"}

    # Remove o prefixo antes de processar
    texto = texto[5:].strip()

    print(f"📝 Texto: {texto[:120]}...")

    dados      = await extrair_dados_orcamento(texto)
    num_orc    = proximo_numero()
    pdf_bytes  = gerar_pdf(dados, numero_orcamento=num_orc, logo_path=LOGO_PATH)
    pdf_b64    = base64.b64encode(pdf_bytes).decode("utf-8")
    await enviar_pdf_whatsapp(pdf_b64, dados, num_orc)

    return {"status": "ok", "orcamento": num_orc}


# ══════════════════════════════════════════
# PROCESSAR ÁUDIO
# ══════════════════════════════════════════
async def processar_audio(msg_data: dict) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{EVOLUTION_URL}/chat/getBase64FromMediaMessage/{INSTANCIA}",
            headers={"apikey": EVOLUTION_KEY},
            json={"message": msg_data},
            timeout=30,
        )
        resp.raise_for_status()
        audio_b64 = resp.json().get("base64", "")

    if not audio_b64:
        raise ValueError("Áudio não retornado pela API")

    audio_bytes = base64.b64decode(audio_b64)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    with open(tmp_path, "rb") as f:
        transcricao = groq_cli.audio.transcriptions.create(
            model="whisper-large-v3",
            file=("audio.ogg", f, "audio/ogg"),
            language="pt",
        )

    os.unlink(tmp_path)
    print(f"🎙️ Transcrição: {transcricao.text[:120]}...")
    return transcricao.text


# ══════════════════════════════════════════
# EXTRAIR DADOS COM CLAUDE
# ══════════════════════════════════════════
async def extrair_dados_orcamento(texto: str) -> dict:
    prompt = f"""Você é um assistente que extrai dados de orçamentos de serviços elétricos a partir de descrições informais enviadas por WhatsApp.

Extraia do texto abaixo e retorne APENAS um JSON válido, sem explicações, sem markdown, sem blocos de código.

Formato:
{{
  "cliente": "nome do cliente ou 'A definir' se não mencionado",
  "itens": [
    {{
      "descricao": "descrição completa do serviço, pode ser multilinha com \\n",
      "valor_unit": "string formatada ex: R$ 140,00\\npor ponto",
      "valor_total": "string formatada ex: Qtd × R$ 140,00 ou R$ 500,00"
    }}
  ],
  "observacoes": "detalhes adicionais como materiais inclusos, condições, etc",
  "forma_pagamento": "forma de pagamento mencionada ou vazio",
  "garantia": "prazo de garantia mencionado ou vazio"
}}

Regras para valor_total:
- Se a quantidade for definida (ex: "3 tomadas", "2 pontos"): calcule e coloque o total em reais (ex: "R$ 240,00")
- Se a quantidade for indefinida (ex: "quantidade a definir", "conforme o cliente"): use fórmula (ex: "Qtd × R$ 140,00")
- Se for valor fixo único: coloque o valor total diretamente (ex: "R$ 500,00")

Texto:
{texto}"""

    resp = claude_cli.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = resp.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    dados = json.loads(raw)
    print(f"📋 Dados extraídos: {json.dumps(dados, ensure_ascii=False)[:200]}")
    return dados


# ══════════════════════════════════════════
# ENVIAR PDF
# ══════════════════════════════════════════
async def enviar_pdf_whatsapp(pdf_b64: str, dados: dict, num_orc: str):
    cliente = dados.get("cliente", "cliente")
    caption = (
        f"✅ *Orçamento {num_orc} gerado*\n"
        f"Cliente: {cliente}\n"
        f"Revise e encaminhe quando estiver ok."
    )
    nome_arquivo = f"orcamento_{num_orc.replace('/', '-')}_{cliente.replace(' ', '_')}.pdf"

    payload = {
        "number":    SEU_NUMERO,
        "mediatype": "document",
        "mimetype":  "application/pdf",
        "caption":   caption,
        "media":     pdf_b64,
        "fileName":  nome_arquivo,
    }
    print(f"📤 Enviando para número: {SEU_NUMERO}")
    print(f"📤 Tamanho base64: {len(pdf_b64)} chars")
    print(f"📤 Primeiros 50 chars do base64: {pdf_b64[:50]}")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{EVOLUTION_URL}/message/sendMedia/{INSTANCIA}",
            headers={"apikey": EVOLUTION_KEY, "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if not resp.is_success:
            print(f"❌ Erro ao enviar PDF: {resp.status_code} — {resp.text}")
            resp.raise_for_status()
    print(f"📤 PDF '{nome_arquivo}' enviado para {SEU_NUMERO}")


# ══════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════
@app.get("/")
def health():
    return {"status": "rodando", "instancia": INSTANCIA}

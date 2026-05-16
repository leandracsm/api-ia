
from fastapi import FastAPI
from supabase import create_client
from fastapi.middleware.cors import CORSMiddleware
import time
import requests
from rembg import remove
from dotenv import load_dotenv

import os

app = FastAPI()

# CORS'
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET = "fotos"

# STATUS GLOBAL
status_processamento = {
    "total": 0,
    "atual": 0,
    "processando": False
}


@app.get("/")
def home():
    return {"status": "API rodando"}


# 🔥 NOVA ROTA PARA A BARRA DE EVOLUÇÃO
@app.get("/status")
def status():
    return status_processamento


@app.post("/processar")
def processar():

    data = supabase.table("Colecoes_Leandra") \
        .select("*") \
        .eq("foto_processada_status", "pending") \
        \
        .execute()

    items = data.data

    if not items:
        return {"msg": "Nada para processar", "total": 0}

    # 🔥 CONTADORES
    sucesso = 0
    erros = 0

    # 🔥 INICIA STATUS
    status_processamento["total"] = len(items)
    status_processamento["atual"] = 0
    status_processamento["processando"] = True

    for index, item in enumerate(items):

        try:
            print(f"📸 Processando: {item['foto_original']}")

            nome_arquivo = item["foto_original"]

            url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{nome_arquivo}"
            response = requests.get(url)

            if response.status_code != 200:
                raise Exception("Erro ao baixar imagem")

            input_bytes = response.content

            output_bytes = remove(input_bytes)

            nome_sem_ext = nome_arquivo.replace(".jpg", "").replace(".png", "")
            caminho = f"removidas/{nome_sem_ext}_nobg.png"

            print("ID:", item["ID"])
            print("PATH:", caminho)

            # upload
            supabase.storage.from_(BUCKET).upload(
                path=caminho,
                file=output_bytes,
                file_options={
                    "content-type": "image/png",
                    "upsert": "true"
                }
            )

            public_url = supabase.storage.from_(BUCKET).get_public_url(caminho)

            print("URL:", public_url)

            update_data = {
                "foto_processada": caminho,
                "foto_processada_path": caminho,
                "foto_processada_url": public_url,
                "foto_processada_status": "done",
                "foto_processada_em": time.strftime("%Y-%m-%d %H:%M:%S")
            }

            print("PAYLOAD FINAL:", update_data)

            # 🔥 UPDATE REAL COM VALIDAÇÃO FORTE
            response_update = supabase.table("Colecoes_Leandra") \
                .update(update_data) \
                .eq("ID", item["ID"]) \
                .execute()

            # 🔥 VERIFICAÇÃO REAL DE SUCESSO
            if not response_update.data:
                raise Exception(f"UPDATE NÃO AFETOU LINHA ID {item['ID']}")

            print("RESPONSE DATA:", response_update.data)

            print("✅ UPDATE CONFIRMADO NO BANCO:", item["ID"])

            # 🔥 SUCESSO
            sucesso += 1

            # 🔥 ATUALIZA STATUS DA BARRA
            status_processamento["atual"] = index + 1

            time.sleep(0.5)

        except Exception as e:
            print("❌ ERRO:", item["ID"], str(e))

            # 🔥 ERRO
            erros += 1

            try:
                supabase.table("Colecoes_Leandra") \
                    .update({
                        "foto_processada_status": "error"
                    }) \
                    .eq("ID", item["ID"]) \
                    .execute()

            except Exception as db_err:
                print("❌ ERRO AO MARCAR ERROR:", db_err)

    # 🔥 FINALIZA STATUS
    status_processamento["processando"] = False

    return {
        "msg": "Processamento finalizado",
        "total": len(items),
        "sucesso": sucesso,
        "erros": erros
    }

    # Ativar venv: venv\Scripts\activate
    #Rodar para funcionar no note e celular: (venv) PS C:\Users\leand> uvicorn api:app --host 0.0.0.0 --port 8000 --reload
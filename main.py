import base64
import io
import os
from dotenv import load_dotenv

import requests
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware


try:
    import face_recognition
except ImportError:
    print("A biblioteca 'face_recognition' não foi encontrada.")
    print("Instale com: pip install face_recognition")
    exit(1)

# Carrega variáveis do .env
load_dotenv()

# Configurações via .env
TOKEN_URL = os.getenv("TOKEN_URL")
TOKEN_AUTH_HEADER = os.getenv("TOKEN_AUTH_HEADER")
TOKEN_USERNAME = os.getenv("TOKEN_USERNAME")
TOKEN_PASSWORD = os.getenv("TOKEN_PASSWORD")
TOKEN_SCOPE = os.getenv("TOKEN_SCOPE")
IMAGE_CONSULT_URL = os.getenv("IMAGE_CONSULT_URL")

# Verificação básica de variáveis
required_vars = [TOKEN_URL, TOKEN_AUTH_HEADER, TOKEN_USERNAME, TOKEN_PASSWORD, TOKEN_SCOPE, IMAGE_CONSULT_URL]
if not all(required_vars):
    missing_vars = []
    if not TOKEN_URL: missing_vars.append("TOKEN_URL")
    if not TOKEN_AUTH_HEADER: missing_vars.append("TOKEN_AUTH_HEADER")
    if not TOKEN_USERNAME: missing_vars.append("TOKEN_USERNAME")
    if not TOKEN_PASSWORD: missing_vars.append("TOKEN_PASSWORD")
    if not TOKEN_SCOPE: missing_vars.append("TOKEN_SCOPE")
    if not IMAGE_CONSULT_URL: missing_vars.append("IMAGE_CONSULT_URL")
    
    print(f"Erro: Variáveis de ambiente não configuradas: {', '.join(missing_vars)}")
    print("Verifique se todas as variáveis estão configuradas no arquivo .env")
    exit(1)

# Configuração da aplicação FastAPI
app = FastAPI(
    title="AI-Cop API",
    description="API com funcionalidades especificas para policiais.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configuração CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache simples para tokens
_token_cache = {"token": None, "expires_at": 0}

# --- Funções Auxiliares ---

async def get_access_token() -> str:
    """Obtém token de acesso da API externa com cache simples."""
    import time
    
    # Verifica se token em cache ainda é válido (válido por 50 minutos)
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        print("Usando token em cache")
        return _token_cache["token"]
    
    print("Obtendo novo token de acesso...")
    
    headers = {
        "Authorization": TOKEN_AUTH_HEADER,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "username": TOKEN_USERNAME,
        "password": TOKEN_PASSWORD,
        "grant_type": "password",
        "scope": TOKEN_SCOPE
    }

    try:
        response = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=500, detail="Token não encontrado na resposta da API.")
        
        # Armazena no cache (válido por 50 minutos)
        _token_cache["token"] = access_token
        _token_cache["expires_at"] = time.time() + (50 * 60)
        
        print("Token obtido com sucesso")
        return access_token
        
    except requests.exceptions.Timeout:
        print("Timeout ao obter token")
        raise HTTPException(status_code=504, detail="Timeout na autenticação")
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição de token: {e}")
        raise HTTPException(status_code=502, detail=f"Erro na autenticação: {str(e)}")
    except Exception as e:
        print(f"Erro inesperado ao obter token: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")


async def get_image_from_external_api(cpf: str, token: str) -> bytes:
    """Obtém imagem da API externa baseada no CPF."""
    print(f"Buscando imagem para CPF: {cpf[:3]}***{cpf[-2:]}")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {"CPF": cpf, "TipoImagem": 1}

    try:
        response = requests.post(IMAGE_CONSULT_URL, headers=headers, json=data, timeout=30)
        
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Imagem não encontrada para o CPF informado.")
        
        response.raise_for_status()
        
        image_data = response.json()
        base64_image = image_data.get("Imagem")

        if not base64_image:
            raise HTTPException(status_code=404, detail="Imagem não encontrada na resposta da API.")

        # Decodifica a imagem base64
        try:
            image_bytes = base64.b64decode(base64_image)
            print("Imagem obtida com sucesso")
            return image_bytes
        except Exception as decode_error:
            print(f"Erro ao decodificar imagem: {decode_error}")
            raise HTTPException(status_code=500, detail="Erro ao processar imagem da API externa.")

    except requests.exceptions.Timeout:
        print("Timeout ao buscar imagem")
        raise HTTPException(status_code=504, detail="Timeout na consulta de imagem")
    except requests.exceptions.RequestException as req_err:
        print(f"Erro na requisição de imagem: {req_err}")
        raise HTTPException(status_code=502, detail="Erro na consulta da API externa")
    except HTTPException:
        raise  # Re-raise HTTPExceptions
    except Exception as e:
        print(f"Erro inesperado: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


def perform_face_match(image1_bytes: bytes, image2_bytes: bytes, tolerance: float = 0.6) -> tuple:
    """Realiza comparação facial entre duas imagens."""
    print("Iniciando comparação facial...")
    
    try:
        # Carrega as imagens
        image1 = face_recognition.load_image_file(io.BytesIO(image1_bytes))
        image2 = face_recognition.load_image_file(io.BytesIO(image2_bytes))

        # Extrai encodings faciais
        face_encodings_1 = face_recognition.face_encodings(image1)
        face_encodings_2 = face_recognition.face_encodings(image2)

        if not face_encodings_1:
            raise HTTPException(status_code=422, detail="Nenhum rosto detectado na imagem fornecida.")
        if not face_encodings_2:
            raise HTTPException(status_code=422, detail="Nenhum rosto detectado na imagem da API externa.")

        # Compara faces
        matches = face_recognition.compare_faces(face_encodings_2, face_encodings_1[0], tolerance=tolerance)
        distances = face_recognition.face_distance(face_encodings_2, face_encodings_1[0])
        
        is_match = any(matches)
        confidence = 1 - min(distances) if distances.size > 0 else 0
        
        print(f"Comparação concluída - Match: {is_match}, Confiança: {confidence:.2f}")
        return is_match, confidence

    except HTTPException:
        raise  # Re-raise HTTPExceptions
    except Exception as e:
        print(f"Erro na comparação facial: {e}")
        raise HTTPException(status_code=500, detail=f"Erro no processamento facial: {str(e)}")


def validate_cpf(cpf: str) -> str:
    """Valida e limpa CPF."""
    # Remove caracteres não numéricos
    cpf_clean = ''.join(filter(str.isdigit, cpf))
    
    if len(cpf_clean) != 11:
        raise HTTPException(status_code=422, detail="CPF deve conter exatamente 11 dígitos.")
    
    # Verifica se não é uma sequência de números iguais
    if len(set(cpf_clean)) == 1:
        raise HTTPException(status_code=422, detail="CPF inválido.")
    
    return cpf_clean


def validate_image(image: UploadFile) -> None:
    """Valida arquivo de imagem."""
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="Arquivo deve ser uma imagem.")
    
    # Verifica tamanho (máximo 10MB)
    if hasattr(image, 'size') and image.size and image.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Imagem muito grande. Máximo 10MB.")


# --- Endpoints ---

# @app.get("/")
# async def root():
#     """Endpoint raiz com informações da API."""
#     return {
#         "message": "AI-Cop Face Recognition API",
#         "version": "1.0.0",
#         "status": "online",
#         "docs": "/docs"
#     }


# @app.get("/health")
# async def health_check():
#     """Health check da aplicação."""
#     return {
#         "status": "healthy",
#         "version": "1.0.0",
#         "services": {
#             "face_recognition": "available",
#             "external_api": "configured"
#         }
#     }


@app.post("/facematch")
async def facematch_endpoint(
    image: UploadFile = File(..., description="Imagem para comparação"),
    cpf: str = Form(..., description="CPF para consulta (11 dígitos)")
):
    """
    Realiza comparação facial entre imagem fornecida e imagem da API externa.
    
    - **image**: Arquivo de imagem (JPG, PNG, etc.)
    - **cpf**: CPF para consulta na API externa (11 dígitos)
    
    Retorna resultado da comparação com nível de confiança.
    """
    import time
    start_time = time.time()
    
    try:
        # Validações
        validate_image(image)
        cpf_clean = validate_cpf(cpf)
        
        # Lê imagem do usuário
        user_image_bytes = await image.read()
        
        # Obtém token e imagem externa
        token = await get_access_token()
        external_image_bytes = await get_image_from_external_api(cpf_clean, token)
        
        # Realiza comparação facial
        is_match, confidence = perform_face_match(user_image_bytes, external_image_bytes)
        
        processing_time = time.time() - start_time
        
        result = {
            "match": is_match,
            "confidence": round(confidence, 3),
            "message": "Face match bem-sucedido" if is_match else "Faces não correspondem",
            "processing_time": round(processing_time, 2),
            "timestamp": time.time()
        }
        
        print(f"Processamento concluído em {processing_time:.2f}s")
        return result
        
    except HTTPException:
        raise  # Re-raise HTTPExceptions
    except Exception as e:
        print(f"Erro inesperado no endpoint: {e}")
        raise HTTPException(status_code=500, detail="Erro interno do servidor")


# --- Execução ---
if __name__ == "__main__":
    print("Iniciando AI-Cop...")
    print(f"Sandbox disponível em: http://localhost:8000/docs")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )


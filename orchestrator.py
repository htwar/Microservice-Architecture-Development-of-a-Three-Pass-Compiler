from fastapi import FastAPI, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx, os, uuid

# environment variables
LEX = os.getenv("LEX_URL", "http://lexer-svc:8000/lex")
PARSE = os.getenv("PARSE_URL", "http://parser-svc:8000/compile")  # <— now calls /compile
BASE_DIR = os.path.dirname(__file__)

app = FastAPI(title="gateway")

@app.get("/healthz")
def healthz():
    return {"ok": True}

class CompileReq(BaseModel):
    source: str

@app.post("/compile")
async def compile(req: CompileReq):
    rid = str(uuid.uuid4())
    hdr = {"X-Request-Id": rid}

    async with httpx.AsyncClient(timeout=10) as c:
        # Step 1: Lexical analysis
        lex = (await c.post(LEX, json={"source": req.source}, headers=hdr)).json()
        if not lex.get("ok"):
            return lex

        # Step 2: Send tokens directly to parser (/compile)
        parse = (await c.post(PARSE, json={"tokens": lex["data"]}, headers=hdr)).json()
        return parse  # parser already forwarded to codegen and returns final output


@app.post("/download")
async def download(req: CompileReq):
    rid = str(uuid.uuid4())
    hdr = {"X-Request-Id": rid}

    async with httpx.AsyncClient(timeout=10) as c:
        lex = (await c.post(LEX, json={"source": req.source}, headers=hdr)).json()
        if not lex.get("ok"):
            return lex

        # Parser handles parsing + codegen internally
        result = (await c.post(PARSE, json={"tokens": lex["data"]}, headers=hdr)).json()
        if not result.get("ok"):
            return result

        text = result["data"]["program"].encode()
        headers = {"Content-Disposition": "attachment; filename=program.tsi"}
        return Response(content=text, media_type="application/octet-stream", headers=headers)


@app.get("/")
def root():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

@app.get("/style.css")
def style():
    return FileResponse(os.path.join(BASE_DIR, "style.css"), media_type="text/css")

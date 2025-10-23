from fastapi import FastAPI, Response
from pydantic import BaseModel
from fastapi.responses import FileResponse
import httpx, os, uuid

LEX = os.getenv("LEX_URL","http://lexer-svc:8000/lex")
PARSE = os.getenv("PARSE_URL","http://parser-svc:8000/parse")
CG = os.getenv("CG_URL","http://codegen-svc:8000/codegen")

app = FastAPI(title="gateway")

@app.get("/healthz")
def healthz():
    return {"ok": True}

class CompileReq(BaseModel):
    source: str

@app.post("/compile")
async def compile(req: CompileReq):
    rid=str(uuid.uuid4()); hdr={"X-Request-Id":rid}
    async with httpx.AsyncClient(timeout=10) as c:
        lex=(await c.post(LEX,json={"source":req.source},headers=hdr)).json()
        if not lex.get("ok"): return lex
        parse=(await c.post(PARSE,json={"tokens":lex["data"]},headers=hdr)).json()
        if not parse.get("ok"): return parse
        code=(await c.post(CG,json={"ast":parse["data"]},headers=hdr)).json()
        return code

@app.post("/download")
async def download(req: CompileReq):
    # same as /compile but returns as a downloadable file
    rid=str(uuid.uuid4()); hdr={"X-Request-Id":rid}
    async with httpx.AsyncClient(timeout=10) as c:
        lex=(await c.post(LEX,json={"source":req.source},headers=hdr)).json()
        if not lex.get("ok"): return lex
        parse=(await c.post(PARSE,json={"tokens":lex["data"]},headers=hdr)).json()
        if not parse.get("ok"): return parse
        code=(await c.post(CG,json={"ast":parse["data"]},headers=hdr)).json()
        if not code.get("ok"): return code
        text=code["data"]["program"].encode()
        headers={"Content-Disposition":"attachment; filename=program.tsi"}
        return Response(content=text, media_type="application/octet-stream", headers=headers)

@app.get("/")
def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "index.html"))


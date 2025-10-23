from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from models import Token, ApiOk, ApiErr
import re

app = FastAPI(title="lexer-svc")

@app.get("/healthz")
def healthz():
    return {"ok":True}

TOKENS = [
    ("KW", r"\b(let|if|else|while|print)\b"),
    ("INT", r"\b0|[1-9]\d*\b"),
    ("IDENT", r"[A-Za-z_]\w*"),
    ("OP", r"==|!=|<=|>=|&&|\|\||[+\-*/%<>=!()]"),
    ("SYM", r"[{};,]"),
    ("WS", r"[ \t\r\n]+"),
    ("COM", r"//[^\n]*"),
]
MASTER = re.compile("|".join(f"(?P<T{i}>{p})" for i,(_,p) in enumerate(TOKENS)))

class LexReq(BaseModel):
    source: str

def classify(kind, text):
    name, _ = TOKENS[int(kind[1:])]
    if name == "KW": return f"KW_{text.upper()}"
    if name == "OP":
        m={"==":"EQEQ","!=":"BANGEQ","<=":"LE",">=":"GE","&&":"AND","||":"OR",
            "+":"PLUS","-":"MINUS","*":"STAR","/":"SLASH","%":"PERCENT",
            "<":"LT",">":"GT","=":"EQUAL","!":"BANG","(":"LPAREN",")":"RPAREN"}
        return m[text]
    if name == "SYM": return {"{":"LBRACE","}":"RBRACE",";":"SEMICOLON",",":"COMMA"}[text]
    return name

@app.post("/lex")
def lex(req: LexReq):
    s=req.source; line=1; col=1; i=0; out: List[Token]=[]
    while i < len(s):
        m=MASTER.match(s,i)
        if not m:
            return ApiErr(phase="lex", line=line, col=col, code="E_LEX_UNK_CHAR", msg=f"Unexpected '{s[i]}'")
        k=m.lastgroup; text=m.group(); si=i; i=m.end()
        lines=text.splitlines()
        line += len(lines)-1
        col = (len(lines[-1])+1) if len(lines)>1 else (col + (i - si))
        name,_=TOKENS[int(k[1:])]
        if name in ("WS","COM"): continue
        ttype=classify(k,text)
        val=int(text) if name=="INT" else None
        out.append(Token(type=ttype, lexeme=text, line=line, col=max(col-1,1), value=val))
    return ApiOk(data=[t.model_dump() for t in out])

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any, Tuple
from models import ApiOk, ApiErr
import os, requests

app = FastAPI(title="parser-svc")
CODEGEN_URL = os.getenv("CODEGEN_URL", "http://codegen-svc:8000")

@app.get("/healthz")
def healthz():
    return {"ok": True}

class ParseReq(BaseModel):
    tokens: List[Dict[str, Any]]

# helpers
class Stream:
    def __init__(self, toks): self.t=toks; self.i=0
    def peek(self): return self.t[self.i] if self.i<len(self.t) else {"type":"EOF","lexeme":""}
    def pop(self): x=self.peek(); self.i+= (self.i<len(self.t)); return x
    def match(self, *kinds):
        if self.peek()["type"] in kinds: return self.pop()
        return None
    def expect(self, kind, code="E_PARSE_EXPECT"):
        tok=self.pop()
        if tok["type"]!=kind:
            raise SyntaxError((tok.get("line"), tok.get("col"), code, f"Expected {kind}, got {tok['type']}"))
        return tok

# Pratt precedence table
PREC = {
    "OR":1, "AND":2,
    "EQEQ":3,"BANGEQ":3,
    "LT":4,"LE":4,"GT":4,"GE":4,
    "PLUS":5,"MINUS":5,
    "STAR":6,"SLASH":6,"PERCENT":6
}

def parse(tokens):
    s=Stream(tokens)
    def primary():
        t=s.peek()["type"]
        if t=="INT": return {"type":"Int","value":s.pop()["value"]}
        if t=="IDENT": return {"type":"Ident","name":s.pop()["lexeme"]}
        if t=="LPAREN":
            s.pop()
            e=expr()
            s.expect("RPAREN")
            return e
        raise SyntaxError((s.peek().get("line"), s.peek().get("col"), "E_PARSE_PRIMARY", f"Bad token {t}"))
    def unary():
        t=s.peek()["type"]
        if t in ("BANG","MINUS"):
            op=s.pop()["type"]; node=unary()
            return {"type":"UnOp","op":"NOT" if op=="BANG" else "NEG","expr":node}
        return primary()
    def binop(minp=1):
        left=unary()
        while True:
            t=s.peek()["type"]
            p=PREC.get(t,0)
            if p<minp: break
            op=s.pop()["type"]
            right=binop(p+1)
            opmap={"PLUS":"+","MINUS":"-","STAR":"*","SLASH":"/","PERCENT":"%",
                    "LT":"<","LE":"<=","GT":">", "GE":">=","EQEQ":"==","BANGEQ":"!=",
                    "AND":"&&","OR":"||"}
            left={"type":"BinOp","op":opmap[op],"left":left,"right":right}
        return left
    def expr(): return binop()

    def block():
        s.expect("LBRACE"); body=[]
        while s.peek()["type"]!="RBRACE":
            body.append(stmt())
        s.expect("RBRACE"); return {"type":"Block","body":body}

    def vardecl():
        s.expect("KW_LET")
        ident=s.expect("IDENT")["lexeme"]
        init=None
        if s.match("EQUAL"): init=expr()
        s.expect("SEMICOLON")
        return {"type":"VarDecl","id":ident,"init":init}

    def assign_stmt():
        ident=s.expect("IDENT")["lexeme"]
        s.expect("EQUAL"); e=expr(); s.expect("SEMICOLON")
        return {"type":"Assign","id":ident,"expr":e}

    def print_stmt():
        s.expect("KW_PRINT"); s.expect("LPAREN"); e=expr(); s.expect("RPAREN"); s.expect("SEMICOLON")
        return {"type":"Print","expr":e}

    def ifstmt():
        s.expect("KW_IF"); s.expect("LPAREN"); test=expr(); s.expect("RPAREN")
        then=block(); els=None
        if s.match("KW_ELSE"): els=block()
        return {"type":"If","test":test,"then":then,"else":els}

    def whilestmt():
        s.expect("KW_WHILE"); s.expect("LPAREN"); test=expr(); s.expect("RPAREN"); body=block()
        return {"type":"While","test":test,"body":body}

    def stmt():
        t = s.peek()["type"]
        if t == "KW_LET": return vardecl()
        if t == "IDENT":
            # safe lookahead for '='
            if s.i + 1 < len(s.t) and s.t[s.i + 1]["type"] == "EQUAL":
                return assign_stmt()
        if t == "KW_PRINT": return print_stmt()
        if t == "KW_IF": return ifstmt()
        if t == "KW_WHILE": return whilestmt()
        raise SyntaxError((s.peek().get("line"), s.peek().get("col"),
                        "E_PARSE_STMT", f"Unexpected {t}"))

    body=[]
    while s.peek()["type"]!="EOF" and s.i < len(s.t):
        body.append(stmt())
    return {"type":"Program","body":body}

@app.post("/parse")
def parse_api(req: ParseReq):
    try:
        ast = parse(req.tokens + [{"type":"EOF","lexeme":"","line":0,"col":0}])
        return ApiOk(data=ast)
    except SyntaxError as e:
        line,col,code,msg = e.args[0]
        return ApiErr(phase="parse", line=line, col=col, code=code, msg=msg)

class CompileReq(BaseModel):
    tokens: List[Dict[str, Any]]

@app.post("/compile")
def compile_api(req: CompileReq):
    try:
        ast = parse(req.tokens + [{"type":"EOF","lexeme":"","line":0,"col":0}])

        # forward AST to codegen
        r = requests.post(f"{CODEGEN_URL}/codegen", json={"ast": ast}, timeout=5)
        r.raise_for_status()
        # assuming codegen returns ApiOk/ApiErr-shape JSON already
        return r.json()

    except SyntaxError as e:
        line, col, code, msg = e.args[0]
        return ApiErr(phase="parse", line=line, col=col, code=code, msg=msg)
    except requests.RequestException as e:
        return ApiErr(phase="parse", line=None, col=None, code="E_FORWARD_CODEGEN",
                    msg=f"Failed to contact codegen: {e}")
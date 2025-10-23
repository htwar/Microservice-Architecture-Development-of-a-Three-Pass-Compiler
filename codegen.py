from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict
from models import ApiOk, ApiErr

app = FastAPI(title="codegen-svc")

@app.get("/healthz")
def healthz():
    return {"ok": True}

class CodegenReq(BaseModel):
    ast: Dict[str, Any]

class Env:
    def __init__(self): self.vars=set()
    def declare(self,v): self.vars.add(v)
    def has(self,v): return v in self.vars

class EM:
    def __init__(self): self.out=[]; self.l=0
    def emit(self,s): self.out.append(s)
    def label(self): x=f"L{self.l}"; self.l+=1; return x

def gen(n, env: Env, e: EM):
    t=n["type"]
    if t=="Program":
        for s in n["body"]: gen(s,env,e)
        e.emit("HALT")
    elif t=="VarDecl":
        if n["init"] is not None:
            gen(n["init"],env,e); e.emit(f"STORE {n['id']}")
        env.declare(n["id"])
    elif t=="Assign":
        if not env.has(n["id"]): raise ValueError(f"Undeclared {n['id']}")
        gen(n["expr"],env,e); e.emit(f"STORE {n['id']}")
    elif t=="Print":
        gen(n["expr"],env,e); e.emit("PRINT")
    elif t=="Block":
        for s in n["body"]: gen(s,env,e)
    elif t=="If":
        Lelse=e.label(); Lend=e.label()
        gen(n["test"],env,e); e.emit(f"JZ {Lelse}")
        gen(n["then"],env,e); e.emit(f"JMP {Lend}")
        e.emit(f"{Lelse}:")
        if n["else"] is not None: gen(n["else"],env,e)
        e.emit(f"{Lend}:")
    elif t=="While":
        Ls=e.label(); Le=e.label()
        e.emit(f"{Ls}:"); gen(n["test"],env,e); e.emit(f"JZ {Le}")
        gen(n["body"],env,e); e.emit(f"JMP {Ls}"); e.emit(f"{Le}:")
    elif t=="Int": e.emit(f"PUSH {n['value']}")
    elif t=="Ident":
        if not env.has(n["name"]): raise ValueError(f"Undeclared {n['name']}")
        e.emit(f"LOAD {n['name']}")
    elif t=="UnOp":
        gen(n["expr"],env,e); e.emit("NOT" if n["op"]=="NOT" else "NEG")
    elif t=="BinOp":
        gen(n["left"],env,e); gen(n["right"],env,e)
        m={"+":"ADD","-":"SUB","*":"MUL","/":"DIV","%":"MOD",
            "<":"CMPLT","<=":"CMPLE",">":"CMPGT",">=":"CMPGE","==":"CMPEQ","!=":"CMPNE",
            "&&":"AND","||":"OR"}
        e.emit(m[n["op"]])
    else: raise ValueError(f"Unknown node {t}")

@app.post("/codegen")
def codegen_api(req: CodegenReq):
    try:
        env=Env(); em=EM(); gen(req.ast,env,em)
        text="\n".join(em.out)+"\n"
        return ApiOk(data={"artifact_name":"program.tsi","program":text})
    except Exception as ex:
        return ApiErr(phase="codegen", code="E_CODEGEN", msg=str(ex))

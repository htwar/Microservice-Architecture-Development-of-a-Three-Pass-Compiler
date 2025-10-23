from pydantic import BaseModel
from typing import Optional, Any, Literal, List

class Token(BaseModel):
    type: str
    lexeme: str
    line: int
    col: int
    value: Optional[int] = None

class ApiErr(BaseModel):
    ok: Literal[False] = False
    phase: Literal["lex","parse","codegen"]
    line: Optional[int] = None
    col: Optional[int] = None
    code: str
    msg: str

class ApiOk(BaseModel):
    ok: Literal[True] = True
    data: Any

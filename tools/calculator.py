import ast
import math
import operator
from typing import Any,Dict

class CalculatorTool:
    name="calculator"
    description="Safely evaluate mathematical expressions."

    OPS={
        ast.Add:operator.add,
        ast.Sub:operator.sub,
        ast.Mult:operator.mul,
        ast.Div:operator.truediv,
        ast.FloorDiv:operator.floordiv,
        ast.Mod:operator.mod,
        ast.Pow:operator.pow,
        ast.USub:operator.neg,
        ast.UAdd:operator.pos,
    }

    FUNCTIONS={
        "sqrt":math.sqrt,
        "sin":math.sin,
        "cos":math.cos,
        "tan":math.tan,
        "log":math.log,
        "log10":math.log10,
        "exp":math.exp,
        "abs":abs,
        "round":round,
        "floor":math.floor,
        "ceil":math.ceil,
    }

    def execute(self,expression:str)->Dict[str,Any]:
        expression=str(expression or "").strip()
        if not expression:
            return {"success":False,"error":"Expression is required."}
        if len(expression)>1000:
            return {"success":False,"error":"Expression is too long."}
        try:
            tree=ast.parse(expression,mode="eval")
            value=self._eval(tree.body)
            if isinstance(value,(int,float)) and not math.isfinite(value):
                raise ValueError("Result is not finite.")
            return {"success":True,"expression":expression,"result":value}
        except Exception as exc:
            return {"success":False,"expression":expression,"error":str(exc)}

    def _eval(self,node):
        if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)):
            return node.value
        if isinstance(node,ast.BinOp) and type(node.op) in self.OPS:
            left=self._eval(node.left)
            right=self._eval(node.right)
            if isinstance(node.op,ast.Pow) and abs(right)>100:
                raise ValueError("Exponent is too large.")
            return self.OPS[type(node.op)](left,right)
        if isinstance(node,ast.UnaryOp) and type(node.op) in self.OPS:
            return self.OPS[type(node.op)](self._eval(node.operand))
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in self.FUNCTIONS:
            if node.keywords:
                raise ValueError("Keyword arguments are not allowed.")
            return self.FUNCTIONS[node.func.id](*[self._eval(x) for x in node.args])
        raise ValueError("Unsupported expression.")
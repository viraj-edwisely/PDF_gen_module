"""Safe arithmetic for model-written expressions (figure curves, answer checks).

Only numbers, arithmetic, comparisons and an allow-list of functions are accepted: no attribute access, subscripts,
lambdas or builtins, so a hijacked expression cannot run code."""
import ast
import numpy as np

_ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Compare, ast.Tuple,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv, ast.USub, ast.UAdd,
            ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)
FUNCS = {k: getattr(np, k) for k in ('sin', 'cos', 'tan', 'exp', 'log', 'log2', 'log10', 'sqrt', 'abs', 'pi', 'e', 'where', 'maximum',
                                     'minimum', 'heaviside', 'arctan', 'arcsin', 'arccos', 'sinh', 'cosh', 'tanh', 'clip', 'sign',
                                     'floor', 'ceil', 'round')}
FUNCS.update(min=min, max=max, int=lambda x: float(np.trunc(x)), float=float)


def safe_eval(expr, **vars_):
    """Numbers are evaluated as floats, so a huge power (9**9**9) overflows at once instead of running for ever; strings and
    tuples outside a function call are refused ('a'*10**9 and (1,)*10**9 would exhaust memory)."""
    env = dict(FUNCS, **vars_)
    tree = ast.parse(str(expr).strip(), mode='eval')
    args = {id(a) for node in ast.walk(tree) if isinstance(node, ast.Call) for a in node.args}
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED): raise ValueError(f'expression not allowed: {expr!r}')
        if isinstance(node, ast.Name) and node.id not in env: raise ValueError(f'unknown name {node.id!r} in {expr!r}')
        if isinstance(node, ast.Call) and not isinstance(node.func, ast.Name): raise ValueError(f'expression not allowed: {expr!r}')
        if isinstance(node, ast.Constant) and (not isinstance(node.value, (int, float)) or isinstance(node.value, bool)): raise ValueError(f'only numbers are allowed: {expr!r}')
        if isinstance(node, ast.Tuple) and id(node) not in args: raise ValueError(f'expression not allowed: {expr!r}')
        if isinstance(node, ast.Constant): node.value = float(node.value)
    return eval(compile(tree, '<expr>', 'eval'), {'__builtins__': {}}, env)

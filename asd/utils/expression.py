"""Safe expression evaluator for parameter expressions.

Replaces eval() with a safer parser that only allows specific operations.
"""

import ast
import math
import operator
import re
from collections.abc import Callable
from typing import Any

# Type aliases for complex type expressions using Python 3.12+ type keyword
type ASTOperatorType = type[ast.operator] | type[ast.unaryop]
type OperatorFunc = Callable[..., Any]
type OperatorMap = dict[ASTOperatorType, OperatorFunc]
type FunctionMap = dict[str, OperatorFunc]
type ContextDict = dict[str, Any]


class SafeExpressionEvaluator:
    """Safely evaluate mathematical expressions."""

    # Allowed operators
    OPERATORS: OperatorMap = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
        ast.BitAnd: operator.and_,
        ast.BitOr: operator.or_,
        ast.BitXor: operator.xor,
        ast.Invert: operator.invert,
        ast.LShift: operator.lshift,
        ast.RShift: operator.rshift,
    }

    # Allowed functions
    FUNCTIONS: FunctionMap = {
        "log2": lambda x: int(math.log2(x)),
        "log10": math.log10,
        "log": math.log,
        "sqrt": math.sqrt,
        "ceil": math.ceil,
        "floor": math.floor,
        "min": min,
        "max": max,
        "abs": abs,
        "int": int,
        "float": float,
        "round": round,
    }

    def __init__(self, context: ContextDict | None = None):
        """Initialize evaluator with optional context.

        Args:
            context: Dictionary of variable values
        """
        self.context = context or {}

    def evaluate(self, expression: str) -> Any:
        """Safely evaluate an expression.

        Args:
            expression: Expression string to evaluate

        Returns:
            Evaluation result

        Raises:
            ValueError: If expression contains unsafe operations
        """
        # First, replace ${VAR} syntax with simple variable names
        expression = self._preprocess_expression(expression)

        try:
            # Parse expression into AST
            tree = ast.parse(expression, mode="eval")

            # Evaluate the AST
            return self._eval_node(tree.body)
        except Exception as e:
            raise ValueError(f"Failed to evaluate expression '{expression}': {e}")

    def _preprocess_expression(self, expr: str) -> str:
        """Preprocess expression to replace ${VAR} with VAR.

        Args:
            expr: Expression with ${} variables

        Returns:
            Expression with simple variable names
        """

        def replace_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            # If the variable exists in context, replace with its value
            # Otherwise keep as variable name for evaluation
            if var_name in self.context:
                value = self.context[var_name]
                # Convert to string representation
                if isinstance(value, bool):
                    return str(int(value))
                return str(value)
            return var_name

        return re.sub(r"\$\{(\w+)\}", replace_var, expr)

    def _eval_node(self, node: ast.AST) -> Any:
        """Recursively evaluate an AST node.

        Args:
            node: AST node to evaluate

        Returns:
            Evaluation result

        Raises:
            ValueError: If node type is not allowed
        """
        # Literals
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num):  # Python < 3.8 compatibility
            return node.n
        elif isinstance(node, ast.Str):  # Python < 3.8 compatibility
            return node.s

        # Variables
        elif isinstance(node, ast.Name):
            if node.id in self.context:
                return self.context[node.id]
            else:
                raise ValueError(f"Unknown variable: {node.id}")

        # Binary operations
        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in self.OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type.__name__}")

            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            return self.OPERATORS[op_type](left, right)

        # Unary operations
        elif isinstance(node, ast.UnaryOp):
            unary_op_type: type[ast.operator] | type[ast.unaryop] = type(node.op)
            if unary_op_type not in self.OPERATORS:
                raise ValueError(f"Unsupported unary operator: {unary_op_type.__name__}")

            operand = self._eval_node(node.operand)
            return self.OPERATORS[unary_op_type](operand)

        # Function calls
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls are allowed")

            func_name = node.func.id
            if func_name not in self.FUNCTIONS:
                raise ValueError(f"Function not allowed: {func_name}")

            # Evaluate arguments
            args = [self._eval_node(arg) for arg in node.args]

            # No keyword arguments allowed for simplicity
            if node.keywords:
                raise ValueError("Keyword arguments not supported")

            return self.FUNCTIONS[func_name](*args)

        # Comparison operations (for min/max with conditionals)
        elif isinstance(node, ast.Compare):
            # Simple support for comparisons
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise ValueError("Complex comparisons not supported")

            left = self._eval_node(node.left)
            right = self._eval_node(node.comparators[0])

            op = node.ops[0]
            if isinstance(op, ast.Lt):
                return left < right
            elif isinstance(op, ast.LtE):
                return left <= right
            elif isinstance(op, ast.Gt):
                return left > right
            elif isinstance(op, ast.GtE):
                return left >= right
            elif isinstance(op, ast.Eq):
                return left == right
            elif isinstance(op, ast.NotEq):
                return left != right
            else:
                raise ValueError(f"Unsupported comparison: {type(op).__name__}")

        # Conditional expressions (ternary operator)
        elif isinstance(node, ast.IfExp):
            test = self._eval_node(node.test)
            if test:
                return self._eval_node(node.body)
            else:
                return self._eval_node(node.orelse)

        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def evaluate_expression(expression: str, context: ContextDict) -> Any:
    """Convenience function to evaluate an expression.

    Args:
        expression: Expression string
        context: Variable context

    Returns:
        Evaluation result
    """
    evaluator = SafeExpressionEvaluator(context)
    return evaluator.evaluate(expression)

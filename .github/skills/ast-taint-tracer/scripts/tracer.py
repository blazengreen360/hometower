#!/usr/bin/env python3
import sys
import ast

class TaintTracer(ast.NodeVisitor):
    def __init__(self, target_sink):
        self.target_sink = target_sink
        self.findings = []
        self.current_func = None

    def visit_FunctionDef(self, node):
        self.current_func = node.name
        self.generic_visit(node)
        self.current_func = None

    def visit_Call(self, node):
        # We are looking for something like session.execute(payload) or similar
        # To keep this generic, we check if the function call string contains our sink
        
        call_str = ""
        if isinstance(node.func, ast.Attribute):
            call_str = node.func.attr
        elif isinstance(node.func, ast.Name):
            call_str = node.func.id

        if self.target_sink in call_str:
            args = []
            for arg in node.args:
                if isinstance(arg, ast.Name):
                    args.append(arg.id)
                else:
                    args.append("<expression>")
            
            self.findings.append({
                "function": self.current_func,
                "line": node.lineno,
                "sink": call_str,
                "tainted_args": args
            })
            
        self.generic_visit(node)

def trace(filepath, sink):
    print(f"🌲 Executing AST Data-Flow Trace over {filepath}... looking for sink '{sink}'")
    try:
        with open(filepath, 'r') as f:
            tree = ast.parse(f.read(), filename=filepath)
    except Exception as e:
        print(f"🔴 FATAL: Could not parse python file. {e}")
        sys.exit(1)

    tracer = TaintTracer(sink)
    tracer.visit(tree)

    if not tracer.findings:
        print(f"✅ PASS: No taint flows reaching the sink '{sink}' were detected.")
    else:
        print("🔴 VULNERABILITY DETECTED! Potential unvalidated sinks identified:")
        for f in tracer.findings:
            print(f"  -> Line {f['line']} in function {f['function']}()")
            print(f"     Sink Call: {f['sink']}")
            print(f"     Parameters flowing into sink: {f['tainted_args']}")
        print("\nSecurity-Auditor -> You MUST trace these parameters back to the router signature to prove exploitability!")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: tracer.py <file_path> <sink_name>")
        sys.exit(1)
    trace(sys.argv[1], sys.argv[2])

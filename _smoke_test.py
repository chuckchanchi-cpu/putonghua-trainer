import ast, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

src = open("app.py", encoding="utf-8").read()
ast.parse(src)
print("syntax OK")

def pin(q, ans, dist, hint):
    opts = [ans]
    for d in dist:
        if d not in opts and d != ans:
            opts.append(d)
        if len(opts) == 4:
            break
    return ("mc", q, ans, opts, hint)

tree = ast.parse(src)
qb = None
at = None
for node in tree.body:
    if isinstance(node, ast.Assign):
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "QUESTION_BANK" in names:
            seg = ast.get_source_segment(src, node.value)
            qb = eval(seg, {"pin": pin})
        if "AI_TOPICS" in names:
            seg = ast.get_source_segment(src, node.value)
            at = eval(seg, {"pin": pin})

assert qb is not None, "QUESTION_BANK not found"
total = 0
for key, val in qb.items():
    qs = val["questions"]
    total += len(qs)
    for item in qs:
        assert len(item) == 5, f"{key}: tuple len != 5"
        typ, q, ans, opts, hint = item
        assert isinstance(opts, list) and len(opts) >= 2, f"{key}: opts < 2"
        assert ans in opts, f"{key}: answer not in options: {ans} | {opts}"
        assert q and ans and hint, f"{key}: empty field"
        assert len(opts) == len(set(opts)), f"{key}: duplicate options: {opts}"
    print(f"{key}: {len(qs)} 題, 答案全喺選項入面")

print(f"QUESTION_BANK total: {total} 題")

assert at is not None, "AI_TOPICS not found"
print(f"AI_TOPICS: {len(at)} topics")
for k in at:
    assert at[k]["name"] and at[k]["context"] and at[k]["concepts"], f"{k} missing fields"

print("done")

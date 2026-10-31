"""Turn a CI log into GitHub annotations: compiler errors with file and line, failing tests with their traceback."""
import re
import sys

kind, path = sys.argv[1], sys.argv[2]
text = open(path, errors='replace').read()
escape = lambda s: s.replace('%', '%25').replace('\r', '').replace('\n', '%0A')
shown = 0
if kind == 'swift':
    for file, line, col, message in re.findall(r'^(\S+?\.swift):(\d+):(\d+): error: (.*)$', text, re.M)[:40]:
        print(f'::error file={file.split("/")[-1]},line={line},col={col}::{escape(message)}'); shown += 1
else:
    for block in re.split(r'\n={20,}\n', text):
        head = re.match(r'(FAIL|ERROR): (\S+) \(([^)]+)\)', block)
        if head and shown < 40:
            print(f'::error title={head[1]} {head[2]}::{escape(block[-1500:])}'); shown += 1
if not shown and re.search(r'(?i)error|fail', text[-3000:]):   # anything else: the end of the log
    print(f'::error title=Last lines::{escape(text[-2500:])}')

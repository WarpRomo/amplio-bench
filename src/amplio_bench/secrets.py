from pathlib import Path
import os
NAMES=('OPENAI_API_KEY','ANTHROPIC_API_KEY','DAYTONA_API_KEY','DAYTONA_API_TOKEN','GOOGLE_API_KEY')
def scan_tree(root):
    secrets={n:os.environ.get(n,'') for n in NAMES if os.environ.get(n,'')}; hits={}
    for p in Path(root).rglob('*'):
        if not p.is_file(): continue
        try: b=p.read_bytes()
        except OSError: continue
        for n,v in secrets.items():
            if v.encode() in b: hits.setdefault(n,[]).append(str(p))
    return hits

#!/usr/bin/env python3
import sys
import json
import urllib.request
import urllib.error

def fuzz(target_path, payload_file):
    url = f"http://localhost:8080{target_path}"
    print(f"💣 Loading fuzz vectors for target: {url}")
    
    with open(payload_file, 'r') as f:
        vectors = json.load(f)

    for idx, payload in enumerate(vectors):
        print(f"Testing Vector {idx+1}/{len(vectors)}: {payload}")
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
        
        try:
            with urllib.request.urlopen(req) as response:
                status = response.status
                print(f"  Result: {status} (Not a 500. Handled gracefully)")
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                print(f"🔴 FATAL: Boundary breach on Vector {idx+1}. Target crashed with {e.code}!")
                print(f"Payload: {payload}")
                sys.exit(1)
            else:
                print(f"  Result: {e.code} (Handled gracefully)")
        except Exception as e:
            print(f"🔴 FATAL: Request failed completely: {e}")
            sys.exit(1)

    print("✅ PASS: All fuzz vectors bounded correctly. Endpoint is resilient.")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: attack.py <target_path> <payload_file>")
        sys.exit(1)
    fuzz(sys.argv[1], sys.argv[2])

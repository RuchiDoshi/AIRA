import re, json

def clean_name(name):
    name = (name or '').strip()
    try:
        name = name.encode('latin-1').decode('utf-8')
    except:
        pass
    name = name.replace('\xa0', ' ')
    name = re.sub(r'[®™]', '', name)
    name = re.sub(r'\s*\*+$', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name

def base_name(name):
    return re.sub(r'[-\s]*(HF|v\d+).*$', '', name, flags=re.IGNORECASE).strip()

with open('data/neb_buffer_raw.json') as f:
    neb = json.load(f)

neb_lookup = {}
neb_lookup_base = {}
for row in neb['data']:
    if len(row) < 8:
        continue
    cln  = clean_name(row[0])
    base = base_name(cln)
    neb_lookup[cln] = 'HAS_DATA'
    if base and base not in neb_lookup_base:
        neb_lookup_base[base] = 'HAS_DATA'

raw  = 'BsaI'
cln  = clean_name(raw)
base = base_name(cln)
print(f'raw={repr(raw)} cln={repr(cln)} base={repr(base)}')
print(f'neb_lookup.get(cln):       {neb_lookup.get(cln)}')
print(f'neb_lookup.get(raw):       {neb_lookup.get(raw)}')
print(f'neb_lookup_base.get(cln):  {neb_lookup_base.get(cln)}')
print(f'neb_lookup_base.get(base): {neb_lookup_base.get(base)}')

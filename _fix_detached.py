path = r'c:\Users\GUEST\.gemini\antigravity\playground\Alta\alta\tests\test_reportes.py'
with open(path, 'rb') as f:
    data = f.read()

# Reemplazar el with Session para que use expire_on_commit=False
data = data.replace(b'    with Session(db_engine) as dB:', b'    with Session(db_engine, expire_on_commit=False) as dB:')
with open(path, 'wb') as f:
    f.write(data)
print('FIXED_DETACHED')

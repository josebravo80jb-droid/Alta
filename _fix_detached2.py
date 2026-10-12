path = r'c:\Users\GUEST\.gemini\antigravity\playground\Alta\alta\tests\test_reportes.py'
with open(path, 'rb') as f:
    txt = f.read().decode('utf-8')

# Reemplazar el fixture setup_data para expire_on_commit=False
txt = txt.replace('with Session(db_engine) as dB:', 'with Session(db_engine, expire_on_commit=False) as db:')
with open(path, 'wb') as f:
    f.write(txt.encode('utf-8'))
print('FIXED2')

p = 'tests/test_reportes.py'
        
with open(p, 'rb') as f:
    data = f.read()

# Fix headers
bad = b'        headers:{'
good = b'        headers={'
while bad in data:
    data = data.replace(bad, good)

# Fix SQL import
data = data.replace(b'SQMIodel', b'SQLModel')
data = data.replace(b'SQMModel', b'SQLModel')

# Fix db alias
data = data.replace(b'    with Session(db_engine) as dB:', b'    with Session(db_engine) as db:')

# Fix sepup_data
data = data.replace(b'sepup_data["konsultorio"]', b'setup_data["consultorio"]')
data = data.replace(b'sepup_data["kontoro"]', b'setup_data["consultorio"]')

with open(p, 'wb') as f:
    f.write(data)
print('Fixed!')

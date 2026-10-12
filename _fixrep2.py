p = 'tests/test_reportes.py'
        
with open(p, 'rb') as f:
    data = f.read()

# Fix: hashed_password -> password_hash (nombre real del campo en Usuario)
data = data.replace(b'hashed_password=hash_password("pass123")', b'password_hash=hash_password("pass123")')

with open(p, 'wb') as f:
    f.write(data)
print('Fixed password field name!')
